#!/usr/bin/env python3
"""
Test script to verify Gemini API integration.
"""
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_gemini_api():
    """Test Gemini API connectivity and agent initialization."""
    print("🧪 Testing Gemini API Integration")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your_google_gemini_api_key_here":
        print("❌ GOOGLE_API_KEY not set properly in .env file")
        print("   Please set your Gemini API key first.")
        return False
    
    print(f"✓ Google API Key found: {api_key[:10]}...")
    
    # Test LLM configuration
    try:
        from src.shared.llm_config import LLMConfig
        
        print("\n📋 Testing LLM Configuration...")
        
        # Test getting default LLM
        llm = LLMConfig.get_llm()
        print(f"✓ Default LLM created: {type(llm).__name__}")
        
        # Test getting agent-specific LLMs
        agents = ["hotel", "transport", "activity", "budget", "itinerary", "orchestrator"]
        for agent in agents:
            try:
                agent_llm = LLMConfig.get_agent_llm(agent)
                print(f"✓ {agent.title()} Agent LLM created")
            except Exception as e:
                print(f"✗ {agent.title()} Agent LLM failed: {e}")
        
        # Test a simple query
        print("\n🤖 Testing Gemini Response...")
        try:
            response = llm.invoke("Hello, please respond with 'Gemini is working!'")
            print(f"✓ Gemini responded: {response.content[:50]}...")
            return True
        except Exception as e:
            print(f"✗ Gemini query failed: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Failed to import LLM configuration: {e}")
        return False


async def test_agent_initialization():
    """Test initializing each agent."""
    print("\n\n🏗️ Testing Agent Initialization")
    print("=" * 60)
    
    agents_to_test = [
        ("Hotel Agent", "src.agents.hotel.hotel_agent_a2a", "HotelAgentA2A"),
        ("Transport Agent", "src.agents.transport.transport_agent_a2a", "TransportAgentA2A"),
        ("Activity Agent", "src.agents.activity.activity_agent_a2a", "ActivityAgentA2A"),
        ("Budget Agent", "src.agents.budget.budget_agent_a2a", "BudgetAgentA2A"),
        ("Itinerary Agent", "src.agents.itinerary.itinerary_agent_a2a", "ItineraryAgentA2A"),
    ]
    
    all_good = True
    
    for agent_name, module_path, class_name in agents_to_test:
        try:
            print(f"\n Testing {agent_name}...")
            
            # Import the module
            import importlib
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)
            
            # Create agent instance
            agent = agent_class()
            print(f"✓ {agent_name} initialized successfully")
            print(f"  - Model: {type(agent.model).__name__}")
            print(f"  - Tools: {len(agent.tools)} tools available")
            
        except Exception as e:
            print(f"✗ {agent_name} failed: {e}")
            all_good = False
    
    return all_good


async def main():
    """Run all tests."""
    print("🚀 Travel Agent System - Gemini Integration Test")
    print("=" * 60)
    
    # Test Gemini API
    gemini_ok = await test_gemini_api()
    
    if gemini_ok:
        # Test agent initialization
        agents_ok = await test_agent_initialization()
        
        print("\n\n📊 Test Summary")
        print("=" * 60)
        
        if gemini_ok and agents_ok:
            print("✅ All tests passed! System is ready to use Gemini.")
            print("\n🎯 Next steps:")
            print("1. Run: python src/launch_agents.py")
            print("2. In another terminal: python src/travel_client.py")
        else:
            print("❌ Some tests failed. Please check the errors above.")
    else:
        print("\n❌ Gemini API key not configured. Please set GOOGLE_API_KEY in .env file")


if __name__ == "__main__":
    asyncio.run(main())