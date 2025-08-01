"""
Orchestrator Agent implementation with A2A protocol.
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncIterable, List, Dict, Optional

from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ...shared.llm_config import LLMConfig

from .remote_agent_connection import RemoteAgentManager
from .tools import TaskAnalyzer, ConflictResolver, DependencyManager
from ...shared.models import TravelPreferences


memory = MemorySaver()


class AgentTaskInput(BaseModel):
    """Input for sending tasks to agents."""
    agent_name: str = Field(..., description="Name of the agent to send task to")
    task: str = Field(..., description="Task description for the agent")


class TripPlanningInput(BaseModel):
    """Input for trip planning."""
    destination: str = Field(..., description="Destination city")
    origin: str = Field(..., description="Origin city")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    budget: float = Field(..., description="Total budget")
    travelers: int = Field(..., description="Number of travelers")


class OrchestratorResponseFormat(BaseModel):
    """Response format for orchestrator."""
    status: str = Field("in_progress", description="Current status")
    message: str = Field(..., description="Status message")
    agents_contacted: List[str] = Field(default_factory=list)
    bookings_confirmed: Dict[str, Any] = Field(default_factory=dict)
    next_steps: List[str] = Field(default_factory=list)


class OrchestratorAgentA2A:
    """Orchestrator Agent using A2A protocol."""
    
    SYSTEM_INSTRUCTION = """You are the Orchestrator Agent, the central coordinator for a multi-agent travel planning system.

Your responsibilities:
1. Coordinate with specialist agents (Hotel, Transport, Activity, Budget, Itinerary)
2. Distribute tasks based on user preferences and dependencies
3. Monitor progress and resolve conflicts between bookings
4. Ensure all bookings align with budget and preferences
5. Generate a complete travel itinerary

Available agents and their capabilities:
- Hotel_Agent: Searches and books accommodations
- Transport_Agent: Books flights, trains, and ground transport
- Activity_Agent: Finds and books local experiences
- Budget_Agent: Monitors spending and validates costs
- Itinerary_Agent: Creates the final travel plan

Workflow:
1. When a user requests trip planning, analyze their requirements
2. Use the send_task_to_agent tool to delegate specific tasks to each agent
3. Hotel and Transport can be contacted in parallel
4. Activity Agent should be contacted after Hotel (needs location)
5. Budget Agent should validate all major expenses
6. Itinerary Agent creates the final plan after all bookings

Important:
- Always be explicit about which agent you're contacting
- Frame requests clearly with all necessary details
- Monitor responses and handle any conflicts
- Keep the user informed of progress"""
    
    def __init__(self, remote_agent_urls: List[str]):
        self.model = LLMConfig.get_agent_llm("orchestrator")
        self.remote_manager = RemoteAgentManager()
        self.task_analyzer = TaskAnalyzer()
        self.conflict_resolver = ConflictResolver()
        self.dependency_manager = DependencyManager()
        
        # Tools will be set after initialization
        self.tools = []
        self.graph = None
        
        # Store agent URLs for async initialization
        self._agent_urls = remote_agent_urls
    
    async def initialize(self):
        """Initialize connections to remote agents."""
        # Connect to all remote agents
        for url in self._agent_urls:
            await self.remote_manager.add_agent(url)
        
        # Create tools with the remote manager
        self.tools = [
            self._create_send_task_tool(),
            self._create_analyze_responses_tool(),
        ]
        
        # Create the agent graph
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self._get_augmented_prompt(),
            response_format=OrchestratorResponseFormat,
        )
    
    def _get_augmented_prompt(self) -> str:
        """Get the prompt with available agents."""
        agents_info = []
        for name, card in self.remote_manager.get_all_agents().items():
            agents_info.append(f"- {name}: {card.info.description}")
        
        agents_list = "\n".join(agents_info) if agents_info else "No agents connected"
        
        return f"""{self.SYSTEM_INSTRUCTION}

Currently connected agents:
{agents_list}

