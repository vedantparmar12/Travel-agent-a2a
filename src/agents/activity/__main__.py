"""
Activity Agent A2A Server.
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

from .agent_executor import ActivityAgentExecutor
from ...security.auth import security_manager, get_ssl_context, A2ASecurityMiddleware


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Agent metadata
AGENT_INFO = AgentInfo(
    name="Activity_Agent",
    description=(
        "I'm a specialized activity and experience booking agent. I help find and book "
        "tours, attractions, restaurants, and local experiences. I consider your interests, "
        "schedule, and budget to recommend the best activities for your trip."
    ),
    welcome_message=(
        "Hello! I'm the Activity Agent. I'll help you discover amazing experiences "
        "at your destination. From cultural tours to adventure activities, dining "
        "experiences to local attractions, I'll find activities that match your interests."
    ),
    instructions=[
        "Tell me your destination and travel dates",
        "Share your interests (culture, adventure, food, nature, etc.)",
        "Specify your activity budget",
        "Let me know any physical limitations or preferences"
    ],
    tools=["search_activities", "check_availability", "recommend_restaurants", "book_tours"],
    conversation_starters=[
        "Find cultural activities in Rome",
        "Book a food tour in Bangkok",
        "What are the must-see attractions in Paris?",
        "Find family-friendly activities in Orlando",
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
                    display_name="Activity Agent",
                    description="Your personal activity and experience planner",
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
    agent_executor = ActivityAgentExecutor()
    
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
app.add_middleware(SecurityMiddleware, service_id="activity")


if __name__ == "__main__":
    port = int(os.getenv("ACTIVITY_AGENT_PORT", "10012"))
    use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
    
    logger.info(f"Starting Activity Agent on port {port}")
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