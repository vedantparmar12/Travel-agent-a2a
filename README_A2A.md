# Multi-Agent Travel Planning System with A2A Protocol

An advanced multi-agent travel planning system built using the A2A (Agent-to-Agent) protocol. Each agent runs as an independent server, communicating through standardized REST APIs for robust, scalable travel planning.

## 🚀 What's New with A2A

### Key Improvements

1. **Independent Agent Servers** - Each agent runs on its own port as a REST API server
2. **Standardized Communication** - A2A protocol handles all inter-agent messaging
3. **Framework Agnostic** - Agents can be built with different frameworks (LangGraph, CrewAI, ADK)
4. **Dynamic Discovery** - Agents are discovered at runtime via AgentCard
5. **Built-in Task Management** - A2A handles task tracking and status updates automatically

## 🏗️ Architecture

### A2A-Based Design

```
┌─────────────────┐
│  Travel Client  │
│  (User Interface)│
└────────┬────────┘
         │ A2A Protocol
         ▼
┌─────────────────┐
│  Orchestrator   │ Port 10001
│     Agent       │ (Coordinator)
└────────┬────────┘
         │ A2A Messages
    ┌────┴────┬────────┬──────────┬──────────┐
    ▼         ▼        ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│Hotel │  │Trans-│  │Activ-│  │Budget│  │Itiner│
│Agent │  │port  │  │ity   │  │Agent │  │ary   │
└──────┘  └──────┘  └──────┘  └──────┘  └──────┘
Port:     Port:     Port:     Port:     Port:
10010     10011     10012     10013     10014
```

### Agent Descriptions

1. **Orchestrator Agent** (Port 10001)
   - Central coordinator using A2A client connections
   - Discovers and communicates with all specialist agents
   - Manages task distribution and conflict resolution

2. **Hotel Agent** (Port 10010)
   - Independent server for accommodation search
   - Implements A2A server with LangGraph
   - Handles all hotel-related queries

3. **Other Agents** (To be implemented)
   - Transport, Activity, Budget, and Itinerary agents
   - Each runs as independent A2A server
   - Can use different frameworks

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Virtual environment

### Installation

1. Clone and setup:
```bash
cd travel-agent-system
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys (optional for mock mode)
```

### Running the System

#### Option 1: Launch All Agents (Recommended)

```bash
python src/launch_agents.py
```

This will:
- Start Hotel Agent on port 10010
- Start Orchestrator Agent on port 10001
- Monitor and restart agents if they crash

#### Option 2: Launch Agents Individually

Terminal 1 - Hotel Agent:
```bash
python -m src.agents.hotel
```

Terminal 2 - Orchestrator Agent:
```bash
python -m src.agents.orchestrator
```

### Using the Travel Client

Once agents are running:

```bash
python src/travel_client.py
```

Choose:
1. Interactive trip planning
2. Quick example (Paris trip)

## 📡 A2A Communication Example

### How Agents Communicate

1. **Client sends request to Orchestrator:**
```python
# Client creates A2A message
message_request = SendMessageRequest(
    id=str(uuid.uuid4()),
    params=MessageSendParams(message={
        "role": "user",
        "parts": [{"type": "text", "text": "Plan a trip to Paris"}]
    })
)
```

2. **Orchestrator delegates to Hotel Agent:**
```python
# Orchestrator sends task to Hotel Agent
await send_task_to_agent(
    agent_name="Hotel_Agent",
    task="Find hotels in Paris from 2024-06-15 to 2024-06-20, budget $200/night"
)
```

3. **Hotel Agent responds with results:**
```python
# Hotel Agent returns structured response
TaskArtifact(
    type="text",
    title="Hotel Search Results",
    artifact=TextArtifact(parts=[TextPart(text=hotel_results)])
)
```

## 🔧 Development

### Adding New Agents

1. **Create Agent Implementation:**
```python
# src/agents/transport/transport_agent_a2a.py
class TransportAgentA2A:
    async def stream(self, query: str, context_id: str):
        # Agent logic here
```

2. **Create A2A Executor:**
```python
# src/agents/transport/agent_executor.py
class TransportAgentExecutor(AgentExecutor):
    async def invoke(self, context, task_updater, event_queue):
        # Process A2A requests
```

3. **Create Server:**
```python
# src/agents/transport/__main__.py
app = create_app()
uvicorn.run(app, port=10011)
```

4. **Update Launch Configuration:**
```python
# src/launch_agents.py
AGENTS["transport"] = {
    "name": "Transport Agent",
    "module": "src.agents.transport",
    "port": 10011
}
```

### Testing Individual Agents

Test Hotel Agent directly:
```bash
curl http://localhost:10010/info
```

Send message via A2A:
```bash
curl -X POST http://localhost:10010/send_message \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "Find hotels in London"}]
      }
    }
  }'
```

## 📊 Monitoring

### Agent Status

The launcher shows real-time status:
```
==================================================
AGENT STATUS
==================================================
✓ Hotel Agent          Running on port 10010 (PID: 12345)
✓ Orchestrator Agent   Running on port 10001 (PID: 12346)
==================================================
```

### Logs

Each agent logs independently:
- Connection status
- Received messages
- Task processing
- Errors and warnings

## 🐛 Troubleshooting

### Common Issues

1. **"Failed to connect to agent"**
   - Check if the agent is running on the correct port
   - Verify no firewall blocking local connections

2. **"Agent not found"**
   - Ensure agent is started before orchestrator
   - Check agent name matches exactly

3. **"Task timeout"**
   - Increase timeout in A2A client configuration
   - Check agent logs for processing errors

### Debug Mode

Enable detailed logging:
```python
# In any agent file
logging.basicConfig(level=logging.DEBUG)
```

## 🔐 Security

- Agents only accept local connections by default
- No authentication in development mode
- Production deployment should add:
  - API key authentication
  - HTTPS endpoints
  - Rate limiting

## 🚧 Current Implementation Status

- ✅ A2A Protocol Integration
- ✅ Orchestrator Agent with A2A client
- ✅ Hotel Agent as A2A server
- ✅ Agent launcher and monitoring
- ✅ Travel planning client
- 🚧 Transport Agent (pending)
- 🚧 Activity Agent (pending)
- 🚧 Budget Agent (pending)
- 🚧 Itinerary Agent (pending)

## 📈 Benefits of A2A Architecture

1. **Scalability** - Agents can run on different machines
2. **Resilience** - Individual agent failures don't crash the system
3. **Flexibility** - Easy to add/remove agents
4. **Debugging** - Clear message flow between agents
5. **Testing** - Agents can be tested independently

## 🔗 Related Resources

- [A2A Protocol Documentation](https://github.com/anthropics/a2a)
- [LangGraph Documentation](https://github.com/langchain-ai/langgraph)
- [Agent Development Best Practices](https://docs.anthropic.com/agents)