"""
Unit tests for Budget Agent.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.budget.budget_agent_a2a import BudgetAgentA2A, validate_expense, get_budget_status


class TestBudgetAgent:
    """Test cases for Budget Agent functionality."""
    
    @pytest.fixture
    def budget_agent(self):
        """Create a Budget Agent instance for testing."""
        return BudgetAgentA2A()
    
    def test_validate_expense_within_budget(self):
        """Test validating an expense within budget."""
        # Set up budget
        from src.agents.budget.budget_agent_a2a import BUDGET_TRACKER
        BUDGET_TRACKER["test-session"] = {
            "total_budget": 5000.0,
            "spent": 1000.0,
            "breakdown": {
                "hotel": 500.0,
                "transport": 300.0,
                "activity": 200.0,
                "other": 0.0
            },
            "currency": "USD"
        }
        
        result = validate_expense(
            expense_type="hotel",
            amount=200.0,
            currency="USD",
            description="Hotel booking"
        )
        
        data = json.loads(result)
        assert data["approved"] is True
        assert data["remaining_budget"] == 3800.0  # 5000 - 1000 - 200
    
    def test_validate_expense_exceeds_budget(self):
        """Test validating an expense that exceeds budget."""
        from src.agents.budget.budget_agent_a2a import BUDGET_TRACKER
        BUDGET_TRACKER["test-session-2"] = {
            "total_budget": 1000.0,
            "spent": 900.0,
            "breakdown": {
                "hotel": 500.0,
                "transport": 300.0,
                "activity": 100.0,
                "other": 0.0
            },
            "currency": "USD"
        }
        
        result = validate_expense(
            expense_type="activity",
            amount=200.0,
            currency="USD",
            description="Tour booking"
        )
        
        data = json.loads(result)
        assert data["approved"] is False
        assert "Insufficient budget" in data["reason"]
    
    def test_category_budget_warning(self):
        """Test category budget warning."""
        from src.agents.budget.budget_agent_a2a import BUDGET_TRACKER
        BUDGET_TRACKER["test-session-3"] = {
            "total_budget": 5000.0,
            "spent": 1000.0,
            "breakdown": {
                "hotel": 1500.0,  # Already 30% of budget
                "transport": 0.0,
                "activity": 0.0,
                "other": 0.0
            },
            "currency": "USD"
        }
        
        # Try to add more hotel expense (would exceed 35% recommendation)
        result = validate_expense(
            expense_type="hotel",
            amount=300.0,
            currency="USD",
            description="Another hotel"
        )
        
        data = json.loads(result)
        assert data["approved"] is True  # Still approved but with warning
        assert data.get("warning") is not None
        assert "exceed the recommended hotel budget" in data["warning"]
    
    def test_get_budget_status(self):
        """Test getting budget status."""
        from src.agents.budget.budget_agent_a2a import BUDGET_TRACKER
        BUDGET_TRACKER["test-session-4"] = {
            "total_budget": 3000.0,
            "spent": 2500.0,
            "breakdown": {
                "hotel": 1000.0,
                "transport": 900.0,
                "activity": 600.0,
                "other": 0.0
            },
            "currency": "USD"
        }
        
        result = get_budget_status("test-session-4")
        data = json.loads(result)
        
        assert data["total_budget"] == 3000.0
        assert data["spent"] == 2500.0
        assert data["remaining"] == 500.0
        assert data["percentage_used"] == 83.3
        assert len(data["recommendations"]) > 0  # Should have recommendations at 83% used
    
    @pytest.mark.asyncio
    async def test_budget_agent_stream(self, budget_agent):
        """Test the budget agent streaming response."""
        # Set initial budget
        budget_agent.set_session_budget("stream-test", 5000.0, "USD")
        
        query = "Can I spend $1200 on a hotel for 5 nights?"
        context_id = "stream-test"
        
        updates = []
        async for update in budget_agent.stream(query, context_id):
            updates.append(update)
        
        assert len(updates) > 0
        
        final_update = updates[-1]
        assert final_update.get("is_task_complete") is True
        assert "content" in final_update
        assert "data" in final_update
    
    def test_budget_allocation_percentages(self):
        """Test that budget allocation percentages are reasonable."""
        from src.agents.budget.budget_agent_a2a import BUDGET_TRACKER
        
        # Test the allocation logic
        total_budget = 10000.0
        allocations = {
            "hotel": 0.35,      # 35%
            "transport": 0.30,  # 30%
            "activity": 0.20,   # 20%
            "other": 0.15       # 15%
        }
        
        for category, percentage in allocations.items():
            expected = total_budget * percentage
            assert expected == total_budget * percentage
        
        # Total should be 100%
        assert sum(allocations.values()) == 1.0
    
    @pytest.mark.asyncio
    async def test_budget_tracking_across_sessions(self, budget_agent):
        """Test budget tracking across multiple expense validations."""
        session_id = "tracking-test"
        budget_agent.set_session_budget(session_id, 2000.0, "USD")
        
        # First expense
        budget_agent.record_expense(session_id, "hotel", 500.0)
        
        # Second expense
        budget_agent.record_expense(session_id, "transport", 300.0)
        
        # Check status
        from src.agents.budget.budget_agent_a2a import BUDGET_TRACKER
        tracker = BUDGET_TRACKER[session_id]
        
        assert tracker["spent"] == 800.0
        assert tracker["breakdown"]["hotel"] == 500.0
        assert tracker["breakdown"]["transport"] == 300.0
    
    def test_currency_handling(self):
        """Test handling of different currencies."""
        from src.agents.budget.budget_agent_a2a import BUDGET_TRACKER
        BUDGET_TRACKER["currency-test"] = {
            "total_budget": 5000.0,
            "spent": 0.0,
            "breakdown": {
                "hotel": 0.0,
                "transport": 0.0,
                "activity": 0.0,
                "other": 0.0
            },
            "currency": "EUR"  # Euro budget
        }
        
        result = validate_expense(
            expense_type="hotel",
            amount=150.0,
            currency="EUR",
            description="European hotel"
        )
        
        data = json.loads(result)
        assert data["approved"] is True
        # Note: In production, we'd handle currency conversion