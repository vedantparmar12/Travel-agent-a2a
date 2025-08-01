"""
Utility functions for the travel agent system.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import logging
import asyncio
from functools import wraps
import aiohttp
import json
from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)


def calculate_duration(start: datetime, end: datetime) -> int:
    """Calculate duration in minutes between two datetimes."""
    duration = end - start
    return int(duration.total_seconds() / 60)


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency string."""
    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "INR": "₹"
    }
    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"


def parse_date_flexible(date_string: str) -> datetime:
    """Parse date string with multiple format support."""
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse date: {date_string}")


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates in kilometers."""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


def is_within_budget(current_spent: float, new_cost: float, budget_limit: float, 
                    buffer_percentage: float = 0.1) -> Tuple[bool, float]:
    """Check if a new cost is within budget with optional buffer."""
    buffer = budget_limit * buffer_percentage
    effective_limit = budget_limit - buffer
    
    if current_spent + new_cost <= effective_limit:
        return True, budget_limit - current_spent - new_cost
    return False, budget_limit - current_spent


def rank_options(options: List[Dict[str, Any]], criteria: Dict[str, float]) -> List[Dict[str, Any]]:
    """Rank options based on weighted criteria."""
    scored_options = []
    
    for option in options:
        score = 0
        for criterion, weight in criteria.items():
            if criterion in option:
                # Normalize value (assumes higher is better)
                value = option[criterion]
                if isinstance(value, (int, float)):
                    score += value * weight
        
        option["_score"] = score
        scored_options.append(option)
    
    # Sort by score descending
    return sorted(scored_options, key=lambda x: x.get("_score", 0), reverse=True)


def extract_booking_window(preferences: Dict[str, Any]) -> Tuple[datetime, datetime]:
    """Extract check-in/check-out or departure/arrival times from preferences."""
    if "start_date" in preferences and "end_date" in preferences:
        start = preferences["start_date"]
        end = preferences["end_date"]
        
        if isinstance(start, str):
            start = parse_date_flexible(start)
        if isinstance(end, str):
            end = parse_date_flexible(end)
        
        return start, end
    
    raise ValueError("Missing start_date or end_date in preferences")


def validate_booking_dates(bookings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate that booking dates don't conflict."""
    conflicts = []
    
    for i, booking1 in enumerate(bookings):
        for j, booking2 in enumerate(bookings[i+1:], i+1):
            # Check if dates overlap
            start1 = booking1.get("start_time", booking1.get("check_in", booking1.get("departure_time")))
            end1 = booking1.get("end_time", booking1.get("check_out", booking1.get("arrival_time")))
            start2 = booking2.get("start_time", booking2.get("check_in", booking2.get("departure_time")))
            end2 = booking2.get("end_time", booking2.get("check_out", booking2.get("arrival_time")))
            
            if start1 and end1 and start2 and end2:
                if isinstance(start1, str):
                    start1 = parse_date_flexible(start1)
                if isinstance(end1, str):
                    end1 = parse_date_flexible(end1)
                if isinstance(start2, str):
                    start2 = parse_date_flexible(start2)
                if isinstance(end2, str):
                    end2 = parse_date_flexible(end2)
                
                # Check for overlap
                if start1 < end2 and start2 < end1:
                    conflicts.append({
                        "booking1": booking1.get("name", f"Booking {i}"),
                        "booking2": booking2.get("name", f"Booking {j}"),
                        "overlap_start": max(start1, start2).isoformat(),
                        "overlap_end": min(end1, end2).isoformat()
                    })
    
    return conflicts


