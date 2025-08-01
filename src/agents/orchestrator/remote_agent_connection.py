"""
Remote agent connection management for A2A protocol.
"""
from typing import Callable, Dict, Any, Optional
import httpx
from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    SendMessageRequest,
    SendMessageResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)


TaskCallbackArg = Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent
TaskUpdateCallback = Callable[[TaskCallbackArg, AgentCard], Task]


class RemoteAgentConnection:
    """A class to hold the connection to a remote agent."""
    
    def __init__(self, agent_card: AgentCard, agent_url: str):
        print(f"Connecting to agent: {agent_card.info.name}")
        print(f"Agent URL: {agent_url}")
        
        self._httpx_client = httpx.AsyncClient(timeout=30)
        self.agent_client = A2AClient(self._httpx_client, agent_card, url=agent_url)
        self.card = agent_card
        self.url = agent_url
        self.conversation_name = None
        self.conversation = None
        self.pending_tasks = set()
    
    def get_agent(self) -> AgentCard:
        """Get the agent card."""
        return self.card
    
    def get_agent_name(self) -> str:
        """Get the agent name."""
        return self.card.info.name
    
    def get_agent_description(self) -> str:
        """Get the agent description."""
        return self.card.info.description
    
    async def send_message(
        self, message_request: SendMessageRequest
    ) -> SendMessageResponse:
        """Send a message to the remote agent."""
        return await self.agent_client.send_message(message_request)
    
    async def close(self):
        """Close the connection."""
        await self._httpx_client.aclose()


class RemoteAgentManager:
    """Manages connections to remote agents."""
    
    def __init__(self):
        self.connections: Dict[str, RemoteAgentConnection] = {}
        self.agent_urls: Dict[str, str] = {}
    
    async def add_agent(self, agent_url: str) -> Optional[RemoteAgentConnection]:
        """Add a remote agent by URL."""
        try:
            # Create temporary client to get agent card
            async with httpx.AsyncClient(timeout=30) as client:
                from a2a.client import A2ACardResolver
                card_resolver = A2ACardResolver(client, agent_url)
                card = await card_resolver.get_agent_card()
            
            # Create connection
            connection = RemoteAgentConnection(card, agent_url)
            agent_name = connection.get_agent_name()
            
            self.connections[agent_name] = connection
            self.agent_urls[agent_name] = agent_url
            
            print(f"Successfully connected to {agent_name}")
            return connection
            
        except Exception as e:
            print(f"Failed to connect to agent at {agent_url}: {e}")
            return None
    
    def get_connection(self, agent_name: str) -> Optional[RemoteAgentConnection]:
        """Get a connection by agent name."""
        return self.connections.get(agent_name)
    
    def get_all_agents(self) -> Dict[str, AgentCard]:
        """Get all connected agents."""
        return {
            name: conn.card 
            for name, conn in self.connections.items()
        }
    
    async def close_all(self):
        """Close all connections."""
        for connection in self.connections.values():
            await connection.close()
        self.connections.clear()