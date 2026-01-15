"""
PROCESS_MEETING_NOTES Skill - Extract tasks and follow-ups from meeting notes.

Risk Level: MEDIUM (bulk task creation may need confirmation)
"""

from datetime import datetime
from typing import Any

from atlas.core.models import IntentType, RiskLevel
from atlas.skills.base import Skill, SkillContext, SkillResult


class ProcessMeetingNotesSkill(Skill):
    """
    Process meeting notes to extract action items and create tasks.
    
    This skill:
    1. Creates a note with the meeting content
    2. Extracts action items from the content
    3. Creates tasks for each action item
    """

    @property
    def name(self) -> str:
        return "process_meeting_notes"

    @property
    def intent_types(self) -> list[IntentType]:
        return [IntentType.PROCESS_MEETING_NOTES]

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def description(self) -> str:
        return "Extract tasks and follow-ups from meeting notes"

    async def execute(self, context: SkillContext) -> SkillResult:
        result = SkillResult(success=True)
        
        params = context.intent.parameters
        entities = context.intent.raw_entities
        
        # Get meeting content
        content = params.get("content", "") or params.get("notes", "")
        if not content and entities:
            content = "\n".join(entities)
        
        meeting_date = params.get("meeting_date", datetime.utcnow().strftime("%Y-%m-%d"))
        attendees = params.get("attendees", [])
        title = params.get("title", f"Meeting Notes - {meeting_date}")
        
        tools = context.tools
        if not tools:
            result.errors.append("Tools registry not available")
            result.success = False
            return result
        
        # Step 1: Create a note for the meeting
        note_call, note_result = await tools.execute(
            "NOTE_CREATE",
            {
                "title": title,
                "content": content,
                "tags": ["meeting"] + ([f"attendee:{a}" for a in attendees[:3]]),
            },
            skip_confirmation=True,
        )
        result.tool_calls.append(note_call)
        
        note_id = None
        if note_result and note_result.success:
            note_id = note_result.data.get("note_id")
            result.changes.extend(note_result.changes)
            if note_result.undo_step:
                result.undo_steps.append(note_result.undo_step)
        
        # Step 2: Extract action items
        action_items = self._extract_action_items(content)
        
        # Step 3: Create tasks for action items
        tasks_created = []
        for item in action_items:
            task_call, task_result = await tools.execute(
                "TASK_CREATE",
                {
                    "title": item["title"],
                    "description": f"From meeting: {title}",
                    "due_date": item.get("due_date"),
                    "priority": item.get("priority", "medium"),
                    "tags": ["meeting", "action-item"],
                },
                skip_confirmation=True,
            )
            result.tool_calls.append(task_call)
            
            if task_result and task_result.success:
                tasks_created.append(task_result.data.get("task_id"))
                result.changes.extend(task_result.changes)
                if task_result.undo_step:
                    result.undo_steps.append(task_result.undo_step)
        
        result.data = {
            "note_id": note_id,
            "meeting_date": meeting_date,
            "action_items_found": len(action_items),
            "tasks_created": len(tasks_created),
            "task_ids": tasks_created,
            "attendees": attendees,
        }
        
        return result

    def _extract_action_items(self, content: str) -> list[dict]:
        """Extract action items from meeting content."""
        action_items = []
        
        # Simple extraction based on common patterns
        lines = content.split("\n")
        
        action_keywords = [
            "action:", "todo:", "task:", "follow up:",
            "- [ ]", "[] ", "action item:",
            "need to", "should", "will",
        ]
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip empty lines
            if not line_lower:
                continue
            
            # Check for action item indicators
            is_action = False
            for keyword in action_keywords:
                if keyword in line_lower:
                    is_action = True
                    break
            
            # Also check for bullet points with action verbs
            if line_lower.startswith(("-", "*", "•")):
                action_verbs = ["schedule", "send", "follow", "review", "update", "create", "prepare", "contact"]
                for verb in action_verbs:
                    if verb in line_lower:
                        is_action = True
                        break
            
            if is_action:
                # Clean up the title
                title = line.strip()
                for prefix in ["- [ ]", "[] ", "-", "*", "•", "action:", "todo:", "task:"]:
                    if title.lower().startswith(prefix):
                        title = title[len(prefix):].strip()
                
                if title:
                    action_items.append({
                        "title": title[:100],  # Limit length
                        "priority": "medium",
                    })
        
        return action_items[:10]  # Max 10 action items
