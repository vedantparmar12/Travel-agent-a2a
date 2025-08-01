# Multi-Agent Travel Planning System with A2A Protocol

A sophisticated multi-agent system built with the A2A (Agent-to-Agent) protocol for automated travel planning. Each agent runs as an independent server, communicating through standardized REST APIs to search, book, and organize complete travel itineraries while managing budgets and resolving conflicts.

## 🚀 What's New: A2A Protocol Integration

This system now uses the **A2A (Agent-to-Agent) protocol**, bringing enterprise-grade agent communication:

- **Independent Agent Servers**: Each agent runs on its own port
- **Standardized Communication**: REST APIs with A2A message format
- **Dynamic Discovery**: Agents are discovered at runtime
- **Framework Agnostic**: Mix LangGraph, CrewAI, and other frameworks
- **Production Ready**: Built-in monitoring, error handling, and resilience

## 🏗️ Architecture

The system implements a distributed multi-agent architecture:

### A2A Network Architecture

```
┌─────────────────┐
│  Travel Client  │  User Interface
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────┐
│  Orchestrator   │  Port: 10001
│     Agent       │  Central Coordinator
└────────┬────────┘
         │ A2A Protocol
    ┌────┴────┬────────┬──────────┬──────────┐
    ▼         ▼        ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│Hotel │  │Trans-│  │Activ-│  │Budget│  │Itiner│
│Agent │  │port  │  │ity   │  │Agent │  │ary   │
└──────┘  └──────┘  └──────┘  └──────┘  └──────┘
 10010     10011     10012     10013     10014
```

### Core Agents

1. **Orchestrator Agent** 🎯 (Port 10001)
   - Central coordinator using A2A client connections
   - Discovers and manages all specialist agents
   - Distributes tasks based on dependencies
   - Resolves conflicts between bookings

2. **Hotel Agent** 🏨 (Port 10010) ✅ Implemented
   - Independent A2A server using LangGraph
   - Searches for accommodations
   - Handles booking confirmations
   - Provides location data to other agents

3. **Transport Agent** ✈️ (Port 10011) 🚧 Planned
   - Will handle flights, trains, and ground transport
   - Coordinates timing with accommodations

4. **Activity Agent** 🎭 (Port 10012) 🚧 Planned
   - Suggests local attractions and experiences
   - Books tours and activities

5. **Budget Agent** 💰 (Port 10013) 🚧 Planned
   - Real-time budget monitoring
   - Validates all bookings

6. **Itinerary Agent** 📅 (Port 10014) 🚧 Planned
   - Creates comprehensive travel plans
   - Generates multiple output formats

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
cd travel-agent-system
```

2. Create and activate a virtual environment:
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Unix/MacOS
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

### Running the System

#### Step 1: Launch All Agents
```bash
python src/launch_agents.py
```

This will:
- Start all agent servers on their respective ports
- Monitor agent health and restart if needed
- Show real-time status of all agents

#### Step 2: Use the Travel Client
In a new terminal:
```bash
python src/travel_client.py
```

Choose from:
1. Interactive trip planning (answer questions)
2. Quick example (pre-configured Paris trip)

## 🔧 Configuration

### Environment Variables

Create a `.env` file with the following:

```env
# LLM API Keys
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Travel APIs (optional for mock mode)
BOOKING_API_KEY=your_key_here
AMADEUS_CLIENT_ID=your_id_here
AMADEUS_CLIENT_SECRET=your_secret_here

# System Settings
MAX_BUDGET_THRESHOLD=10000
HUMAN_APPROVAL_THRESHOLD=5000
```

## 📖 Usage Examples

### Using the Travel Client

```python
import asyncio
from src.travel_client import TravelPlannerClient

async def plan_trip():
    client = TravelPlannerClient()
    await client.connect()
    
    request = """Plan a trip with these details:
    - Destination: Paris, France
    - Origin: London, UK
    - Dates: 2024-08-15 to 2024-08-20
    - Budget: $3000 USD
    - Travelers: 2
    - Special requests: Romantic hotel near Eiffel Tower"""
    
    result = await client.plan_trip(request)
    print(result)
    
    await client.close()

asyncio.run(plan_trip())
```

### Direct Agent Communication

```bash
# Query Hotel Agent directly
curl -X POST http://localhost:10010/send_message \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "Find hotels in Paris for June 15-20"}]
      }
    }
  }'
