"""
Unit tests for data models.
"""
import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from src.shared.models import (
    TravelPreferences,
    HotelBooking,
    TransportBooking,
    ActivityBooking,
    BudgetStatus,
    TravelItinerary,
    AgentMessage,
    ConflictInfo,
    HumanApprovalRequest,
    MessageType,
    BookingStatus,
    TravelMode,
    Location
)


class TestTravelPreferences:
    """Test cases for TravelPreferences model."""
    
    def test_valid_travel_preferences(self):
        """Test creating valid travel preferences."""
        prefs = TravelPreferences(
            destination="Paris, France",
            origin="New York, USA",
            start_date=datetime.now() + timedelta(days=30),
            end_date=datetime.now() + timedelta(days=37),
            budget=3000.0,
            currency="USD",
            travelers=2,
            preferred_hotel_rating=4,
            activity_preferences=["museums", "restaurants"],
            dietary_restrictions=["vegetarian"]
        )
        
        assert prefs.destination == "Paris, France"
        assert prefs.budget == 3000.0
        assert prefs.travelers == 2
        assert len(prefs.activity_preferences) == 2
    
    def test_end_date_validation(self):
        """Test that end_date must be after start_date."""
        start = datetime.now() + timedelta(days=30)
        
        with pytest.raises(ValidationError):
            TravelPreferences(
                destination="London",
                origin="Boston",
                start_date=start,
                end_date=start - timedelta(days=1),  # Before start date
                budget=2000.0
            )
    
    def test_hotel_rating_validation(self):
        """Test hotel rating must be between 1 and 5."""
        base_date = datetime.now() + timedelta(days=30)
        
        # Valid ratings
        for rating in [1, 2, 3, 4, 5]:
            prefs = TravelPreferences(
                destination="Rome",
                origin="Madrid",
                start_date=base_date,
                end_date=base_date + timedelta(days=5),
                budget=2000.0,
                preferred_hotel_rating=rating
            )
            assert prefs.preferred_hotel_rating == rating
        
        # Invalid ratings
        for rating in [0, 6, -1]:
            with pytest.raises(ValidationError):
                TravelPreferences(
                    destination="Rome",
                    origin="Madrid",
                    start_date=base_date,
                    end_date=base_date + timedelta(days=5),
                    budget=2000.0,
                    preferred_hotel_rating=rating
                )


class TestHotelBooking:
    """Test cases for HotelBooking model."""
    
    def test_valid_hotel_booking(self):
        """Test creating a valid hotel booking."""
        location = Location(
            latitude=48.8566,
            longitude=2.3522,
            city="Paris",
            country="France"
        )
        
        booking = HotelBooking(
            hotel_name="Hotel Example",
            location=location,
            check_in=datetime.now() + timedelta(days=30),
            check_out=datetime.now() + timedelta(days=35),
            room_type="Double Room",
            guests=2,
            cost_per_night=150.0,
            total_cost=750.0,
            cancellation_policy="Free cancellation up to 24 hours",
            rating=4.5
        )
        
        assert booking.hotel_name == "Hotel Example"
        assert booking.total_cost == 750.0
        assert booking.status == BookingStatus.PENDING
        assert booking.rating == 4.5


class TestTransportBooking:
    """Test cases for TransportBooking model."""
    
    def test_valid_transport_booking(self):
        """Test creating a valid transport booking."""
        departure = datetime.now() + timedelta(days=30, hours=10)
        arrival = departure + timedelta(hours=8, minutes=30)
        
        booking = TransportBooking(
            mode=TravelMode.FLIGHT,
            carrier="Example Airlines",
            departure_time=departure,
            arrival_time=arrival,
            origin="JFK",
            destination="CDG",
            cost=850.0,
            seat_class="Economy",
            stops=0
        )
        
        assert booking.mode == TravelMode.FLIGHT
        assert booking.carrier == "Example Airlines"
        assert booking.cost == 850.0
        assert booking.stops == 0


