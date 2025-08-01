"""
Activity Agent implementation for A2A protocol.
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


class ActivitySearchInput(BaseModel):
    """Input schema for activity search."""
    destination: str = Field(..., description="City or location for activities")
    date: str = Field(..., description="Date for activities in YYYY-MM-DD format")
    category: str = Field(..., description="Activity category: culture, adventure, food, nature, entertainment")
    interests: List[str] = Field(default_factory=list, description="List of specific interests")
    budget_per_person: float = Field(..., description="Maximum budget per person")
    duration_hours: float = Field(None, description="Preferred activity duration in hours")
    group_size: int = Field(1, description="Number of people in the group")


class RestaurantSearchInput(BaseModel):
    """Input schema for restaurant search."""
    location: str = Field(..., description="City or area for dining")
    cuisine_type: str = Field(None, description="Type of cuisine preferred")
    meal_type: str = Field(..., description="breakfast, lunch, dinner, or snack")
    budget_per_person: float = Field(..., description="Maximum budget per person")
    dietary_restrictions: List[str] = Field(default_factory=list, description="Any dietary restrictions")
    date: str = Field(..., description="Reservation date in YYYY-MM-DD format")
    time: str = Field(..., description="Preferred dining time in HH:MM format")
    party_size: int = Field(1, description="Number of diners")


class ActivityResponseFormat(BaseModel):
    """Response format for activity agent."""
    status: str = Field("completed", description="Status of the response")
    message: str = Field(..., description="Response message")
    activities: List[Dict[str, Any]] = Field(default_factory=list, description="List of activities found")
    restaurants: List[Dict[str, Any]] = Field(default_factory=list, description="List of restaurants found")
    recommended_itinerary: List[Dict[str, Any]] = Field(default_factory=list, description="Suggested daily schedule")
    total_cost: float = Field(0, description="Total estimated cost for all activities")


@tool(args_schema=ActivitySearchInput)
async def search_activities(
    destination: str,
    date: str,
    category: str,
    interests: List[str] = None,
    budget_per_person: float = 100.0,
    duration_hours: float = None,
    group_size: int = 1
) -> str:
    """Search for activities and experiences at the destination."""
    try:
        interests = interests or []
        activity_date = datetime.strptime(date, "%Y-%m-%d")
        
        # Mock activity data based on category
        activity_templates = {
            "culture": [
                {"name": "Museum Tour", "duration": 3, "price_range": (15, 40)},
                {"name": "Historical Walking Tour", "duration": 2.5, "price_range": (20, 35)},
                {"name": "Art Gallery Experience", "duration": 2, "price_range": (10, 25)},
                {"name": "Cultural Performance", "duration": 2, "price_range": (30, 80)},
                {"name": "Architecture Tour", "duration": 3, "price_range": (25, 45)}
            ],
            "adventure": [
                {"name": "Zip Line Adventure", "duration": 4, "price_range": (50, 120)},
                {"name": "Rock Climbing", "duration": 3, "price_range": (40, 80)},
                {"name": "Kayaking Tour", "duration": 3, "price_range": (35, 70)},
                {"name": "Mountain Biking", "duration": 4, "price_range": (30, 60)},
                {"name": "Paragliding", "duration": 2, "price_range": (80, 200)}
            ],
            "food": [
                {"name": "Food Walking Tour", "duration": 3, "price_range": (40, 80)},
                {"name": "Cooking Class", "duration": 4, "price_range": (50, 100)},
                {"name": "Wine Tasting", "duration": 2, "price_range": (30, 70)},
                {"name": "Market Tour & Lunch", "duration": 3, "price_range": (35, 60)},
                {"name": "Chef's Table Experience", "duration": 3, "price_range": (80, 200)}
            ],
            "nature": [
                {"name": "National Park Tour", "duration": 6, "price_range": (30, 60)},
                {"name": "Wildlife Safari", "duration": 4, "price_range": (50, 150)},
                {"name": "Botanical Garden Visit", "duration": 2, "price_range": (10, 20)},
                {"name": "Hiking Expedition", "duration": 5, "price_range": (20, 40)},
                {"name": "Beach & Snorkeling", "duration": 4, "price_range": (40, 80)}
            ],
            "entertainment": [
                {"name": "Theme Park Visit", "duration": 8, "price_range": (60, 120)},
                {"name": "Theater Show", "duration": 2.5, "price_range": (40, 150)},
                {"name": "Concert", "duration": 3, "price_range": (50, 200)},
                {"name": "Comedy Club", "duration": 2, "price_range": (20, 40)},
                {"name": "Escape Room", "duration": 1.5, "price_range": (25, 40)}
            ]
        }
        
        templates = activity_templates.get(category, activity_templates["culture"])
        activities = []
        
        for template in templates:
            base_price = random.uniform(*template["price_range"])
            total_price = base_price * group_size
            
            if total_price <= budget_per_person * group_size:
                if duration_hours is None or abs(template["duration"] - duration_hours) <= 2:
                    time_slot = random.choice(["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"])
                    
                    activity = {
                        "name": f"{template['name']} in {destination}",
                        "category": category,
                        "date": date,
                        "time": time_slot,
                        "duration_hours": template["duration"],
                        "price_per_person": round(base_price, 2),
                        "total_price": round(total_price, 2),
                        "description": f"Experience the best of {destination} with this {category} activity",
                        "rating": round(random.uniform(4.0, 5.0), 1),
                        "reviews": random.randint(50, 500),
                        "includes": random.sample([
                            "Professional guide",
                            "Transportation",
                            "Equipment",
                            "Refreshments",
                            "Insurance",
                            "Photos"
                        ], k=3),
                        "meeting_point": f"Central {destination}",
                        "cancellation": "Free cancellation up to 24 hours"
                    }
                    
                    # Match with interests
                    if interests:
                        relevance = sum(1 for interest in interests if interest.lower() in activity["name"].lower())
                        activity["relevance_score"] = relevance
                    
                    activities.append(activity)
        
        # Sort by relevance and rating
        activities.sort(key=lambda x: (x.get("relevance_score", 0), x["rating"]), reverse=True)
        
        return json.dumps({
            "found": len(activities),
            "activities": activities[:10],  # Top 10 activities
            "destination": destination,
            "date": date
        })
        
    except Exception as e:
        return json.dumps({
            "error": f"Error searching activities: {str(e)}"
        })


@tool(args_schema=RestaurantSearchInput)
async def search_restaurants(
    location: str,
    meal_type: str,
    date: str,
    time: str,
    party_size: int = 1,
    cuisine_type: str = None,
    budget_per_person: float = 50.0,
    dietary_restrictions: List[str] = None
) -> str:
    """Search for restaurants and dining options."""
    try:
        dietary_restrictions = dietary_restrictions or []
        
        # Mock restaurant data
        cuisines = ["Italian", "French", "Japanese", "Thai", "Mexican", "American", "Indian", "Mediterranean", "Chinese", "Local"]
        if cuisine_type:
            cuisines = [cuisine_type] * 5 + random.sample(cuisines, 5)
        
        restaurants = []
        
        for i in range(10):
            cuisine = random.choice(cuisines)
            base_price = random.uniform(15, budget_per_person)
            
            restaurant = {
                "name": f"{cuisine} {random.choice(['Bistro', 'Kitchen', 'Table', 'House', 'Restaurant'])}",
                "cuisine": cuisine,
                "location": f"{location} - {random.choice(['Downtown', 'Old Town', 'Waterfront', 'City Center'])}",
                "price_per_person": round(base_price, 2),
                "rating": round(random.uniform(3.5, 5.0), 1),
                "reviews": random.randint(100, 2000),
                "available_times": [
                    time,
                    f"{int(time.split(':')[0])+1}:00",
                    f"{int(time.split(':')[0])-1}:00"
                ],
                "meal_types": ["breakfast", "lunch", "dinner"] if meal_type == "lunch" else [meal_type],
                "ambiance": random.choice(["Casual", "Fine Dining", "Romantic", "Family Friendly", "Business"]),
                "features": random.sample([
                    "Outdoor seating",
                    "Wine list",
                    "Private dining",
                    "Live music",
                    "City view",
                    "Historic building"
                ], k=3),
                "dietary_options": random.sample([
                    "Vegetarian",
                    "Vegan",
                    "Gluten-free",
                    "Halal",
                    "Kosher",
                    "Dairy-free"
                ], k=2)
            }
            
            # Check dietary restrictions
            if not dietary_restrictions or any(diet in restaurant["dietary_options"] for diet in dietary_restrictions):
                restaurants.append(restaurant)
        
        # Sort by rating
        restaurants.sort(key=lambda x: x["rating"], reverse=True)
        
        return json.dumps({
            "found": len(restaurants),
            "restaurants": restaurants[:5],  # Top 5 restaurants
            "location": location,
            "date": date,
            "time": time
        })
        
    except Exception as e:
        return json.dumps({
            "error": f"Error searching restaurants: {str(e)}"
        })


class ActivityAgentA2A:
    """Activity Agent for A2A protocol."""
    
    SYSTEM_INSTRUCTION = """You are an Activity and Experience Planning Agent specializing in tours, attractions, dining, and local experiences.

