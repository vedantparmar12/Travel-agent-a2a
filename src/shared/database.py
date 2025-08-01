"""
Database models and persistence layer using SQLAlchemy.
"""
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
from contextlib import asynccontextmanager

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, DateTime, 
    Boolean, JSON, ForeignKey, Text, Enum as SQLEnum, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

from .models import BookingStatus, TravelMode, MessageType

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://travel_agent:password@localhost:5432/travel_agent_db")
# Convert to async URL if needed
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

Base = declarative_base()


# Database Models
class TripSession(Base):
    """Store trip planning sessions."""
    __tablename__ = "trip_sessions"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)
    status = Column(String, default="active")
    
    # Travel preferences
    destination = Column(String, nullable=False)
    origin = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    budget = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    travelers = Column(Integer, default=1)
    
    # Preferences as JSON
    preferences = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = relationship("Booking", back_populates="session", cascade="all, delete-orphan")
    messages = relationship("AgentMessageLog", back_populates="session", cascade="all, delete-orphan")
    budget_tracker = relationship("BudgetTracker", back_populates="session", uselist=False, cascade="all, delete-orphan")
    

class Booking(Base):
    """Store all types of bookings."""
    __tablename__ = "bookings"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("trip_sessions.id"))
    booking_type = Column(String, nullable=False)  # hotel, transport, activity
    
    # Common fields
    name = Column(String, nullable=False)
    confirmation_number = Column(String, nullable=True)
    status = Column(SQLEnum(BookingStatus), default=BookingStatus.PENDING)
    cost = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    
    # Booking details as JSON
    details = Column(JSON, nullable=False)
    
    # Timestamps
    booking_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("TripSession", back_populates="bookings")
    
    # Indexes
    __table_args__ = (
        Index('idx_session_type', 'session_id', 'booking_type'),
        Index('idx_booking_date', 'booking_date'),
    )


class AgentMessageLog(Base):
    """Log all agent communications."""
    __tablename__ = "agent_messages"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("trip_sessions.id"))
    
    sender = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    message_type = Column(SQLEnum(MessageType), nullable=False)
    
    # Message content
    content = Column(JSON, nullable=False)
    
    # Response tracking
    correlation_id = Column(String, nullable=True)
    response_to = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("TripSession", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index('idx_session_sender', 'session_id', 'sender'),
        Index('idx_correlation', 'correlation_id'),
    )


class BudgetTracker(Base):
    """Track budget for each session."""
    __tablename__ = "budget_trackers"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("trip_sessions.id"), unique=True)
    
    total_budget = Column(Float, nullable=False)
    spent = Column(Float, default=0.0)
    allocated = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    
    # Category breakdown
    hotel_spent = Column(Float, default=0.0)
    transport_spent = Column(Float, default=0.0)
    activity_spent = Column(Float, default=0.0)
    other_spent = Column(Float, default=0.0)
    
    # Alerts
    budget_warnings = Column(JSON, default=[])
    
    # Timestamps
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("TripSession", back_populates="budget_tracker")


class ConflictLog(Base):
    """Log conflicts and resolutions."""
    __tablename__ = "conflict_logs"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    
    conflict_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    affected_bookings = Column(JSON, default=[])
    
    resolution = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_session_conflicts', 'session_id', 'resolved'),
    )


