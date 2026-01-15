"""
Skill Registry - Central management of skills.

The registry maps intent types to skills and provides
skill lookup and execution coordination.
"""

from typing import Any

from atlas.core.models import Intent, IntentType
from atlas.skills.base import Skill, SkillContext, SkillResult


class SkillRegistry:
    """
    Central registry for all skills.
    
    Manages skill registration, lookup, and provides
    a unified interface for skill execution.
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._intent_map: dict[IntentType, Skill] = {}

    def register(self, skill: Skill) -> None:
        """
        Register a skill.
        
        Args:
            skill: The skill to register
        """
        self._skills[skill.name] = skill
        
        # Map each intent type to this skill
        for intent_type in skill.intent_types:
            self._intent_map[intent_type] = skill

    def unregister(self, name: str) -> bool:
        """
        Unregister a skill by name.
        
        Args:
            name: Skill name
            
        Returns:
            True if removed, False if not found
        """
        skill = self._skills.pop(name, None)
        if skill:
            for intent_type in skill.intent_types:
                if self._intent_map.get(intent_type) == skill:
                    del self._intent_map[intent_type]
            return True
        return False

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_for_intent(self, intent: Intent) -> Skill | None:
        """
        Get the skill that handles a specific intent.
        
        Args:
            intent: The intent to find a skill for
            
        Returns:
            The skill or None if no skill handles this intent
        """
        return self._intent_map.get(intent.type)

    def list_skills(self) -> list[str]:
        """Get list of registered skill names."""
        return list(self._skills.keys())

    def get_skill_info(self) -> list[dict[str, Any]]:
        """Get info about all registered skills."""
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "intent_types": [it.value for it in skill.intent_types],
                "risk_level": skill.risk_level.value,
            }
            for skill in self._skills.values()
        ]

    async def execute(self, context: SkillContext) -> SkillResult:
        """
        Execute the appropriate skill for the context's intent.
        
        Args:
            context: Execution context
            
        Returns:
            SkillResult from the skill execution
        """
        skill = self.get_for_intent(context.intent)
        
        if not skill:
            return SkillResult(
                success=False,
                errors=[f"No skill registered for intent type: {context.intent.type.value}"],
            )
        
        return await skill.execute(context)
