"""
Integration tests for multi-agent workflows.
"""
import pytest
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List
import json

from src.shared.models import TravelPreferences
from src.agents.orchestrator.orchestrator_a2a import OrchestratorAgentA2A
from src.agents.hotel.hotel_agent_a2a import HotelAgentA2A
from src.agents.transport.transport_agent_a2a import TransportAgentA2A
from src.agents.activity.activity_agent_a2a import ActivityAgentA2A
from src.agents.budget.budget_agent_a2a import BudgetAgentA2A
from src.agents.itinerary.itinerary_agent_a2a import ItineraryAgentA2A


@pytest.mark.integration
class TestMultiAgentWorkflow:
    """Test cases for multi-agent travel planning workflows."""
    
    @pytest.fixture
    async def mock_agent_urls(self, monkeypatch):
        """Mock agent URLs for testing."""
        # In real integration tests, these would be actual running agents
        urls = [
            "http://localhost:10010",  # Hotel
            "http://localhost:10011",  # Transport
            "http://localhost:10012",  # Activity
            "http://localhost:10013",  # Budget
            "http://localhost:10014",  # Itinerary
        ]
        return urls
    
    @pytest.fixture
    def travel_preferences(self):
        """Create sample travel preferences."""
        return TravelPreferences(
            destination="Paris, France",
            origin="New York, USA",
            start_date=datetime.now() + timedelta(days=60),
            end_date=datetime.now() + timedelta(days=67),
            budget=5000.0,
            currency="USD",
            travelers=2,
            preferred_hotel_rating=4,
            activity_preferences=["museums", "culture", "food"],
            dietary_restrictions=["vegetarian"]
        )
    
    @pytest.mark.asyncio
    async def test_hotel_agent_workflow(self):
        """Test hotel agent standalone workflow."""
        agent = HotelAgentA2A()
        
        query = "Find hotels in Paris for July 15-20, 2025, budget $200/night for 2 people"
        context_id = "test-hotel-session"
        
        responses = []
        async for response in agent.stream(query, context_id):
            responses.append(response)
        
        assert len(responses) > 0
        final_response = responses[-1]
        
        assert final_response["is_task_complete"] is True
        assert "content" in final_response
        assert "data" in final_response
        assert "hotels" in final_response["data"]
    
    @pytest.mark.asyncio
    async def test_transport_agent_workflow(self):
        """Test transport agent standalone workflow."""
        agent = TransportAgentA2A()
        
        query = "Find flights from New York to Paris, departing July 15, returning July 20, for 2 people"
        context_id = "test-transport-session"
        
        responses = []
        async for response in agent.stream(query, context_id):
            responses.append(response)
        
        assert len(responses) > 0
        final_response = responses[-1]
        
        assert final_response["is_task_complete"] is True
        assert "flights" in final_response["data"]
    
    @pytest.mark.asyncio
    async def test_activity_agent_workflow(self):
        """Test activity agent standalone workflow."""
        agent = ActivityAgentA2A()
        
        query = "Find cultural activities and restaurants in Paris for July 16-19, interested in museums and French cuisine"
        context_id = "test-activity-session"
        
        responses = []
        async for response in agent.stream(query, context_id):
            responses.append(response)
        
        assert len(responses) > 0
        final_response = responses[-1]
        
        assert final_response["is_task_complete"] is True
        assert "activities" in final_response["data"] or "restaurants" in final_response["data"]
    
    @pytest.mark.asyncio
    async def test_budget_agent_workflow(self):
        """Test budget agent workflow."""
        agent = BudgetAgentA2A()
        
        # Set up budget
        agent.set_session_budget("test-budget-session", 5000.0, "USD")
        
        query = "Check if I can spend $800 on hotel for 5 nights"
        context_id = "test-budget-session"
        
        responses = []
        async for response in agent.stream(query, context_id):
            responses.append(response)
        
        assert len(responses) > 0
        final_response = responses[-1]
        
        assert final_response["is_task_complete"] is True
        assert "data" in final_response
        assert "budget_status" in final_response["data"]
    
    @pytest.mark.asyncio
    async def test_itinerary_agent_workflow(self):
        """Test itinerary agent workflow."""
        agent = ItineraryAgentA2A()
        
        # Mock bookings data
        bookings_data = {
            "trip_name": "Paris Summer Trip",
            "start_date": "2025-07-15",
            "end_date": "2025-07-20",
            "destination": "Paris, France",
            "travelers": 2,
            "bookings": [
                {
                    "booking_type": "hotel",
                    "name": "Hotel Eiffel View",
                    "date": "2025-07-15",
                    "location": "Near Eiffel Tower",
                    "cost": 800,
                    "confirmation_number": "HTL123456"
                },
                {
                    "booking_type": "flight",
                    "name": "AA 100",
                    "date": "2025-07-15",
                    "time": "08:00",
                    "location": "JFK to CDG",
                    "cost": 1200
                }
            ]
        }
        
        query = f"Create itinerary for: {json.dumps(bookings_data)}"
        context_id = "test-itinerary-session"
        
        responses = []
        async for response in agent.stream(query, context_id):
            responses.append(response)
        
        assert len(responses) > 0
        final_response = responses[-1]
        
        assert final_response["is_task_complete"] is True
        assert "itinerary_days" in final_response["data"]
    
    @pytest.mark.asyncio
    async def test_agent_communication_flow(self):
        """Test communication flow between agents."""
        # This test simulates the orchestrator coordinating with other agents
        
        # 1. Hotel search
        hotel_agent = HotelAgentA2A()
        hotel_query = "Hotels in Rome, April 10-15, budget $150/night"
        
        hotel_responses = []
        async for response in hotel_agent.stream(hotel_query, "comm-test-1"):
            hotel_responses.append(response)
        
        assert hotel_responses[-1]["is_task_complete"] is True
        hotel_data = hotel_responses[-1]["data"]
        
        # 2. Activity search based on hotel location
        activity_agent = ActivityAgentA2A()
        activity_query = f"Activities near {hotel_data['hotels'][0]['name']} in Rome"
        
        activity_responses = []
        async for response in activity_agent.stream(activity_query, "comm-test-2"):
            activity_responses.append(response)
        
        assert activity_responses[-1]["is_task_complete"] is True
        
        # 3. Budget validation
        budget_agent = BudgetAgentA2A()
        budget_agent.set_session_budget("comm-test-3", 3000.0)
        
        total_cost = hotel_data['hotels'][0]['total_cost']
        budget_query = f"Validate expense: hotel ${total_cost}"
        
        budget_responses = []
        async for response in budget_agent.stream(budget_query, "comm-test-3"):
            budget_responses.append(response)
        
        assert budget_responses[-1]["is_task_complete"] is True
        assert budget_responses[-1]["data"]["approved"] is True
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complete_trip_planning_workflow(self, travel_preferences):
        """Test complete trip planning workflow with all agents."""
        # Note: This test requires all agents to be running
        # In CI/CD, this would be done with docker-compose or similar
        
        context_id = "full-workflow-test"
        
        # 1. Initialize all agents
        agents = {
            "hotel": HotelAgentA2A(),
            "transport": TransportAgentA2A(),
            "activity": ActivityAgentA2A(),
            "budget": BudgetAgentA2A(),
            "itinerary": ItineraryAgentA2A()
        }
        
        # 2. Set budget
        agents["budget"].set_session_budget(
            context_id, 
            travel_preferences.budget,
            travel_preferences.currency
        )
        
        # 3. Search hotels
        hotel_query = (
            f"Find hotels in {travel_preferences.destination} "
            f"from {travel_preferences.start_date.strftime('%Y-%m-%d')} "
            f"to {travel_preferences.end_date.strftime('%Y-%m-%d')}, "
            f"budget ${travel_preferences.budget * 0.35 / 7}/night, "  # 35% for hotels
            f"{travel_preferences.travelers} people"
        )
        
        hotel_results = []
        async for response in agents["hotel"].stream(hotel_query, context_id):
            if response["is_task_complete"]:
                hotel_results = response["data"]["hotels"]
        
        assert len(hotel_results) > 0
        
        # 4. Search transport
        transport_query = (
            f"Find flights from {travel_preferences.origin} to {travel_preferences.destination}, "
            f"departing {travel_preferences.start_date.strftime('%Y-%m-%d')}, "
            f"returning {travel_preferences.end_date.strftime('%Y-%m-%d')}, "
            f"{travel_preferences.travelers} passengers"
        )
        
        transport_results = []
        async for response in agents["transport"].stream(transport_query, context_id):
            if response["is_task_complete"]:
                transport_results = response["data"]["flights"]
        
        assert len(transport_results) > 0
        
        # 5. Search activities
        activity_query = (
            f"Find activities in {travel_preferences.destination} "
            f"interested in {', '.join(travel_preferences.activity_preferences)}"
        )
        
        activity_results = []
        async for response in agents["activity"].stream(activity_query, context_id):
            if response["is_task_complete"]:
                activity_results = response["data"].get("activities", [])
        
        assert len(activity_results) > 0
        
        # 6. Create itinerary
        bookings = {
            "trip_name": f"Trip to {travel_preferences.destination}",
            "start_date": travel_preferences.start_date.strftime('%Y-%m-%d'),
            "end_date": travel_preferences.end_date.strftime('%Y-%m-%d'),
            "destination": travel_preferences.destination,
            "travelers": travel_preferences.travelers,
            "bookings": [
                {
                    "booking_type": "hotel",
                    "name": hotel_results[0]["name"],
                    "date": travel_preferences.start_date.strftime('%Y-%m-%d'),
                    "cost": hotel_results[0]["total_cost"]
                },
                {
                    "booking_type": "flight",
                    "name": transport_results[0]["flight_number"],
                    "date": travel_preferences.start_date.strftime('%Y-%m-%d'),
                    "cost": transport_results[0]["total_price"]
                }
            ]
        }
        
        itinerary_query = f"Create itinerary: {json.dumps(bookings)}"
        
        final_itinerary = None
        async for response in agents["itinerary"].stream(itinerary_query, context_id):
            if response["is_task_complete"]:
                final_itinerary = response["data"]
        
        assert final_itinerary is not None
        assert "itinerary_days" in final_itinerary
        assert len(final_itinerary["itinerary_days"]) > 0


