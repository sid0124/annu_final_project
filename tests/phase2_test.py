"""Phase 2 integration test: Core Components."""

from app.core.task_engine import (
    task_engine, create_research_task, add_plan_step, get_plan,
    update_step, update_plan, get_task_statistics, StateMachine
)
from app.core.policy_engine import (
    policy_engine, check_tool_permission, check_operation,
    get_tool_registry, get_allowed_tools
)
from app.core.tool_registry import (
    tool_registry, get_tool, get_all_tools,
    get_safe_tools, get_controlled_tools, get_approval_tools
)


def test_task_engine():
    """Test task engine functionality."""
    print("=== Testing Task Engine ===")
    
    # Create task
    plan = create_research_task('Test research goal', 'user_1', 'proj_1')
    assert plan.plan_id is not None
    assert plan.goal == 'Test research goal'
    assert plan.status == 'created' or plan.status.value == 'created'
    print("✓ Task creation works")
    
    # Add step
    step = type('PlanStep', (), {
        'step_id': 'S1',
        'description': 'Test step',
        'required_tool': 'retriever',
        'risk_level': 1,
        'requires_approval': False
    })()
    result = add_plan_step(plan.plan_id, step)
    assert result is True
    print("✓ Step addition works")
    
    # Get plan
    retrieved = get_plan(plan.plan_id)
    assert retrieved is not None
    assert retrieved.plan_id == plan.plan_id
    print("✓ Plan retrieval works")
    
    # Update step status
    result = update_step(plan.plan_id, 'S1', 'completed', result={'output': 'test'})
    assert result is True
    print("✓ Step status update works")
    
    # Update plan status
    result = update_plan(plan.plan_id, 'completed')
    assert result is True
    print("✓ Plan status update works")
    
    # Get stats
    stats = get_task_statistics()
    assert isinstance(stats, dict)
    print("✓ Task statistics work")
    
    # Test state machine
    assert StateMachine.can_transition('created', 'planning') is True
    assert StateMachine.can_transition('created', 'completed') is False
    print("✓ State machine transitions work")
    
    print("✓ Task Engine tests passed\n")


def test_policy_engine():
    """Test policy engine functionality."""
    print("=== Testing Policy Engine ===")
    
    # Check tool permission
    decision = check_tool_permission('retriever', 'researcher')
    assert decision is not None
    assert decision.tool_id == 'retriever'
    assert decision.user_role == 'researcher'
    print("✓ Tool permission check works")
    
    # Check denied tool
    decision = check_tool_permission('python_sandbox', 'end_user')
    assert decision.decision in ('DENY', 'REQUIRE_APPROVAL')
    print("✓ Denied tool check works")
    
    # Check allowed tool
    decision = check_tool_permission('calculator', 'end_user')
    assert decision.decision == 'ALLOW'
    print("✓ Allowed tool check works")
    
    # Get all tools
    tools = get_all_tools()
    assert len(tools) > 0
    print(f"✓ Tool registry has {len(tools)} tools")
    
    # Get allowed tools for role
    allowed = get_allowed_tools('researcher')
    assert len(allowed) > 0
    print(f"✓ Allowed tools for researcher: {len(allowed)} tools")
    
    # Get safe tools
    safe = get_safe_tools()
    assert 'calculator' in safe
    print("✓ Safe tools identification works")
    
    # Get controlled tools
    controlled = get_controlled_tools()
    assert 'python_sandbox' in controlled
    print("✓ Controlled tools identification works")
    
    # Get approval tools
    approval = get_approval_tools()
    assert 'python_sandbox' in approval
    print("✓ Approval tools identification works")
    
    print("✓ Policy Engine tests passed\n")


def test_tool_registry():
    """Test tool registry functionality."""
    print("=== Testing Tool Registry ===")
    
    # Get all tools
    all_tools = get_all_tools()
    assert len(all_tools) > 0
    print(f"✓ All tools registered: {len(all_tools)}")
    
    # Get specific tool
    tool = get_tool('retriever')
    assert tool is not None
    assert tool.name == 'Research Retrieval'
    print("✓ Tool retrieval works")
    
    # Get safe tools
    safe = get_safe_tools()
    assert 'calculator' in safe
    print("✓ Safe tools filter works")
    
    # Get controlled tools
    controlled = get_controlled_tools()
    assert 'python_sandbox' in controlled
    print("✓ Controlled tools filter works")
    
    # Get approval tools
    approval = get_approval_tools()
    assert 'python_sandbox' in approval
    print("✓ Approval tools filter works")
    
    # Get tools by risk level
    low_risk = tool_registry.get_tools_by_risk(type('RiskLevel', (), {'LEVEL_0': 0, 'LEVEL_1': 1})())
    # Simpler check
    safe_tools = [t for t in all_tools.values() if t.risk_level.value <= 1]
    assert len(low_risk) > 0
    print("✓ Risk-level filtering works")
    
    # Search tools by capability
    matching = tool_registry.search_tools('search')
    assert len(matching) > 0
    print("✓ Tool search by capability works")
    
    # Get risk distribution
    dist = tool_registry.get_tool_risk_distribution()
    assert isinstance(dist, dict)
    print("✓ Risk distribution calculation works")
    
    print("✓ Tool Registry tests passed\n")


def test_integration():
    """Test integration between components."""
    print("=== Testing Integration ===")
    
    # Create task with step
    plan = create_research_task('Integration test', 'user_1', 'proj_1')
    step = type('PlanStep', (), {
        'step_id': 'S1',
        'description': 'Integration test step',
        'required_tool': 'retriever',
        'risk_level': 1,
        'requires_approval': False
    })()
    add_plan_step(plan.plan_id, step)
    
    # Check permissions
    decision = check_tool_permission('retriever', 'researcher')
    assert decision.decision in ('ALLOW', 'REQUIRE_APPROVAL')
    
    # Update step
    update_step(plan.plan_id, 'S1', 'completed', result={'output': 'Integration successful'})
    
    # Get updated plan
    retrieved = get_plan(plan.plan_id)
    assert retrieved is not None
    
    # Get stats
    stats = get_task_statistics()
    assert isinstance(stats, dict)
    
    print("✓ Integration between components works")
    print("✓ Integration tests passed\n")


if __name__ == "__main__":
    test_task_engine()
    test_policy_engine()
    test_tool_registry()
    test_integration()
    print("=" * 50)
    print("ALL PHASE 2 TESTS PASSED!")
    print("=" * 50)