Your responsibilities:
1. Search for activities based on destination, dates, and interests
2. Recommend restaurants and dining experiences
3. Create balanced daily itineraries
4. Consider travel time between activities
5. Match activities to traveler interests and physical abilities

When searching for activities:
- Use search_activities for tours, attractions, and experiences
- Use search_restaurants for dining recommendations
- Consider the total daily budget
- Factor in rest time between activities
- Account for meal times
- Check weather-dependent activities

Always structure your response with:
- A summary of activities found
- Recommended daily itinerary
- Restaurant suggestions for meals
- Total estimated cost
- Important tips or warnings

Remember: You're part of a travel planning system. Coordinate activity times with hotel locations and transport schedules."""
    
    def __init__(self):
        self.model = LLMConfig.get_agent_llm("activity")
        self.tools = [search_activities, search_restaurants]
        
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ActivityResponseFormat,
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
                    "updates": "Searching for activities and experiences..."
                }
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,
                    "updates": "Analyzing options and creating itinerary..."
                }
        
        # Get final response
        yield self._get_final_response(config)
    
    def _get_final_response(self, config) -> Dict[str, Any]:
        """Get the final response from the agent."""
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")
        
        if structured_response and isinstance(structured_response, ActivityResponseFormat):
            content_parts = [f"**{structured_response.message}**\n"]
            
            if structured_response.activities:
                content_parts.append(f"\n🎯 **Activities & Experiences** ({len(structured_response.activities)} found):\n")
                
                for i, activity in enumerate(structured_response.activities[:5], 1):
                    content_parts.append(f"\n{i}. **{activity.get('name', 'Activity')}**")
                    content_parts.append(f"   📅 {activity.get('date')} at {activity.get('time')}")
                    content_parts.append(f"   ⏱️ Duration: {activity.get('duration_hours')} hours")
                    content_parts.append(f"   💰 ${activity.get('price_per_person')}/person")
                    content_parts.append(f"   ⭐ {activity.get('rating')} ({activity.get('reviews')} reviews)")
                    if activity.get('includes'):
                        content_parts.append(f"   ✅ Includes: {', '.join(activity['includes'])}")
            
            if structured_response.restaurants:
                content_parts.append(f"\n\n🍽️ **Dining Recommendations**:\n")
                
                for i, restaurant in enumerate(structured_response.restaurants[:3], 1):
                    content_parts.append(f"\n{i}. **{restaurant.get('name')}** - {restaurant.get('cuisine')}")
                    content_parts.append(f"   📍 {restaurant.get('location')}")
                    content_parts.append(f"   💰 ${restaurant.get('price_per_person')}/person")
                    content_parts.append(f"   ⭐ {restaurant.get('rating')} ({restaurant.get('reviews')} reviews)")
                    content_parts.append(f"   🍴 {restaurant.get('ambiance')}")
            
            if structured_response.recommended_itinerary:
                content_parts.append(f"\n\n📅 **Suggested Daily Schedule**:\n")
                for item in structured_response.recommended_itinerary:
                    content_parts.append(f"- {item.get('time')}: {item.get('activity')}")
            
            if structured_response.total_cost > 0:
                content_parts.append(f"\n\n💵 **Total Estimated Cost**: ${structured_response.total_cost:.2f}")
            
            return {
                "is_task_complete": True,
                "content": "\n".join(content_parts),
                "data": {
                    "activities": structured_response.activities,
                    "restaurants": structured_response.restaurants,
                    "itinerary": structured_response.recommended_itinerary,
                    "total_cost": structured_response.total_cost
                }
            }
        
        return {
            "is_task_complete": False,
            "content": "Unable to process activity search request. Please try again.",
            "data": {}
        }