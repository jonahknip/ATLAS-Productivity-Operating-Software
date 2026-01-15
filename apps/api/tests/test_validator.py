"""Tests for the Intent Validator."""

import pytest

from atlas.core.models import IntentType, RiskLevel
from atlas.core.validator import Validator


class TestValidator:
    """Test intent validation."""

    @pytest.fixture
    def validator(self) -> Validator:
        return Validator()

    def test_valid_intent_passes(self, validator: Validator) -> None:
        """Valid intent data should pass validation."""
        data = {
            "type": "CAPTURE_TASKS",
            "confidence": 0.95,
            "parameters": {},
            "raw_entities": ["buy milk", "call mom"],
        }

        result = validator.validate_intent(data)

        assert result.valid
        assert result.intent is not None
        assert result.intent.type == IntentType.CAPTURE_TASKS
        assert result.intent.confidence == 0.95
        assert result.risk_level == RiskLevel.LOW

    def test_missing_type_fails(self, validator: Validator) -> None:
        """Missing type field should fail."""
        data = {"confidence": 0.9}

        result = validator.validate_intent(data)

        assert not result.valid
        assert any(e.field == "type" for e in result.errors)

    def test_missing_confidence_fails(self, validator: Validator) -> None:
        """Missing confidence field should fail."""
        data = {"type": "CAPTURE_TASKS"}

        result = validator.validate_intent(data)

        assert not result.valid
        assert any(e.field == "confidence" for e in result.errors)

    def test_invalid_intent_type_fails(self, validator: Validator) -> None:
        """Unknown intent type should fail."""
        data = {"type": "INVALID_TYPE", "confidence": 0.9}

        result = validator.validate_intent(data)

        assert not result.valid
        assert any(e.code == "INVALID_INTENT_TYPE" for e in result.errors)

    def test_confidence_below_zero_fails(self, validator: Validator) -> None:
        """Confidence below 0 should fail."""
        data = {"type": "CAPTURE_TASKS", "confidence": -0.1}

        result = validator.validate_intent(data)

        assert not result.valid
        assert any(e.code == "OUT_OF_RANGE" for e in result.errors)

    def test_confidence_above_one_fails(self, validator: Validator) -> None:
        """Confidence above 1 should fail."""
        data = {"type": "CAPTURE_TASKS", "confidence": 1.5}

        result = validator.validate_intent(data)

        assert not result.valid
        assert any(e.code == "OUT_OF_RANGE" for e in result.errors)

    def test_confidence_at_boundaries(self, validator: Validator) -> None:
        """Confidence at 0 and 1 should pass."""
        data_zero = {"type": "CAPTURE_TASKS", "confidence": 0.0}
        data_one = {"type": "CAPTURE_TASKS", "confidence": 1.0}

        assert validator.validate_intent(data_zero).valid
        assert validator.validate_intent(data_one).valid

    def test_non_numeric_confidence_fails(self, validator: Validator) -> None:
        """Non-numeric confidence should fail."""
        data = {"type": "CAPTURE_TASKS", "confidence": "high"}

        result = validator.validate_intent(data)

        assert not result.valid
        assert any(e.code == "INVALID_TYPE" for e in result.errors)

    def test_risk_level_assignment(self, validator: Validator) -> None:
        """Risk levels should be assigned correctly."""
        test_cases = [
            ("CAPTURE_TASKS", RiskLevel.LOW),
            ("SEARCH_SUMMARIZE", RiskLevel.LOW),
            ("PLAN_DAY", RiskLevel.MEDIUM),
            ("PROCESS_MEETING_NOTES", RiskLevel.MEDIUM),
            ("BUILD_WORKFLOW", RiskLevel.HIGH),
            ("UNKNOWN", RiskLevel.LOW),
        ]

        for intent_type, expected_risk in test_cases:
            data = {"type": intent_type, "confidence": 0.9}
            result = validator.validate_intent(data)

            assert result.valid, f"Failed for {intent_type}"
            assert result.risk_level == expected_risk, f"Wrong risk for {intent_type}"

    def test_invalid_raw_entities_type_fails(self, validator: Validator) -> None:
        """raw_entities must be a list."""
        data = {
            "type": "CAPTURE_TASKS",
            "confidence": 0.9,
            "raw_entities": "not a list",
        }

        result = validator.validate_intent(data)

        assert not result.valid
        assert any(e.field == "raw_entities" for e in result.errors)

    def test_invalid_entity_item_fails(self, validator: Validator) -> None:
        """Entity items must be strings."""
        data = {
            "type": "CAPTURE_TASKS",
            "confidence": 0.9,
            "raw_entities": ["valid", 123, "also valid"],
        }

        result = validator.validate_intent(data)

        assert not result.valid
        assert any("raw_entities[1]" in e.field for e in result.errors)

    def test_parameters_are_optional(self, validator: Validator) -> None:
        """Missing parameters should default to empty dict."""
        data = {"type": "CAPTURE_TASKS", "confidence": 0.9}

        result = validator.validate_intent(data)

        assert result.valid
        assert result.intent is not None
        assert result.intent.parameters == {}

    def test_plan_day_date_validation(self, validator: Validator) -> None:
        """PLAN_DAY should validate date format in parameters."""
        # Valid date
        valid = {
            "type": "PLAN_DAY",
            "confidence": 0.9,
            "parameters": {"date": "2024-01-15"},
        }
        assert validator.validate_intent(valid).valid

        # Invalid date
        invalid = {
            "type": "PLAN_DAY",
            "confidence": 0.9,
            "parameters": {"date": "not-a-date"},
        }
        result = validator.validate_intent(invalid)
        assert not result.valid
        assert any(e.code == "INVALID_DATE" for e in result.errors)