class AsyncRetry:
    """Decorator for async functions with retry logic."""
    
    def __init__(self, max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
    
    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = self.delay
            
            for attempt in range(self.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_attempts - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        delay *= self.backoff
                    else:
                        logger.error(f"All {self.max_attempts} attempts failed")
            
            raise last_exception
        
        return wrapper


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_with_retry(session: aiohttp.ClientSession, url: str, 
                          method: str = "GET", **kwargs) -> Dict[str, Any]:
    """Fetch URL with retry logic."""
    async with session.request(method, url, **kwargs) as response:
        response.raise_for_status()
        return await response.json()


async def parallel_fetch(urls: List[str], headers: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Fetch multiple URLs in parallel."""
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [fetch_with_retry(session, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {urls[i]}: {result}")
                valid_results.append(None)
            else:
                valid_results.append(result)
        
        return valid_results


def create_calendar_event(booking: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """Create a calendar event from a booking."""
    event = {
        "type": event_type,
        "summary": booking.get("name", f"{event_type} Booking"),
        "location": None,
        "start": None,
        "end": None,
        "description": ""
    }
    
    # Extract times based on booking type
    if event_type == "hotel":
        event["start"] = booking.get("check_in")
        event["end"] = booking.get("check_out")
        event["location"] = booking.get("hotel_name")
        event["description"] = f"Confirmation: {booking.get('confirmation_number', 'N/A')}"
    
    elif event_type == "transport":
        event["start"] = booking.get("departure_time")
        event["end"] = booking.get("arrival_time")
        event["summary"] = f"{booking.get('mode', 'Transport')}: {booking.get('origin')} to {booking.get('destination')}"
        event["description"] = f"Carrier: {booking.get('carrier', 'N/A')}\nReference: {booking.get('booking_reference', 'N/A')}"
    
    elif event_type == "activity":
        event["start"] = booking.get("start_time")
        event["end"] = booking.get("end_time")
        event["location"] = booking.get("activity_name")
        event["description"] = f"{booking.get('description', '')}\nConfirmation: {booking.get('confirmation_number', 'N/A')}"
    
    return event


def generate_booking_summary(bookings: Dict[str, List[Dict[str, Any]]]) -> str:
    """Generate a text summary of all bookings."""
    summary_lines = ["Travel Booking Summary", "=" * 50, ""]
    
    # Hotels
    if bookings.get("hotels"):
        summary_lines.append("ACCOMMODATIONS:")
        for hotel in bookings["hotels"]:
            summary_lines.append(f"  • {hotel.get('hotel_name', 'Hotel')}")
            summary_lines.append(f"    Check-in: {hotel.get('check_in', 'N/A')}")
            summary_lines.append(f"    Check-out: {hotel.get('check_out', 'N/A')}")
            summary_lines.append(f"    Cost: {format_currency(hotel.get('total_cost', 0))}")
            summary_lines.append("")
    
    # Transport
    if bookings.get("transport"):
        summary_lines.append("TRANSPORTATION:")
        for transport in bookings["transport"]:
            summary_lines.append(f"  • {transport.get('mode', 'Transport').title()}: {transport.get('origin')} → {transport.get('destination')}")
            summary_lines.append(f"    Departure: {transport.get('departure_time', 'N/A')}")
            summary_lines.append(f"    Arrival: {transport.get('arrival_time', 'N/A')}")
            summary_lines.append(f"    Cost: {format_currency(transport.get('cost', 0))}")
            summary_lines.append("")
    
    # Activities
    if bookings.get("activities"):
        summary_lines.append("ACTIVITIES:")
        for activity in bookings["activities"]:
            summary_lines.append(f"  • {activity.get('activity_name', 'Activity')}")
            summary_lines.append(f"    Date: {activity.get('start_time', 'N/A')}")
            summary_lines.append(f"    Duration: {calculate_duration(activity.get('start_time'), activity.get('end_time'))} minutes")
            summary_lines.append(f"    Cost: {format_currency(activity.get('total_cost', 0))}")
            summary_lines.append("")
    
    # Total cost
    total_cost = sum(
        booking.get("total_cost", booking.get("cost", 0))
        for booking_list in bookings.values()
        for booking in booking_list
    )
    summary_lines.append("=" * 50)
    summary_lines.append(f"TOTAL COST: {format_currency(total_cost)}")
    
    return "\n".join(summary_lines)