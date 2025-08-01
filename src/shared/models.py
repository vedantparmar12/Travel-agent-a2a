"""
Data models for the travel agent system.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class MessageType(str, Enum):
    """Types of messages exchanged between agents."""
    TASK_ASSIGNMENT = "task_assignment"
    BOOKING_REQUEST = "booking_request"
    BUDGET_VALIDATION = "budget_validation"
    BUDGET_APPROVAL = "budget_approval"
    BUDGET_REJECTION = "budget_rejection"
    CONFLICT_ALERT = "conflict_alert"
    STATUS_UPDATE = "status_update"
    HUMAN_ESCALATION = "human_escalation"
    MODIFICATION_REQUEST = "modification_request"
    COMPLETION_NOTIFICATION = "completion_notification"


class BookingStatus(str, Enum):
    """Status of a booking."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REQUIRES_MODIFICATION = "requires_modification"


class TravelMode(str, Enum):
    """Modes of transportation."""
    FLIGHT = "flight"
    TRAIN = "train"
    CAR = "car"
    BUS = "bus"
    FERRY = "ferry"


class Location(BaseModel):
    """Geographic location."""
    latitude: float
    longitude: float
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class TravelPreferences(BaseModel):
    """User travel preferences."""
    destination: str
    origin: str
    start_date: datetime
    end_date: datetime
    budget: float
    currency: str = "USD"
    travelers: int = 1
    preferred_hotel_rating: Optional[int] = Field(None, ge=1, le=5)
    preferred_transport_mode: Optional[TravelMode] = None
    activity_preferences: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)
    accessibility_requirements: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class HotelBooking(BaseModel):
    """Hotel booking details."""
    booking_id: Optional[str] = None
    hotel_name: str
    location: Location
    check_in: datetime
    check_out: datetime
    room_type: str
    guests: int
    cost_per_night: float
    total_cost: float
    currency: str = "USD"
    amenities: List[str] = Field(default_factory=list)
    cancellation_policy: str
    confirmation_number: Optional[str] = None
    status: BookingStatus = BookingStatus.PENDING
    rating: Optional[float] = None
    images: List[str] = Field(default_factory=list)


class TransportBooking(BaseModel):
    """Transport booking details."""
    booking_id: Optional[str] = None
    mode: TravelMode
    carrier: str
    departure_time: datetime
    arrival_time: datetime
    origin: str
    destination: str
    origin_location: Optional[Location] = None
    destination_location: Optional[Location] = None
    cost: float
    currency: str = "USD"
    booking_reference: Optional[str] = None
    seat_class: Optional[str] = None
    status: BookingStatus = BookingStatus.PENDING
    duration_minutes: Optional[int] = None
    stops: int = 0


class ActivityBooking(BaseModel):
    """Activity booking details."""
    booking_id: Optional[str] = None
    activity_name: str
    provider: str
    location: Location
    start_time: datetime
    end_time: datetime
    cost_per_person: float
    total_cost: float
    currency: str = "USD"
    participants: int
    description: str
    category: str
    confirmation_number: Optional[str] = None
    status: BookingStatus = BookingStatus.PENDING
    rating: Optional[float] = None
    cancellation_policy: Optional[str] = None


class BudgetStatus(BaseModel):
    """Current budget status."""
    total_budget: float
    spent: float
    allocated: float
    available: float
    currency: str = "USD"
    breakdown: Dict[str, float] = Field(default_factory=dict)
    
    @property
    def percentage_used(self) -> float:
        return (self.spent / self.total_budget) * 100 if self.total_budget > 0 else 0


class TravelItinerary(BaseModel):
    """Complete travel itinerary."""
    trip_id: str
    traveler_name: str
    destination: str
    start_date: datetime
    end_date: datetime
    total_cost: float
    currency: str = "USD"
    hotels: List[HotelBooking] = Field(default_factory=list)
    transport: List[TransportBooking] = Field(default_factory=list)
    activities: List[ActivityBooking] = Field(default_factory=list)
    budget_status: BudgetStatus
    notes: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AgentMessage(BaseModel):
    """Message exchanged between agents."""
    message_id: str
    sender: str
    recipient: str
    session_id: str
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    requires_response: bool = True
    priority: int = Field(default=5, ge=1, le=10)
    correlation_id: Optional[str] = None  # For tracking related messages


class ConflictInfo(BaseModel):
    """Information about a conflict between bookings."""
    conflict_type: str  # timing, location, budget, availability
    affected_agents: List[str]
    description: str
    suggested_resolutions: List[Dict[str, Any]]
    severity: int = Field(default=5, ge=1, le=10)


class HumanApprovalRequest(BaseModel):
    """Request for human approval."""
    request_id: str
    session_id: str
    reason: str
    context: Dict[str, Any]
    options: List[Dict[str, Any]]
    timeout_seconds: int = 300
    created_at: datetime = Field(default_factory=datetime.now)
    resolved: bool = False
    resolution: Optional[Dict[str, Any]] = None