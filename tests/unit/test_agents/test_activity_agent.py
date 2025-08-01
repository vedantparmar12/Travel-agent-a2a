"""
Unit tests for Activity Agent.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.activity.activity_agent_a2a import ActivityAgentA2A, search_activities, search_restaurants


class TestActivityAgent:
    """Test cases for Activity Agent functionality."""
    
    @pytest.fixture
    def activity_agent(self):
        """Create an Activity Agent instance for testing."""
        return ActivityAgentA2A()
    
    @pytest.mark.asyncio
    async def test_search_activities_valid_input(self):
        """Test search_activities with valid input parameters."""
        result = await search_activities(
            destination="Paris",
            date="2025-08-15",
            category="culture",
            interests=["museums", "art"],
            budget_per_person=100.0,
            group_size=2
        )
        
        data = json.loads(result)
        assert "activities" in data
        assert "found" in data
        assert data["found"] > 0
        assert len(data["activities"]) > 0
        
        # Check first activity
        activity = data["activities"][0]
        assert "name" in activity
        assert "price_per_person" in activity
        assert "duration_hours" in activity
        assert "rating" in activity
        assert activity["category"] == "culture"
        assert activity["total_price"] <= 200.0  # 100 per person * 2 people
    
    @pytest.mark.asyncio
    async def test_search_activities_by_category(self):
        """Test that activities match requested category."""
        categories = ["culture", "adventure", "food", "nature", "entertainment"]
        
        for category in categories:
            result = await search_activities(
                destination="Barcelona",
                date="2025-09-01",
                category=category,
                budget_per_person=150.0
            )
            
            data = json.loads(result)
            if data["found"] > 0:
                for activity in data["activities"]:
                    assert activity["category"] == category
    
    @pytest.mark.asyncio
    async def test_search_restaurants_valid_input(self):
        """Test search_restaurants with valid input parameters."""
        result = await search_restaurants(
            location="Rome",
            meal_type="dinner",
            date="2025-08-15",
            time="19:00",
            party_size=4,
            cuisine_type="Italian",
            budget_per_person=50.0
        )
        
        data = json.loads(result)
        assert "restaurants" in data
        assert "found" in data
        assert data["found"] > 0
        assert len(data["restaurants"]) > 0
        
        # Check first restaurant
        restaurant = data["restaurants"][0]
        assert "name" in restaurant
        assert "cuisine" in restaurant
        assert "price_per_person" in restaurant
        assert "rating" in restaurant
        assert restaurant["price_per_person"] <= 50.0
    
    @pytest.mark.asyncio
    async def test_search_restaurants_dietary_restrictions(self):
        """Test that dietary restrictions are considered."""
        result = await search_restaurants(
            location="London",
            meal_type="lunch",
            date="2025-08-20",
            time="12:30",
            party_size=2,
            dietary_restrictions=["vegetarian", "gluten-free"],
            budget_per_person=40.0
        )
        
        data = json.loads(result)
        if data["found"] > 0:
            for restaurant in data["restaurants"]:
                assert "dietary_options" in restaurant
                # Check that at least one dietary restriction is supported
                assert any(diet in restaurant["dietary_options"] 
                          for diet in ["Vegetarian", "Gluten-free"])
    
    @pytest.mark.asyncio
    async def test_activity_agent_stream(self, activity_agent):
        """Test the activity agent streaming response."""
        query = "Find cultural activities and restaurants in Paris for August 15, 2025"
        context_id = "test-session-456"
        
        updates = []
        async for update in activity_agent.stream(query, context_id):
            updates.append(update)
        
        assert len(updates) > 0
        
        # Check final update
        final_update = updates[-1]
        assert final_update.get("is_task_complete") is True
        assert "content" in final_update
        assert "data" in final_update
        
        # Check that data contains both activities and restaurants
        data = final_update.get("data", {})
        assert "activities" in data or "restaurants" in data
    
    @pytest.mark.asyncio
    async def test_activities_duration_filter(self):
        """Test that activities respect duration preferences."""
        result = await search_activities(
            destination="Tokyo",
            date="2025-10-01",
            category="entertainment",
            duration_hours=2.0,
            budget_per_person=100.0
        )
        
        data = json.loads(result)
        if data["found"] > 0:
            # Activities should be close to requested duration
            for activity in data["activities"]:
                duration_diff = abs(activity["duration_hours"] - 2.0)
                assert duration_diff <= 2.0  # Within 2 hours tolerance
    
    @pytest.mark.asyncio
    async def test_invalid_date_handling(self):
        """Test error handling for invalid dates."""
        result = await search_activities(
            destination="Sydney",
            date="not-a-date",
            category="nature",
            budget_per_person=80.0
        )
        
        data = json.loads(result)
        assert "error" in data


class TestActivityAgentIntegration:
    """Integration tests for Activity Agent."""
    
    @pytest.mark.asyncio
    async def test_combined_search_flow(self):
        """Test searching for both activities and restaurants."""
        agent = ActivityAgentA2A()
        query = """Plan a day in New York on September 15, 2025:
        - Morning: cultural activity
        - Lunch: Italian restaurant
        - Afternoon: entertainment
        - Dinner: fine dining"""
        
        results = []
        async for update in agent.stream(query, "test-session-789"):
            results.append(update)
        
        final = results[-1]
        assert final["is_task_complete"] is True
        
        # Should have comprehensive day plan
        content = final["content"]
        assert "Activities" in content or "activities" in content
        assert "Dining" in content or "Restaurants" in content