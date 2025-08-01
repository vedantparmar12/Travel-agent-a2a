# Quick Start Guide - A2A Travel Agent System

## 🚀 5-Minute Setup

### 1. Install Dependencies

```bash
cd travel-agent-system
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys (optional for mock mode)
```

### 3. Launch the Agent System

```bash
# Start all agents with one command
python src/launch_agents.py
```

This will:
- ✅ Start Hotel Agent on port 10010
- ✅ Start Orchestrator Agent on port 10001
- ✅ Monitor agents and restart if needed

### 4. Plan Your First Trip

In a new terminal:
```bash
python src/travel_client.py
```

Choose option 2 for a quick Paris trip example!

## 📝 Creating Your Own Trip

### Option 1: Interactive Client

When you run `python src/travel_client.py`, choose option 1 for interactive planning:

```
Where would you like to go? Paris
Where are you traveling from? New York
How many days from now do you want to travel? 30
How many days is your trip? 5
What's your total budget (USD)? 3000
How many travelers? 2
```

### Option 2: Direct API Communication

```python
import asyncio
from src.travel_client import TravelPlannerClient

async def custom_trip():
    client = TravelPlannerClient()
    await client.connect()
    
    request = """Plan a trip with these details:
    - Destination: Barcelona, Spain
    - Origin: London, UK
    - Dates: 2024-07-15 to 2024-07-20
    - Budget: $2500 USD
    - Travelers: 2
    - Special requests: Beach nearby, tapas restaurants"""
    
    result = await client.plan_trip(request)
    print(result)
    
    await client.close()

asyncio.run(custom_trip())
```

## 🔍 Understanding the A2A System

### What Happens When You Launch

```
============================================================
AGENT STATUS
============================================================
✓ Hotel Agent          Running on port 10010 (PID: 12345)
✓ Orchestrator Agent   Running on port 10001 (PID: 12346)
============================================================

Access points:
- Orchestrator API: http://localhost:10001
- Hotel Agent API: http://localhost:10010
```

### Travel Planning Output

```
TRAVEL PLANNER - A2A CLIENT
============================================================
Connected to Orchestrator_Agent

Planning your trip...
------------------------------------------------------------
✓ Status: COMPLETED

**Travel Planning Results**

Found 5 hotels:

1. **The Plaza Hotel**
   - Price: $2250.00 total ($450.00/night)
   - Rating: 4.7/5
   - Location: 768 5th Ave, New York, NY 10019
   - Amenities: WiFi, Spa, Gym, Restaurant, Bar

**Recommended: The Plaza Hotel**
This hotel offers the best value for your requirements.
```

## 🎯 Key A2A Concepts

### How A2A Changes Everything

1. **Independent Agents**: Each agent runs as its own server
2. **REST APIs**: Agents communicate via HTTP/REST
3. **Dynamic Discovery**: Orchestrator finds agents at runtime
4. **Standardized Messages**: A2A protocol ensures compatibility

### Agent Communication Flow

```
Client → Orchestrator (port 10001)
         ├→ Hotel Agent (port 10010)
         ├→ Transport Agent (port 10011)
         └→ Budget Agent (port 10013)
```

### Why A2A is Better

- **Scalability**: Agents can run on different machines
- **Resilience**: One agent failing doesn't crash others
- **Flexibility**: Mix different frameworks (LangGraph, CrewAI, etc.)
- **Debugging**: Clear HTTP messages between agents

## 🛠️ Troubleshooting

### Common A2A Issues

1. **"Failed to connect to agent"**
   ```bash
   # Check if agents are running:
   python src/launch_agents.py
   ```

2. **"Agent Hotel_Agent not found"**
   - Agents must be started before the orchestrator
   - Check the agent launcher output for errors

3. **"Connection refused on port 10010"**
   - Port might be in use: `lsof -i :10010` (Linux/Mac)
   - Try different ports in .env file

4. **"No module named 'a2a'"**
   ```bash
   pip install a2a
   ```

### Testing Individual Agents

```bash
# Check if Hotel Agent is running:
curl http://localhost:10010/info

# Check Orchestrator:
curl http://localhost:10001/info
```

## 📚 Next Steps

1. **Customize Agents**: Modify agent behavior in `src/agents/`
2. **Add APIs**: Integrate real booking APIs
3. **Extend Features**: Add new agent types
4. **Build UI**: Create a web interface

## 💡 Tips

- Start with short trips (3-5 days) for faster planning
- Use major cities for better mock data coverage
- Keep budgets realistic for the destination
- Run examples first to understand the flow

## 🆘 Getting Help

- Check the [README](../README.md) for detailed documentation
- Review [agent implementations](../src/agents/) for customization
- Look at [example trips](../examples/sample_trips.py) for inspiration