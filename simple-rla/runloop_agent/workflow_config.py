"""Workflow configuration loader for runloop agent.

Loads workflow.yaml and provides structured access to prompts, execution params, etc.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


logger = logging.getLogger("simple_rla.workflow")


@dataclass(frozen=True)
class LLMConfig:
    system_prompt: str
    initial_message_template: str
    default_message: str


@dataclass(frozen=True)
class ExecutionConfig:
    max_steps: int
    request_timeout_s: float


@dataclass(frozen=True)
class ToolsConfig:
    on_error: str  # continue|abort
    include_traceback: bool


@dataclass(frozen=True)
class ExitCondition:
    name: str
    description: str
    enabled: bool
    pattern: str | None = None


@dataclass(frozen=True)
class OutputConfig:
    print_raw_on_empty: bool
    pretty_print: bool


@dataclass(frozen=True)
class WorkflowConfig:
    name: str
    version: str
    description: str
    llm: LLMConfig
    execution: ExecutionConfig
    tools: ToolsConfig
    exit_conditions: list[ExitCondition]
    output: OutputConfig


def _safe_get(data: dict, path: str, default: Any = None) -> Any:
    """Safely navigate nested dict with dot-notation path."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def load_workflow(path: str | Path) -> WorkflowConfig:
    """Load workflow configuration from YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML is required to load workflow.yaml. Install: pip install pyyaml")
    
    p = Path(path).expanduser().resolve()
    logger.info("workflow.load path=%s", p)
    
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    
    # Parse exit conditions
    exit_conditions_raw = _safe_get(raw, "exit_conditions", [])
    exit_conditions = []
    for ec in exit_conditions_raw:
        if isinstance(ec, dict):
            exit_conditions.append(ExitCondition(
                name=str(ec.get("name", "")),
                description=str(ec.get("description", "")),
                enabled=bool(ec.get("enabled", True)),
                pattern=ec.get("pattern"),
            ))
    
    cfg = WorkflowConfig(
        name=str(_safe_get(raw, "name", "unnamed")),
        version=str(_safe_get(raw, "version", "0.1")),
        description=str(_safe_get(raw, "description", "")),
        llm=LLMConfig(
            system_prompt=str(_safe_get(raw, "llm.system_prompt", "")),
            initial_message_template=str(_safe_get(raw, "llm.initial_message_template", "")),
            default_message=str(_safe_get(raw, "llm.default_message", "")),
        ),
        execution=ExecutionConfig(
            max_steps=int(_safe_get(raw, "execution.max_steps", 12)),
            request_timeout_s=float(_safe_get(raw, "execution.request_timeout_s", 300)),
        ),
        tools=ToolsConfig(
            on_error=str(_safe_get(raw, "tools.on_error", "continue")),
            include_traceback=bool(_safe_get(raw, "tools.include_traceback", False)),
        ),
        exit_conditions=exit_conditions,
        output=OutputConfig(
            print_raw_on_empty=bool(_safe_get(raw, "output.print_raw_on_empty", True)),
            pretty_print=bool(_safe_get(raw, "output.pretty_print", True)),
        ),
    )
    
    logger.info("workflow.loaded name=%s version=%s max_steps=%d", cfg.name, cfg.version, cfg.execution.max_steps)
    return cfg


def format_message(template: str, context: dict[str, Any]) -> str:
    """Format a message template with context variables.
    
    Uses Python str.format() with safe defaults for missing keys.
    """
    try:
        return template.format(**context)
    except KeyError as e:
        logger.warning("workflow.format missing_key=%s template=%r", e, template[:100])
        # Return template with available substitutions, missing keys stay as {key}
        return template
