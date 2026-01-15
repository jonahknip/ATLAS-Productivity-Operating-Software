"""
JSON Normalizer - Extract and repair JSON from LLM output.

The normalizer is the first line of defense in the reliability engine.
It handles the common failure mode of LLMs: wrapping JSON in markdown,
adding commentary, or producing malformed JSON.

Flow:
1. Try direct JSON parse
2. Extract from markdown code blocks
3. Find JSON-like structures in text
4. Apply basic repairs (trailing commas, unquoted keys)
"""

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizerResult:
    """Result of JSON normalization attempt."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    repairs_applied: list[str] | None = None


class JSONNormalizer:
    """Extract and repair JSON from model output."""

    # Patterns for JSON extraction
    MARKDOWN_JSON_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    JSON_OBJECT_PATTERN = re.compile(r"\{[\s\S]*\}")
    JSON_ARRAY_PATTERN = re.compile(r"\[[\s\S]*\]")

    def normalize(self, raw_output: str) -> NormalizerResult:
        """
        Attempt to extract valid JSON from raw model output.

        Args:
            raw_output: Raw string output from model

        Returns:
            NormalizerResult with success status and parsed data or error
        """
        repairs: list[str] = []

        # Step 1: Try direct parse
        result = self._try_parse(raw_output)
        if result.success:
            return result

        # Step 2: Extract from markdown code blocks
        extracted = self._extract_from_markdown(raw_output)
        if extracted:
            repairs.append("extracted_from_markdown")
            result = self._try_parse(extracted)
            if result.success:
                result.repairs_applied = repairs
                return result
            raw_output = extracted  # Continue with extracted content

        # Step 3: Find JSON-like structure in text
        extracted = self._find_json_structure(raw_output)
        if extracted and extracted != raw_output:
            repairs.append("extracted_json_structure")
            result = self._try_parse(extracted)
            if result.success:
                result.repairs_applied = repairs
                return result
            raw_output = extracted

        # Step 4: Apply repairs
        repaired, repair_list = self._apply_repairs(raw_output)
        repairs.extend(repair_list)

        result = self._try_parse(repaired)
        if result.success:
            result.repairs_applied = repairs
            return result

        return NormalizerResult(
            success=False,
            error=f"Failed to normalize JSON after repairs: {repairs}",
            repairs_applied=repairs,
        )

    def _try_parse(self, text: str) -> NormalizerResult:
        """Attempt to parse text as JSON."""
        try:
            data = json.loads(text.strip())
            if isinstance(data, dict):
                return NormalizerResult(success=True, data=data)
            # Wrap arrays in a data key for consistency
            if isinstance(data, list):
                return NormalizerResult(success=True, data={"items": data})
            return NormalizerResult(
                success=False, error=f"Unexpected JSON type: {type(data).__name__}"
            )
        except json.JSONDecodeError as e:
            return NormalizerResult(success=False, error=str(e))

    def _extract_from_markdown(self, text: str) -> str | None:
        """Extract JSON from markdown code blocks."""
        matches = self.MARKDOWN_JSON_PATTERN.findall(text)
        if matches:
            # Return the first match that looks like JSON
            for match in matches:
                stripped = match.strip()
                if stripped.startswith(("{", "[")):
                    return stripped
        return None

    def _find_json_structure(self, text: str) -> str | None:
        """Find JSON object or array in text."""
        # Try to find an object first
        obj_match = self.JSON_OBJECT_PATTERN.search(text)
        if obj_match:
            return obj_match.group()

        # Fall back to array
        arr_match = self.JSON_ARRAY_PATTERN.search(text)
        if arr_match:
            return arr_match.group()

        return None

    def _apply_repairs(self, text: str) -> tuple[str, list[str]]:
        """Apply common JSON repairs."""
        repairs: list[str] = []
        result = text

        # Remove trailing commas before } or ]
        trailing_comma_pattern = re.compile(r",(\s*[}\]])")
        if trailing_comma_pattern.search(result):
            result = trailing_comma_pattern.sub(r"\1", result)
            repairs.append("removed_trailing_commas")

        # Fix unquoted keys (simple cases)
        unquoted_key_pattern = re.compile(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)")
        if unquoted_key_pattern.search(result):
            result = unquoted_key_pattern.sub(r'\1"\2"\3', result)
            repairs.append("quoted_keys")

        # Fix single quotes to double quotes (careful with nested)
        if "'" in result and '"' not in result:
            result = result.replace("'", '"')
            repairs.append("single_to_double_quotes")

        return result, repairs
