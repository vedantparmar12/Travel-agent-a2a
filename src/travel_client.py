"""
Client for interacting with the A2A Travel Agent System.
"""
import asyncio
import httpx
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

from a2a.client import A2AClient, A2ACardResolver
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from dotenv import load_dotenv


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TravelPlannerClient:
    """Client for the travel planning system."""
    
    def __init__(self, orchestrator_url: str = "http://localhost:10001"):
        self.orchestrator_url = orchestrator_url
        self.client = None
        self.agent_card = None
        self.connected = False
    
    async def connect(self):
        """Connect to the orchestrator agent."""
        try:
            self.client = httpx.AsyncClient(timeout=60)
            
            # Get the orchestrator's agent card
            card_resolver = A2ACardResolver(self.client, self.orchestrator_url)
            self.agent_card = await card_resolver.get_agent_card()
            
            self.connected = True
            logger.info(f"Connected to {self.agent_card.info.name}")
            logger.info(f"Description: {self.agent_card.info.description}")
            
        except Exception as e:
            logger.error(f"Failed to connect to orchestrator: {e}")
            raise
    
    async def plan_trip(self, request: str) -> Dict[str, Any]:
        """Send a trip planning request to the orchestrator."""
        if not self.connected:
            await self.connect()
        
        # Create A2A client
        a2a_client = A2AClient(self.client, self.agent_card, url=self.orchestrator_url)
        
        # Create message
        message_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        
        payload = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": request}],
                "messageId": message_id,
                "taskId": task_id,
                "contextId": context_id,
            },
        }
        
        message_request = SendMessageRequest(
            id=message_id,
            params=MessageSendParams.model_validate(payload)
        )
        
        try:
            # Send request
            logger.info("Sending trip planning request...")
            response: SendMessageResponse = await a2a_client.send_message(message_request)
            
            # Process response
            if isinstance(response.root, SendMessageSuccessResponse) and isinstance(response.root.result, Task):
                # Extract result
                result = {
                    "status": response.root.result.status,
                    "task_id": response.root.result.id,
                    "content": []
                }
                
                # Extract artifacts
                if response.root.result.artifacts:
                    for artifact in response.root.result.artifacts:
                        if hasattr(artifact.artifact, 'parts'):
                            for part in artifact.artifact.parts:
                                if hasattr(part, 'text'):
                                    result["content"].append(part.text)
                
                return result
            else:
                return {"error": "Invalid response from orchestrator"}
                
        except Exception as e:
            logger.error(f"Error planning trip: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """Close the client connection."""
        if self.client:
            await self.client.aclose()
            self.connected = False


async def interactive_trip_planning():
    """Interactive trip planning session."""
    client = TravelPlannerClient()
    
    try:
        print("\n" + "="*60)
        print("TRAVEL PLANNER - A2A CLIENT")
        print("="*60)
        
        await client.connect()
        
        print("\nWelcome to the Travel Planning System!")
        print("I'll help you plan your perfect trip.\n")
        
        # Get trip details
        destination = input("Where would you like to go? ")
        origin = input("Where are you traveling from? ")
        
        # Get dates
        days_ahead = input("How many days from now do you want to travel? (default: 30) ") or "30"
        trip_length = input("How many days is your trip? (default: 5) ") or "5"
        
        start_date = datetime.now() + timedelta(days=int(days_ahead))
        end_date = start_date + timedelta(days=int(trip_length))
        
        budget = input("What's your total budget (USD)? ")
        travelers = input("How many travelers? (default: 2) ") or "2"
        
        # Optional preferences
        print("\nOptional preferences (press Enter to skip):")
        hotel_rating = input("Minimum hotel rating (1-5)? ") or ""
        special_requests = input("Any special requests or preferences? ") or ""
        
        # Construct request
        request = f"""Plan a trip with these details:
- Destination: {destination}
- Origin: {origin}
- Dates: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}
- Budget: ${budget} USD
- Travelers: {travelers}"""
        
        if hotel_rating:
            request += f"\n- Minimum hotel rating: {hotel_rating}/5"
        if special_requests:
            request += f"\n- Special requests: {special_requests}"
        
        print("\n" + "-"*60)
        print("Planning your trip...")
        print("-"*60)
        
        # Send request
        result = await client.plan_trip(request)
        
        # Display result
        if "error" in result:
            print(f"\n❌ Error: {result['error']}")
        else:
            print(f"\n✓ Status: {result['status']}")
            if result.get("content"):
                print("\n" + "\n".join(result["content"]))
        
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await client.close()


async def quick_trip_example():
    """Quick example trip planning."""
    client = TravelPlannerClient()
    
    try:
        await client.connect()
        
        # Example trip
        request = """Plan a trip with these details:
- Destination: Paris, France
- Origin: New York, USA
- Dates: 2024-06-15 to 2024-06-20
- Budget: $3000 USD
- Travelers: 2
- Minimum hotel rating: 4/5
- Special requests: Near Eiffel Tower, romantic atmosphere"""
        
        print("\n" + "="*60)
        print("PLANNING EXAMPLE TRIP TO PARIS")
        print("="*60)
        print(request)
        print("\nProcessing...\n")
        
        result = await client.plan_trip(request)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✓ Status: {result['status']}")
            if result.get("content"):
                print("\n" + "\n".join(result["content"]))
                
    finally:
        await client.close()


def main():
    """Main entry point."""
    import sys
    
    print("\n" + "="*60)
    print("TRAVEL PLANNER CLIENT")
    print("="*60)
    print("\nOptions:")
    print("1. Interactive trip planning")
    print("2. Quick example (Paris trip)")
    print("0. Exit")
    
    choice = input("\nSelect option: ")
    
    if choice == "1":
        asyncio.run(interactive_trip_planning())
    elif choice == "2":
        asyncio.run(quick_trip_example())
    else:
        print("Goodbye!")


if __name__ == "__main__":
    main()