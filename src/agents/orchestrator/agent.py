"""
Orchestrator Agent implementation.
"""
import asyncio
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import uuid

from ...shared.base_agent import BaseAgent
from ...shared.models import (
    AgentMessage, MessageType, TravelPreferences,
    ConflictInfo, HumanApprovalRequest
)
from ...shared.protocols import MessageBuilder
from .prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT, TASK_ANALYSIS_PROMPT,
    CONFLICT_RESOLUTION_PROMPT, HUMAN_ESCALATION_PROMPT
)
from .tools import TaskAnalyzer, ConflictResolver, DependencyManager


logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent that coordinates all other agents."""
    
    def __init__(self, state_manager, message_router):
        super().__init__("orchestrator", state_manager, message_router)
        self.task_analyzer = TaskAnalyzer()
        self.conflict_resolver = ConflictResolver()
        self.dependency_manager = DependencyManager()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self, session_id: str):
        """Initialize orchestrator for a new session."""
        self.active_sessions[session_id] = {
            "status": "initializing",
            "agents_ready": set(),
            "pending_conflicts": [],
            "human_approvals": []
        }
        await self.update_status(session_id, "active")
        logger.info(f"Orchestrator initialized for session {session_id}")
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process incoming messages and coordinate responses."""
        logger.info(f"Orchestrator processing {message.message_type} from {message.sender}")
        
        if message.message_type == MessageType.TASK_ASSIGNMENT:
            return await self._handle_new_request(message)
        
        elif message.message_type == MessageType.CONFLICT_ALERT:
            return await self._handle_conflict(message)
        
        elif message.message_type == MessageType.STATUS_UPDATE:
            return await self._handle_status_update(message)
        
        elif message.message_type == MessageType.HUMAN_ESCALATION:
            return await self._handle_human_escalation(message)
        
        elif message.message_type == MessageType.COMPLETION_NOTIFICATION:
            return await self._handle_completion(message)
        
        return None
    
    async def _handle_new_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle new travel request and distribute tasks."""
        session_id = message.session_id
        preferences = TravelPreferences(**message.content["preferences"])
        
        # Initialize session
        await self.initialize(session_id)
        
        # Get current state
        state = await self.get_state(session_id)
        
        # Analyze request and create task assignments
        task_analysis = await self.task_analyzer.analyze_request(
            preferences,
            state["budget_limit"],
            state["budget_spent"],
            state["budget_limit"] - state["budget_spent"]
        )
        
        # Update session tracking
        self.active_sessions[session_id]["task_analysis"] = task_analysis
        self.active_sessions[session_id]["status"] = "distributing_tasks"
        
        # Create task assignments for each agent
        tasks = []
        
        # 1. Budget Agent - Always active for monitoring
        budget_task = MessageBuilder.create_task_assignment(
            sender=self.name,
            recipient="budget",
            session_id=session_id,
            task_details={
                "action": "monitor",
                "budget_limit": preferences.budget,
                "currency": preferences.currency,
                "alert_threshold": 0.8  # Alert at 80% spent
            }
        )
        tasks.append(self.send_message(budget_task))
        
        # 2. Hotel Agent - First priority
        hotel_task = MessageBuilder.create_task_assignment(
            sender=self.name,
            recipient="hotel",
            session_id=session_id,
            task_details={
                "action": "search_and_book",
                "destination": preferences.destination,
                "check_in": preferences.start_date.isoformat(),
                "check_out": preferences.end_date.isoformat(),
                "guests": preferences.travelers,
                "preferences": {
                    "rating": preferences.preferred_hotel_rating,
                    "max_budget": task_analysis["hotel_budget"]
                }
            }
        )
        tasks.append(self.send_message(hotel_task))
        
        # 3. Transport Agent - Can run parallel with hotel
        transport_task = MessageBuilder.create_task_assignment(
            sender=self.name,
            recipient="transport",
            session_id=session_id,
            task_details={
                "action": "search_and_book",
                "origin": preferences.origin,
                "destination": preferences.destination,
                "departure_date": preferences.start_date.isoformat(),
                "return_date": preferences.end_date.isoformat(),
                "travelers": preferences.travelers,
                "preferences": {
                    "mode": preferences.preferred_transport_mode,
                    "max_budget": task_analysis["transport_budget"]
                }
            }
        )
        tasks.append(self.send_message(transport_task))
        
        # Wait for initial tasks to be distributed
        await asyncio.gather(*tasks)
        
        # Activity Agent will be triggered after hotel confirmation
        self.active_sessions[session_id]["pending_agents"] = ["activity", "itinerary"]
        
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=self.name,
            recipient=message.sender,
            session_id=session_id,
            message_type=MessageType.STATUS_UPDATE,
            content={
                "status": "tasks_distributed",
                "agents_activated": ["budget", "hotel", "transport"],
                "message": "Travel planning initiated. Searching for accommodations and transport."
            }
        )
    
    async def _handle_conflict(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle conflicts reported by agents."""
        session_id = message.session_id
        conflict_info = ConflictInfo(**message.content["conflict"])
        
        logger.warning(f"Conflict detected: {conflict_info.conflict_type}")
        
        # Add to session tracking
        self.active_sessions[session_id]["pending_conflicts"].append(conflict_info)
        
        # Get current state
        state = await self.get_state(session_id)
        
        # Attempt automatic resolution
        resolution_plan = await self.conflict_resolver.resolve_conflict(
            conflict_info,
            state["bookings"],
            state["user_preferences"]
        )
        
        if resolution_plan["can_resolve_automatically"]:
            # Send resolution instructions to affected agents
            resolution_tasks = []
            
            for agent, instruction in resolution_plan["instructions"].items():
                resolution_message = AgentMessage(
                    message_id=str(uuid.uuid4()),
                    sender=self.name,
                    recipient=agent,
                    session_id=session_id,
                    message_type=MessageType.MODIFICATION_REQUEST,
                    content=instruction
                )
                resolution_tasks.append(self.send_message(resolution_message))
            
            await asyncio.gather(*resolution_tasks)
            
            # Log conflict resolution
            await self.state_manager.add_conflict(session_id, conflict_info)
            
            return AgentMessage(
                message_id=str(uuid.uuid4()),
                sender=self.name,
                recipient=message.sender,
                session_id=session_id,
                message_type=MessageType.STATUS_UPDATE,
                content={
                    "status": "conflict_resolved",
                    "resolution": resolution_plan["summary"]
                }
            )
        else:
            # Escalate to human
            await self._escalate_to_human(
                session_id,
                f"Conflict: {conflict_info.conflict_type}",
                {
                    "conflict": conflict_info.dict(),
                    "current_bookings": state["bookings"],
                    "attempted_resolution": resolution_plan
                },
                conflict_info.suggested_resolutions
            )
            
            return None
    
    async def _handle_status_update(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle status updates from agents."""
        session_id = message.session_id
        sender = message.sender
        status = message.content.get("status")
        
        logger.info(f"Status update from {sender}: {status}")
        
        # Update agent status in state
        await self.update_status(session_id, "processing_update")
        
        # Handle specific status types
        if status == "booking_confirmed" and sender == "hotel":
            # Hotel is booked, now activate Activity Agent
            if "activity" in self.active_sessions[session_id].get("pending_agents", []):
                hotel_location = message.content.get("details", {}).get("location")
                
                activity_task = MessageBuilder.create_task_assignment(
                    sender=self.name,
                    recipient="activity",
                    session_id=session_id,
                    task_details={
                        "action": "search_and_book",
                        "location": hotel_location,
                        "dates": {
                            "start": message.content["details"]["check_in"],
                            "end": message.content["details"]["check_out"]
                        },
                        "preferences": message.content.get("user_preferences", {})
                            .get("activity_preferences", [])
                    }
                )
                
                await self.send_message(activity_task)
                self.active_sessions[session_id]["pending_agents"].remove("activity")
        
        # Check if all bookings are complete
        if await self._check_all_bookings_complete(session_id):
            # Trigger itinerary generation
            await self._trigger_itinerary_generation(session_id)
        
        return None
    
    async def _handle_human_escalation(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle human escalation requests."""
        session_id = message.session_id
        
        approval_request = HumanApprovalRequest(
            request_id=str(uuid.uuid4()),
            session_id=session_id,
            reason=message.content["reason"],
            context=message.content["context"],
            options=message.content["options"]
        )
        
        # Store in session
        self.active_sessions[session_id]["human_approvals"].append(approval_request)
        
        # Update state to require human approval
        await self.state_manager.request_human_approval(
            session_id,
            approval_request.dict()
        )
        
        logger.info(f"Human approval requested for session {session_id}: {approval_request.reason}")
        
        return None
    
    async def _handle_completion(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle completion notifications from agents."""
        session_id = message.session_id
        
        if message.sender == "itinerary":
            # Itinerary is complete, finalize session
            await self.state_manager.finalize_session(session_id, "completed")
            
            return AgentMessage(
                message_id=str(uuid.uuid4()),
                sender=self.name,
                recipient="user",  # Special recipient for user notifications
                session_id=session_id,
                message_type=MessageType.COMPLETION_NOTIFICATION,
                content={
                    "status": "trip_planned",
                    "message": "Your trip has been successfully planned!",
                    "itinerary": message.content.get("itinerary")
                }
            )
        
        return None
    
    async def _check_all_bookings_complete(self, session_id: str) -> bool:
        """Check if all required bookings are complete."""
        state = await self.get_state(session_id)
        
        # Check minimum requirements
        has_hotel = len(state["bookings"].get("hotels", [])) > 0
        has_transport = len(state["bookings"].get("transport", [])) > 0
        
        # Activities are optional
        # Check if there are no pending agents
        pending = self.active_sessions[session_id].get("pending_agents", [])
        no_pending = len([a for a in pending if a != "itinerary"]) == 0
        
        return has_hotel and has_transport and no_pending
    
    async def _trigger_itinerary_generation(self, session_id: str):
        """Trigger the itinerary agent to create final itinerary."""
        state = await self.get_state(session_id)
        
        itinerary_task = MessageBuilder.create_task_assignment(
            sender=self.name,
            recipient="itinerary",
            session_id=session_id,
            task_details={
                "action": "generate",
                "bookings": state["bookings"],
                "preferences": state["user_preferences"],
                "budget_status": await self.state_manager.get_budget_status(session_id)
            }
        )
        
        await self.send_message(itinerary_task)
        
        # Remove from pending
        if "itinerary" in self.active_sessions[session_id].get("pending_agents", []):
            self.active_sessions[session_id]["pending_agents"].remove("itinerary")
    
    async def _escalate_to_human(self, session_id: str, reason: str,
                                context: Dict[str, Any], options: List[Dict[str, Any]]):
        """Escalate decision to human approval."""
        await self.request_human_approval(session_id, reason, context, options)
        
        # Pause automated processing
        self.active_sessions[session_id]["status"] = "awaiting_human_approval"
        
    async def handle_human_decision(self, session_id: str, decision: Dict[str, Any]):
        """Handle human decision on escalated issue."""
        await self.state_manager.resolve_human_approval(
            session_id,
            decision["approved"],
            decision
        )
        
        # Resume processing based on decision
        if decision["approved"]:
            # Implement the chosen option
            chosen_option = decision.get("chosen_option")
            if chosen_option:
                # Send instructions to relevant agents
                for agent, instruction in chosen_option.get("actions", {}).items():
                    message = AgentMessage(
                        message_id=str(uuid.uuid4()),
                        sender=self.name,
                        recipient=agent,
                        session_id=session_id,
                        message_type=MessageType.MODIFICATION_REQUEST,
                        content=instruction
                    )
                    await self.send_message(message)
        
        # Resume normal processing
        self.active_sessions[session_id]["status"] = "active"