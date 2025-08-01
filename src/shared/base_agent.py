"""
Base agent class for all travel agents.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import uuid

from .models import AgentMessage, MessageType
from .state import StateManager
from .protocols import MessageRouter, MessageBuilder


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all travel agents."""
    
    def __init__(self, name: str, state_manager: StateManager, 
                 message_router: MessageRouter):
        self.name = name
        self.state_manager = state_manager
        self.message_router = message_router
        self.message_queue = asyncio.Queue()
        self.running = False
        self._task = None
        
        # Register with message router
        self.message_router.register_agent(self.name, self)
        
        logger.info(f"Initialized {self.name} agent")
    
    @abstractmethod
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process incoming message and return response if needed."""
        pass
    
    @abstractmethod
    async def initialize(self, session_id: str):
        """Initialize agent for a new session."""
        pass
    
    async def receive_message(self, message: AgentMessage):
        """Receive and queue message for processing."""
        await self.message_queue.put(message)
        logger.debug(f"{self.name} received message: {message.message_type} from {message.sender}")
    
    async def send_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Send a message through the router."""
        return await self.message_router.send_message(message)
    
    async def respond_to_message(self, original_message: AgentMessage, 
                               response_content: Dict[str, Any],
                               message_type: Optional[MessageType] = None):
        """Send a response to a received message."""
        response = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=self.name,
            recipient=original_message.sender,
            session_id=original_message.session_id,
            message_type=message_type or MessageType.STATUS_UPDATE,
            content=response_content,
            correlation_id=original_message.message_id,
            requires_response=False
        )
        
        await self.message_router.send_response(original_message.message_id, response)
    
    async def update_status(self, session_id: str, status: str):
        """Update agent status in state."""
        await self.state_manager.update_agent_status(session_id, self.name, status)
    
    async def get_state(self, session_id: str):
        """Get current state for a session."""
        return await self.state_manager.get_state(session_id)
    
    async def request_budget_validation(self, session_id: str, 
                                      booking_details: Dict[str, Any],
                                      cost: float) -> bool:
        """Request budget validation for a booking."""
        message = MessageBuilder.create_budget_validation_request(
            sender=self.name,
            session_id=session_id,
            booking_details=booking_details,
            cost=cost
        )
        
        response = await self.send_message(message)
        
        if response and response.content.get("approved", False):
            return True
        return False
    
    async def report_conflict(self, session_id: str, conflict_details: Dict[str, Any],
                            affected_agents: List[str]):
        """Report a conflict to the orchestrator."""
        message = MessageBuilder.create_conflict_alert(
            sender=self.name,
            session_id=session_id,
            conflict_details=conflict_details,
            affected_agents=affected_agents
        )
        
        await self.send_message(message)
    
    async def request_human_approval(self, session_id: str, reason: str,
                                   context: Dict[str, Any], options: List[Dict[str, Any]]):
        """Request human approval for a decision."""
        message = MessageBuilder.create_human_escalation(
            sender=self.name,
            session_id=session_id,
            reason=reason,
            context=context,
            options=options
        )
        
        await self.send_message(message)
        await self.state_manager.request_human_approval(session_id, {
            "requesting_agent": self.name,
            "reason": reason,
            "context": context,
            "options": options,
            "timestamp": datetime.now().isoformat()
        })
    
    async def run(self):
        """Main agent loop."""
        self.running = True
        await self.update_status("system", "active")
        
        while self.running:
            try:
                # Wait for message with timeout to allow graceful shutdown
                message = await asyncio.wait_for(
                    self.message_queue.get(), 
                    timeout=1.0
                )
                
                # Update status
                await self.update_status(message.session_id, "processing")
                
                # Process the message
                try:
                    response = await self.process_message(message)
                    
                    # Send response if needed
                    if response and message.requires_response:
                        await self.message_router.send_response(
                            message.message_id, 
                            response
                        )
                    
                except Exception as e:
                    logger.error(f"{self.name} error processing message: {e}")
                    
                    # Send error response
                    if message.requires_response:
                        error_response = AgentMessage(
                            message_id=str(uuid.uuid4()),
                            sender=self.name,
                            recipient=message.sender,
                            session_id=message.session_id,
                            message_type=MessageType.STATUS_UPDATE,
                            content={
                                "status": "error",
                                "error": str(e),
                                "original_message_id": message.message_id
                            },
                            correlation_id=message.message_id
                        )
                        await self.message_router.send_response(
                            message.message_id,
                            error_response
                        )
                
                # Update status back to idle
                await self.update_status(message.session_id, "idle")
                
            except asyncio.TimeoutError:
                # No message received, continue
                continue
            except Exception as e:
                logger.error(f"{self.name} unexpected error in run loop: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on errors
    
    def start(self):
        """Start the agent."""
        if not self.running:
            self._task = asyncio.create_task(self.run())
            logger.info(f"Started {self.name} agent")
    
    async def stop(self):
        """Stop the agent."""
        self.running = False
        if self._task:
            await self._task
        self.message_router.unregister_agent(self.name)
        logger.info(f"Stopped {self.name} agent")
    
    async def handle_error(self, error: Exception, context: Dict[str, Any]):
        """Handle errors in a standardized way."""
        logger.error(f"{self.name} error: {error}, context: {context}")
        
        # Log to state if session_id available
        if "session_id" in context:
            state = await self.get_state(context["session_id"])
            if state:
                state["error_log"].append({
                    "agent": self.name,
                    "error": str(error),
                    "context": context,
                    "timestamp": datetime.now().isoformat()
                })
                await self.state_manager.update_state(
                    context["session_id"],
                    {"error_log": state["error_log"]}
                )