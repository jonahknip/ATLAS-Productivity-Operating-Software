"""Tests for the JSON Normalizer."""

import pytest

from atlas.core.normalizer import JSONNormalizer, NormalizerResult


class TestJSONNormalizer:
    """Test JSON normalization and repair."""

    @pytest.fixture
    def normalizer(self) -> JSONNormalizer:
        return JSONNormalizer()

    def test_valid_json_passes_through(self, normalizer: JSONNormalizer) -> None:
        """Valid JSON should pass through unchanged."""
        raw = '{"type": "CAPTURE_TASKS", "confidence": 0.95}'
        result = normalizer.normalize(raw)

        assert result.success
        assert result.data == {"type": "CAPTURE_TASKS", "confidence": 0.95}
        assert result.repairs_applied is None

    def test_extracts_from_markdown_code_block(self, normalizer: JSONNormalizer) -> None:
        """Should extract JSON from markdown code blocks."""
        raw = """Here's the intent classification:

```json
{"type": "PLAN_DAY", "confidence": 0.88}
```

Let me know if you need anything else."""

        result = normalizer.normalize(raw)

        assert result.success
        assert result.data == {"type": "PLAN_DAY", "confidence": 0.88}
        assert "extracted_from_markdown" in (result.repairs_applied or [])

    def test_extracts_from_plain_code_block(self, normalizer: JSONNormalizer) -> None:
        """Should extract from code block without json tag."""
        raw = """
```
{"type": "SEARCH_SUMMARIZE", "confidence": 0.75}
```
"""
        result = normalizer.normalize(raw)

        assert result.success
        assert result.data["type"] == "SEARCH_SUMMARIZE"

    def test_finds_json_object_in_text(self, normalizer: JSONNormalizer) -> None:
        """Should find JSON object embedded in text."""
        raw = 'The classification is {"type": "CAPTURE_TASKS", "confidence": 0.9} based on the input.'

        result = normalizer.normalize(raw)

        assert result.success
        assert result.data["type"] == "CAPTURE_TASKS"

    def test_removes_trailing_commas(self, normalizer: JSONNormalizer) -> None:
        """Should remove trailing commas in objects and arrays."""
        raw = '{"type": "PLAN_DAY", "confidence": 0.8,}'

        result = normalizer.normalize(raw)

        assert result.success
        assert result.data == {"type": "PLAN_DAY", "confidence": 0.8}
        assert "removed_trailing_commas" in (result.repairs_applied or [])

    def test_quotes_unquoted_keys(self, normalizer: JSONNormalizer) -> None:
        """Should add quotes to unquoted keys."""
        raw = '{type: "CAPTURE_TASKS", confidence: 0.9}'

        result = normalizer.normalize(raw)

        assert result.success
        assert result.data["type"] == "CAPTURE_TASKS"
        assert "quoted_keys" in (result.repairs_applied or [])

    def test_handles_single_quotes(self, normalizer: JSONNormalizer) -> None:
        """Should convert single quotes to double quotes."""
        raw = "{'type': 'PLAN_DAY', 'confidence': 0.85}"

        result = normalizer.normalize(raw)

        assert result.success
        assert result.data["type"] == "PLAN_DAY"

    def test_wraps_array_in_items_key(self, normalizer: JSONNormalizer) -> None:
        """Should wrap top-level arrays for consistency."""
        raw = '["task1", "task2", "task3"]'

        result = normalizer.normalize(raw)

        assert result.success
        assert result.data == {"items": ["task1", "task2", "task3"]}

    def test_fails_on_completely_invalid_input(self, normalizer: JSONNormalizer) -> None:
        """Should fail gracefully on non-JSON input."""
        raw = "This is just plain text with no JSON at all."

        result = normalizer.normalize(raw)

        assert not result.success
        assert result.error is not None

    def test_fails_on_empty_input(self, normalizer: JSONNormalizer) -> None:
        """Should fail on empty input."""
        result = normalizer.normalize("")

        assert not result.success

    def test_handles_nested_objects(self, normalizer: JSONNormalizer) -> None:
        """Should handle nested JSON objects."""
        raw = """```json
{
    "type": "PLAN_DAY",
    "confidence": 0.9,
    "parameters": {
        "date": "2024-01-15",
        "tasks": ["a", "b", "c"]
    }
}
```"""
        result = normalizer.normalize(raw)

        assert result.success
        assert result.data["parameters"]["date"] == "2024-01-15"
        assert len(result.data["parameters"]["tasks"]) == 3
