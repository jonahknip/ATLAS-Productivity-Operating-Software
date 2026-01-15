"""
CAPTURE_TASKS Skill - Extract and create tasks from user input.

Risk Level: LOW
"""

from typing import Any

from atlas.core.models import IntentType, RiskLevel, ToolCall, ToolCallStatus
from atlas.skills.base import Skill, SkillContext, SkillResult


class CaptureTasksSkill(Skill):
    """
    Extract tasks from user input and create them.
    
    This skill parses the raw_entities from intent classification
    and creates tasks using the TASK_CREATE tool.
    """

    @property
    def name(self) -> str:
        return "capture_tasks"

    @property
    def intent_types(self) -> list[IntentType]:
        return [IntentType.CAPTURE_TASKS]

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Extract and create tasks from user input"

    async def execute(self, context: SkillContext) -> SkillResult:
        result = SkillResult(success=True)
        
        # Get entities from intent
        entities = context.intent.raw_entities
        params = context.intent.parameters
        
        # Also check for tasks in parameters
        if "tasks" in params:
            task_list = params["tasks"]
            if isinstance(task_list, list):
                for task_data in task_list:
                    if isinstance(task_data, dict):
                        entities.append(task_data.get("title", str(task_data)))
                    else:
                        entities.append(str(task_data))
        
        if not entities:
            result.warnings.append("No tasks found in input")
            return result
        
        # Create each task
        tools = context.tools
        if not tools:
            result.errors.append("Tools registry not available")
            result.success = False
            return result
        
        created_count = 0
        for entity in entities:
            # Parse task from entity string
            title = entity.strip()
            due_date = None
            priority = "medium"
            
            # Simple parsing for due dates
            title_lower = title.lower()
            if "by friday" in title_lower:
                due_date = self._get_next_weekday(4)  # Friday
                title = title.replace("by Friday", "").replace("by friday", "").strip()
            elif "tomorrow" in title_lower:
                due_date = self._get_tomorrow()
                title = title.replace("tomorrow", "").strip()
            elif "today" in title_lower:
                due_date = self._get_today()
                title = title.replace("today", "").strip()
            
            # Simple priority detection
            if "urgent" in title_lower or "asap" in title_lower:
                priority = "high"
            elif "low priority" in title_lower or "whenever" in title_lower:
                priority = "low"
            
            # Execute TASK_CREATE
            tool_call, tool_result = await tools.execute(
                "TASK_CREATE",
                {
                    "title": title,
                    "due_date": due_date,
                    "priority": priority,
                },
                skip_confirmation=True,  # LOW risk
            )
            
            result.tool_calls.append(tool_call)
            
            if tool_result and tool_result.success:
                created_count += 1
                result.changes.extend(tool_result.changes)
                if tool_result.undo_step:
                    result.undo_steps.append(tool_result.undo_step)
            elif tool_call.error:
                result.warnings.append(f"Failed to create task '{title}': {tool_call.error}")
        
        result.data["tasks_created"] = created_count
        result.data["tasks_requested"] = len(entities)
        
        if created_count == 0:
            result.success = False
            result.errors.append("Failed to create any tasks")
        
        return result

    def _get_today(self) -> str:
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d")

    def _get_tomorrow(self) -> str:
        from datetime import datetime, timedelta
        return (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    def _get_next_weekday(self, weekday: int) -> str:
        """Get the next occurrence of a weekday (0=Monday, 4=Friday)."""
        from datetime import datetime, timedelta
        today = datetime.utcnow()
        days_ahead = weekday - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
