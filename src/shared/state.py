"""
State management for the travel agent system using LangGraph.
"""
from typing import TypedDict, Dict, Any, List, Optional
from datetime import datetime
import uuid
from langgraph.checkpoint import MemorySaver
from .models import (
    TravelPreferences, HotelBooking, TransportBooking, 
    ActivityBooking, BudgetStatus, AgentMessage, ConflictInfo
)


class TravelState(TypedDict):
    """Shared state across all agents."""
    session_id: str
    user_preferences: Dict[str, Any]
    budget_limit: float
    budget_spent: float
    budget_allocated: float
    bookings: Dict[str, List[Dict[str, Any]]]  # hotel, transport, activities
    conflicts: List[Dict[str, Any]]
    status: str  # planning, booking, confirmed, failed
    human_approval_needed: bool
    human_approval_context: Optional[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]
    agent_status: Dict[str, str]  # Status of each agent
    error_log: List[Dict[str, Any]]
    created_at: str
    updated_at: str


class StateManager:
    """Manages state persistence and updates."""
    
    def __init__(self):
        self.checkpointer = MemorySaver()
        self.active_sessions: Dict[str, TravelState] = {}
    
    async def create_session(self, user_preferences: TravelPreferences) -> str:
        """Initialize new travel planning session."""
        session_id = str(uuid.uuid4())
        
        initial_state: TravelState = {
            "session_id": session_id,
            "user_preferences": user_preferences.dict(),
            "budget_limit": user_preferences.budget,
            "budget_spent": 0.0,
            "budget_allocated": 0.0,
            "bookings": {
                "hotels": [],
                "transport": [],
                "activities": []
            },
            "conflicts": [],
            "status": "planning",
            "human_approval_needed": False,
            "human_approval_context": None,
            "conversation_history": [],
            "agent_status": {
                "orchestrator": "active",
                "hotel": "idle",
                "transport": "idle",
                "activity": "idle",
                "budget": "active",
                "itinerary": "idle"
            },
            "error_log": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Save to checkpointer
        await self.checkpointer.put(
            config={"configurable": {"thread_id": session_id}},
            checkpoint={"state": initial_state}
        )
        
        # Cache in memory for fast access
        self.active_sessions[session_id] = initial_state
        
        return session_id
    
    async def get_state(self, session_id: str) -> Optional[TravelState]:
        """Retrieve current state for a session."""
        # Try memory cache first
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # Fall back to checkpointer
        checkpoint = await self.checkpointer.get(
            config={"configurable": {"thread_id": session_id}}
        )
        
        if checkpoint:
            state = checkpoint["state"]
            self.active_sessions[session_id] = state
            return state
        
        return None
    
    async def update_state(self, session_id: str, updates: Dict[str, Any]):
        """Update state with partial updates."""
        state = await self.get_state(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        # Apply updates
        for key, value in updates.items():
            if key in state:
                if isinstance(state[key], dict) and isinstance(value, dict):
                    state[key].update(value)
                elif isinstance(state[key], list) and isinstance(value, list):
                    state[key].extend(value)
                else:
                    state[key] = value
        
        state["updated_at"] = datetime.now().isoformat()
        
        # Save to checkpointer
        await self.checkpointer.put(
            config={"configurable": {"thread_id": session_id}},
            checkpoint={"state": state}
        )
        
        # Update cache
        self.active_sessions[session_id] = state
    
    async def add_booking(self, session_id: str, booking_type: str, booking: Dict[str, Any]):
        """Add a booking to the state."""
        state = await self.get_state(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        if booking_type not in state["bookings"]:
            state["bookings"][booking_type] = []
        
        state["bookings"][booking_type].append(booking)
        state["budget_spent"] += booking.get("total_cost", booking.get("cost", 0))
        
        await self.update_state(session_id, {
            "bookings": state["bookings"],
            "budget_spent": state["budget_spent"]
        })
    
    async def update_agent_status(self, session_id: str, agent: str, status: str):
        """Update the status of a specific agent."""
        state = await self.get_state(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        state["agent_status"][agent] = status
        await self.update_state(session_id, {"agent_status": state["agent_status"]})
    
    async def add_conflict(self, session_id: str, conflict: ConflictInfo):
        """Add a conflict to the state."""
        state = await self.get_state(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        state["conflicts"].append(conflict.dict())
        await self.update_state(session_id, {"conflicts": state["conflicts"]})
    
    async def resolve_conflict(self, session_id: str, conflict_index: int):
        """Mark a conflict as resolved."""
        state = await self.get_state(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        if 0 <= conflict_index < len(state["conflicts"]):
            state["conflicts"].pop(conflict_index)
            await self.update_state(session_id, {"conflicts": state["conflicts"]})
    
    async def get_budget_status(self, session_id: str) -> BudgetStatus:
        """Get current budget status."""
        state = await self.get_state(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        breakdown = {}
        for booking_type, bookings in state["bookings"].items():
            total = sum(
                b.get("total_cost", b.get("cost", 0)) 
                for b in bookings
            )
            if total > 0:
                breakdown[booking_type] = total
        
        return BudgetStatus(
            total_budget=state["budget_limit"],
            spent=state["budget_spent"],
            allocated=state["budget_allocated"],
            available=state["budget_limit"] - state["budget_spent"] - state["budget_allocated"],
            breakdown=breakdown
        )
    
    async def add_message(self, session_id: str, message: AgentMessage):
        """Add a message to conversation history."""
        state = await self.get_state(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        state["conversation_history"].append(message.dict())
        await self.update_state(session_id, {
            "conversation_history": state["conversation_history"]
        })
    
    async def request_human_approval(self, session_id: str, context: Dict[str, Any]):
        """Set state to require human approval."""
        await self.update_state(session_id, {
            "human_approval_needed": True,
            "human_approval_context": context,
            "status": "awaiting_human_approval"
        })
    
    async def resolve_human_approval(self, session_id: str, approved: bool, resolution: Dict[str, Any]):
        """Resolve human approval request."""
        updates = {
            "human_approval_needed": False,
            "human_approval_context": None,
            "status": "booking" if approved else "planning"
        }
        
        if resolution:
            updates["conversation_history"] = [{
                "type": "human_decision",
                "approved": approved,
                "resolution": resolution,
                "timestamp": datetime.now().isoformat()
            }]
        
        await self.update_state(session_id, updates)
    
    async def finalize_session(self, session_id: str, status: str = "completed"):
        """Finalize a session."""
        await self.update_state(session_id, {"status": status})
        
        # Remove from active cache after a delay
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]