"""
Sample trip planning scenarios for testing the Travel Agent System.
"""
import asyncio
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import TravelAgentSystem
from src.shared.models import TravelPreferences


async def romantic_paris_getaway():
    """Plan a romantic getaway to Paris."""
    print("🗼 Planning a Romantic Paris Getaway...")
    print("="*60)
    
    system = TravelAgentSystem()
    await system.initialize()
    
    preferences = TravelPreferences(
        destination="Paris, France",
        origin="New York, USA",
        start_date=datetime.now() + timedelta(days=60),
        end_date=datetime.now() + timedelta(days=65),
        budget=4000.0,
        currency="USD",
        travelers=2,
        preferred_hotel_rating=4,
        activity_preferences=["romantic dinner", "Eiffel Tower", "Seine cruise", "Louvre"],
        constraints=["Near city center", "Romantic atmosphere"]
    )
    
    session_id = await system.plan_trip(preferences)
    
    # Monitor progress
    await monitor_trip_progress(system, session_id, "Paris Getaway")
    
    await system.shutdown()


async def family_tokyo_adventure():
    """Plan a family adventure to Tokyo."""
    print("🗾 Planning a Family Tokyo Adventure...")
    print("="*60)
    
    system = TravelAgentSystem()
    await system.initialize()
    
    preferences = TravelPreferences(
        destination="Tokyo, Japan",
        origin="Los Angeles, USA",
        start_date=datetime.now() + timedelta(days=90),
        end_date=datetime.now() + timedelta(days=97),
        budget=8000.0,
        currency="USD",
        travelers=4,  # Family of 4
        preferred_hotel_rating=3,
        activity_preferences=["Disneyland", "temples", "sushi making", "robot restaurant"],
        constraints=["Family-friendly", "English-speaking staff preferred"]
    )
    
    session_id = await system.plan_trip(preferences)
    
    # Monitor progress
    await monitor_trip_progress(system, session_id, "Tokyo Adventure")
    
    await system.shutdown()


async def budget_backpacking_europe():
    """Plan a budget backpacking trip through Europe."""
    print("🎒 Planning a Budget Europe Backpacking Trip...")
    print("="*60)
    
    system = TravelAgentSystem()
    await system.initialize()
    
    # Note: Multi-city trips would need enhanced orchestrator logic
    preferences = TravelPreferences(
        destination="Amsterdam, Netherlands",  # Starting point
        origin="London, UK",
        start_date=datetime.now() + timedelta(days=30),
        end_date=datetime.now() + timedelta(days=35),
        budget=1000.0,  # Budget trip
        currency="EUR",
        travelers=1,
        preferred_hotel_rating=2,  # Hostels/budget hotels
        activity_preferences=["museums", "walking tours", "local food", "nightlife"],
        constraints=["Hostel preferred", "Public transport accessible"]
    )
    
    session_id = await system.plan_trip(preferences)
    
    # Monitor progress
    await monitor_trip_progress(system, session_id, "Backpacking Europe")
    
    await system.shutdown()


async def business_trip_singapore():
    """Plan a business trip to Singapore with some leisure time."""
    print("💼 Planning a Business Trip to Singapore...")
    print("="*60)
    
    system = TravelAgentSystem()
    await system.initialize()
    
    preferences = TravelPreferences(
        destination="Singapore",
        origin="London, UK",
        start_date=datetime.now() + timedelta(days=14),  # Short notice
        end_date=datetime.now() + timedelta(days=18),
        budget=3000.0,
        currency="USD",
        travelers=1,
        preferred_hotel_rating=4,
        activity_preferences=["business district", "conference venues", "evening entertainment"],
        constraints=["Near CBD", "Business center required", "24hr room service"]
    )
    
    session_id = await system.plan_trip(preferences)
    
    # Monitor progress
    await monitor_trip_progress(system, session_id, "Singapore Business Trip")
    
    await system.shutdown()


