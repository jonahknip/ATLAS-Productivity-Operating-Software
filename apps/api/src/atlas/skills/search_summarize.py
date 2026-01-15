"""
SEARCH_SUMMARIZE Skill - Search notes and summarize results.

Risk Level: LOW
"""

from typing import Any

from atlas.core.models import IntentType, RiskLevel
from atlas.skills.base import Skill, SkillContext, SkillResult


class SearchSummarizeSkill(Skill):
    """
    Search notes and summarize the results.
    
    This skill searches notes using the NOTE_SEARCH tool
    and returns structured results with citations.
    """

    @property
    def name(self) -> str:
        return "search_summarize"

    @property
    def intent_types(self) -> list[IntentType]:
        return [IntentType.SEARCH_SUMMARIZE]

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Search notes and summarize results with citations"

    async def execute(self, context: SkillContext) -> SkillResult:
        result = SkillResult(success=True)
        
        params = context.intent.parameters
        entities = context.intent.raw_entities
        
        # Build search query
        query = params.get("query", "")
        if not query and entities:
            query = " ".join(entities)
        
        tags = params.get("tags", [])
        sources = params.get("sources", ["notes"])
        
        tools = context.tools
        if not tools:
            result.errors.append("Tools registry not available")
            result.success = False
            return result
        
        search_results = []
        
        # Search notes if requested
        if "notes" in sources:
            tool_call, tool_result = await tools.execute(
                "NOTE_SEARCH",
                {"query": query, "tags": tags, "limit": 10},
                skip_confirmation=True,
            )
            result.tool_calls.append(tool_call)
            
            if tool_result and tool_result.success:
                notes = tool_result.data.get("notes", [])
                for note in notes:
                    search_results.append({
                        "source": "notes",
                        "id": note["note_id"],
                        "title": note["title"],
                        "snippet": note["snippet"],
                        "relevance": note["relevance"],
                    })
        
        # Search tasks if requested
        if "tasks" in sources:
            tool_call, tool_result = await tools.execute(
                "TASK_LIST",
                {"limit": 20},
                skip_confirmation=True,
            )
            result.tool_calls.append(tool_call)
            
            if tool_result and tool_result.success:
                tasks = tool_result.data.get("tasks", [])
                query_lower = query.lower()
                for task in tasks:
                    # Simple relevance scoring for tasks
                    relevance = 0.0
                    if query_lower in task["title"].lower():
                        relevance = 0.7
                    elif query_lower in task.get("description", "").lower():
                        relevance = 0.5
                    
                    if relevance > 0 or not query:
                        search_results.append({
                            "source": "tasks",
                            "id": task["task_id"],
                            "title": task["title"],
                            "snippet": task.get("description", "")[:100],
                            "relevance": relevance or 0.3,
                            "status": task["status"],
                            "due_date": task.get("due_date"),
                        })
        
        # Sort by relevance
        search_results.sort(key=lambda x: x["relevance"], reverse=True)
        
        # Build summary
        summary = self._build_summary(query, search_results)
        
        result.data = {
            "query": query,
            "results": search_results[:10],  # Top 10
            "total_found": len(search_results),
            "summary": summary,
            "citations": [
                {"source": r["source"], "id": r["id"], "title": r["title"]}
                for r in search_results[:5]
            ],
        }
        
        if not search_results:
            result.warnings.append(f"No results found for query: {query}")
        
        return result

    def _build_summary(self, query: str, results: list[dict]) -> str:
        """Build a summary of search results."""
        if not results:
            return f"No results found for '{query}'."
        
        note_count = len([r for r in results if r["source"] == "notes"])
        task_count = len([r for r in results if r["source"] == "tasks"])
        
        parts = []
        parts.append(f"Found {len(results)} result(s) for '{query}'.")
        
        if note_count:
            parts.append(f"{note_count} note(s)")
        if task_count:
            parts.append(f"{task_count} task(s)")
        
        # Add top result info
        top = results[0]
        parts.append(f"Top result: {top['title']} (from {top['source']})")
        
        return " ".join(parts)
