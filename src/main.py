"""
Main entry point for the Travel Agent System.
"""
import asyncio
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import uuid

from shared.state import StateManager
from shared.protocols import MessageRouter, MessageBuilder
from shared.models import TravelPreferences, MessageType
from agents.orchestrator.agent import OrchestratorAgent
from agents.hotel.agent import HotelAgent


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TravelAgentSystem:
    """Main system orchestrating all agents."""
    
    def __init__(self):
        self.state_manager = StateManager()
        self.message_router = MessageRouter()
        self.agents = {}
        self.running = False
        
    async def initialize(self):
        """Initialize all agents and systems."""
        logger.info("Initializing Travel Agent System...")
        
        # Initialize agents
        self.agents['orchestrator'] = OrchestratorAgent(
            self.state_manager, 
            self.message_router
        )
        
        # Hotel agent with mock API config
        hotel_api_config = {
            "api_key": os.getenv("BOOKING_API_KEY", "mock_key"),
            "base_url": "https://api.hotels.mock"
        }
        self.agents['hotel'] = HotelAgent(
            self.state_manager,
            self.message_router,
            hotel_api_config
        )
        
        # Note: In a complete implementation, you would initialize all agents here:
        # - TransportAgent
        # - ActivityAgent  
        # - BudgetAgent
        # - ItineraryAgent
        
        # Start all agents
        for agent_name, agent in self.agents.items():
            agent.start()
            logger.info(f"Started {agent_name} agent")
        
        self.running = True
        logger.info("Travel Agent System initialized successfully")
    
    async def plan_trip(self, preferences: TravelPreferences) -> str:
        """Plan a trip based on user preferences."""
        # Create new session
        session_id = await self.state_manager.create_session(preferences)
        logger.info(f"Created session {session_id} for trip planning")
        
        # Create initial task assignment message
        task_message = MessageBuilder.create_task_assignment(
            sender="system",
            recipient="orchestrator",
            session_id=session_id,
            task_details={
                "action": "plan_trip",
                "preferences": preferences.dict()
            }
        )
        
        # Send to orchestrator to start the process
        await self.message_router.send_message(task_message)
        
        return session_id
    
    async def get_trip_status(self, session_id: str) -> dict:
        """Get current status of trip planning."""
        state = await self.state_manager.get_state(session_id)
        if not state:
            return {"error": "Session not found"}
        
        return {
            "session_id": session_id,
            "status": state["status"],
            "bookings": state["bookings"],
            "budget_spent": state["budget_spent"],
            "agent_status": state["agent_status"],
            "human_approval_needed": state["human_approval_needed"]
        }
    
    async def shutdown(self):
        """Shutdown all agents and systems."""
        logger.info("Shutting down Travel Agent System...")
        self.running = False
        
        # Stop all agents
        for agent_name, agent in self.agents.items():
            await agent.stop()
            logger.info(f"Stopped {agent_name} agent")
        
        logger.info("Travel Agent System shutdown complete")


async def example_trip_planning():
    """Example of planning a trip."""
    system = TravelAgentSystem()
    
    try:
        # Initialize system
        await system.initialize()
        
        # Create travel preferences
        preferences = TravelPreferences(
            destination="New York, USA",
            origin="San Francisco, USA",
            start_date=datetime.now() + timedelta(days=30),
            end_date=datetime.now() + timedelta(days=37),
            budget=3000.0,
            currency="USD",
            travelers=2,
            preferred_hotel_rating=4,
            activity_preferences=["museums", "theater", "restaurants"],
            dietary_restrictions=["vegetarian"]
        )
        
        # Start trip planning
        session_id = await system.plan_trip(preferences)
        print(f"Trip planning started. Session ID: {session_id}")
        
        # Monitor progress
        for i in range(30):  # Check for 30 seconds
            await asyncio.sleep(1)
            status = await system.get_trip_status(session_id)
            
            print(f"\nStatus Update {i+1}:")
            print(f"  Overall Status: {status['status']}")
            print(f"  Budget Spent: ${status['budget_spent']:.2f}")
            print(f"  Agent Status: {status['agent_status']}")
            
            if status['status'] in ['completed', 'failed']:
                break
            
            if status['human_approval_needed']:
                print("  ⚠️  Human approval required!")
                # In a real system, this would trigger UI for human input
                break
        
        # Final status
        final_status = await system.get_trip_status(session_id)
        print("\n" + "="*50)
        print("FINAL TRIP STATUS")
        print("="*50)
        print(f"Status: {final_status['status']}")
        print(f"Total Spent: ${final_status['budget_spent']:.2f}")
        
        if final_status['bookings']['hotels']:
            print("\nHotel Bookings:")
            for hotel in final_status['bookings']['hotels']:
                print(f"  - {hotel['hotel_name']}")
                print(f"    Check-in: {hotel['check_in']}")
                print(f"    Check-out: {hotel['check_out']}")
                print(f"    Cost: ${hotel['total_cost']:.2f}")
        
    except Exception as e:
        logger.error(f"Error in trip planning: {e}")
        raise
    finally:
        await system.shutdown()


async def interactive_trip_planning():
    """Interactive trip planning with user input."""
    system = TravelAgentSystem()
    
    try:
        await system.initialize()
        
        print("Welcome to the Travel Agent System!")
        print("="*50)
        
        # Get user input
        destination = input("Where would you like to go? ")
        origin = input("Where are you traveling from? ")
        
        start_date_str = input("Start date (YYYY-MM-DD): ")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        
        end_date_str = input("End date (YYYY-MM-DD): ")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        
        budget = float(input("What's your budget (USD)? $"))
        travelers = int(input("How many travelers? "))
        
        # Create preferences
        preferences = TravelPreferences(
            destination=destination,
            origin=origin,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            currency="USD",
            travelers=travelers
        )
        
        # Start planning
        session_id = await system.plan_trip(preferences)
        print(f"\nPlanning your trip... (Session: {session_id})")
        
        # Monitor and display progress
        while True:
            await asyncio.sleep(2)
            status = await system.get_trip_status(session_id)
            
            print(f"\rStatus: {status['status']} | Budget Used: ${status['budget_spent']:.2f}", end="")
            
            if status['status'] in ['completed', 'failed']:
                print("\n\nTrip planning complete!")
                break
            
            if status['human_approval_needed']:
                print("\n\n⚠️  Your approval is needed for some decisions.")
                # Handle human input here
                break
        
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await system.shutdown()


if __name__ == "__main__":
    # Run example trip planning
    asyncio.run(example_trip_planning())
    
    # Or run interactive mode:
    # asyncio.run(interactive_trip_planning())