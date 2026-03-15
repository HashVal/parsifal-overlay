from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(slots=True)
class StepErrorInfo:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StepToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    success: bool | None = None
    output: Any = None
    error: str | None = None


@dataclass(slots=True)
class StepContext:
    phase_id: str
    step_id: str
    attempt: int = 1
    inputs: dict[str, Any] = field(default_factory=dict)
    shared_state: dict[str, Any] = field(default_factory=dict)
    available_artifacts: dict[str, Any] = field(default_factory=dict)
    allowed_tool_families: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    tool_budget_snapshot: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StepResult:
    step_id: str
    status: StepStatus
    output: Any = None
    compact_output: Any = None
    exit_ready: bool = False
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[StepToolCall] = field(default_factory=list)
    produced_artifacts: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    error: StepErrorInfo | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StepSpec:
    step_id: str
    description: str = ""
    input_keys: tuple[str, ...] = ()
    output_keys: tuple[str, ...] = ()
    allowed_tool_families: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    max_attempts: int = 1
    repair_attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseStep(ABC):
    """Base abstraction for a single step execution.

    A step is the smallest LLM/tool execution unit in the workflow.
    It is responsible for:
    - defining its prompt/invocation contract
    - constraining the tools/actions allowed in this step
    - validating whether its own exit-condition is satisfied
    - returning a structured StepResult for phase-level control
    """

    def __init__(self, spec: StepSpec) -> None:
        self.spec = spec

    @property
    def step_id(self) -> str:
        return self.spec.step_id

    def allowed_tool_families(self, ctx: StepContext) -> tuple[str, ...]:
        return self.spec.allowed_tool_families or ctx.allowed_tool_families

    def allowed_tools(self, ctx: StepContext) -> tuple[str, ...]:
        return self.spec.allowed_tools or ctx.allowed_tools

    @abstractmethod
    def build_prompt(self, ctx: StepContext) -> str | dict[str, Any]:
        """Build the guiding prompt/input for one step execution."""

    @abstractmethod
    def run(self, ctx: StepContext) -> StepResult:
        """Execute the step once and return a structured StepResult."""

    @abstractmethod
    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        """Return True if this step has satisfied its own exit-condition."""

    def compact_output(self, result: StepResult, ctx: StepContext) -> Any:
        """Return a compact representation suitable for downstream step/phase handoff."""
        if result.compact_output is not None:
            return result.compact_output
        return result.output

    def mark_exit_ready(self, result: StepResult, ctx: StepContext) -> StepResult:
        result.exit_ready = self.validate_exit(result, ctx)
        if result.exit_ready and result.status == StepStatus.RUNNING:
            result.status = StepStatus.COMPLETED
        return result
