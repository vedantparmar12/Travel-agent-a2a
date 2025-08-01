"""
Hotel Agent implementation for A2A protocol.
"""
import asyncio
import json
import random
from typing import Any, AsyncIterable, Dict, List
from datetime import datetime, timedelta
import uuid

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .tools import HotelSearchAPI, HotelRanker, HotelValidator


memory = MemorySaver()


class HotelSearchInput(BaseModel):
    """Input schema for hotel search."""
    destination: str = Field(..., description="Destination city for hotel search")
    check_in: str = Field(..., description="Check-in date in YYYY-MM-DD format")
    check_out: str = Field(..., description="Check-out date in YYYY-MM-DD format")
    guests: int = Field(..., description="Number of guests")
    max_budget: float = Field(..., description="Maximum budget for the stay")
    min_rating: float = Field(3.0, description="Minimum hotel rating (1-5)")


class ResponseFormat(BaseModel):
    """Response format for the agent."""
    status: str = Field("completed", description="Status of the response")
    message: str = Field(..., description="Response message")
    hotels: List[Dict[str, Any]] = Field(default_factory=list, description="List of hotels found")
    selected_hotel: Dict[str, Any] = Field(default=None, description="Selected hotel for booking")


@tool(args_schema=HotelSearchInput)
async def search_hotels(
    destination: str,
    check_in: str,
    check_out: str,
    guests: int,
    max_budget: float,
    min_rating: float = 3.0
) -> str:
    """Search for hotels based on criteria."""
    try:
        # Parse dates
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (check_out_date - check_in_date).days
        
        if nights <= 0:
            return json.dumps({
                "error": "Invalid date range. Check-out must be after check-in."
            })
        
        # Calculate max per night
        max_per_night = max_budget / nights
        
        # Mock search using existing tools
        api_config = {"api_key": "mock_key"}
        search_api = HotelSearchAPI(api_config)
        ranker = HotelRanker()
        
        # Search hotels
        results = await search_api.search(
            destination=destination,
            check_in=check_in_date,
            check_out=check_out_date,
            guests=guests,
            max_price=max_per_night,
            min_rating=min_rating
        )
        
        if not results:
            return json.dumps({
                "error": f"No hotels found in {destination} for the specified dates and budget."
            })
        
        # Rank hotels
        ranked_hotels = await ranker.rank_hotels(
            results,
            {"rating": min_rating},
            max_budget
        )
        
        # Return top 5 hotels
        top_hotels = ranked_hotels[:5]
        
        return json.dumps({
            "found": len(results),
            "hotels": top_hotels,
            "best_option": top_hotels[0] if top_hotels else None
        })
        
    except Exception as e:
        return json.dumps({
            "error": f"Error searching hotels: {str(e)}"
        })


class HotelAgentA2A:
    """Hotel Agent for A2A protocol."""
    
    SYSTEM_INSTRUCTION = """You are a Hotel Booking Agent specializing in finding and booking accommodations.

Your responsibilities:
1. Search for hotels based on user requirements (destination, dates, budget, guests)
2. Compare and rank hotels by value, location, and amenities
3. Provide detailed information about available options
4. Handle special requests (late check-in, accessibility needs, etc.)
5. Coordinate with other agents on timing and location

When searching for hotels:
- Use the search_hotels tool with proper parameters
- Consider the total budget for the entire stay
- Prioritize hotels with good ratings and cancellation policies
- Provide clear comparisons between options

Always structure your response with:
- A summary of what was searched
- The top hotel recommendations with key details
- A selected best option with justification
- Any important notes or warnings

Remember: You're part of a larger travel planning system. Focus only on accommodation needs."""
    
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
        self.tools = [search_hotels]
        
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat,
        )
    
    async def stream(self, query: str, context_id: str) -> AsyncIterable[Dict[str, Any]]:
        """Stream the agent's response."""
        config = {"configurable": {"thread_id": context_id}}
        
        # Add context about today's date
        today_str = f"Today's date is {datetime.now().strftime('%Y-%m-%d')}."
        augmented_query = f"{today_str}\n\nUser request: {query}"
        
        inputs = {"messages": [("user", augmented_query)]}
        
        # Stream the agent's processing
        for item in self.graph.stream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            
            if isinstance(message, AIMessage) and message.tool_calls:
                yield {
                    "is_task_complete": False,
                    "updates": "Searching for hotels..."
                }
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,
                    "updates": "Analyzing hotel options..."
                }
        
        # Get final response
        yield self._get_final_response(config)
    
    def _get_final_response(self, config) -> Dict[str, Any]:
        """Get the final response from the agent."""
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")
        
        if structured_response and isinstance(structured_response, ResponseFormat):
            # Format the response nicely
            content_parts = [f"**{structured_response.message}**\n"]
            
            if structured_response.hotels:
                content_parts.append(f"\nFound {len(structured_response.hotels)} hotels:\n")
                
                for i, hotel in enumerate(structured_response.hotels[:5], 1):
                    content_parts.append(f"\n{i}. **{hotel.get('name', 'Unknown Hotel')}**")
                    content_parts.append(f"   - Price: ${hotel.get('total_price', 0):.2f} total (${hotel.get('price_per_night', 0):.2f}/night)")
                    content_parts.append(f"   - Rating: {hotel.get('rating', 'N/A')}/5")
                    content_parts.append(f"   - Location: {hotel.get('address', 'Unknown')}")
                    if hotel.get('amenities'):
                        content_parts.append(f"   - Amenities: {', '.join(hotel['amenities'][:5])}")
            
            if structured_response.selected_hotel:
                hotel = structured_response.selected_hotel
                content_parts.append(f"\n**Recommended: {hotel.get('name')}**")
                content_parts.append(f"This hotel offers the best value for your requirements.")
            
            return {
                "is_task_complete": True,
                "content": "\n".join(content_parts),
                "data": {
                    "hotels": structured_response.hotels,
                    "selected": structured_response.selected_hotel
                }
            }
        
        return {
            "is_task_complete": False,
            "content": "Unable to process hotel search request. Please try again.",
            "data": {}
        }