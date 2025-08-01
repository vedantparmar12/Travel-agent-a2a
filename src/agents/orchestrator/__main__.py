"""
Orchestrator Agent A2A Server.
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
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.utils.errors import ServerError
from dotenv import load_dotenv

from .orchestrator_a2a import OrchestratorAgentA2A


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Agent metadata
AGENT_INFO = AgentInfo(
    name="Orchestrator_Agent",
    description=(
        "I'm the Orchestrator Agent that coordinates all aspects of travel planning. "
        "I work with specialized agents to book hotels, transportation, activities, "
        "and create comprehensive travel itineraries while managing your budget."
    ),
    welcome_message=(
        "Welcome! I'm your Travel Planning Orchestrator. I'll coordinate with my team "
        "of specialized agents to plan your perfect trip. Just tell me where you want "
        "to go, when, and your budget, and I'll handle the rest!"
    ),
    instructions=[
        "Tell me your destination and origin cities",
        "Specify your travel dates",
        "Share your budget and number of travelers",
        "Mention any special preferences or requirements"
    ],
    tools=["send_task_to_agent", "analyze_agent_responses"],
    conversation_starters=[
        "Plan a week-long trip to Paris for 2 people with a $5000 budget",
        "I need to book a business trip to New York next month",
        "Help me plan a family vacation to Disney World",
        "Organize a romantic getaway to Bali for our anniversary",
    ],
)


class OrchestratorExecutor(AgentExecutor):
    """A2A executor for Orchestrator Agent."""
    
    def __init__(self, agent: OrchestratorAgentA2A):
        self.agent = agent
    
    async def invoke(
        self,
        context: RequestContext,
        task_updater: TaskUpdater,
        event_queue: EventQueue,
    ):
        """Invoke the Orchestrator Agent."""
        if not context.message or not context.message.parts:
            raise ServerError("No message provided in the request.")
        
        query = " ".join([part.text for part in context.message.parts if part.text])
        context_id = context.message.context_id or str(uuid.uuid4())
        
        try:
            # Stream the agent's response
            async for update in self.agent.stream(query, context_id):
                if update.get("is_task_complete"):
                    # Final response
                    content = update.get("content", "Task completed")
                    
                    # Create artifact
                    from a2a.types import TaskArtifact, TextArtifact, TextPart, TaskStatus
                    import uuid
                    
                    artifact = TaskArtifact(
                        id=str(uuid.uuid4()),
                        type="text",
                        title="Travel Planning Results",
                        artifact=TextArtifact(
                            parts=[TextPart(text=content)]
                        ),
                    )
                    
                    # Update task
                    await task_updater.update_task(
                        status=TaskStatus.COMPLETED,
                        artifacts=[artifact],
                    )
                else:
                    # Progress update
                    await task_updater.update_task(
                        status=TaskStatus.IN_PROGRESS,
                    )
            
            return await task_updater.get_task()
            
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            await task_updater.update_task(
                status=TaskStatus.FAILED,
            )
            return await task_updater.get_task()


# Get remote agent URLs from environment or use defaults
def get_agent_urls():
    """Get the URLs for remote agents."""
    return [
        os.getenv("HOTEL_AGENT_URL", "http://localhost:10010"),
        os.getenv("TRANSPORT_AGENT_URL", "http://localhost:10011"),
        os.getenv("ACTIVITY_AGENT_URL", "http://localhost:10012"),
        os.getenv("BUDGET_AGENT_URL", "http://localhost:10013"),
        os.getenv("ITINERARY_AGENT_URL", "http://localhost:10014"),
    ]


# Create conversation info
def get_conversation_info() -> ConversationInfo:
    """Get the conversation info for the agent."""
    return ConversationInfo(
        participants=[
            ConversationParticipant(
                role=ConversationRole.ASSISTANT,
                metadata=ConversationMetadata(
                    display_name="Travel Orchestrator",
                    description="Your central travel planning coordinator",
                ),
            )
        ]
    )


# Global agent instance
orchestrator_agent = None


async def initialize_orchestrator():
    """Initialize the orchestrator agent."""
    global orchestrator_agent
    agent_urls = get_agent_urls()
    orchestrator_agent = OrchestratorAgentA2A(agent_urls)
    await orchestrator_agent.initialize()
    logger.info("Orchestrator agent initialized with remote connections")


# Create the A2A application
def create_app() -> A2AStarletteApplication:
    """Create the A2A Starlette application."""
    # Create agent card
    agent_card = AgentCard(
        info=AGENT_INFO,
        conversation=get_conversation_info(),
    )
    
    # Create executor
    agent_executor = OrchestratorExecutor(orchestrator_agent)
    
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


if __name__ == "__main__":
    import asyncio
    
    # Initialize orchestrator first
    asyncio.run(initialize_orchestrator())
    
    # Create app
    app = create_app()
    
    # Get port
    port = int(os.getenv("ORCHESTRATOR_AGENT_PORT", "10001"))
    
    logger.info(f"Starting Orchestrator Agent on port {port}")
    logger.info(f"Agent: {AGENT_INFO.name}")
    logger.info(f"Connected agents: {list(orchestrator_agent.remote_manager.connections.keys())}")
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )