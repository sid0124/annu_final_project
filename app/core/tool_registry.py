"""
VTR-Agent: Tool Registry

Central registry for approved tools with metadata, permissions, and availability.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from vtr_agent.core.policy_engine import ToolPermission, policy_engine
from vtr_agent.utils import RiskLevel


class ToolMetadata(BaseModel):
    """Tool metadata for registry display."""
    tool_id: str
    name: str
    description: str
    version: str = "1.0.0"
    risk_level: RiskLevel
    requires_approval: bool
    estimated_latency: Optional[float] = None  # seconds
    supports: List[str] = Field(default_factory=list)  # Supported operation types


class ToolRegistry:
    """Central registry for all approved research tools."""
    
    def __init__(self):
        self.tools: Dict[str, ToolMetadata] = {}
        self._init_default_registry()
    
    def _init_default_registry(self) -> None:
        """Initialize with default approved tools."""
        # Register tools through the policy engine
        policy_engine._init_default_tools()
        
        # Build metadata from policy engine
        for tool_id, tool_perm in policy_engine.tool_registry.items():
            self.tools[tool_id] = ToolMetadata(
                tool_id=tool_id,
                name=tool_perm.tool_name,
                description=tool_perm.description,
                risk_level=tool_perm.risk_level,
                requires_approval=tool_perm.requires_human_approval,
                estimated_latency=self._estimate_latency(tool_id),
                supports=self._get_tool_capabilities(tool_id)
            )
    
    def _estimate_latency(self, tool_id: str) -> Optional[float]:
        """Estimate execution latency for a tool."""
        latency_map = {
            "calculator": 0.5,
            "retriever": 2.0,
            "calculator": 0.5,
            "python_sandbox": 15.0,
            "visualizer": 5.0,
            "evidence_tool": 1.0,
        }
        return latency_map.get(tool_id)
    
    def _get_tool_capabilities(self, tool_id: str) -> List[str]:
        """Get tool capabilities/supported operations."""
        capability_map = {
            "calculator": ["basic_math", "statistics"],
            "retriever": ["search", "read_document"],
            "python_sandbox": ["execute_code", "data_analysis", "math"],
            "visualizer": ["create_charts", "generate_plots"],
            "evidence_tool": ["store_evidence", "link_claim"],
        }
        return capability_map.get(tool_id, [])
    
    def register_tool(self, tool_id: str, metadata: ToolMetadata) -> bool:
        """Register a new tool in the registry."""
        # Also register with policy engine
        tool_perm = ToolPermission(
            tool_id=tool_id,
            tool_name=metadata.name,
            risk_level=metadata.risk_level,
            permissions=metadata.supports,
            requires_human_approval=metadata.requires_approval,
            network_allowed=metadata.filesystem_access != "none",
            filesystem_access=metadata.filesystem_access,
            description=metadata.description
        )
        policy_engine.register_tool(tool_id, tool_perm)
        self.tools[tool_id] = metadata
        return True
    
    def get_tool(self, tool_id: str) -> Optional[ToolMetadata]:
        """Get tool metadata by ID."""
        return self.tools.get(tool_id)
    
    def get_all_tools(self) -> Dict[str, ToolMetadata]:
        """Get all registered tools."""
        return self.tools.copy()
    
    def get_allowed_tools(self, user_role: str) -> Dict[str, ToolMetadata]:
        """Get tools allowed for a specific user role."""
        allowed = {}
        for tool_id, tool in self.tools.items():
            decision = policy_engine.check_tool_permission(tool_id, user_role)
            if decision.decision in ("ALLOW", "REQUIRE_APPROVAL"):
                allowed[tool_id] = tool
        return allowed
    
    def get_tools_by_risk(self, max_risk: Any) -> Dict[str, ToolMetadata]:
        """Get tools with risk level at or below specified maximum."""
        if isinstance(max_risk, int):
            max_val = max_risk
        elif hasattr(max_risk, "value") and isinstance(max_risk.value, int):
            max_val = max_risk.value
        elif hasattr(max_risk, "LEVEL_1"):
            max_val = getattr(max_risk, "LEVEL_1")
        else:
            max_val = 1

        allowed = {}
        for tool_id, tool in self.tools.items():
            tool_val = tool.risk_level.value if hasattr(tool.risk_level, "value") else int(tool.risk_level)
            if tool_val <= max_val:
                allowed[tool_id] = tool
        return allowed
    
    def search_tools(self, capability: str) -> List[ToolMetadata]:
        """Search tools by capability."""
        return [t for t in self.tools.values() if capability in t.supports]

    def get_tool_risk_distribution(self) -> Dict[int, int]:
        """Get count of tools at each risk level."""
        distribution: Dict[int, int] = {}
        for tool in self.tools.values():
            risk_val = tool.risk_level.value if hasattr(tool.risk_level, "value") else int(tool.risk_level)
            distribution[risk_val] = distribution.get(risk_val, 0) + 1
        return distribution
    
    def get_safe_tools(self) -> Dict[str, ToolMetadata]:
        """Get only LEVEL_0 safe tools (automatic execution)."""
        return {k: v for k, v in self.tools.items() if v.risk_level == RiskLevel.LEVEL_0}
    
    @property
    def safe_tools(self) -> Dict[str, ToolMetadata]:
        return self.get_safe_tools()
    
    def get_controlled_tools(self) -> Dict[str, ToolMetadata]:
        """Get controlled tools (policy-supervised / sandboxed)."""
        return {k: v for k, v in self.tools.items() if v.risk_level in (RiskLevel.LEVEL_1, RiskLevel.LEVEL_2)}
    
    @property
    def controlled_tools(self) -> Dict[str, ToolMetadata]:
        return self.get_controlled_tools()
    
    def get_approval_tools(self) -> Dict[str, ToolMetadata]:
        """Get LEVEL_2+ tools requiring human approval."""
        return {k: v for k, v in self.tools.items() if v.requires_approval or v.risk_level >= RiskLevel.LEVEL_2}
    
    @property
    def approval_tools(self) -> Dict[str, ToolMetadata]:
        return self.get_approval_tools()
    
    def unregister_tool(self, tool_id: str) -> bool:
        """Remove a tool from the registry."""
        if tool_id in self.tools:
            del self.tools[tool_id]
            # Remove from policy engine too
            if tool_id in policy_engine.tool_registry:
                del policy_engine.tool_registry[tool_id]
            return True
        return False
    
    def update_tool(self, tool_id: str, metadata: ToolMetadata) -> bool:
        """Update tool metadata."""
        return self.register_tool(tool_id, metadata)


# Global tool registry instance
tool_registry = ToolRegistry()


# Convenience functions
def get_tool(tool_id: str) -> Optional[ToolMetadata]:
    """Get tool metadata by ID."""
    return tool_registry.get_tool(tool_id)


def get_all_tools() -> Dict[str, ToolMetadata]:
    """Get all registered tools."""
    return tool_registry.get_all_tools()


def get_allowed_tools(user_role: str) -> Dict[str, ToolMetadata]:
    """Get tools allowed for a user role."""
    return tool_registry.get_allowed_tools(user_role)


def get_safe_tools() -> Dict[str, ToolMetadata]:
    """Get only LEVEL_0 safe tools."""
    return tool_registry.safe_tools


def get_controlled_tools() -> Dict[str, ToolMetadata]:
    """Get LEVEL_1 controlled tools."""
    return tool_registry.controlled_tools


def get_approval_tools() -> Dict[str, ToolMetadata]:
    """Get LEVEL_2+ tools requiring approval."""
    return tool_registry.approval_tools


def search_tools(capability: str) -> List[ToolMetadata]:
    """Search tools by capability."""
    matching = []
    for tool_id, tool in tool_registry.get_all_tools().items():
        if capability in tool.supports:
            matching.append(tool)
    return matching


def get_tool_risk_distribution() -> Dict[int, int]:
    """Get count of tools at each risk level."""
    distribution: Dict[int, int] = {}
    for tool_id, tool in tool_registry.get_all_tools().items():
        risk_val = tool.risk_level.value
        distribution[risk_val] = distribution.get(risk_val, 0) + 1
    return distribution