```

## 🔄 A2A Communication Flow

### How Agents Communicate

1. **Client → Orchestrator** (HTTP/REST)
   ```json
   {
     "message": {
       "role": "user",
       "parts": [{"type": "text", "text": "Plan a trip to Paris"}]
     }
   }
   ```

2. **Orchestrator → Hotel Agent** (A2A Protocol)
   ```python
   await send_task_to_agent(
       agent_name="Hotel_Agent",
       task="Find hotels in Paris, June 15-20, budget $200/night"
   )
   ```

3. **Hotel Agent → Orchestrator** (A2A Response)
   ```json
   {
     "status": "COMPLETED",
     "artifacts": [{
       "type": "text",
       "title": "Hotel Results",
       "artifact": {"parts": [{"text": "Found 5 hotels..."}]}
     }]
   }
   ```

### A2A Benefits

- **Standardized Protocol**: All agents speak the same language
- **Async Communication**: Non-blocking message passing
- **Task Tracking**: Built-in status updates and progress monitoring
- **Error Handling**: Standardized error responses

## 🧪 Testing

Run the test suite:
```bash
pytest tests/
```

For specific test categories:
```bash
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests
```

## 📊 Monitoring & Management

### Agent Status Dashboard

When running `launch_agents.py`, you'll see:
```
============================================================
AGENT STATUS
============================================================
✓ Hotel Agent          Running on port 10010 (PID: 12345)
✓ Orchestrator Agent   Running on port 10001 (PID: 12346)
============================================================
```

### Health Checks

```bash
# Check individual agent health
curl http://localhost:10010/health
curl http://localhost:10001/health

# View agent info
curl http://localhost:10010/info
```

### Logs

Each agent logs independently:
- Connection events
- Message received/sent
- Errors and warnings
- Task processing status

## 🛠️ Development

### Adding New A2A Agents

1. **Create Agent Implementation** (`src/agents/transport/transport_agent_a2a.py`):
   ```python
   class TransportAgentA2A:
       async def stream(self, query: str, context_id: str):
           # Your agent logic
   ```

2. **Create A2A Executor** (`src/agents/transport/agent_executor.py`):
   ```python
   class TransportAgentExecutor(AgentExecutor):
       async def invoke(self, context, task_updater, event_queue):
           # Handle A2A requests
   ```

3. **Create Server** (`src/agents/transport/__main__.py`):
   ```python
   app = create_app()
   uvicorn.run(app, port=10011)
   ```

4. **Update Launcher** (`src/launch_agents.py`):
   ```python
   AGENTS["transport"] = {
       "name": "Transport Agent",
       "module": "src.agents.transport",
       "port": 10011
   }
   ```

### Project Structure

```
travel-agent-system/
├── src/
│   ├── agents/                    # A2A Agent Servers
│   │   ├── orchestrator/
│   │   │   ├── __main__.py       # A2A server entry
│   │   │   ├── orchestrator_a2a.py
│   │   │   └── remote_agent_connection.py
│   │   ├── hotel/
│   │   │   ├── __main__.py       # A2A server entry
│   │   │   ├── hotel_agent_a2a.py
│   │   │   └── agent_executor.py
│   │   └── ...
│   ├── shared/                   # Legacy shared components
│   ├── launch_agents.py          # Agent launcher & monitor
│   └── travel_client.py          # Client application
├── tests/                        # Test suite
├── config/                       # Configuration files
├── README_A2A.md                # A2A specific docs
└── requirements.txt             # Dependencies
```

## 🤝 Human-in-the-Loop

The system automatically escalates to human approval when:

- Budget exceeds threshold
- No suitable options found
- Conflicting requirements can't be resolved
- Critical decisions need confirmation

## 🔒 Security Considerations

- API keys stored in environment variables
- No sensitive data in logs
- Secure state management
- Input validation on all user data

## 📈 Performance

- Agents run asynchronously for optimal performance
- Parallel execution where dependencies allow
- Built-in retry logic for API failures
- Graceful degradation on service unavailability

## 🚧 Current Implementation Status

### ✅ Completed
- A2A Protocol integration
- Orchestrator Agent with dynamic agent discovery
- Hotel Agent as independent A2A server
- Agent launcher with monitoring
- Travel planning client
- Distributed architecture foundation

### 🚧 In Progress
- Transport Agent (flights, trains)
- Activity Agent (tours, experiences)
- Budget Agent (cost monitoring)
- Itinerary Agent (plan generation)

### 📋 Planned Enhancements
- Real API integrations (Amadeus, Booking.com)
- Multi-destination trip support
- Web interface for agent monitoring
- Agent deployment to cloud (Kubernetes)
- Advanced conflict resolution strategies
- ML-based preference learning

## 🗺️ Why A2A Protocol?

The A2A protocol transformation brings:

1. **Scalability**: Agents can run on separate servers/containers
2. **Resilience**: Agent failures don't crash the system
3. **Flexibility**: Mix different AI frameworks per agent
4. **Maintainability**: Clear interfaces between agents
5. **Observability**: HTTP traffic can be monitored/debugged
6. **Extensibility**: Easy to add new agents without modifying core

## 📝 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Inspired by modern travel planning needs
- Uses agent-based architecture patterns