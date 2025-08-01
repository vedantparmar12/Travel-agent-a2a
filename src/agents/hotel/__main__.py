"""
Hotel Agent A2A Server.
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

from .agent_executor import HotelAgentExecutor


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Agent metadata
AGENT_INFO = AgentInfo(
    name="Hotel_Agent",
    description=(
        "I'm a specialized hotel booking agent that helps find and book accommodations. "
        "I can search for hotels based on destination, dates, budget, and guest preferences. "
        "I provide detailed comparisons and recommendations for the best options."
    ),
    welcome_message=(
        "Hello! I'm the Hotel Agent. I'll help you find the perfect accommodation "
        "for your trip. Just let me know your destination, dates, budget, and any "
        "special preferences you have."
    ),
    instructions=[
        "Provide your destination city",
        "Specify check-in and check-out dates", 
        "Tell me your budget and number of guests",
        "Share any special requirements (location preference, amenities, etc.)"
    ],
    tools=["search_hotels", "rank_hotels", "validate_availability"],
    conversation_starters=[
        "Find hotels in Paris for next weekend",
        "I need a business hotel in New York for 3 nights",
        "Search for family-friendly resorts in Orlando",
        "What are the best budget hotels in Tokyo?",
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
                    display_name="Hotel Agent",
                    description="Your personal hotel booking assistant",
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
    agent_executor = HotelAgentExecutor()
    
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


# Create the app instance
app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("HOTEL_AGENT_PORT", "10010"))
    
    logger.info(f"Starting Hotel Agent on port {port}")
    logger.info(f"Agent: {AGENT_INFO.name}")
    logger.info(f"Description: {AGENT_INFO.description}")
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )