from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runloop_agent.step import StepSpec


@dataclass(slots=True)
class ValidationResult:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_step_output(spec: StepSpec, parsed: Any) -> ValidationResult:
    schema = spec.metadata.get("output_schema") or {}
    if not schema:
        return ValidationResult(accepted=True)

    errors: list[str] = []

    expected_type = schema.get("type")
    if expected_type == "object" and not isinstance(parsed, dict):
        errors.append("output must be a JSON object")

    required = schema.get("required") or []
    if required and isinstance(parsed, dict):
        for key in required:
            if key not in parsed:
                errors.append(f"missing required field: {key}")

    return ValidationResult(accepted=not errors, errors=errors)
