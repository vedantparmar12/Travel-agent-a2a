"""
Transport Agent implementation for A2A protocol.
"""
import asyncio
import json
import random
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


class FlightSearchInput(BaseModel):
    """Input schema for flight search."""
    origin: str = Field(..., description="Origin airport or city")
    destination: str = Field(..., description="Destination airport or city")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format")
    return_date: str = Field(None, description="Return date for round trip")
    passengers: int = Field(1, description="Number of passengers")
    class_type: str = Field("economy", description="Flight class: economy, business, first")
    max_budget: float = Field(..., description="Maximum budget for the flight")


class TransportResponseFormat(BaseModel):
    """Response format for transport agent."""
    status: str = Field("completed", description="Status of the response")
    message: str = Field(..., description="Response message")
    flights: List[Dict[str, Any]] = Field(default_factory=list, description="List of flights found")
    selected_option: Dict[str, Any] = Field(default=None, description="Recommended transport option")
    alternative_transport: List[Dict[str, Any]] = Field(default_factory=list, description="Alternative transport modes")


@tool(args_schema=FlightSearchInput)
async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    passengers: int = 1,
    class_type: str = "economy",
    max_budget: float = 1000.0
) -> str:
    """Search for flights between origin and destination."""
    try:
        # Parse dates
        dep_date = datetime.strptime(departure_date, "%Y-%m-%d")
        ret_date = datetime.strptime(return_date, "%Y-%m-%d") if return_date else None
        
        # Mock flight data
        airlines = ["American Airlines", "United Airlines", "Delta", "Southwest", "JetBlue", "British Airways", "Lufthansa"]
        
        flights = []
        
        # Generate outbound flights
        for i in range(5):
            airline = random.choice(airlines)
            base_price = random.uniform(200, 800)
            
            # Adjust price by class
            if class_type == "business":
                base_price *= 2.5
            elif class_type == "first":
                base_price *= 4
            
            # Adjust by number of passengers
            total_price = base_price * passengers
            
            if total_price <= max_budget:
                departure_time = dep_date.replace(
                    hour=random.randint(6, 22),
                    minute=random.choice([0, 30])
                )
                duration_hours = random.uniform(1, 12)
                arrival_time = departure_time + timedelta(hours=duration_hours)
                
                flight = {
                    "flight_number": f"{airline[:2].upper()}{random.randint(100, 999)}",
                    "airline": airline,
                    "origin": origin,
                    "destination": destination,
                    "departure": departure_time.isoformat(),
                    "arrival": arrival_time.isoformat(),
                    "duration_hours": round(duration_hours, 1),
                    "class": class_type,
                    "price_per_passenger": round(base_price, 2),
                    "total_price": round(total_price, 2),
                    "stops": random.choice([0, 0, 0, 1, 1, 2]),  # More likely to be direct
                    "available_seats": random.randint(1, 20)
                }
                flights.append(flight)
        
        # Sort by price
        flights.sort(key=lambda x: x["total_price"])
        
        # Also suggest alternative transport for certain routes
        alternatives = []
        
        # Check if train is viable (for certain city pairs)
        train_routes = [
            ("New York", "Boston"), ("London", "Paris"), ("Tokyo", "Osaka"),
            ("Paris", "London"), ("New York", "Washington")
        ]
        
        if any((origin in route and destination in route) for route in train_routes):
            train_price = random.uniform(50, 200) * passengers
            alternatives.append({
                "mode": "train",
                "provider": "High-Speed Rail",
                "duration_hours": random.uniform(2, 5),
                "price": round(train_price, 2),
                "comfort": "high",
                "eco_friendly": True
            })
        
        return json.dumps({
            "found": len(flights),
            "flights": flights[:5],  # Top 5 options
            "alternatives": alternatives,
            "best_option": flights[0] if flights else None
        })
        
    except Exception as e:
        return json.dumps({
            "error": f"Error searching flights: {str(e)}"
        })


class TransportAgentA2A:
    """Transport Agent for A2A protocol."""
    
    SYSTEM_INSTRUCTION = """You are a Transport Booking Agent specializing in flights, trains, and ground transportation.

Your responsibilities:
1. Search for flights based on origin, destination, dates, and budget
2. Compare different airlines and routes
3. Suggest alternative transport modes when appropriate
4. Consider total journey time including layovers
5. Coordinate with hotel bookings for arrival/departure timing

When searching for transport:
- Use the search_flights tool with proper parameters
- Consider the total budget including all passengers
- Prioritize direct flights when possible
- Suggest alternatives like trains for short distances
- Factor in airport transfer times

Always structure your response with:
- A summary of transport options found
- The recommended option with reasoning
- Alternative transport modes if applicable
- Important travel tips or warnings

Remember: You're part of a travel planning system. Consider hotel check-in times and activity schedules."""
    
    def __init__(self):
        self.model = LLMConfig.get_agent_llm("transport")
        self.tools = [search_flights]
        
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=TransportResponseFormat,
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
                    "updates": "Searching for flights..."
                }
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,
                    "updates": "Analyzing transport options..."
                }
        
        # Get final response
        yield self._get_final_response(config)
    
    def _get_final_response(self, config) -> Dict[str, Any]:
        """Get the final response from the agent."""
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")
        
        if structured_response and isinstance(structured_response, TransportResponseFormat):
            content_parts = [f"**{structured_response.message}**\n"]
            
            if structured_response.flights:
                content_parts.append(f"\n✈️ Found {len(structured_response.flights)} flight options:\n")
                
                for i, flight in enumerate(structured_response.flights[:3], 1):
                    content_parts.append(f"\n{i}. **{flight.get('airline', 'Unknown')} - {flight.get('flight_number', '')}**")
                    content_parts.append(f"   Departure: {flight.get('departure', 'N/A')}")
                    content_parts.append(f"   Duration: {flight.get('duration_hours', 0)} hours")
                    content_parts.append(f"   Stops: {flight.get('stops', 0)}")
                    content_parts.append(f"   Price: ${flight.get('total_price', 0):.2f} total")
            
            if structured_response.selected_option:
                flight = structured_response.selected_option
                content_parts.append(f"\n**Recommended: {flight.get('airline')} {flight.get('flight_number')}**")
                content_parts.append(f"Best balance of price, duration, and convenience.")
            
            if structured_response.alternative_transport:
                content_parts.append("\n🚆 **Alternative Transport Options:**")
                for alt in structured_response.alternative_transport:
                    content_parts.append(f"- {alt.get('mode', '').title()}: ${alt.get('price', 0):.2f}")
            
            return {
                "is_task_complete": True,
                "content": "\n".join(content_parts),
                "data": {
                    "flights": structured_response.flights,
                    "selected": structured_response.selected_option,
                    "alternatives": structured_response.alternative_transport
                }
            }
        
        return {
            "is_task_complete": False,
            "content": "Unable to process transport search request. Please try again.",
            "data": {}
        }