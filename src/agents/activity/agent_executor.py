"""
A2A Agent Executor for Activity Agent.
"""
import json
import uuid
from typing import Any, AsyncIterable

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    TextArtifact,
    TextPart,
    Task,
    TaskArtifact,
    TaskStatus,
)
from a2a.utils.errors import ServerError

from .activity_agent_a2a import ActivityAgentA2A


class ActivityAgentExecutor(AgentExecutor):
    """A2A executor for Activity Agent."""
    
    def __init__(self):
        self.agent = ActivityAgentA2A()
    
    async def invoke(
        self,
        context: RequestContext,
        task_updater: TaskUpdater,
        event_queue: EventQueue,
    ) -> Task:
        """Invoke the Activity Agent."""
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
                    
                    # Create artifact with the response
                    artifact = TaskArtifact(
                        id=str(uuid.uuid4()),
                        type="text",
                        title="Activity Recommendations",
                        artifact=TextArtifact(
                            parts=[TextPart(text=content)]
                        ),
                    )
                    
                    # Include data artifact if available
                    artifacts = [artifact]
                    if update.get("data"):
                        data_artifact = TaskArtifact(
                            id=str(uuid.uuid4()),
                            type="text",
                            title="Activity Data",
                            artifact=TextArtifact(
                                parts=[TextPart(text=json.dumps(update["data"], indent=2))]
                            ),
                        )
                        artifacts.append(data_artifact)
                    
                    # Update task with final result
                    await task_updater.update_task(
                        status=TaskStatus.COMPLETED,
                        artifacts=artifacts,
                    )
                    
                    return await task_updater.get_task()
                else:
                    # Progress update
                    update_text = update.get("updates", "Processing...")
                    
                    # Send progress update
                    await task_updater.update_task(
                        status=TaskStatus.IN_PROGRESS,
                    )
                    
                    if update_text != "Processing...":
                        artifact = TaskArtifact(
                            id=str(uuid.uuid4()),
                            type="text",
                            title="Status Update",
                            artifact=TextArtifact(
                                parts=[TextPart(text=update_text)]
                            ),
                        )
                        await task_updater.update_task(artifacts=[artifact])
            
            # If we get here without completing, mark as completed
            return await task_updater.update_task(status=TaskStatus.COMPLETED)
            
        except Exception as e:
            # Handle errors
            error_artifact = TaskArtifact(
                id=str(uuid.uuid4()),
                type="text",
                title="Error",
                artifact=TextArtifact(
                    parts=[TextPart(text=f"Error processing activity request: {str(e)}")]
                ),
            )
            
            await task_updater.update_task(
                status=TaskStatus.FAILED,
                artifacts=[error_artifact],
            )
            
            return await task_updater.get_task()