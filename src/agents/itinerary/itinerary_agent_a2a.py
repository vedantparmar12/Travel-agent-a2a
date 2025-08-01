"""
Itinerary Agent implementation for A2A protocol.
"""
import asyncio
import json
from typing import Any, AsyncIterable, Dict, List
from datetime import datetime, timedelta
import uuid

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from ...shared.llm_config import LLMConfig


memory = MemorySaver()


class BookingData(BaseModel):
    """Booking information for itinerary compilation."""
    booking_type: str = Field(..., description="Type: hotel, flight, activity, restaurant")
    name: str = Field(..., description="Name of the booking")
    confirmation_number: str = Field(None, description="Booking confirmation number")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    time: str = Field(None, description="Time in HH:MM format")
    end_time: str = Field(None, description="End time for activities")
    location: str = Field(..., description="Location/address")
    cost: float = Field(..., description="Total cost")
    notes: str = Field(None, description="Additional notes")


class ItineraryCompileInput(BaseModel):
    """Input schema for itinerary compilation."""
    trip_name: str = Field(..., description="Name of the trip")
    start_date: str = Field(..., description="Trip start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="Trip end date in YYYY-MM-DD format")
    destination: str = Field(..., description="Main destination")
    travelers: int = Field(1, description="Number of travelers")
    bookings: List[Dict[str, Any]] = Field(..., description="List of all bookings")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")


class ConflictCheckInput(BaseModel):
    """Input schema for checking scheduling conflicts."""
    bookings: List[Dict[str, Any]] = Field(..., description="List of bookings to check")
    buffer_minutes: int = Field(30, description="Minimum buffer time between activities")


class ItineraryResponseFormat(BaseModel):
    """Response format for itinerary agent."""
    status: str = Field("completed", description="Status of the response")
    message: str = Field(..., description="Response message")
    itinerary_days: List[Dict[str, Any]] = Field(default_factory=list, description="Day-by-day itinerary")
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="Scheduling conflicts found")
    total_cost: float = Field(0, description="Total trip cost")
    important_notes: List[str] = Field(default_factory=list, description="Important reminders and notes")
    documents_generated: List[str] = Field(default_factory=list, description="List of generated documents")


@tool(args_schema=ItineraryCompileInput)
async def compile_itinerary(
    trip_name: str,
    start_date: str,
    end_date: str,
    destination: str,
    travelers: int,
    bookings: List[Dict[str, Any]],
    preferences: Dict[str, Any] = None
) -> str:
    """Compile all bookings into a structured itinerary."""
    try:
        preferences = preferences or {}
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Group bookings by date
        days = {}
        current_date = start
        
        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")
            days[date_str] = {
                "date": date_str,
                "day_name": current_date.strftime("%A"),
                "day_number": (current_date - start).days + 1,
                "events": []
            }
            current_date += timedelta(days=1)
        
        # Process bookings
        total_cost = 0
        for booking in bookings:
            booking_date = booking.get("date", "")
            if booking_date in days:
                event = {
                    "time": booking.get("time", "All day"),
                    "type": booking.get("booking_type", "unknown"),
                    "name": booking.get("name", "Unnamed booking"),
                    "location": booking.get("location", ""),
                    "confirmation": booking.get("confirmation_number", ""),
                    "cost": booking.get("cost", 0),
                    "notes": booking.get("notes", ""),
                    "duration": booking.get("duration_hours", 0)
                }
                days[booking_date]["events"].append(event)
                total_cost += event["cost"]
        
        # Sort events by time for each day
        for day in days.values():
            day["events"].sort(key=lambda x: x["time"] if x["time"] != "All day" else "00:00")
        
        # Create summary
        itinerary_data = {
            "trip_name": trip_name,
            "destination": destination,
            "duration": f"{(end - start).days + 1} days",
            "travelers": travelers,
            "total_cost": round(total_cost, 2),
            "days": list(days.values()),
            "booking_count": len(bookings)
        }
        
        return json.dumps(itinerary_data)
        
    except Exception as e:
        return json.dumps({
            "error": f"Error compiling itinerary: {str(e)}"
        })


@tool(args_schema=ConflictCheckInput)
async def check_scheduling_conflicts(
    bookings: List[Dict[str, Any]],
    buffer_minutes: int = 30
) -> str:
    """Check for scheduling conflicts between bookings."""
    try:
        conflicts = []
        
        # Sort bookings by date and time
        sorted_bookings = sorted(
            bookings,
            key=lambda x: (x.get("date", ""), x.get("time", "00:00"))
        )
        
        # Check for conflicts
        for i in range(len(sorted_bookings) - 1):
            current = sorted_bookings[i]
            next_booking = sorted_bookings[i + 1]
            
            if current.get("date") == next_booking.get("date"):
                # Calculate end time of current booking
                if current.get("time") and current.get("duration_hours"):
                    try:
                        start_time = datetime.strptime(f"{current['date']} {current['time']}", "%Y-%m-%d %H:%M")
                        end_time = start_time + timedelta(hours=current['duration_hours'])
                        
                        next_start = datetime.strptime(f"{next_booking['date']} {next_booking['time']}", "%Y-%m-%d %H:%M")
                        
                        # Check if there's enough buffer time
                        time_diff = (next_start - end_time).total_seconds() / 60
                        
                        if time_diff < buffer_minutes:
                            conflicts.append({
                                "type": "timing_conflict",
                                "booking1": current["name"],
                                "booking2": next_booking["name"],
                                "date": current["date"],
                                "issue": f"Only {int(time_diff)} minutes between activities (need {buffer_minutes})",
                                "severity": "high" if time_diff < 0 else "medium"
                            })
                    except:
                        pass
                
                # Check for location conflicts (if both at same time)
                if current.get("time") == next_booking.get("time"):
                    conflicts.append({
                        "type": "double_booking",
                        "booking1": current["name"],
                        "booking2": next_booking["name"],
                        "date": current["date"],
                        "time": current["time"],
                        "issue": "Two bookings at the same time",
                        "severity": "high"
                    })
        
        return json.dumps({
            "conflicts_found": len(conflicts),
            "conflicts": conflicts
        })
        
    except Exception as e:
        return json.dumps({
            "error": f"Error checking conflicts: {str(e)}"
        })


class ItineraryAgentA2A:
    """Itinerary Agent for A2A protocol."""
    
    SYSTEM_INSTRUCTION = """You are an Itinerary Compilation Agent responsible for creating comprehensive travel plans.

Your responsibilities:
1. Compile all bookings into a structured, day-by-day itinerary
2. Check for scheduling conflicts and overlaps
3. Generate travel documents in various formats
4. Add helpful travel tips and reminders
5. Ensure all information is accurate and well-organized

When creating itineraries:
- Use compile_itinerary to structure all bookings
- Use check_scheduling_conflicts to identify issues
- Organize events chronologically for each day
- Include all confirmation numbers
- Add travel time estimates between locations
- Highlight important details (check-in times, meeting points)

Always structure your response with:
- A complete day-by-day breakdown
- Any scheduling conflicts found
- Total trip cost summary
- Important reminders (passport, visas, etc.)
- Suggested preparations

Remember: This is the final step. Ensure the itinerary is clear, complete, and ready for the traveler to use."""
    
    def __init__(self):
        self.model = LLMConfig.get_agent_llm("itinerary")
        self.tools = [compile_itinerary, check_scheduling_conflicts]
        
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ItineraryResponseFormat,
        )
    
    async def stream(self, query: str, context_id: str) -> AsyncIterable[Dict[str, Any]]:
        """Stream the agent's response."""
        config = {"configurable": {"thread_id": context_id}}
        
        # Add context
        today_str = f"Today's date is {datetime.now().strftime('%Y-%m-%d')}."
        augmented_query = f"{today_str}\n\nUser request: {query}"
        
        inputs = {"messages": [("user", augmented_query)]}
        
        # Stream processing
        for item in self.graph.stream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            
            if isinstance(message, AIMessage) and message.tool_calls:
                yield {
                    "is_task_complete": False,
                    "updates": "Compiling your travel itinerary..."
                }
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,
                    "updates": "Checking for conflicts and organizing schedule..."
                }
        
        # Get final response
        yield self._get_final_response(config)
    
    def _get_final_response(self, config) -> Dict[str, Any]:
        """Get the final response from the agent."""
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")
        
        if structured_response and isinstance(structured_response, ItineraryResponseFormat):
            content_parts = [f"# {structured_response.message}\n"]
            
            if structured_response.conflicts:
                content_parts.append("\n⚠️ **Scheduling Conflicts Found:**")
                for conflict in structured_response.conflicts:
                    content_parts.append(f"- {conflict.get('issue')} on {conflict.get('date')}")
                content_parts.append("")
            
            if structured_response.itinerary_days:
                content_parts.append("\n## 📅 Day-by-Day Itinerary\n")
                
                for day in structured_response.itinerary_days:
                    content_parts.append(f"### Day {day.get('day_number')} - {day.get('day_name')}, {day.get('date')}")
                    
                    if day.get('events'):
                        for event in day['events']:
                            content_parts.append(f"\n**{event.get('time')}** - {event.get('name')}")
                            if event.get('location'):
                                content_parts.append(f"📍 {event['location']}")
                            if event.get('confirmation'):
                                content_parts.append(f"🎫 Confirmation: {event['confirmation']}")
                            if event.get('cost') > 0:
                                content_parts.append(f"💰 Cost: ${event['cost']:.2f}")
                            if event.get('notes'):
                                content_parts.append(f"📝 {event['notes']}")
                    else:
                        content_parts.append("\n*No scheduled activities*")
                    
                    content_parts.append("")
            
            if structured_response.total_cost > 0:
                content_parts.append(f"\n## 💵 Trip Summary")
                content_parts.append(f"- **Total Cost**: ${structured_response.total_cost:.2f}")
            
            if structured_response.important_notes:
                content_parts.append(f"\n## 📋 Important Notes")
                for note in structured_response.important_notes:
                    content_parts.append(f"- {note}")
            
            if structured_response.documents_generated:
                content_parts.append(f"\n## 📄 Generated Documents")
                for doc in structured_response.documents_generated:
                    content_parts.append(f"- {doc}")
            
            return {
                "is_task_complete": True,
                "content": "\n".join(content_parts),
                "data": {
                    "itinerary_days": structured_response.itinerary_days,
                    "conflicts": structured_response.conflicts,
                    "total_cost": structured_response.total_cost,
                    "notes": structured_response.important_notes
                }
            }
        
        return {
            "is_task_complete": False,
            "content": "Unable to compile itinerary. Please ensure all booking information is provided.",
            "data": {}
        }