Today's date: {datetime.now().strftime('%Y-%m-%d')}"""
    
    def _create_send_task_tool(self):
        """Create the tool for sending tasks to agents."""
        remote_manager = self.remote_manager
        
        @tool(args_schema=AgentTaskInput)
        async def send_task_to_agent(agent_name: str, task: str) -> str:
            """Send a task to a specific agent and get their response."""
            connection = remote_manager.get_connection(agent_name)
            
            if not connection:
                return json.dumps({
                    "error": f"Agent {agent_name} not found. Available agents: {list(remote_manager.connections.keys())}"
                })
            
            try:
                # Create message request
                message_id = str(uuid.uuid4())
                task_id = str(uuid.uuid4())
                context_id = str(uuid.uuid4())
                
                payload = {
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": task}],
                        "messageId": message_id,
                        "taskId": task_id,
                        "contextId": context_id,
                    },
                }
                
                message_request = SendMessageRequest(
                    id=message_id, 
                    params=MessageSendParams.model_validate(payload)
                )
                
                # Send message
                response: SendMessageResponse = await connection.send_message(message_request)
                
                # Process response
                if isinstance(response.root, SendMessageSuccessResponse) and isinstance(response.root.result, Task):
                    # Extract response content
                    response_parts = []
                    if response.root.result.artifacts:
                        for artifact in response.root.result.artifacts:
                            if hasattr(artifact.artifact, 'parts'):
                                for part in artifact.artifact.parts:
                                    if hasattr(part, 'text'):
                                        response_parts.append(part.text)
                    
                    return json.dumps({
                        "agent": agent_name,
                        "status": response.root.result.status,
                        "response": "\n".join(response_parts) if response_parts else "Task received",
                    })
                else:
                    return json.dumps({
                        "agent": agent_name,
                        "error": "Invalid response format"
                    })
                    
            except Exception as e:
                return json.dumps({
                    "agent": agent_name,
                    "error": f"Communication error: {str(e)}"
                })
        
        return send_task_to_agent
    
    def _create_analyze_responses_tool(self):
        """Create tool for analyzing agent responses."""
        @tool
        def analyze_agent_responses(responses: List[Dict[str, Any]]) -> str:
            """Analyze responses from multiple agents to find common availability or conflicts."""
            try:
                # Group responses by type
                hotel_responses = [r for r in responses if r.get("agent") == "Hotel_Agent"]
                transport_responses = [r for r in responses if r.get("agent") == "Transport_Agent"]
                
                analysis = {
                    "summary": f"Analyzed {len(responses)} agent responses",
                    "hotels_found": len(hotel_responses),
                    "transport_found": len(transport_responses),
                    "conflicts": [],
                    "recommendations": []
                }
                
                # Check for timing conflicts
                # This is simplified - in production, would do deeper analysis
                if hotel_responses and transport_responses:
                    analysis["recommendations"].append("Check that flight arrival aligns with hotel check-in time")
                
                return json.dumps(analysis)
                
            except Exception as e:
                return json.dumps({"error": f"Analysis failed: {str(e)}"})
        
        return analyze_agent_responses
    
    async def stream(self, query: str, context_id: str) -> AsyncIterable[Dict[str, Any]]:
        """Stream the orchestrator's response."""
        if not self.graph:
            yield {
                "is_task_complete": False,
                "content": "Orchestrator not initialized. Please wait..."
            }
            return
        
        config = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [("user", query)]}
        
        # Stream processing
        for item in self.graph.stream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            
            # Yield progress updates
            if hasattr(message, 'tool_calls') and message.tool_calls:
                yield {
                    "is_task_complete": False,
                    "updates": "Coordinating with travel agents..."
                }
        
        # Get final response
        yield self._get_final_response(config)
    
    def _get_final_response(self, config) -> Dict[str, Any]:
        """Format the final response."""
        current_state = self.graph.get_state(config)
        response = current_state.values.get("structured_response")
        
        if response and isinstance(response, OrchestratorResponseFormat):
            content_parts = [f"**{response.message}**\n"]
            
            if response.agents_contacted:
                content_parts.append(f"\n✓ Contacted agents: {', '.join(response.agents_contacted)}")
            
            if response.bookings_confirmed:
                content_parts.append("\n**Confirmed Bookings:**")
                for booking_type, details in response.bookings_confirmed.items():
                    content_parts.append(f"- {booking_type}: {details}")
            
            if response.next_steps:
                content_parts.append("\n**Next Steps:**")
                for step in response.next_steps:
                    content_parts.append(f"- {step}")
            
            return {
                "is_task_complete": response.status == "completed",
                "content": "\n".join(content_parts),
                "data": {
                    "status": response.status,
                    "bookings": response.bookings_confirmed
                }
            }
        
        return {
            "is_task_complete": False,
            "content": "Processing your travel request...",
            "data": {}
        }