class TestBudgetStatus:
    """Test cases for BudgetStatus model."""
    
    def test_budget_calculations(self):
        """Test budget status calculations."""
        budget = BudgetStatus(
            total_budget=5000.0,
            spent=1500.0,
            allocated=2000.0,
            available=1500.0,
            breakdown={
                "hotel": 800.0,
                "transport": 500.0,
                "activities": 200.0
            }
        )
        
        assert budget.percentage_used == 30.0  # 1500/5000 * 100
        assert budget.available == 1500.0
        assert sum(budget.breakdown.values()) == budget.spent
    
    def test_zero_budget(self):
        """Test budget status with zero total budget."""
        budget = BudgetStatus(
            total_budget=0.0,
            spent=0.0,
            allocated=0.0,
            available=0.0
        )
        
        assert budget.percentage_used == 0.0


class TestAgentMessage:
    """Test cases for AgentMessage model."""
    
    def test_valid_agent_message(self):
        """Test creating a valid agent message."""
        message = AgentMessage(
            message_id="msg-123",
            sender="hotel_agent",
            recipient="orchestrator",
            session_id="session-456",
            message_type=MessageType.BOOKING_REQUEST,
            content={
                "hotel_id": "hotel-789",
                "check_in": "2025-08-15",
                "check_out": "2025-08-20"
            },
            priority=8
        )
        
        assert message.message_id == "msg-123"
        assert message.message_type == MessageType.BOOKING_REQUEST
        assert message.priority == 8
        assert message.requires_response is True
    
    def test_priority_validation(self):
        """Test message priority must be between 1 and 10."""
        base_message = {
            "message_id": "msg-123",
            "sender": "test",
            "recipient": "test",
            "session_id": "session-123",
            "message_type": MessageType.STATUS_UPDATE,
            "content": {}
        }
        
        # Valid priorities
        for priority in range(1, 11):
            msg = AgentMessage(**base_message, priority=priority)
            assert msg.priority == priority
        
        # Invalid priorities
        for priority in [0, 11, -1]:
            with pytest.raises(ValidationError):
                AgentMessage(**base_message, priority=priority)


class TestConflictInfo:
    """Test cases for ConflictInfo model."""
    
    def test_valid_conflict_info(self):
        """Test creating valid conflict information."""
        conflict = ConflictInfo(
            conflict_type="timing",
            affected_agents=["hotel_agent", "transport_agent"],
            description="Flight arrival after hotel check-in closes",
            suggested_resolutions=[
                {"action": "change_flight", "details": "Earlier flight available"},
                {"action": "late_checkin", "details": "Request late check-in"}
            ],
            severity=8
        )
        
        assert conflict.conflict_type == "timing"
        assert len(conflict.affected_agents) == 2
        assert len(conflict.suggested_resolutions) == 2
        assert conflict.severity == 8


class TestTravelItinerary:
    """Test cases for TravelItinerary model."""
    
    def test_complete_itinerary(self):
        """Test creating a complete travel itinerary."""
        hotel = HotelBooking(
            hotel_name="Test Hotel",
            location=Location(latitude=0, longitude=0),
            check_in=datetime.now() + timedelta(days=30),
            check_out=datetime.now() + timedelta(days=35),
            room_type="Suite",
            guests=2,
            cost_per_night=200.0,
            total_cost=1000.0,
            cancellation_policy="Flexible"
        )
        
        budget = BudgetStatus(
            total_budget=5000.0,
            spent=1000.0,
            allocated=1500.0,
            available=2500.0
        )
        
        itinerary = TravelItinerary(
            trip_id="trip-123",
            traveler_name="John Doe",
            destination="Paris, France",
            start_date=datetime.now() + timedelta(days=30),
            end_date=datetime.now() + timedelta(days=35),
            total_cost=1000.0,
            hotels=[hotel],
            budget_status=budget
        )
        
        assert itinerary.trip_id == "trip-123"
        assert len(itinerary.hotels) == 1
        assert itinerary.total_cost == 1000.0
        assert isinstance(itinerary.created_at, datetime)