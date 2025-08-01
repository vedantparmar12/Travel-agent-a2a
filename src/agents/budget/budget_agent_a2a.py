"""
Budget Agent implementation for A2A protocol.
"""
import json
from typing import Any, AsyncIterable, Dict, List, Optional
from datetime import datetime
import uuid

from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from ...shared.llm_config import LLMConfig


memory = MemorySaver()


class BudgetValidationInput(BaseModel):
    """Input schema for budget validation."""
    expense_type: str = Field(..., description="Type of expense: hotel, transport, activity")
    amount: float = Field(..., description="Amount to validate")
    currency: str = Field("USD", description="Currency code")
    description: str = Field(..., description="Description of the expense")


class BudgetStatusInput(BaseModel):
    """Input schema for budget status check."""
    session_id: str = Field(..., description="Travel session ID")


class BudgetResponseFormat(BaseModel):
    """Response format for budget agent."""
    status: str = Field("completed", description="Status of the response")
    message: str = Field(..., description="Response message")
    approved: bool = Field(False, description="Whether the expense is approved")
    total_budget: float = Field(..., description="Total budget for the trip")
    spent: float = Field(..., description="Amount already spent")
    remaining: float = Field(..., description="Remaining budget")
    breakdown: Dict[str, float] = Field(default_factory=dict, description="Spending breakdown by category")
    recommendations: List[str] = Field(default_factory=list, description="Budget recommendations")


# In-memory budget tracking (in production, use Redis or database)
BUDGET_TRACKER = {}


@tool(args_schema=BudgetValidationInput)
def validate_expense(
    expense_type: str,
    amount: float,
    currency: str = "USD",
    description: str = ""
) -> str:
    """Validate if an expense fits within the budget."""
    # Get or create session budget (in production, this would come from state)
    session_id = "default_session"  # Would be passed in real implementation
    
    if session_id not in BUDGET_TRACKER:
        BUDGET_TRACKER[session_id] = {
            "total_budget": 5000.0,  # Default budget
            "spent": 0.0,
            "breakdown": {
                "hotel": 0.0,
                "transport": 0.0,
                "activity": 0.0,
                "other": 0.0
            },
            "currency": "USD"
        }
    
    budget_data = BUDGET_TRACKER[session_id]
    remaining = budget_data["total_budget"] - budget_data["spent"]
    
    # Check if expense can be approved
    if amount > remaining:
        return json.dumps({
            "approved": False,
            "reason": "Insufficient budget",
            "remaining_budget": remaining,
            "requested_amount": amount,
            "recommendation": f"This {expense_type} expense of {currency} {amount} exceeds your remaining budget of {currency} {remaining}"
        })
    
    # Check if expense is reasonable for category
    budget_allocation = {
        "hotel": 0.35,      # 35% of budget
        "transport": 0.30,  # 30% of budget
        "activity": 0.20,   # 20% of budget
        "other": 0.15       # 15% buffer
    }
    
    category_budget = budget_data["total_budget"] * budget_allocation.get(expense_type, 0.15)
    category_spent = budget_data["breakdown"].get(expense_type, 0.0)
    
    warning = None
    if category_spent + amount > category_budget:
        warning = f"This will exceed the recommended {expense_type} budget of {currency} {category_budget}"
    
    # Approve the expense
    return json.dumps({
        "approved": True,
        "remaining_budget": remaining - amount,
        "category_budget": category_budget,
        "category_spent": category_spent,
        "warning": warning,
        "percentage_used": ((budget_data["spent"] + amount) / budget_data["total_budget"]) * 100
    })


@tool(args_schema=BudgetStatusInput)
def get_budget_status(session_id: str = "default_session") -> str:
    """Get current budget status and breakdown."""
    if session_id not in BUDGET_TRACKER:
        return json.dumps({
            "error": "No budget found for this session",
            "session_id": session_id
        })
    
    budget_data = BUDGET_TRACKER[session_id]
    remaining = budget_data["total_budget"] - budget_data["spent"]
    percentage_used = (budget_data["spent"] / budget_data["total_budget"]) * 100 if budget_data["total_budget"] > 0 else 0
    
    # Generate recommendations based on spending
    recommendations = []
    if percentage_used > 80:
        recommendations.append("You've used over 80% of your budget. Consider more economical options.")
    if percentage_used > 90:
        recommendations.append("Critical: Less than 10% of budget remaining!")
    
    # Check category spending
    for category, spent in budget_data["breakdown"].items():
        if spent > 0:
            category_percentage = (spent / budget_data["total_budget"]) * 100
            if category == "hotel" and category_percentage > 40:
                recommendations.append("Hotel costs are high. Consider more budget-friendly accommodations.")
            elif category == "transport" and category_percentage > 35:
                recommendations.append("Transport costs are significant. Look for alternative routes or booking times.")
    
    return json.dumps({
        "total_budget": budget_data["total_budget"],
        "spent": budget_data["spent"],
        "remaining": remaining,
        "percentage_used": round(percentage_used, 1),
        "breakdown": budget_data["breakdown"],
        "currency": budget_data["currency"],
        "recommendations": recommendations
    })


