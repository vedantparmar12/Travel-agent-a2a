"""
Communication protocols for inter-agent messaging.
"""
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import uuid
import logging
from .models import AgentMessage, MessageType


logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes messages between agents."""
    
    def __init__(self):
        self.agents: Dict[str, 'BaseAgent'] = {}
        self.message_log: List[AgentMessage] = []
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.pending_responses: Dict[str, asyncio.Future] = {}
    
    def register_agent(self, agent_name: str, agent: 'BaseAgent'):
        """Register an agent with the router."""
        self.agents[agent_name] = agent
        logger.info(f"Registered agent: {agent_name}")
    
    def unregister_agent(self, agent_name: str):
        """Unregister an agent."""
        if agent_name in self.agents:
            del self.agents[agent_name]
            logger.info(f"Unregistered agent: {agent_name}")
    
    async def send_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Route a message to its recipient."""
        # Log the message
        self.message_log.append(message)
        
        # Check if recipient exists
        if message.recipient not in self.agents:
            logger.error(f"Unknown recipient: {message.recipient}")
            raise ValueError(f"Unknown recipient: {message.recipient}")
        
        # Create response future if message requires response
        response_future = None
        if message.requires_response:
            response_future = asyncio.Future()
            self.pending_responses[message.message_id] = response_future
        
        # Deliver message to recipient
        recipient_agent = self.agents[message.recipient]
        asyncio.create_task(recipient_agent.receive_message(message))
        
        # Wait for response if required
        if response_future:
            try:
                response = await asyncio.wait_for(response_future, timeout=30.0)
                return response
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response to message {message.message_id}")
                del self.pending_responses[message.message_id]
                return None
        
        return None
    
    async def send_response(self, original_message_id: str, response: AgentMessage):
        """Send a response to a message."""
        if original_message_id in self.pending_responses:
            self.pending_responses[original_message_id].set_result(response)
            del self.pending_responses[original_message_id]
        else:
            # Just route as a regular message
            await self.send_message(response)
    
    async def broadcast(self, sender: str, message_content: Dict[str, Any], 
                       recipients: List[str], message_type: MessageType,
                       session_id: str) -> List[Optional[AgentMessage]]:
        """Broadcast message to multiple agents."""
        tasks = []
        
        for recipient in recipients:
            if recipient in self.agents:
                message = AgentMessage(
                    message_id=str(uuid.uuid4()),
                    sender=sender,
                    recipient=recipient,
                    session_id=session_id,
                    message_type=message_type,
                    content=message_content,
                    requires_response=True
                )
                tasks.append(self.send_message(message))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_responses = []
        for response in responses:
            if isinstance(response, Exception):
                logger.error(f"Error in broadcast: {response}")
                valid_responses.append(None)
            else:
                valid_responses.append(response)
        
        return valid_responses
    
    def get_message_history(self, session_id: Optional[str] = None, 
                           agent: Optional[str] = None,
                           message_type: Optional[MessageType] = None) -> List[AgentMessage]:
        """Get message history with optional filters."""
        messages = self.message_log
        
        if session_id:
            messages = [m for m in messages if m.session_id == session_id]
        
        if agent:
            messages = [m for m in messages if m.sender == agent or m.recipient == agent]
        
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        
        return messages


class MessageBuilder:
    """Helper class to build standardized messages."""
    
    @staticmethod
    def create_task_assignment(sender: str, recipient: str, session_id: str,
                             task_details: Dict[str, Any]) -> AgentMessage:
        """Create a task assignment message."""
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            recipient=recipient,
            session_id=session_id,
            message_type=MessageType.TASK_ASSIGNMENT,
            content={
                "task": task_details,
                "deadline": None,
                "priority": task_details.get("priority", 5)
            }
        )
    
    @staticmethod
    def create_budget_validation_request(sender: str, session_id: str,
                                       booking_details: Dict[str, Any],
                                       cost: float) -> AgentMessage:
        """Create a budget validation request."""
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            recipient="budget",
            session_id=session_id,
            message_type=MessageType.BUDGET_VALIDATION,
            content={
                "booking_type": sender,
                "booking_details": booking_details,
                "cost": cost,
                "currency": booking_details.get("currency", "USD")
            },
            priority=8  # High priority for budget checks
        )
    
    @staticmethod
    def create_conflict_alert(sender: str, session_id: str,
                            conflict_details: Dict[str, Any],
                            affected_agents: List[str]) -> AgentMessage:
        """Create a conflict alert message."""
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            recipient="orchestrator",
            session_id=session_id,
            message_type=MessageType.CONFLICT_ALERT,
            content={
                "conflict": conflict_details,
                "affected_agents": affected_agents,
                "severity": conflict_details.get("severity", 5)
            },
            priority=9  # High priority for conflicts
        )
    
    @staticmethod
    def create_status_update(sender: str, recipient: str, session_id: str,
                           status: str, details: Optional[Dict[str, Any]] = None) -> AgentMessage:
        """Create a status update message."""
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            recipient=recipient,
            session_id=session_id,
            message_type=MessageType.STATUS_UPDATE,
            content={
                "status": status,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            },
            requires_response=False,
            priority=3  # Low priority for status updates
        )
    
    @staticmethod
    def create_human_escalation(sender: str, session_id: str,
                              reason: str, context: Dict[str, Any],
                              options: List[Dict[str, Any]]) -> AgentMessage:
        """Create a human escalation request."""
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            recipient="orchestrator",
            session_id=session_id,
            message_type=MessageType.HUMAN_ESCALATION,
            content={
                "reason": reason,
                "context": context,
                "options": options,
                "timeout_seconds": 300
            },
            priority=10  # Highest priority
        )


class ProtocolValidator:
    """Validates messages against protocol rules."""
    
    @staticmethod
    def validate_message(message: AgentMessage) -> tuple[bool, Optional[str]]:
        """Validate a message against protocol rules."""
        # Check required fields
        if not message.sender or not message.recipient:
            return False, "Sender and recipient are required"
        
        if not message.session_id:
            return False, "Session ID is required"
        
        # Validate message type specific content
        if message.message_type == MessageType.BUDGET_VALIDATION:
            if "cost" not in message.content:
                return False, "Budget validation requires 'cost' field"
            if message.content["cost"] < 0:
                return False, "Cost cannot be negative"
        
        elif message.message_type == MessageType.CONFLICT_ALERT:
            if "affected_agents" not in message.content:
                return False, "Conflict alert requires 'affected_agents' field"
        
        elif message.message_type == MessageType.HUMAN_ESCALATION:
            if "reason" not in message.content or "options" not in message.content:
                return False, "Human escalation requires 'reason' and 'options' fields"
        
        return True, None