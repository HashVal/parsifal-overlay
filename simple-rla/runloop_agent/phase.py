from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from runloop_agent.step import BaseStep, StepResult, StepStatus


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(slots=True)
class RollbackDecision:
    allowed: bool
    target_step_id: str | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PhaseCheckpoint:
    phase_id: str
    status: PhaseStatus
    summary: dict[str, Any] = field(default_factory=dict)
    compact_bundle: dict[str, Any] = field(default_factory=dict)
    step_outputs: dict[str, Any] = field(default_factory=dict)
    budget_usage: dict[str, int] = field(default_factory=dict)
    dump_refs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PhaseState:
    phase_id: str
    status: PhaseStatus = PhaseStatus.PENDING
    step_index: int = 0
    rollback_count: int = 0
    step_attempts: dict[str, int] = field(default_factory=dict)
    shared_state: dict[str, Any] = field(default_factory=dict)
    available_artifacts: dict[str, Any] = field(default_factory=dict)
    completed_step_results: dict[str, StepResult] = field(default_factory=dict)
    budget_usage: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    checkpoint: PhaseCheckpoint | None = None


@dataclass(slots=True)
class PhaseSpec:
    phase_id: str
    description: str = ""
    max_rollbacks: int = 0
    max_step_attempts: int = 1
    allowed_tool_families: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    tool_budget: dict[str, int] = field(default_factory=dict)
    rollback_anchors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class BasePhase(ABC):
    """Base abstraction for a phase containing a controlled sequence of steps.

    A phase is responsible for:
    - owning a sequence of steps and their shared state
    - deciding whether a step may rerun or rollback to a phase-local anchor
    - enforcing per-phase tool families / budgets
    - validating phase completion independently from any single step
    - producing a checkpoint/compact bundle for cross-phase handoff
    """

    def __init__(self, spec: PhaseSpec) -> None:
        self.spec = spec

    @property
    def phase_id(self) -> str:
        return self.spec.phase_id

    @abstractmethod
    def steps(self) -> list[BaseStep]:
        """Return the ordered step sequence for this phase."""

    def allowed_tool_families(self) -> tuple[str, ...]:
        return self.spec.allowed_tool_families

    def allowed_tools(self) -> tuple[str, ...]:
        return self.spec.allowed_tools

    def tool_budget(self) -> dict[str, int]:
        return dict(self.spec.tool_budget)

    def rollback_targets(self) -> tuple[str, ...]:
        return self.spec.rollback_anchors

    def max_rollbacks(self) -> int:
        return self.spec.max_rollbacks

    def max_step_attempts(self) -> int:
        return self.spec.max_step_attempts

    def can_rerun_step(self, state: PhaseState, step_id: str) -> bool:
        attempts = state.step_attempts.get(step_id, 0)
        return attempts < self.max_step_attempts()

    def can_rollback_to(self, state: PhaseState, step_id: str) -> bool:
        if state.rollback_count >= self.max_rollbacks():
            return False
        return step_id in self.rollback_targets()

    def select_rollback_target(self, state: PhaseState, failed_step_id: str) -> RollbackDecision:
        anchors = self.rollback_targets()
        if not anchors:
            return RollbackDecision(False, reason="no rollback anchors configured")
        if state.rollback_count >= self.max_rollbacks():
            return RollbackDecision(False, reason="phase rollback budget exhausted")
        if failed_step_id in anchors:
            return RollbackDecision(True, target_step_id=failed_step_id, reason="failed step is a rollback anchor")
        return RollbackDecision(True, target_step_id=anchors[-1], reason="fallback to last configured rollback anchor")

    @abstractmethod
    def phase_exit_check(self, state: PhaseState) -> bool:
        """Return True only when the phase as a whole is complete and valid."""

    def build_checkpoint(self, state: PhaseState) -> PhaseCheckpoint:
        compact_bundle: dict[str, Any] = {}
        step_outputs: dict[str, Any] = {}
        for step_id, result in state.completed_step_results.items():
            compact_bundle[step_id] = result.compact_output if result.compact_output is not None else result.output
            step_outputs[step_id] = result.output
        return PhaseCheckpoint(
            phase_id=state.phase_id,
            status=state.status,
            summary={"notes": list(state.notes)},
            compact_bundle=compact_bundle,
            step_outputs=step_outputs,
            budget_usage=dict(state.budget_usage),
            metadata={"rollback_count": state.rollback_count},
        )

    def finalize_phase(self, state: PhaseState) -> PhaseCheckpoint:
        checkpoint = self.build_checkpoint(state)
        state.checkpoint = checkpoint
        return checkpoint

    def next_phase(self) -> str | None:
        return None

    def mark_step_result(self, state: PhaseState, result: StepResult) -> None:
        state.completed_step_results[result.step_id] = result
        state.step_attempts[result.step_id] = state.step_attempts.get(result.step_id, 0) + 1
        if result.status == StepStatus.COMPLETED:
            state.step_index += 1
