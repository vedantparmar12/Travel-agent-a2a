"""
Budget Agent A2A Server.
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

from .agent_executor import BudgetAgentExecutor
from ...security.auth import security_manager, get_ssl_context, A2ASecurityMiddleware


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Agent metadata
AGENT_INFO = AgentInfo(
    name="Budget_Agent",
    description=(
        "I'm the Budget Management Agent responsible for tracking expenses and ensuring "
        "your trip stays within budget. I validate all bookings, provide spending summaries, "
        "and offer cost-saving recommendations throughout your travel planning."
    ),
    welcome_message=(
        "Hello! I'm the Budget Agent. I'll help you manage your travel expenses and "
        "ensure everything stays within your budget. I'll track spending across hotels, "
        "transport, and activities, and alert you if we're approaching your limits."
    ),
    instructions=[
        "Tell me your total trip budget",
        "I'll validate each expense before approval",
        "I'll track spending by category (hotel, transport, activities)",
        "I'll provide warnings and recommendations to stay on budget"
    ],
    tools=["validate_expense", "get_budget_status", "suggest_savings"],
    conversation_starters=[
        "Set my trip budget to $5000",
        "Can I afford a $300/night hotel?",
        "Show me my current spending breakdown",
        "How much budget do I have left?",
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
                    display_name="Budget Agent",
                    description="Your travel budget manager",
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
    agent_executor = BudgetAgentExecutor()
    
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
app.add_middleware(SecurityMiddleware, service_id="budget")


if __name__ == "__main__":
    port = int(os.getenv("BUDGET_AGENT_PORT", "10013"))
    use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
    
    logger.info(f"Starting Budget Agent on port {port}")
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