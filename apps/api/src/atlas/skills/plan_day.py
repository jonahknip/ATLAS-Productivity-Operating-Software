"""
PLAN_DAY Skill - Generate a day plan with calendar blocks.

Risk Level: MEDIUM (calendar writes require confirmation)
"""

from datetime import datetime
from typing import Any

from atlas.core.models import IntentType, RiskLevel, ToolCallStatus
from atlas.skills.base import Skill, SkillContext, SkillResult


class PlanDaySkill(Skill):
    """
    Generate a day plan based on tasks and calendar.
    
    This skill:
    1. Gets the current calendar for the day
    2. Gets pending tasks
    3. Generates time blocks for tasks
    4. Creates calendar blocks (requires confirmation)
    """

    @property
    def name(self) -> str:
        return "plan_day"

    @property
    def intent_types(self) -> list[IntentType]:
        return [IntentType.PLAN_DAY]

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def description(self) -> str:
        return "Generate a day plan with scheduled time blocks"

    async def execute(self, context: SkillContext) -> SkillResult:
        result = SkillResult(success=True)
        
        params = context.intent.parameters
        entities = context.intent.raw_entities
        
        # Get target date (default to today)
        target_date = params.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        
        tools = context.tools
        if not tools:
            result.errors.append("Tools registry not available")
            result.success = False
            return result
        
        # Step 1: Get current calendar
        cal_call, cal_result = await tools.execute(
            "CALENDAR_GET_DAY",
            {"date": target_date},
            skip_confirmation=True,
        )
        result.tool_calls.append(cal_call)
        
        existing_blocks = []
        free_slots = []
        if cal_result and cal_result.success:
            existing_blocks = cal_result.data.get("blocks", [])
            free_slots = cal_result.data.get("free_slots", [])
        
        # Step 2: Get pending tasks (or use provided task list)
        tasks_to_schedule = []
        
        # Check if tasks were provided in parameters
        if "tasks_to_schedule" in params:
            task_ids = params["tasks_to_schedule"]
            for task_id in task_ids:
                task_call, task_result = await tools.execute(
                    "TASK_GET",
                    {"task_id": task_id},
                    skip_confirmation=True,
                )
                result.tool_calls.append(task_call)
                if task_result and task_result.success:
                    tasks_to_schedule.append(task_result.data["task"])
        
        # Also get pending tasks
        list_call, list_result = await tools.execute(
            "TASK_LIST",
            {"status": "pending", "limit": 10},
            skip_confirmation=True,
        )
        result.tool_calls.append(list_call)
        
        if list_result and list_result.success:
            for task in list_result.data.get("tasks", []):
                if task not in tasks_to_schedule:
                    tasks_to_schedule.append(task)
        
        # Also include any entities as ad-hoc tasks
        for entity in entities:
            tasks_to_schedule.append({
                "task_id": f"adhoc_{hash(entity) % 10000}",
                "title": entity,
                "priority": "medium",
            })
        
        if not tasks_to_schedule:
            result.warnings.append("No tasks to schedule")
            result.data = {
                "date": target_date,
                "existing_blocks": existing_blocks,
                "plan": [],
                "message": "No tasks to schedule",
            }
            return result
        
        # Step 3: Generate time blocks for tasks
        planned_blocks = self._generate_plan(
            tasks_to_schedule,
            free_slots,
            params.get("preferences", {}),
        )
        
        # Step 4: Create calendar blocks (requires confirmation)
        if planned_blocks:
            create_call, create_result = await tools.execute(
                "CALENDAR_CREATE_BLOCKS",
                {"date": target_date, "blocks": planned_blocks},
                skip_confirmation=False,  # MEDIUM risk - needs confirmation
            )
            result.tool_calls.append(create_call)
            
            if create_result and create_result.success:
                result.changes.extend(create_result.changes)
                if create_result.undo_step:
                    result.undo_steps.append(create_result.undo_step)
                result.data["blocks_created"] = len(create_result.data.get("created", []))
            elif create_call.status == ToolCallStatus.PENDING_CONFIRM:
                result.data["pending_confirmation"] = True
                result.data["blocks_pending"] = planned_blocks
        
        result.data["date"] = target_date
        result.data["existing_blocks"] = existing_blocks
        result.data["plan"] = planned_blocks
        result.data["tasks_scheduled"] = len(tasks_to_schedule)
        
        return result

    def _generate_plan(
        self,
        tasks: list[dict],
        free_slots: list[dict],
        preferences: dict,
    ) -> list[dict]:
        """Generate time blocks for tasks based on free slots."""
        plan = []
        
        # Simple scheduling: assign tasks to free slots
        slot_index = 0
        
        # Sort tasks by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_tasks = sorted(
            tasks,
            key=lambda t: priority_order.get(t.get("priority", "medium"), 1),
        )
        
        for task in sorted_tasks[:5]:  # Max 5 tasks per day
            if slot_index >= len(free_slots):
                break
            
            slot = free_slots[slot_index]
            
            # Calculate block duration (default 1 hour)
            start = slot["start"]
            
            # Parse start time and add 1 hour
            start_hour = int(start.split(":")[0])
            start_min = int(start.split(":")[1])
            end_hour = start_hour + 1
            end_min = start_min
            
            # Check if we exceed the slot
            slot_end_hour = int(slot["end"].split(":")[0])
            if end_hour > slot_end_hour:
                end_hour = slot_end_hour
                end_min = int(slot["end"].split(":")[1])
            
            end = f"{end_hour:02d}:{end_min:02d}"
            
            # Determine block type
            block_type = "task"
            if task.get("priority") == "high":
                block_type = "focus"
            
            plan.append({
                "title": task["title"],
                "start": start,
                "end": end,
                "type": block_type,
                "task_id": task.get("task_id"),
            })
            
            # Update slot for next task
            free_slots[slot_index] = {
                "start": end,
                "end": slot["end"],
            }
            
            # If slot is exhausted, move to next
            if end >= slot["end"]:
                slot_index += 1
        
        return plan