async def monitor_trip_progress(system: TravelAgentSystem, session_id: str, trip_name: str):
    """Monitor and display trip planning progress."""
    print(f"\n📍 Monitoring {trip_name} (Session: {session_id})")
    print("-" * 40)
    
    max_iterations = 20
    for i in range(max_iterations):
        await asyncio.sleep(1.5)
        
        status = await system.get_trip_status(session_id)
        
        # Display progress
        print(f"\r⏳ Status: {status['status']} | "
              f"💰 Spent: ${status['budget_spent']:.2f} | "
              f"🤖 Agents: {sum(1 for s in status['agent_status'].values() if s == 'active')} active",
              end="", flush=True)
        
        # Check for completion
        if status['status'] == 'completed':
            print("\n✅ Trip planning completed!")
            display_final_itinerary(status)
            break
        elif status['status'] == 'failed':
            print("\n❌ Trip planning failed!")
            break
        elif status['human_approval_needed']:
            print("\n⚠️  Human approval required!")
            print(f"Context: {status.get('human_approval_context', 'No context available')}")
            break
    else:
        print(f"\n⏱️  Planning still in progress after {max_iterations} checks...")


def display_final_itinerary(status: dict):
    """Display the final itinerary."""
    print("\n" + "="*60)
    print("📋 FINAL ITINERARY")
    print("="*60)
    
    bookings = status['bookings']
    
    # Display hotels
    if bookings.get('hotels'):
        print("\n🏨 ACCOMMODATIONS:")
        for hotel in bookings['hotels']:
            print(f"  📍 {hotel['hotel_name']}")
            print(f"     Check-in: {hotel['check_in']}")
            print(f"     Check-out: {hotel['check_out']}")
            print(f"     Room: {hotel['room_type']}")
            print(f"     Cost: ${hotel['total_cost']:.2f}")
            if hotel.get('confirmation_number'):
                print(f"     Confirmation: {hotel['confirmation_number']}")
    
    # Display transport (when implemented)
    if bookings.get('transport'):
        print("\n✈️ TRANSPORTATION:")
        for transport in bookings['transport']:
            print(f"  📍 {transport['mode']}: {transport['origin']} → {transport['destination']}")
            print(f"     Departure: {transport['departure_time']}")
            print(f"     Cost: ${transport['cost']:.2f}")
    
    # Display activities (when implemented)
    if bookings.get('activities'):
        print("\n🎭 ACTIVITIES:")
        for activity in bookings['activities']:
            print(f"  📍 {activity['activity_name']}")
            print(f"     Date: {activity['start_time']}")
            print(f"     Cost: ${activity['total_cost']:.2f}")
    
    # Summary
    print("\n" + "-"*60)
    print(f"💰 TOTAL COST: ${status['budget_spent']:.2f}")
    print("="*60)


async def run_all_examples():
    """Run all example trip planning scenarios."""
    examples = [
        ("Romantic Paris Getaway", romantic_paris_getaway),
        ("Family Tokyo Adventure", family_tokyo_adventure),
        ("Budget Europe Backpacking", budget_backpacking_europe),
        ("Singapore Business Trip", business_trip_singapore)
    ]
    
    print("🌍 TRAVEL AGENT SYSTEM - EXAMPLE TRIPS")
    print("="*60)
    print("Running multiple trip planning examples...\n")
    
    for name, example_func in examples:
        print(f"\n{'='*60}")
        print(f"Starting: {name}")
        print(f"{'='*60}\n")
        
        try:
            await example_func()
        except Exception as e:
            print(f"❌ Error in {name}: {e}")
        
        print("\n" + "="*60)
        print("Waiting before next example...")
        await asyncio.sleep(3)
    
    print("\n✅ All examples completed!")


def menu():
    """Display menu for selecting examples."""
    print("\n🌍 TRAVEL AGENT SYSTEM - EXAMPLES")
    print("="*40)
    print("1. Romantic Paris Getaway (5 days, $4000)")
    print("2. Family Tokyo Adventure (7 days, $8000)")
    print("3. Budget Europe Backpacking (5 days, $1000)")
    print("4. Singapore Business Trip (4 days, $3000)")
    print("5. Run All Examples")
    print("0. Exit")
    print("="*40)
    
    choice = input("\nSelect an example (0-5): ")
    
    examples = {
        "1": romantic_paris_getaway,
        "2": family_tokyo_adventure,
        "3": budget_backpacking_europe,
        "4": business_trip_singapore,
        "5": run_all_examples
    }
    
    return examples.get(choice)


if __name__ == "__main__":
    while True:
        example_func = menu()
        
        if example_func is None:
            print("👋 Goodbye!")
            break
        
        try:
            asyncio.run(example_func())
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        input("\nPress Enter to continue...")
        print("\n" * 2)