"""
Hotel Agent implementation.
"""
import asyncio
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import uuid

from ...shared.base_agent import BaseAgent
from ...shared.models import (
    AgentMessage, MessageType, HotelBooking, 
    Location, BookingStatus
)
from ...shared.protocols import MessageBuilder
from ...shared.utils import calculate_duration, format_currency, AsyncRetry
from .prompts import (
    HOTEL_SYSTEM_PROMPT, HOTEL_SEARCH_PROMPT,
    HOTEL_SELECTION_PROMPT, LATE_CHECKIN_REQUEST_PROMPT
)
from .tools import HotelSearchAPI, HotelRanker


logger = logging.getLogger(__name__)


class HotelAgent(BaseAgent):
    """Hotel agent that handles accommodation search and booking."""
    
    def __init__(self, state_manager, message_router, api_config: Dict[str, Any]):
        super().__init__("hotel", state_manager, message_router)
        self.search_api = HotelSearchAPI(api_config)
        self.ranker = HotelRanker()
        self.pending_bookings: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self, session_id: str):
        """Initialize hotel agent for a new session."""
        await self.update_status(session_id, "ready")
        logger.info(f"Hotel agent initialized for session {session_id}")
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process incoming messages."""
        logger.info(f"Hotel agent processing {message.message_type} from {message.sender}")
        
        if message.message_type == MessageType.TASK_ASSIGNMENT:
            return await self._handle_task_assignment(message)
        
        elif message.message_type == MessageType.BUDGET_APPROVAL:
            return await self._handle_budget_approval(message)
        
        elif message.message_type == MessageType.BUDGET_REJECTION:
            return await self._handle_budget_rejection(message)
        
        elif message.message_type == MessageType.MODIFICATION_REQUEST:
            return await self._handle_modification_request(message)
        
        return None
    
    async def _handle_task_assignment(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle hotel search and booking task."""
        session_id = message.session_id
        task = message.content["task_details"]
        
        await self.update_status(session_id, "searching")
        
        try:
            # Extract search parameters
            destination = task["destination"]
            check_in = datetime.fromisoformat(task["check_in"])
            check_out = datetime.fromisoformat(task["check_out"])
            guests = task["guests"]
            preferences = task.get("preferences", {})
            
            # Calculate nights and budget
            nights = (check_out - check_in).days
            max_total_budget = preferences.get("max_budget", float('inf'))
            max_per_night = max_total_budget / nights if nights > 0 else max_total_budget
            
            # Search for hotels
            search_results = await self._search_hotels(
                destination, check_in, check_out, guests, max_per_night, preferences
            )
            
            if not search_results:
                # No hotels found
                await self.report_conflict(
                    session_id,
                    {
                        "conflict_type": "availability",
                        "description": f"No hotels found in {destination} for specified dates",
                        "severity": 8
                    },
                    ["hotel", "orchestrator"]
                )
                return None
            
            # Rank hotels based on preferences
            ranked_hotels = await self.ranker.rank_hotels(
                search_results, preferences, max_total_budget
            )
            
            # Select best option
            best_hotel = ranked_hotels[0]
            
            # Create booking object
            booking = HotelBooking(
                hotel_name=best_hotel["name"],
                location=Location(
                    latitude=best_hotel["latitude"],
                    longitude=best_hotel["longitude"],
                    address=best_hotel["address"],
                    city=destination
                ),
                check_in=check_in,
                check_out=check_out,
                room_type=best_hotel["room_type"],
                guests=guests,
                cost_per_night=best_hotel["price_per_night"],
                total_cost=best_hotel["total_price"],
                amenities=best_hotel.get("amenities", []),
                cancellation_policy=best_hotel.get("cancellation_policy", "Standard"),
                rating=best_hotel.get("rating")
            )
            
            # Store pending booking
            self.pending_bookings[session_id] = {
                "booking": booking,
                "alternatives": ranked_hotels[1:5]  # Keep alternatives
            }
            
            # Request budget validation
            budget_request = MessageBuilder.create_budget_validation_request(
                sender=self.name,
                session_id=session_id,
                booking_details=booking.dict(),
                cost=booking.total_cost
            )
            
            await self.send_message(budget_request)
            await self.update_status(session_id, "awaiting_budget_approval")
            
            # Send status update
            return MessageBuilder.create_status_update(
                sender=self.name,
                recipient=message.sender,
                session_id=session_id,
                status="hotels_found",
                details={
                    "found_count": len(search_results),
                    "selected": booking.hotel_name,
                    "price": booking.total_cost
                }
            )
            
        except Exception as e:
            logger.error(f"Error in hotel search: {e}")
            await self.handle_error(e, {"session_id": session_id, "task": task})
            return None
    
    async def _handle_budget_approval(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle budget approval and proceed with booking."""
        session_id = message.session_id
        
        if session_id not in self.pending_bookings:
            logger.error(f"No pending booking for session {session_id}")
            return None
        
        pending = self.pending_bookings[session_id]
        booking = pending["booking"]
        
        await self.update_status(session_id, "booking")
        
        try:
            # Simulate booking confirmation
            # In real implementation, this would call booking API
            confirmation = await self._confirm_booking(booking)
            
            if confirmation["success"]:
                booking.confirmation_number = confirmation["confirmation_number"]
                booking.status = BookingStatus.CONFIRMED
                
                # Save to state
                await self.state_manager.add_booking(
                    session_id, "hotels", booking.dict()
                )
                
                # Clean up pending
                del self.pending_bookings[session_id]
                
                # Notify orchestrator and other relevant agents
                await self.send_message(
                    MessageBuilder.create_status_update(
                        sender=self.name,
                        recipient="orchestrator",
                        session_id=session_id,
                        status="booking_confirmed",
                        details={
                            "hotel_name": booking.hotel_name,
                            "location": booking.location.dict(),
                            "check_in": booking.check_in.isoformat(),
                            "check_out": booking.check_out.isoformat(),
                            "confirmation": booking.confirmation_number
                        }
                    )
                )
                
                await self.update_status(session_id, "completed")
                
                return MessageBuilder.create_status_update(
                    sender=self.name,
                    recipient=message.sender,
                    session_id=session_id,
                    status="booking_confirmed",
                    details={"confirmation_number": booking.confirmation_number}
                )
            else:
                # Booking failed
                await self.report_conflict(
                    session_id,
                    {
                        "conflict_type": "availability",
                        "description": f"Hotel {booking.hotel_name} no longer available",
                        "severity": 7
                    },
                    ["hotel", "orchestrator"]
                )
                
        except Exception as e:
            logger.error(f"Error confirming booking: {e}")
            await self.handle_error(e, {"session_id": session_id, "booking": booking.dict()})
        
        return None
    
    async def _handle_budget_rejection(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle budget rejection and find alternatives."""
        session_id = message.session_id
        available_budget = message.content.get("available_budget", 0)
        
        if session_id not in self.pending_bookings:
            logger.error(f"No pending booking for session {session_id}")
            return None
        
        pending = self.pending_bookings[session_id]
        alternatives = pending["alternatives"]
        
        # Find alternatives within budget
        affordable_options = [
            hotel for hotel in alternatives
            if hotel["total_price"] <= available_budget
        ]
        
        if affordable_options:
            # Select best affordable option
            new_selection = affordable_options[0]
            
            # Update pending booking
            booking = HotelBooking(
                hotel_name=new_selection["name"],
                location=Location(
                    latitude=new_selection["latitude"],
                    longitude=new_selection["longitude"],
                    address=new_selection["address"]
                ),
                check_in=pending["booking"].check_in,
                check_out=pending["booking"].check_out,
                room_type=new_selection["room_type"],
                guests=pending["booking"].guests,
                cost_per_night=new_selection["price_per_night"],
                total_cost=new_selection["total_price"],
                amenities=new_selection.get("amenities", []),
                cancellation_policy=new_selection.get("cancellation_policy", "Standard"),
                rating=new_selection.get("rating")
            )
            
            self.pending_bookings[session_id]["booking"] = booking
            
            # Request budget validation for new option
            budget_request = MessageBuilder.create_budget_validation_request(
                sender=self.name,
                session_id=session_id,
                booking_details=booking.dict(),
                cost=booking.total_cost
            )
            
            await self.send_message(budget_request)
            
        else:
            # No affordable options
            await self.request_human_approval(
                session_id,
                "No hotels found within budget",
                {
                    "available_budget": available_budget,
                    "cheapest_option": alternatives[0] if alternatives else None
                },
                [
                    {"action": "increase_budget", "amount_needed": alternatives[0]["total_price"] - available_budget},
                    {"action": "change_destination", "reason": "Find more affordable location"},
                    {"action": "change_dates", "reason": "Try different dates"}
                ]
            )
        
        return None
    
    async def _handle_modification_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle modification requests like late check-in."""
        session_id = message.session_id
        action = message.content.get("action")
        
        if action == "request_late_checkin":
            arrival_time = message.content.get("arrival_time")
            
            # Get current booking
            state = await self.get_state(session_id)
            hotels = state["bookings"].get("hotels", [])
            
            if hotels:
                current_booking = hotels[0]
                
                # Simulate late check-in request
                # In real implementation, this would contact hotel
                success = await self._request_late_checkin(
                    current_booking["hotel_name"],
                    current_booking["check_in"],
                    arrival_time
                )
                
                if success:
                    return MessageBuilder.create_status_update(
                        sender=self.name,
                        recipient=message.sender,
                        session_id=session_id,
                        status="modification_confirmed",
                        details={"late_checkin_confirmed": True, "arrival_time": arrival_time}
                    )
        
        return None
    
    @AsyncRetry(max_attempts=3, delay=1.0)
    async def _search_hotels(self, destination: str, check_in: datetime,
                           check_out: datetime, guests: int,
                           max_per_night: float, preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for hotels using API."""
        return await self.search_api.search(
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            max_price=max_per_night,
            min_rating=preferences.get("rating", 3.0),
            amenities=preferences.get("amenities", [])
        )
    
    async def _confirm_booking(self, booking: HotelBooking) -> Dict[str, Any]:
        """Confirm hotel booking."""
        # Simulate booking confirmation
        # In real implementation, this would call booking API
        await asyncio.sleep(1)  # Simulate API call
        
        return {
            "success": True,
            "confirmation_number": f"HTL-{uuid.uuid4().hex[:8].upper()}"
        }
    
    async def _request_late_checkin(self, hotel_name: str, 
                                   original_time: str, arrival_time: str) -> bool:
        """Request late check-in from hotel."""
        # Simulate late check-in request
        # In real implementation, this would contact hotel
        await asyncio.sleep(0.5)
        
        # Usually successful for reasonable times
        return True