@pytest.mark.integration
class TestAgentErrorHandling:
    """Test error handling in multi-agent scenarios."""
    
    @pytest.mark.asyncio
    async def test_invalid_date_handling(self):
        """Test how agents handle invalid dates."""
        agent = HotelAgentA2A()
        
        query = "Find hotels in Paris for invalid-date"
        context_id = "error-test-1"
        
        responses = []
        async for response in agent.stream(query, context_id):
            responses.append(response)
        
        # Agent should handle error gracefully
        assert len(responses) > 0
    
    @pytest.mark.asyncio
    async def test_budget_exceeded_handling(self):
        """Test budget exceeded scenario."""
        budget_agent = BudgetAgentA2A()
        budget_agent.set_session_budget("error-test-2", 1000.0)
        
        query = "Validate expense: hotel $2000"
        
        responses = []
        async for response in budget_agent.stream(query, "error-test-2"):
            responses.append(response)
        
        final_response = responses[-1]
        assert final_response["is_task_complete"] is True
        assert final_response["data"]["approved"] is False
    
    @pytest.mark.asyncio
    async def test_no_results_handling(self):
        """Test scenario where no results are found."""
        agent = ActivityAgentA2A()
        
        # Very specific query that might return no results
        query = "Find underwater basket weaving classes in Antarctica"
        
        responses = []
        async for response in agent.stream(query, "error-test-3"):
            responses.append(response)
        
        # Should complete even with no/few results
        assert responses[-1]["is_task_complete"] is True