class BudgetAgentA2A:
    """Budget Agent for A2A protocol."""
    
    SYSTEM_INSTRUCTION = """You are a Budget Management Agent responsible for tracking and validating travel expenses.

Your responsibilities:
1. Validate all expenses against the available budget
2. Track spending by category (hotel, transport, activities)
3. Provide warnings when approaching budget limits
4. Suggest cost-saving alternatives when needed
5. Ensure the trip stays within financial constraints

When validating expenses:
- Use the validate_expense tool to check if an expense can be approved
- Use the get_budget_status tool to provide budget summaries
- Consider the overall trip budget and category allocations
- Provide clear approval or rejection with reasoning
- Suggest alternatives if an expense is too high

Budget allocation guidelines:
- Hotels: ~35% of total budget
- Transport: ~30% of total budget
- Activities: ~20% of total budget
- Buffer/Other: ~15% of total budget

Always provide:
- Clear approval/rejection status
- Current budget status after the expense
- Warnings if approaching limits
- Cost-saving recommendations when appropriate

Remember: Your role is to ensure financial responsibility while helping create a great travel experience."""
    
    def __init__(self):
        self.model = LLMConfig.get_agent_llm("budget")
        self.tools = [validate_expense, get_budget_status]
        
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=BudgetResponseFormat,
        )
    
    def set_session_budget(self, session_id: str, total_budget: float, currency: str = "USD"):
        """Set the budget for a session."""
        BUDGET_TRACKER[session_id] = {
            "total_budget": total_budget,
            "spent": 0.0,
            "breakdown": {
                "hotel": 0.0,
                "transport": 0.0,
                "activity": 0.0,
                "other": 0.0
            },
            "currency": currency
        }
    
    def record_expense(self, session_id: str, expense_type: str, amount: float):
        """Record an approved expense."""
        if session_id in BUDGET_TRACKER:
            BUDGET_TRACKER[session_id]["spent"] += amount
            if expense_type in BUDGET_TRACKER[session_id]["breakdown"]:
                BUDGET_TRACKER[session_id]["breakdown"][expense_type] += amount
            else:
                BUDGET_TRACKER[session_id]["breakdown"]["other"] += amount
    
    async def stream(self, query: str, context_id: str) -> AsyncIterable[Dict[str, Any]]:
        """Stream the agent's response."""
        config = {"configurable": {"thread_id": context_id}}
        
        # Check if this is a budget setup request
        if "total budget" in query.lower() and any(curr in query for curr in ["$", "USD", "EUR", "GBP"]):
            # Extract budget amount (simple extraction, in production use NLP)
            import re
            numbers = re.findall(r'\d+(?:,\d+)*(?:\.\d+)?', query)
            if numbers:
                budget_amount = float(numbers[0].replace(',', ''))
                self.set_session_budget(context_id, budget_amount, "USD")
        
        inputs = {"messages": [("user", query)]}
        
        # Stream processing
        for item in self.graph.stream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            
            if hasattr(message, 'tool_calls') and message.tool_calls:
                yield {
                    "is_task_complete": False,
                    "updates": "Checking budget constraints..."
                }
        
        # Get final response
        yield self._get_final_response(config)
    
    def _get_final_response(self, config) -> Dict[str, Any]:
        """Get the final response from the agent."""
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")
        
        if structured_response and isinstance(structured_response, BudgetResponseFormat):
            content_parts = [f"**{structured_response.message}**\n"]
            
            # Approval status
            if hasattr(structured_response, 'approved'):
                if structured_response.approved:
                    content_parts.append("✅ **Expense Approved**")
                else:
                    content_parts.append("❌ **Expense Not Approved**")
            
            # Budget summary
            content_parts.append(f"\n💰 **Budget Status:**")
            content_parts.append(f"- Total Budget: ${structured_response.total_budget:,.2f}")
            content_parts.append(f"- Spent: ${structured_response.spent:,.2f}")
            content_parts.append(f"- Remaining: ${structured_response.remaining:,.2f}")
            
            # Breakdown if available
            if structured_response.breakdown:
                content_parts.append(f"\n📊 **Spending Breakdown:**")
                for category, amount in structured_response.breakdown.items():
                    if amount > 0:
                        percentage = (amount / structured_response.total_budget) * 100
                        content_parts.append(f"- {category.title()}: ${amount:,.2f} ({percentage:.1f}%)")
            
            # Recommendations
            if structured_response.recommendations:
                content_parts.append(f"\n💡 **Recommendations:**")
                for rec in structured_response.recommendations:
                    content_parts.append(f"- {rec}")
            
            return {
                "is_task_complete": True,
                "content": "\n".join(content_parts),
                "data": {
                    "approved": structured_response.approved,
                    "budget_status": {
                        "total": structured_response.total_budget,
                        "spent": structured_response.spent,
                        "remaining": structured_response.remaining
                    }
                }
            }
        
        return {
            "is_task_complete": False,
            "content": "Unable to process budget request. Please try again.",
            "data": {}
        }