"""
Transport Agent A2A Server.
"""
import asyncio
import logging
import os
from typing import Optional

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentInfo,
    ConversationInfo,
    ConversationMetadata,
    ConversationParticipant,
    ConversationRole,
)
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .agent_executor import TransportAgentExecutor
from ...security.auth import security_manager, get_ssl_context, A2ASecurityMiddleware


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Agent metadata
AGENT_INFO = AgentInfo(
    name="Transport_Agent",
    description=(
        "I'm a specialized transport booking agent that helps arrange flights, trains, "
        "and ground transportation. I can search for the best routes, compare prices, "
        "and suggest alternative transport modes based on your journey needs."
    ),
    welcome_message=(
        "Hello! I'm the Transport Agent. I'll help you find the best way to reach "
        "your destination. Whether you need flights, trains, or other transport, "
        "I'll search for options that fit your schedule and budget."
    ),
    instructions=[
        "Tell me your origin and destination cities",
        "Specify your travel dates (departure and return if applicable)",
        "Share your budget and number of travelers",
        "Let me know any preferences (direct flights, specific airlines, etc.)"
    ],
    tools=["search_flights", "compare_transport_modes", "check_schedules"],
    conversation_starters=[
        "Find flights from New York to Paris next month",
        "I need a round trip to Tokyo for 2 people",
        "What's the best way to get from London to Amsterdam?",
        "Search for business class flights to Singapore",
    ],
)


# Create conversation info
def get_conversation_info() -> ConversationInfo:
    """Get the conversation info for the agent."""
    return ConversationInfo(
        participants=[
            ConversationParticipant(
                role=ConversationRole.ASSISTANT,
                metadata=ConversationMetadata(
                    display_name="Transport Agent",
                    description="Your personal travel transport assistant",
                ),
            )
        ]
    )


# Create the A2A application
def create_app(
    agent_info: Optional[AgentInfo] = None,
    conversation_info: Optional[ConversationInfo] = None,
) -> A2AStarletteApplication:
    """Create the A2A Starlette application."""
    # Use provided or default agent info
    agent_info = agent_info or AGENT_INFO
    conversation_info = conversation_info or get_conversation_info()
    
    # Create agent card
    agent_card = AgentCard(
        info=agent_info,
        conversation=conversation_info,
    )
    
    # Create executor
    agent_executor = TransportAgentExecutor()
    
    # Create task store
    task_store = InMemoryTaskStore()
    
    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_card=agent_card,
        agent_executor=agent_executor,
        task_store=task_store,
    )
    
    # Create and return the application
    return A2AStarletteApplication(request_handler=request_handler)


# Security middleware
class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for agent endpoints."""
    
    def __init__(self, app, service_id: str):
        super().__init__(app)
        self.security = A2ASecurityMiddleware(service_id)
    
    async def dispatch(self, request: Request, call_next):
        # Skip security for health check
        if request.url.path == "/health":
            return await call_next(request)
        
        # Verify incoming request
        headers = dict(request.headers)
        is_valid, requester = await self.security.verify_incoming_request(headers)
        
        if not is_valid:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )
        
        # Add requester info to request state
        request.state.requester = requester
        
        # Check rate limit
        if not security_manager.check_rate_limit(requester or request.client.host):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"}
            )
        
        response = await call_next(request)
        return response


# Create the app instance
app = create_app()

# Add security middleware
app.add_middleware(SecurityMiddleware, service_id="transport")


if __name__ == "__main__":
    port = int(os.getenv("TRANSPORT_AGENT_PORT", "10011"))
    use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
    
    logger.info(f"Starting Transport Agent on port {port}")
    logger.info(f"Agent: {AGENT_INFO.name}")
    logger.info(f"Description: {AGENT_INFO.description}")
    logger.info(f"SSL/TLS: {'Enabled' if use_ssl else 'Disabled'}")
    
    # Prepare SSL config if enabled
    ssl_config = {}
    if use_ssl:
        ssl_context = get_ssl_context()
        ssl_config = {
            "ssl_keyfile": os.getenv("SSL_KEY_FILE", "certs/server.key"),
            "ssl_certfile": os.getenv("SSL_CERT_FILE", "certs/server.crt"),
        }
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        **ssl_config
    )