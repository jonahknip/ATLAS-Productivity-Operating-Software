"""
BUILD_WORKFLOW Skill - Create automation workflows.

Risk Level: HIGH (workflow enabling always requires confirmation)
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from atlas.core.models import IntentType, RiskLevel, ToolCallStatus
from atlas.skills.base import Skill, SkillContext, SkillResult
from atlas.tools.base import Tool, ToolResult
from atlas.core.models import Change, UndoStep


# In-memory workflow storage
_workflows: dict[str, dict[str, Any]] = {}


class BuildWorkflowSkill(Skill):
    """
    Create and manage automation workflows.
    
    Creating workflows is allowed, but ENABLING them
    always requires confirmation.
    """

    @property
    def name(self) -> str:
        return "build_workflow"

    @property
    def intent_types(self) -> list[IntentType]:
        return [IntentType.BUILD_WORKFLOW]

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH

    @property
    def description(self) -> str:
        return "Create automation workflows"

    async def execute(self, context: SkillContext) -> SkillResult:
        result = SkillResult(success=True)
        
        params = context.intent.parameters
        entities = context.intent.raw_entities
        
        # Get workflow details
        name = params.get("name", "")
        if not name and entities:
            name = entities[0]
        if not name:
            name = f"Workflow {datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        trigger = params.get("trigger", {"type": "manual"})
        actions = params.get("actions", [])
        
        # If no actions provided, create a simple notification action
        if not actions:
            actions = [{"type": "notify", "message": f"Workflow '{name}' triggered"}]
        
        tools = context.tools
        if not tools:
            result.errors.append("Tools registry not available")
            result.success = False
            return result
        
        # Create the workflow (saved but NOT enabled)
        workflow_id = f"wf_{uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        
        workflow = {
            "workflow_id": workflow_id,
            "name": name,
            "trigger": trigger,
            "actions": actions,
            "enabled": False,
            "created_at": now,
            "updated_at": now,
            "run_count": 0,
            "last_run": None,
        }
        
        _workflows[workflow_id] = workflow
        
        result.changes.append(
            Change(
                entity_type="workflow",
                entity_id=workflow_id,
                action="created",
                after=workflow,
            )
        )
        
        result.undo_steps.append(
            UndoStep(
                tool_name="WORKFLOW_DELETE",
                args={"workflow_id": workflow_id},
                description=f"Delete workflow: {name}",
            )
        )
        
        result.data = {
            "workflow_id": workflow_id,
            "name": name,
            "trigger": trigger,
            "actions": actions,
            "enabled": False,
            "message": "Workflow created but NOT enabled. Use WORKFLOW_ENABLE to activate.",
        }
        
        return result


# Workflow Tools (separate from skill for clarity)

class WorkflowSaveTool(Tool):
    """Save a workflow definition."""

    @property
    def name(self) -> str:
        return "WORKFLOW_SAVE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW  # Saving is safe

    async def execute(
        self,
        name: str,
        trigger: dict[str, Any],
        actions: list[dict[str, Any]],
        enabled: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        workflow_id = f"wf_{uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        
        workflow = {
            "workflow_id": workflow_id,
            "name": name,
            "trigger": trigger,
            "actions": actions,
            "enabled": False,  # Always start disabled
            "created_at": now,
            "updated_at": now,
        }
        
        _workflows[workflow_id] = workflow
        
        return ToolResult(
            success=True,
            data={"workflow_id": workflow_id, "status": "saved", "enabled": False},
            changes=[
                Change(
                    entity_type="workflow",
                    entity_id=workflow_id,
                    action="created",
                    after=workflow,
                )
            ],
            undo_step=UndoStep(
                tool_name="WORKFLOW_DELETE",
                args={"workflow_id": workflow_id},
                description=f"Delete workflow: {name}",
            ),
        )


class WorkflowEnableTool(Tool):
    """Enable/disable a workflow. Always requires confirmation."""

    @property
    def name(self) -> str:
        return "WORKFLOW_ENABLE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH  # Always confirm

    async def execute(
        self,
        workflow_id: str,
        enabled: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        workflow = _workflows.get(workflow_id)
        
        if not workflow:
            return ToolResult(
                success=False,
                error=f"Workflow not found: {workflow_id}",
            )
        
        before = workflow.copy()
        workflow["enabled"] = enabled
        workflow["updated_at"] = datetime.utcnow().isoformat()
        
        return ToolResult(
            success=True,
            data={
                "workflow_id": workflow_id,
                "enabled": enabled,
                "next_run": None,  # Would calculate based on trigger
            },
            changes=[
                Change(
                    entity_type="workflow",
                    entity_id=workflow_id,
                    action="updated",
                    before=before,
                    after=workflow.copy(),
                )
            ],
            undo_step=UndoStep(
                tool_name="WORKFLOW_ENABLE",
                args={"workflow_id": workflow_id, "enabled": not enabled},
                description=f"{'Disable' if enabled else 'Enable'} workflow",
            ),
        )


class WorkflowListTool(Tool):
    """List all workflows."""

    @property
    def name(self) -> str:
        return "WORKFLOW_LIST"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, **kwargs: Any) -> ToolResult:
        workflows = list(_workflows.values())
        return ToolResult(
            success=True,
            data={"workflows": workflows, "total": len(workflows)},
        )


class WorkflowDeleteTool(Tool):
    """Delete a workflow."""

    @property
    def name(self) -> str:
        return "WORKFLOW_DELETE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    async def execute(self, workflow_id: str, **kwargs: Any) -> ToolResult:
        workflow = _workflows.pop(workflow_id, None)
        
        if not workflow:
            return ToolResult(
                success=False,
                error=f"Workflow not found: {workflow_id}",
            )
        
        return ToolResult(
            success=True,
            data={"workflow_id": workflow_id, "deleted": True},
            changes=[
                Change(
                    entity_type="workflow",
                    entity_id=workflow_id,
                    action="deleted",
                    before=workflow,
                )
            ],
        )


def get_all_workflows() -> dict[str, dict[str, Any]]:
    """Get all workflows."""
    return _workflows.copy()


def clear_all_workflows() -> None:
    """Clear all workflows."""
    _workflows.clear()
