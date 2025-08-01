"""
Tools for the Hotel Agent.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import random
import logging

from ...shared.utils import calculate_distance, rank_options


logger = logging.getLogger(__name__)


class HotelSearchAPI:
    """Mock hotel search API for development."""
    
    def __init__(self, api_config: Dict[str, Any]):
        self.api_key = api_config.get("api_key", "mock_key")
        self.base_url = api_config.get("base_url", "https://api.hotels.mock")
        
        # Mock hotel data for demonstration
        self.mock_hotels = {
            "New York": [
                {
                    "name": "The Plaza Hotel",
                    "latitude": 40.7644,
                    "longitude": -73.9745,
                    "address": "768 5th Ave, New York, NY 10019",
                    "price_per_night": 450,
                    "rating": 4.7,
                    "amenities": ["WiFi", "Spa", "Gym", "Restaurant", "Bar"],
                    "room_types": ["Deluxe Room", "Suite", "Presidential Suite"],
                    "cancellation_policy": "Free cancellation up to 24 hours"
                },
                {
                    "name": "Hilton Times Square",
                    "latitude": 40.7628,
                    "longitude": -73.9857,
                    "address": "234 W 42nd St, New York, NY 10036",
                    "price_per_night": 280,
                    "rating": 4.3,
                    "amenities": ["WiFi", "Gym", "Restaurant", "Business Center"],
                    "room_types": ["Standard Room", "Executive Room"],
                    "cancellation_policy": "Free cancellation up to 48 hours"
                },
                {
                    "name": "Pod Times Square",
                    "latitude": 40.7614,
                    "longitude": -73.9866,
                    "address": "400 W 42nd St, New York, NY 10036",
                    "price_per_night": 150,
                    "rating": 4.1,
                    "amenities": ["WiFi", "Rooftop Bar"],
                    "room_types": ["Pod Room", "Bunk Pod"],
                    "cancellation_policy": "Non-refundable"
                }
            ],
            "Paris": [
                {
                    "name": "Four Seasons Hotel George V",
                    "latitude": 48.8689,
                    "longitude": 2.3008,
                    "address": "31 Av. George V, 75008 Paris",
                    "price_per_night": 850,
                    "rating": 4.9,
                    "amenities": ["WiFi", "Spa", "Gym", "Michelin Restaurant", "Concierge"],
                    "room_types": ["Superior Room", "Deluxe Suite", "Penthouse"],
                    "cancellation_policy": "Free cancellation up to 7 days"
                },
                {
                    "name": "Hotel des Grands Boulevards",
                    "latitude": 48.8715,
                    "longitude": 2.3437,
                    "address": "17 Bd Poissonnière, 75002 Paris",
                    "price_per_night": 220,
                    "rating": 4.5,
                    "amenities": ["WiFi", "Restaurant", "Bar", "Room Service"],
                    "room_types": ["Cosy Room", "Deluxe Room"],
                    "cancellation_policy": "Free cancellation up to 48 hours"
                }
            ],
            "Tokyo": [
                {
                    "name": "Park Hyatt Tokyo",
                    "latitude": 35.6857,
                    "longitude": 139.6907,
                    "address": "3-7-1-2 Nishi Shinjuku, Tokyo",
                    "price_per_night": 600,
                    "rating": 4.8,
                    "amenities": ["WiFi", "Spa", "Pool", "Gym", "Multiple Restaurants"],
                    "room_types": ["Park Room", "View Room", "Suite"],
                    "cancellation_policy": "Free cancellation up to 24 hours"
                },
                {
                    "name": "Hotel Gracery Shinjuku",
                    "latitude": 35.6951,
                    "longitude": 139.7029,
                    "address": "1-19-1 Kabukicho, Shinjuku, Tokyo",
                    "price_per_night": 180,
                    "rating": 4.2,
                    "amenities": ["WiFi", "Restaurant", "Godzilla View"],
                    "room_types": ["Standard Room", "Godzilla Room"],
                    "cancellation_policy": "Free cancellation up to 24 hours"
                }
            ]
        }
    
    async def search(self, destination: str, check_in: datetime, check_out: datetime,
                    guests: int, max_price: float, min_rating: float = 3.0,
                    amenities: List[str] = None) -> List[Dict[str, Any]]:
        """Search for hotels."""
        # Simulate API delay
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Get base hotels for destination
        city_key = None
        for key in self.mock_hotels.keys():
            if key.lower() in destination.lower():
                city_key = key
                break
        
        if not city_key:
            # Return generic hotels for unknown destinations
            city_key = "New York"
        
        hotels = self.mock_hotels[city_key].copy()
        
        # Calculate total price and filter
        nights = (check_out - check_in).days
        results = []
        
        for hotel in hotels:
            # Add some price variation
            price_variation = random.uniform(0.9, 1.1)
            price_per_night = hotel["price_per_night"] * price_variation
            
            # Apply filters
            if price_per_night > max_price:
                continue
            if hotel["rating"] < min_rating:
                continue
            
            # Check amenities if specified
            if amenities:
                hotel_amenities = set(hotel["amenities"])
                required_amenities = set(amenities)
                if not required_amenities.issubset(hotel_amenities):
                    continue
            
            # Create result
            result = hotel.copy()
            result["price_per_night"] = round(price_per_night, 2)
            result["total_price"] = round(price_per_night * nights, 2)
            result["available_rooms"] = random.randint(1, 10)
            result["room_type"] = random.choice(hotel["room_types"])
            
            results.append(result)
        
        return results


class HotelRanker:
    """Ranks hotels based on user preferences."""
    
    def __init__(self):
        self.default_weights = {
            "price": 0.3,
            "rating": 0.25,
            "location": 0.25,
            "amenities": 0.15,
            "cancellation": 0.05
        }
    
    async def rank_hotels(self, hotels: List[Dict[str, Any]], 
                         preferences: Dict[str, Any],
                         budget: float) -> List[Dict[str, Any]]:
        """Rank hotels based on multiple criteria."""
        
        # Score each hotel
        scored_hotels = []
        
        for hotel in hotels:
            scores = {}
            
            # Price score (lower is better, normalized)
            price_ratio = hotel["total_price"] / budget if budget > 0 else 1
            scores["price"] = max(0, 1 - price_ratio)
            
            # Rating score (normalized to 0-1)
            scores["rating"] = hotel["rating"] / 5.0
            
            # Location score (would use real distance calculation)
            # For now, use a random score
            scores["location"] = random.uniform(0.6, 1.0)
            
            # Amenities score
            desired_amenities = set(preferences.get("amenities", []))
            hotel_amenities = set(hotel.get("amenities", []))
            if desired_amenities:
                amenity_match = len(desired_amenities & hotel_amenities) / len(desired_amenities)
                scores["amenities"] = amenity_match
            else:
                scores["amenities"] = 0.5
            
            # Cancellation policy score
            if "free cancellation" in hotel.get("cancellation_policy", "").lower():
                scores["cancellation"] = 1.0
            else:
                scores["cancellation"] = 0.3
            
            # Calculate weighted score
            total_score = sum(
                scores[criterion] * self.default_weights[criterion]
                for criterion in self.default_weights
            )
            
            hotel_copy = hotel.copy()
            hotel_copy["_score"] = total_score
            hotel_copy["_scores"] = scores
            scored_hotels.append(hotel_copy)
        
        # Sort by score
        return sorted(scored_hotels, key=lambda h: h["_score"], reverse=True)


class HotelValidator:
    """Validates hotel bookings and availability."""
    
    @staticmethod
    async def validate_availability(hotel: Dict[str, Any], 
                                  check_in: datetime,
                                  check_out: datetime,
                                  guests: int) -> tuple[bool, Optional[str]]:
        """Validate if hotel is available for dates."""
        # Simulate availability check
        await asyncio.sleep(0.2)
        
        # Random availability for demonstration
        if random.random() > 0.9:  # 10% chance of unavailable
            return False, "No rooms available for selected dates"
        
        if hotel.get("available_rooms", 1) < 1:
            return False, "All rooms are booked"
        
        # Check guest capacity (assume 2 per room max)
        rooms_needed = (guests + 1) // 2
        if rooms_needed > hotel.get("available_rooms", 1):
            return False, f"Not enough rooms available. Need {rooms_needed} rooms."
        
        return True, None
    
    @staticmethod
    def validate_checkin_time(hotel_checkin: str, arrival_time: datetime) -> tuple[bool, Optional[str]]:
        """Validate if check-in time works with arrival."""
        # Standard check-in is usually 3 PM
        standard_checkin_hour = 15
        
        if arrival_time.hour > standard_checkin_hour + 6:  # After 9 PM
            return False, "Arrival too late for standard check-in"
        
        return True, None