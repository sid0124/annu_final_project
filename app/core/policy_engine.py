"""
VTR-Agent: Policy Engine

Policy and permission enforcement for tool execution and research operations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from vtr_agent.core.config import get_settings
from vtr_agent.utils import get_role_permissions, RiskLevel


class PolicyDecision(BaseModel):
    """Policy engine decision output."""
    decision: str  # "ALLOW", "DENY", "REQUIRE_APPROVAL"
    reason: str
    requires_approval: bool
    risk_level: RiskLevel
    tool_id: str
    user_role: str
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None
    conditions: Dict[str, Any] = Field(default_factory=dict)


class ToolPermission(BaseModel):
    """Tool permission metadata."""
    tool_id: str
    tool_name: str
    risk_level: RiskLevel
    permissions: List[str]
    requires_human_approval: bool
    network_allowed: bool
    filesystem_access: str  # "none", "readonly", "readwrite", "sandbox_only"
    description: str


class PolicyEngine:
    """Policy engine that controls tool execution and research operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.tool_registry: Dict[str, ToolPermission] = {}
        self._init_default_tools()
    
    def _init_default_tools(self) -> None:
        """Initialize default tool permissions."""
        self.register_tool("retriever", ToolPermission(
            tool_id="retriever",
            tool_name="Research Retrieval",
            risk_level=RiskLevel.LEVEL_1,
            permissions=["search", "read_document"],
            requires_human_approval=False,
            network_allowed=False,
            filesystem_access="readonly",
            description="Search approved research corpus and retrieve documents"
        ))
        
        self.register_tool("python_sandbox", ToolPermission(
            tool_id="python_sandbox",
            tool_name="Python Sandbox",
            risk_level=RiskLevel.LEVEL_2,
            permissions=["execute_code", "data_analysis", "math"],
            requires_human_approval=True,
            network_allowed=False,
            filesystem_access="sandbox_only",
            description="Execute Python code in isolated sandbox environment"
        ))
        
        self.register_tool("calculator", ToolPermission(
            tool_id="calculator",
            tool_name="Mathematical Calculator",
            risk_level=RiskLevel.LEVEL_0,
            permissions=["basic_math", "statistics"],
            requires_human_approval=False,
            network_allowed=False,
            filesystem_access="none",
            description="Perform mathematical calculations"
        ))
        
        self.register_tool("visualizer", ToolPermission(
            tool_id="visualizer",
            tool_name="Data Visualization",
            risk_level=RiskLevel.LEVEL_1,
            permissions=["create_charts", "generate_plots"],
            requires_human_approval=False,
            network_allowed=False,
            filesystem_access="sandbox_only",
            description="Create charts and visualizations"
        ))
        
        self.register_tool("evidence_tool", ToolPermission(
            tool_id="evidence_tool",
            tool_name="Evidence Manager",
            risk_level=RiskLevel.LEVEL_1,
            permissions=["store_evidence", "link_claim"],
            requires_human_approval=False,
            network_allowed=False,
            filesystem_access="output_directory",
            description="Store source/evidence relationships and provenance"
        ))
    
    def register_tool(self, tool_id: str, tool_perm: ToolPermission) -> None:
        """Register a new tool with its permissions."""
        self.tool_registry[tool_id] = tool_perm
    
    def check_tool_permission(
        self, 
        tool_id: str, 
        user_role: str, 
        operation: str = "execute"
    ) -> PolicyDecision:
        """Check if a user role can execute a tool."""
        tool = self.tool_registry.get(tool_id)
        if not tool:
            return PolicyDecision(
                decision="DENY",
                reason=f"Tool '{tool_id}' not registered in policy engine",
                requires_approval=False,
                risk_level=RiskLevel.LEVEL_3,
                tool_id=tool_id,
                user_role=user_role
            )
        
        # Check role permissions
        role_perms = get_role_permissions(user_role)
        if tool.risk_level == RiskLevel.LEVEL_3:
            has_permission = False
        elif tool.risk_level == RiskLevel.LEVEL_0:
            has_permission = True
        elif user_role == "admin":
            has_permission = True
        elif role_perms.get("request_tool", False):
            has_permission = True
        elif user_role == "reviewer" and tool.risk_level <= RiskLevel.LEVEL_1:
            has_permission = True
        else:
            has_permission = False
        
        # Determine risk and approval requirements
        requires_approval = tool.requires_human_approval and user_role != "admin"
        risk_level = tool.risk_level
        
        # Decision logic
        if not has_permission:
            decision = "DENY"
            reason = f"User role '{user_role}' does not have permission for tool '{tool_id}'"
        elif requires_approval and operation == "execute":
            decision = "REQUIRE_APPROVAL"
            reason = f"Tool '{tool_id}' requires human approval (risk level {risk_level.value})"
        elif risk_level.value >= 2 and user_role not in ("admin", "expert"):
            decision = "REQUIRE_APPROVAL"
            reason = f"Tool '{tool_id}' has high risk (level {risk_level.value}) requiring approval"
        else:
            decision = "ALLOW"
            reason = f"Tool '{tool_id}' allowed for role '{user_role}' (risk level {risk_level.value})"
        
        return PolicyDecision(
            decision=decision,
            reason=reason,
            requires_approval=requires_approval,
            risk_level=risk_level,
            tool_id=tool_id,
            user_role=user_role,
        )
    
    def check_operation(
        self, 
        tool_id: str, 
        user_role: str, 
        operation: str = "execute",
        context: Optional[Dict[str, Any]] = None
    ) -> PolicyDecision:
        """Full operation check including context awareness."""
        # Base permission check
        base_decision = self.check_tool_permission(tool_id, user_role, operation)

        if base_decision.decision == "ALLOW":
            # Additional context checks
            tool = self.tool_registry.get(tool_id)  # look up once here
            if context and tool:
                # Check for sensitive data operations
                if self._requires_sensitive_data_check(tool_id, context):
                    if not self._has_sensitive_data_permission(user_role):
                        base_decision = PolicyDecision(
                            decision="DENY",
                            reason="Sensitive data operation blocked without proper permissions",
                            requires_approval=True,
                            risk_level=base_decision.risk_level,
                            tool_id=tool_id,
                            user_role=user_role
                        )

                # Check for network operations
                if self._requires_network_check(tool_id, context):
                    if not tool.network_allowed and user_role != "admin":
                        if base_decision.decision == "ALLOW":
                            base_decision = PolicyDecision(
                                decision="DENY",
                                reason="Network access not allowed for this tool",
                                requires_approval=base_decision.requires_approval,
                                risk_level=base_decision.risk_level,
                                tool_id=tool_id,
                                user_role=user_role
                            )

        return base_decision
    
    def _requires_sensitive_data_check(self, tool_id: str, context: Dict) -> bool:
        """Check if tool operation requires sensitive data protection."""
        sensitive_tools = ["python_sandbox", "visualizer"]
        return tool_id in sensitive_tools and context is not None
    
    def _has_sensitive_data_permission(self, user_role: str) -> bool:
        """Check if user role has sensitive data permissions."""
        perms = get_role_permissions(user_role)
        return perms.get("manage_users", False) or user_role in ("admin", "expert")
    
    def _requires_network_check(self, tool_id: str, context: Dict) -> bool:
        """Check if tool operation requires network access check."""
        network_tools = []
        return tool_id in network_tools
    
    def get_tool_info(self, tool_id: str) -> Optional[ToolPermission]:
        """Get tool permission information."""
        return self.tool_registry.get(tool_id)
    
    def get_all_tools(self) -> Dict[str, ToolPermission]:
        """Get all registered tools."""
        return self.tool_registry.copy()
    
    def get_allowed_tools(self, user_role: str) -> Dict[str, ToolPermission]:
        """Get tools allowed for a specific user role."""
        allowed = {}
        for tool_id, tool in self.tool_registry.items():
            decision = self.check_tool_permission(tool_id, user_role)
            if decision.decision in ("ALLOW", "REQUIRE_APPROVAL"):
                allowed[tool_id] = tool
        return allowed


# Global policy engine instance
policy_engine = PolicyEngine()


# Convenience functions
def check_tool_permission(
    tool_id: str, 
    user_role: str, 
    operation: str = "execute"
) -> PolicyDecision:
    """Check if a user can execute a tool."""
    return policy_engine.check_tool_permission(tool_id, user_role, operation)


def check_operation(
    tool_id: str, 
    user_role: str, 
    operation: str = "execute",
    context: Optional[Dict[str, Any]] = None
) -> PolicyDecision:
    """Full operation check with context awareness."""
    return policy_engine.check_operation(tool_id, user_role, operation, context)


def get_tool_registry() -> Dict[str, ToolPermission]:
    """Get all registered tools."""
    return policy_engine.get_all_tools()


def get_allowed_tools(user_role: str) -> Dict[str, ToolPermission]:
    """Get tools allowed for a user role."""
    return policy_engine.get_allowed_tools(user_role)