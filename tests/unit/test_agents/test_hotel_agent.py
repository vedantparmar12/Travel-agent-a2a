"""
Unit tests for Hotel Agent.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.hotel.hotel_agent_a2a import HotelAgentA2A, search_hotels


class TestHotelAgent:
    """Test cases for Hotel Agent functionality."""
    
    @pytest.fixture
    def hotel_agent(self):
        """Create a Hotel Agent instance for testing."""
        return HotelAgentA2A()
    
    @pytest.mark.asyncio
    async def test_search_hotels_valid_input(self):
        """Test search_hotels with valid input parameters."""
        result = await search_hotels(
            destination="Paris",
            check_in="2025-08-15",
            check_out="2025-08-20",
            guests=2,
            max_price_per_night=200.0,
            rating_min=4
        )
        
        data = json.loads(result)
        assert "hotels" in data
        assert "found" in data
        assert data["found"] > 0
        assert len(data["hotels"]) > 0
        
        # Check first hotel
        hotel = data["hotels"][0]
        assert "name" in hotel
        assert "price_per_night" in hotel
        assert "rating" in hotel
        assert hotel["rating"] >= 4
        assert hotel["price_per_night"] <= 200.0
    
    @pytest.mark.asyncio
    async def test_search_hotels_budget_constraint(self):
        """Test that hotels respect budget constraints."""
        result = await search_hotels(
            destination="London",
            check_in="2025-09-01",
            check_out="2025-09-05",
            guests=1,
            max_price_per_night=50.0,
            rating_min=3
        )
        
        data = json.loads(result)
        if data["found"] > 0:
            for hotel in data["hotels"]:
                assert hotel["price_per_night"] <= 50.0
    
    @pytest.mark.asyncio
    async def test_search_hotels_invalid_dates(self):
        """Test search_hotels with invalid date format."""
        result = await search_hotels(
            destination="New York",
            check_in="invalid-date",
            check_out="2025-08-20",
            guests=2,
            max_price_per_night=150.0
        )
        
        data = json.loads(result)
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_hotel_agent_stream(self, hotel_agent):
        """Test the hotel agent streaming response."""
        query = "Find hotels in Rome for August 15-20, 2025"
        context_id = "test-session-123"
        
        updates = []
        async for update in hotel_agent.stream(query, context_id):
            updates.append(update)
        
        assert len(updates) > 0
        
        # Check final update
        final_update = updates[-1]
        assert final_update.get("is_task_complete") is True
        assert "content" in final_update
        assert "data" in final_update
    
    def test_hotel_preferences_matching(self):
        """Test that hotel preferences are considered in search."""
        # This would test the preference matching logic
        # In the current implementation, preferences are simulated
        # In production, this would test actual filtering
        pass
    
    @pytest.mark.asyncio
    async def test_concurrent_searches(self, hotel_agent):
        """Test that multiple concurrent searches work correctly."""
        queries = [
            "Hotels in Paris for next week",
            "Budget hotels in London",
            "Luxury hotels in Tokyo"
        ]
        
        tasks = []
        for i, query in enumerate(queries):
            context_id = f"test-session-{i}"
            task = self._collect_stream_results(hotel_agent, query, context_id)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        for result in results:
            assert result[-1].get("is_task_complete") is True
    
    async def _collect_stream_results(self, agent, query, context_id):
        """Helper to collect all streaming results."""
        results = []
        async for update in agent.stream(query, context_id):
            results.append(update)
        return results


class TestHotelAgentTools:
    """Test cases for Hotel Agent tools."""
    
    @pytest.mark.asyncio
    async def test_search_hotels_sorting(self):
        """Test that hotels are sorted by price."""
        result = await search_hotels(
            destination="Barcelona",
            check_in="2025-07-01",
            check_out="2025-07-05",
            guests=2,
            max_price_per_night=300.0
        )
        
        data = json.loads(result)
        hotels = data["hotels"]
        
        # Check that hotels are sorted by price (ascending)
        for i in range(1, len(hotels)):
            assert hotels[i]["price_per_night"] >= hotels[i-1]["price_per_night"]
    
    @pytest.mark.asyncio
    async def test_search_hotels_amenities(self):
        """Test that hotels include amenities information."""
        result = await search_hotels(
            destination="Miami",
            check_in="2025-10-01",
            check_out="2025-10-07",
            guests=2,
            preferences=["pool", "gym"]
        )
        
        data = json.loads(result)
        if data["found"] > 0:
            hotel = data["hotels"][0]
            assert "amenities" in hotel
            assert isinstance(hotel["amenities"], list)
            assert len(hotel["amenities"]) > 0