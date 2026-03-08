"""Parsifal validate tool: frontmatter + schema checks for DEBUG_STEPS/KEY_EVIDENCE."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft7Validator


@dataclass
class ValidateResult:
    path: str
    kind: str
    ok: bool
    errors: list[str]


class Tool:
    """Minimal shim for nanobot Tool interface.

    This file is intended to be copied into nanobot/agent/tools and inherit
    the real Tool base class. The interface here mirrors nanobot Tool usage.
    """

    name: str = "parsifal_validate"
    description: str = "Validate Parsifal DEBUG_STEPS/KEY_EVIDENCE frontmatter and schemas."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["validate"]},
                "path": {"type": "string"},
                "paths": {"type": "array", "items": {"type": "string"}},
                "kind": {"type": "string", "enum": ["auto", "debug_steps", "key_evidence"]},
                "schema_dir": {"type": "string"},
                "require_schema": {"type": "boolean"},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        validator = ParsifalValidator()
        results = validator.handle(**kwargs)
        ok = all(r.ok for r in results)
        payload = {
            "ok": ok,
            "results": [asdict(r) for r in results],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


class ParsifalValidator:
    def __init__(self) -> None:
        overlay_root = Path(__file__).resolve().parents[1]
        self.default_schema_dir = overlay_root.parent / "kernel-rca-bot" / "schemas"

    def handle(self, **kwargs: Any) -> list[ValidateResult]:
        action = kwargs.get("action")
        if action != "validate":
            raise ValueError(f"Unknown action: {action}")

        paths = _coalesce_paths(kwargs.get("path"), kwargs.get("paths"))
        if not paths:
            raise ValueError("path or paths is required")

        kind = kwargs.get("kind") or "auto"
        schema_dir = Path(kwargs.get("schema_dir") or self.default_schema_dir).expanduser()
        require_schema = bool(kwargs.get("require_schema"))

        results = []
        for path in paths:
            results.append(self._validate_path(path, kind, schema_dir, require_schema))
        return results

    def _validate_path(self, path: str, kind: str, schema_dir: Path, require_schema: bool) -> ValidateResult:
        errors: list[str] = []
        p = Path(path).expanduser()
        if not p.exists():
            return ValidateResult(path=str(p), kind=kind, ok=False, errors=["file not found"])

        content = p.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(content)
        if frontmatter is None:
            return ValidateResult(path=str(p), kind=kind, ok=False, errors=["missing or invalid frontmatter"])

        resolved_kind = self._resolve_kind(kind, p.name, frontmatter)
        required, non_empty = _required_paths_for(resolved_kind)

        errors.extend(_check_required(frontmatter, required, non_empty))
        errors.extend(self._schema_errors(resolved_kind, frontmatter, schema_dir, require_schema))

        return ValidateResult(path=str(p), kind=resolved_kind, ok=not errors, errors=errors)

    def _resolve_kind(self, kind: str, filename: str, frontmatter: dict) -> str:
        if kind != "auto":
            return kind
        upper = filename.upper()
        if "DEBUG_STEPS" in upper or "debug_steps_id" in frontmatter:
            return "debug_steps"
        if "KEY_EVIDENCE" in upper or "evidence_id" in frontmatter:
            return "key_evidence"
        raise ValueError("Unable to determine kind; pass kind=debug_steps or kind=key_evidence")

    def _schema_errors(
        self, kind: str, frontmatter: dict, schema_dir: Path, require_schema: bool
    ) -> list[str]:
        schema_path = schema_dir / ("debug_steps.schema.json" if kind == "debug_steps" else "key_evidence.schema.json")
        if not schema_path.exists():
            return ["schema file missing"] if require_schema else []

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft7Validator(schema)
        errors = []
        for err in validator.iter_errors(frontmatter):
            loc = ".".join([str(x) for x in err.absolute_path])
            prefix = f"schema:{loc}" if loc else "schema"
            errors.append(f"{prefix}: {err.message}")
        return errors


def _parse_frontmatter(content: str) -> dict | None:
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    raw = parts[1]
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _required_paths_for(kind: str) -> tuple[list[str], list[str]]:
    if kind == "debug_steps":
        required = [
            "debug_steps_id",
            "jira_key",
            "created_at",
            "round",
            "bug.title",
            "bug.description_short",
            "target.platform",
            "target.kernel.repo",
            "target.kernel.branch",
            "target.kernel.commit",
            "target.kernel.localversion",
            "target.kernel.dtb",
            "inputs.jira_url",
            "inputs.test_artifacts",
            "inputs.kb_hits",
            "budget.max_device_commands",
            "budget.max_code_reads",
            "hypotheses",
            "code_check",
            "device_check",
            "stop_conditions",
        ]
        non_empty = [
            "debug_steps_id",
            "jira_key",
            "created_at",
            "bug.title",
            "bug.description_short",
            "target.platform",
            "target.kernel.repo",
            "target.kernel.branch",
            "target.kernel.commit",
            "target.kernel.localversion",
            "target.kernel.dtb",
            "inputs.test_artifacts",
            "hypotheses",
            "code_check",
            "device_check",
            "stop_conditions",
        ]
        return required, non_empty

    required = [
        "evidence_id",
        "jira_key",
        "created_at",
        "bug.title",
        "bug.description_short",
        "target.platform",
        "target.kernel.repo",
        "target.kernel.branch",
        "target.kernel.commit",
        "target.kernel.localversion",
        "target.kernel.dtb",
        "rca.one_line",
        "rca.scope",
        "confidence.value",
        "claims",
        "next_actions",
    ]
    non_empty = [
        "evidence_id",
        "jira_key",
        "created_at",
        "bug.title",
        "bug.description_short",
        "target.platform",
        "target.kernel.repo",
        "target.kernel.branch",
        "target.kernel.commit",
        "target.kernel.localversion",
        "target.kernel.dtb",
        "rca.one_line",
        "rca.scope",
        "claims",
        "next_actions",
    ]
    return required, non_empty


def _check_required(data: dict, required: Iterable[str], non_empty: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for path in required:
        value, found = _get_path(data, path)
        if not found:
            errors.append(f"missing: {path}")
            continue
        if path in non_empty and _is_empty(value):
            errors.append(f"empty: {path}")
    return errors


def _get_path(data: dict, path: str) -> tuple[Any, bool]:
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None, False
    return cur, True


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


def _coalesce_paths(path: str | None, paths: Iterable[str] | None) -> list[str]:
    result = []
    if path:
        result.append(path)
    if paths:
        result.extend([p for p in paths if p])
    return result