# Database Manager
class DatabaseManager:
    """Manage database connections and operations."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or ASYNC_DATABASE_URL
        self.engine = None
        self.async_session = None
    
    async def initialize(self):
        """Initialize the database connection."""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            poolclass=NullPool,  # Disable connection pooling for async
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create tables if they don't exist
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
    
    @asynccontextmanager
    async def get_session(self):
        """Get a database session."""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    # Trip Session Operations
    async def create_trip_session(self, session_id: str, preferences: Dict[str, Any]) -> TripSession:
        """Create a new trip session."""
        async with self.get_session() as session:
            trip = TripSession(
                id=session_id,
                destination=preferences["destination"],
                origin=preferences["origin"],
                start_date=preferences["start_date"],
                end_date=preferences["end_date"],
                budget=preferences["budget"],
                currency=preferences.get("currency", "USD"),
                travelers=preferences.get("travelers", 1),
                preferences=preferences
            )
            session.add(trip)
            
            # Create budget tracker
            budget_tracker = BudgetTracker(
                id=f"budget-{session_id}",
                session_id=session_id,
                total_budget=preferences["budget"],
                currency=preferences.get("currency", "USD")
            )
            session.add(budget_tracker)
            
            await session.commit()
            return trip
    
    async def get_trip_session(self, session_id: str) -> Optional[TripSession]:
        """Get a trip session by ID."""
        async with self.get_session() as session:
            result = await session.get(TripSession, session_id)
            return result
    
    # Booking Operations
    async def create_booking(self, session_id: str, booking_data: Dict[str, Any]) -> Booking:
        """Create a new booking."""
        async with self.get_session() as session:
            booking = Booking(
                id=booking_data.get("id", f"booking-{datetime.utcnow().timestamp()}"),
                session_id=session_id,
                booking_type=booking_data["type"],
                name=booking_data["name"],
                confirmation_number=booking_data.get("confirmation_number"),
                status=BookingStatus(booking_data.get("status", "pending")),
                cost=booking_data["cost"],
                currency=booking_data.get("currency", "USD"),
                details=booking_data["details"],
                booking_date=booking_data.get("booking_date", datetime.utcnow())
            )
            session.add(booking)
            
            # Update budget tracker
            await self._update_budget_spent(session, session_id, booking_data["type"], booking_data["cost"])
            
            await session.commit()
            return booking
    
    async def update_booking_status(self, booking_id: str, status: BookingStatus):
        """Update booking status."""
        async with self.get_session() as session:
            booking = await session.get(Booking, booking_id)
            if booking:
                booking.status = status
                await session.commit()
    
    # Budget Operations
    async def _update_budget_spent(self, session: AsyncSession, session_id: str, category: str, amount: float):
        """Update budget spending."""
        tracker = await session.query(BudgetTracker).filter_by(session_id=session_id).first()
        if tracker:
            tracker.spent += amount
            
            if category == "hotel":
                tracker.hotel_spent += amount
            elif category == "transport":
                tracker.transport_spent += amount
            elif category == "activity":
                tracker.activity_spent += amount
            else:
                tracker.other_spent += amount
    
    async def get_budget_status(self, session_id: str) -> Optional[BudgetTracker]:
        """Get budget status for a session."""
        async with self.get_session() as session:
            tracker = await session.query(BudgetTracker).filter_by(session_id=session_id).first()
            return tracker
    
    # Message Logging
    async def log_message(self, message_data: Dict[str, Any]):
        """Log an agent message."""
        async with self.get_session() as session:
            message = AgentMessageLog(
                id=message_data["message_id"],
                session_id=message_data["session_id"],
                sender=message_data["sender"],
                recipient=message_data["recipient"],
                message_type=MessageType(message_data["message_type"]),
                content=message_data["content"],
                correlation_id=message_data.get("correlation_id"),
                response_to=message_data.get("response_to")
            )
            session.add(message)
            await session.commit()
    
    # Conflict Logging
    async def log_conflict(self, session_id: str, conflict_data: Dict[str, Any]):
        """Log a conflict."""
        async with self.get_session() as session:
            conflict = ConflictLog(
                id=f"conflict-{datetime.utcnow().timestamp()}",
                session_id=session_id,
                conflict_type=conflict_data["type"],
                description=conflict_data["description"],
                affected_bookings=conflict_data.get("affected_bookings", [])
            )
            session.add(conflict)
            await session.commit()
            return conflict


# Global database manager instance
db_manager = DatabaseManager()