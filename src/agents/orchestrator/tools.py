"""
Tools for the Orchestrator Agent.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from ...shared.models import TravelPreferences, ConflictInfo


logger = logging.getLogger(__name__)


class TaskAnalyzer:
    """Analyzes travel requests and creates task assignments."""
    
    def __init__(self):
        self.budget_allocations = {
            "hotel": 0.35,      # 35% of budget
            "transport": 0.30,  # 30% of budget
            "activities": 0.20, # 20% of budget
            "buffer": 0.15      # 15% buffer
        }
    
    async def analyze_request(self, preferences: TravelPreferences,
                            total_budget: float, spent: float,
                            available: float) -> Dict[str, Any]:
        """Analyze travel request and create budget allocations."""
        
        # Calculate trip duration
        trip_days = (preferences.end_date - preferences.start_date).days
        
        # Allocate budget based on percentages
        allocations = {
            "hotel_budget": available * self.budget_allocations["hotel"],
            "transport_budget": available * self.budget_allocations["transport"],
            "activities_budget": available * self.budget_allocations["activities"],
            "buffer": available * self.budget_allocations["buffer"]
        }
        
        # Adjust based on trip characteristics
        if trip_days > 7:  # Longer trips need more hotel budget
            allocations["hotel_budget"] *= 1.1
            allocations["activities_budget"] *= 0.9
        
        if preferences.travelers > 2:  # Groups need different allocations
            allocations["transport_budget"] *= 1.15
            allocations["hotel_budget"] *= 0.95
        
        # Identify priorities based on preferences
        priorities = self._determine_priorities(preferences)
        
        # Create dependency graph
        dependencies = {
            "hotel": [],  # No dependencies
            "transport": [],  # No dependencies
            "activity": ["hotel"],  # Depends on hotel location
            "itinerary": ["hotel", "transport", "activity"]  # Depends on all
        }
        
        return {
            "allocations": allocations,
            "priorities": priorities,
            "dependencies": dependencies,
            "trip_characteristics": {
                "duration_days": trip_days,
                "group_size": preferences.travelers,
                "destination_type": self._classify_destination(preferences.destination)
            }
        }
    
    def _determine_priorities(self, preferences: TravelPreferences) -> List[str]:
        """Determine booking priorities based on preferences."""
        priorities = []
        
        # Always prioritize accommodation
        priorities.append("hotel")
        
        # Transport priority based on distance/international
        if self._is_international(preferences.origin, preferences.destination):
            priorities.append("transport")
        
        # Activities based on preferences
        if preferences.activity_preferences:
            priorities.append("activities")
        
        priorities.append("itinerary")
        
        return priorities
    
    def _is_international(self, origin: str, destination: str) -> bool:
        """Simple check if travel is international."""
        # In a real implementation, this would use geocoding
        # For now, simple heuristic
        return origin.lower().split(",")[-1].strip() != destination.lower().split(",")[-1].strip()
    
    def _classify_destination(self, destination: str) -> str:
        """Classify destination type."""
        destination_lower = destination.lower()
        
        if any(city in destination_lower for city in ["paris", "london", "tokyo", "new york"]):
            return "major_city"
        elif any(beach in destination_lower for beach in ["beach", "coast", "island"]):
            return "beach"
        elif any(nature in destination_lower for nature in ["mountain", "park", "forest"]):
            return "nature"
        else:
            return "general"


class ConflictResolver:
    """Resolves conflicts between agent bookings."""
    
    def __init__(self):
        self.resolution_strategies = {
            "timing": self._resolve_timing_conflict,
            "budget": self._resolve_budget_conflict,
            "availability": self._resolve_availability_conflict,
            "location": self._resolve_location_conflict
        }
    
    async def resolve_conflict(self, conflict: ConflictInfo,
                             current_bookings: Dict[str, List[Dict[str, Any]]],
                             preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to resolve a conflict automatically."""
        
        strategy = self.resolution_strategies.get(
            conflict.conflict_type,
            self._default_resolution
        )
        
        resolution = await strategy(conflict, current_bookings, preferences)
        
        return {
            "can_resolve_automatically": resolution["can_resolve"],
            "instructions": resolution.get("instructions", {}),
            "summary": resolution.get("summary", ""),
            "requires_human": not resolution["can_resolve"]
        }
    
    async def _resolve_timing_conflict(self, conflict: ConflictInfo,
                                     bookings: Dict[str, List[Dict[str, Any]]],
                                     preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve timing conflicts between bookings."""
        
        # Example: Flight arrives after hotel check-in time
        if "late_arrival" in conflict.description.lower():
            return {
                "can_resolve": True,
                "instructions": {
                    "hotel": {
                        "action": "request_late_checkin",
                        "arrival_time": conflict.suggested_resolutions[0].get("arrival_time")
                    }
                },
                "summary": "Requesting late check-in from hotel"
            }
        
        # Example: Activity overlaps with transport
        if "overlap" in conflict.description.lower():
            return {
                "can_resolve": True,
                "instructions": {
                    "activity": {
                        "action": "reschedule",
                        "new_time": conflict.suggested_resolutions[0].get("alternative_time")
                    }
                },
                "summary": "Rescheduling activity to avoid overlap"
            }
        
        return {
            "can_resolve": False,
            "summary": "Cannot automatically resolve timing conflict"
        }
    
    async def _resolve_budget_conflict(self, conflict: ConflictInfo,
                                     bookings: Dict[str, List[Dict[str, Any]]],
                                     preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve budget conflicts."""
        
        # Try to find cheaper alternatives
        affected_agent = conflict.affected_agents[0]
        
        return {
            "can_resolve": True,
            "instructions": {
                affected_agent: {
                    "action": "find_cheaper_alternative",
                    "max_budget": conflict.suggested_resolutions[0].get("reduced_budget")
                }
            },
            "summary": f"Requesting cheaper options from {affected_agent}"
        }
    
    async def _resolve_availability_conflict(self, conflict: ConflictInfo,
                                           bookings: Dict[str, List[Dict[str, Any]]],
                                           preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve availability conflicts."""
        
        # Try alternative dates or options
        return {
            "can_resolve": True,
            "instructions": {
                conflict.affected_agents[0]: {
                    "action": "find_alternative",
                    "constraints": conflict.suggested_resolutions[0]
                }
            },
            "summary": "Searching for alternative options"
        }
    
    async def _resolve_location_conflict(self, conflict: ConflictInfo,
                                        bookings: Dict[str, List[Dict[str, Any]]],
                                        preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve location conflicts."""
        
        # Example: Activity too far from hotel
        if "distance" in conflict.description.lower():
            return {
                "can_resolve": True,
                "instructions": {
                    "activity": {
                        "action": "find_closer_alternative",
                        "max_distance_km": 10
                    }
                },
                "summary": "Finding activities closer to accommodation"
            }
        
        return {
            "can_resolve": False,
            "summary": "Cannot automatically resolve location conflict"
        }
    
    async def _default_resolution(self, conflict: ConflictInfo,
                                bookings: Dict[str, List[Dict[str, Any]]],
                                preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Default resolution when no specific strategy exists."""
        return {
            "can_resolve": False,
            "summary": f"No automatic resolution available for {conflict.conflict_type}"
        }


class DependencyManager:
    """Manages dependencies between agent tasks."""
    
    def __init__(self):
        self.dependency_graph = {
            "hotel": set(),
            "transport": set(),
            "activity": {"hotel"},  # Activities depend on hotel location
            "budget": set(),  # Budget monitors all
            "itinerary": {"hotel", "transport", "activity"}  # Itinerary needs all bookings
        }
    
    def get_ready_agents(self, completed_agents: set) -> List[str]:
        """Get agents that are ready to execute based on completed dependencies."""
        ready = []
        
        for agent, dependencies in self.dependency_graph.items():
            if agent not in completed_agents:
                if dependencies.issubset(completed_agents):
                    ready.append(agent)
        
        return ready
    
    def get_execution_order(self) -> List[List[str]]:
        """Get the execution order respecting dependencies."""
        # Topological sort
        visited = set()
        order = []
        
        def visit(agent):
            if agent in visited:
                return
            visited.add(agent)
            for dep in self.dependency_graph.get(agent, set()):
                visit(dep)
            order.append(agent)
        
        for agent in self.dependency_graph:
            visit(agent)
        
        # Group by levels (agents that can run in parallel)
        levels = []
        placed = set()
        
        while placed != set(order):
            level = []
            for agent in order:
                if agent not in placed:
                    deps = self.dependency_graph.get(agent, set())
                    if deps.issubset(placed):
                        level.append(agent)
            levels.append(level)
            placed.update(level)
        
        return levels
    
    def validate_completion_order(self, completion_order: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate that agents completed in valid order."""
        completed = set()
        
        for agent in completion_order:
            deps = self.dependency_graph.get(agent, set())
            if not deps.issubset(completed):
                missing = deps - completed
                return False, f"{agent} completed before dependencies: {missing}"
            completed.add(agent)
        
        return True, None