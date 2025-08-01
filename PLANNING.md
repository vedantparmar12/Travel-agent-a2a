# Travel Agent System - Project Planning & Architecture

## Overview

The Travel Agent System is a distributed multi-agent application that automates travel planning using the A2A (Agent-to-Agent) protocol. Each agent runs as an independent server communicating through standardized REST APIs to search, book, and organize complete travel itineraries while managing budgets and resolving conflicts.

## Architecture

### System Design

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

### Technology Stack

- **Framework**: LangGraph + LangChain for agent logic
- **Protocol**: A2A (Agent-to-Agent) for inter-agent communication
- **Web Framework**: FastAPI/Starlette for HTTP endpoints
- **Security**: JWT tokens + API keys for authentication
- **LLM Providers**: Anthropic Claude, OpenAI GPT, Google Gemini
- **Async**: Python asyncio for concurrent operations
- **Testing**: Pytest with async support

### Core Components

#### 1. Orchestrator Agent (Port 10001)
- Central coordinator using A2A client connections
- Discovers and manages all specialist agents
- Distributes tasks based on dependencies
- Resolves conflicts between bookings
- Manages overall workflow state

#### 2. Hotel Agent (Port 10010) ✅ Implemented
- Independent A2A server using LangGraph
- Searches for accommodations
- Handles booking confirmations
- Provides location data to other agents
- Mock API integration ready

#### 3. Transport Agent (Port 10011) ✅ Implemented
- Handles flights, trains, and ground transport
- Coordinates timing with accommodations
- Searches multiple transport modes
- Price comparison and optimization

#### 4. Activity Agent (Port 10012) 🚧 Not Implemented
- Suggests local attractions and experiences
- Books tours and activities
- Considers traveler preferences
- Time and location aware

#### 5. Budget Agent (Port 10013) 🚧 Partially Implemented
- Real-time budget monitoring
- Validates all bookings
- Tracks spending across agents
- Alerts on budget overruns

#### 6. Itinerary Agent (Port 10014) 🚧 Not Implemented
- Creates comprehensive travel plans
- Generates multiple output formats
- Resolves scheduling conflicts
- Produces final deliverables

### Data Models

Located in `src/shared/models.py`:

- **TravelPreferences**: User input preferences
- **HotelBooking**: Hotel reservation details
- **TransportBooking**: Flight/train bookings
- **ActivityBooking**: Tours and activities
- **BudgetStatus**: Budget tracking
- **TravelItinerary**: Complete trip plan
- **AgentMessage**: Inter-agent communication
- **ConflictInfo**: Booking conflicts
- **HumanApprovalRequest**: Escalation handling

### Security Architecture

#### Authentication
- JWT tokens for service-to-service auth
- API keys for client authentication
- Automatic token refresh
- Service account management

#### Encryption
- Fernet encryption for sensitive data
- SSL/TLS support for production
- Secure password hashing with bcrypt

#### Rate Limiting
- Per-minute request limits
- Service-specific quotas
- Graceful degradation

### Communication Flow

1. **Client → Orchestrator**: HTTP REST API
2. **Orchestrator → Agents**: A2A protocol over HTTP
3. **Agent → Agent**: Direct A2A communication
4. **Agents → External APIs**: Async HTTP clients

### State Management

- In-memory state for development
- Redis support for production (configured)
- Session-based isolation
- Atomic state updates

## Development Guidelines

### Code Structure

Each agent follows this structure:
```
agents/
  hotel/
    __init__.py          # Package init
    __main__.py          # A2A server entry
    agent.py             # Core agent logic
    agent_executor.py    # A2A executor
    hotel_agent_a2a.py   # LangGraph implementation
    prompts.py           # System prompts
    tools.py             # Agent tools
```

### Adding New Agents

1. Create agent directory structure
2. Implement A2A agent class
3. Create executor for A2A protocol
4. Add server entry point
5. Update launcher configuration
6. Add to agent registry

### Testing Strategy

- Unit tests for individual components
- Integration tests for agent communication
- End-to-end tests for complete workflows
- Mock external APIs for testing

### Error Handling

- Graceful degradation on agent failure
- Automatic retry with exponential backoff
- Human escalation for critical decisions
- Comprehensive logging

## Configuration

### Environment Variables

Key configuration in `.env`:
- LLM API keys (Anthropic, OpenAI, Google)
- Service API keys (auto-generated)
- Port assignments for each agent
- Security settings (JWT secret, encryption)
- Feature flags (caching, rate limiting)

### Production Considerations

- Use SSL/TLS for all communication
- Deploy agents as separate containers
- Implement proper monitoring (OpenTelemetry ready)
- Use external message queue for scale
- Database persistence for state

## Current Status

### Completed ✅
- Core architecture implementation
- A2A protocol integration
- Hotel Agent (fully functional)
- Transport Agent (fully functional)
- Budget Agent (partial - server only)
- Orchestrator Agent (functional)
- Security infrastructure
- Basic client implementation

### In Progress 🚧
- Activity Agent implementation
- Itinerary Agent implementation
- Comprehensive test suite
- Real API integrations
- Production deployment configs

### Planned 📋
- Web UI for monitoring
- Kubernetes deployment
- Advanced conflict resolution
- ML-based preference learning
- Multi-destination support

## Design Decisions

### Why A2A Protocol?
- Standard communication format
- Language/framework agnostic
- Built-in async support
- Easy debugging/monitoring
- Supports streaming responses

### Why Separate Agents?
- Independent scaling
- Fault isolation
- Technology flexibility
- Clear responsibilities
- Easier testing

### Why LangGraph?
- Native agent support
- State management
- Tool integration
- Streaming capabilities
- Production ready

## API Standards

### A2A Message Format
```json
{
  "message": {
    "role": "user",
    "parts": [{"type": "text", "text": "content"}]
  }
}
```

### Response Format
```json
{
  "status": "COMPLETED",
  "artifacts": [{
    "type": "text",
    "title": "Results",
    "artifact": {"parts": [{"text": "content"}]}
  }]
}
```

## Performance Targets

- Agent startup: < 5 seconds
- Message processing: < 100ms overhead
- Search operations: < 3 seconds
- End-to-end booking: < 30 seconds
- Concurrent sessions: 100+

## Monitoring & Observability

- Health endpoints for each agent
- Structured logging with context
- OpenTelemetry integration ready
- Metrics collection configured
- Error tracking with Sentry support

## Future Enhancements

1. **Phase 2**: Real API Integration
   - Amadeus for flights
   - Booking.com for hotels
   - Google Places for activities

2. **Phase 3**: Advanced Features
   - Multi-city trips
   - Group travel coordination
   - Loyalty program integration
   - Price tracking

3. **Phase 4**: ML Enhancement
   - Preference learning
   - Recommendation engine
   - Dynamic pricing optimization
   - Anomaly detection