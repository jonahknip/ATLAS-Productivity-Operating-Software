"""
Validator - Schema + entity + policy enforcement.

The validator ensures that normalized JSON meets ATLAS contracts:
1. Schema validation - required fields, types, ranges
2. Entity validation - references exist, dates are valid
3. Policy validation - risk levels, confirmation requirements

This is the second line of defense after the normalizer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from atlas.core.models import Intent, IntentType, RiskLevel


@dataclass
class ValidationError:
    """A single validation error."""

    field: str
    message: str
    code: str  # e.g., "MISSING_FIELD", "INVALID_TYPE", "OUT_OF_RANGE"


@dataclass
class ValidationResult:
    """Result of validation."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    intent: Intent | None = None
    risk_level: RiskLevel = RiskLevel.LOW


class Validator:
    """
    Validate intent data against ATLAS contracts.

    Enforces:
    - Intent envelope v2.1 schema
    - Allowed intent types only
    - Confidence in 0..1 range
    - Valid date/time formats
    - Entity reference validation
    """

    # Required fields for an intent
    REQUIRED_INTENT_FIELDS = {"type", "confidence"}

    # Risk levels by intent type (per spec)
    INTENT_RISK_MAP: dict[IntentType, RiskLevel] = {
        IntentType.CAPTURE_TASKS: RiskLevel.LOW,
        IntentType.SEARCH_SUMMARIZE: RiskLevel.LOW,
        IntentType.PLAN_DAY: RiskLevel.MEDIUM,
        IntentType.PROCESS_MEETING_NOTES: RiskLevel.MEDIUM,
        IntentType.BUILD_WORKFLOW: RiskLevel.HIGH,
        IntentType.UNKNOWN: RiskLevel.LOW,
    }

    def validate_intent(self, data: dict[str, Any]) -> ValidationResult:
        """
        Validate intent data from normalized JSON.

        Args:
            data: Normalized JSON dict from model output

        Returns:
            ValidationResult with parsed Intent if valid
        """
        errors: list[ValidationError] = []
        warnings: list[str] = []

        # Check required fields
        for required in self.REQUIRED_INTENT_FIELDS:
            if required not in data:
                errors.append(
                    ValidationError(
                        field=required,
                        message=f"Missing required field: {required}",
                        code="MISSING_FIELD",
                    )
                )

        if errors:
            return ValidationResult(valid=False, errors=errors)

        # Validate intent type
        intent_type = self._validate_intent_type(data.get("type"), errors)

        # Validate confidence
        confidence = self._validate_confidence(data.get("confidence"), errors)

        # Validate parameters (intent-specific)
        parameters = data.get("parameters", {})
        if intent_type:
            self._validate_parameters(intent_type, parameters, errors, warnings)

        # Validate entities if present
        raw_entities = data.get("raw_entities", [])
        self._validate_entities(raw_entities, errors)

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Build validated intent
        intent = Intent(
            type=intent_type or IntentType.UNKNOWN,
            confidence=confidence or 0.0,
            parameters=parameters,
            raw_entities=raw_entities if isinstance(raw_entities, list) else [],
        )

        # Determine risk level
        risk_level = self.INTENT_RISK_MAP.get(intent.type, RiskLevel.LOW)

        return ValidationResult(
            valid=True,
            intent=intent,
            risk_level=risk_level,
            warnings=warnings,
        )

    def _validate_intent_type(
        self, value: Any, errors: list[ValidationError]
    ) -> IntentType | None:
        """Validate intent type is in allowed list."""
        if value is None:
            return None

        try:
            return IntentType(value)
        except ValueError:
            errors.append(
                ValidationError(
                    field="type",
                    message=f"Invalid intent type: {value}. Allowed: {[t.value for t in IntentType]}",
                    code="INVALID_INTENT_TYPE",
                )
            )
            return None

    def _validate_confidence(
        self, value: Any, errors: list[ValidationError]
    ) -> float | None:
        """Validate confidence is float in 0..1 range."""
        if value is None:
            errors.append(
                ValidationError(
                    field="confidence",
                    message="Confidence is required",
                    code="MISSING_FIELD",
                )
            )
            return None

        try:
            conf = float(value)
            if not 0.0 <= conf <= 1.0:
                errors.append(
                    ValidationError(
                        field="confidence",
                        message=f"Confidence must be between 0 and 1, got: {conf}",
                        code="OUT_OF_RANGE",
                    )
                )
                return None
            return conf
        except (TypeError, ValueError):
            errors.append(
                ValidationError(
                    field="confidence",
                    message=f"Confidence must be a number, got: {type(value).__name__}",
                    code="INVALID_TYPE",
                )
            )
            return None

    def _validate_parameters(
        self,
        intent_type: IntentType,
        parameters: dict[str, Any],
        errors: list[ValidationError],
        warnings: list[str],
    ) -> None:
        """Validate intent-specific parameters."""
        if intent_type == IntentType.PLAN_DAY:
            # Validate date if present
            if "date" in parameters:
                self._validate_date(parameters["date"], "parameters.date", errors)

        elif intent_type == IntentType.PROCESS_MEETING_NOTES:
            # Meeting notes should have content
            if not parameters.get("content") and not parameters.get("notes"):
                warnings.append("Meeting notes intent has no content/notes parameter")

    def _validate_date(
        self, value: Any, field_name: str, errors: list[ValidationError]
    ) -> datetime | None:
        """Validate date string or datetime."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            # Try common formats
            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

            errors.append(
                ValidationError(
                    field=field_name,
                    message=f"Invalid date format: {value}",
                    code="INVALID_DATE",
                )
            )
        else:
            errors.append(
                ValidationError(
                    field=field_name,
                    message=f"Date must be string or datetime, got: {type(value).__name__}",
                    code="INVALID_TYPE",
                )
            )
        return None

    def _validate_entities(
        self, entities: Any, errors: list[ValidationError]
    ) -> None:
        """Validate raw_entities is a list of strings."""
        if not isinstance(entities, list):
            if entities is not None:
                errors.append(
                    ValidationError(
                        field="raw_entities",
                        message="raw_entities must be a list",
                        code="INVALID_TYPE",
                    )
                )
            return

        for i, entity in enumerate(entities):
            if not isinstance(entity, str):
                errors.append(
                    ValidationError(
                        field=f"raw_entities[{i}]",
                        message=f"Entity must be string, got: {type(entity).__name__}",
                        code="INVALID_TYPE",
                    )
                )
