from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from runloop_agent.phase import BasePhase, PhaseCheckpoint, PhaseState, PhaseStatus, RollbackDecision
from runloop_agent.step import BaseStep, StepContext, StepResult, StepStatus


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(slots=True)
class WorkflowPolicy:
    allow_cross_phase_rerun: bool = False
    allow_phase_skip: bool = False
    allow_step_merge: bool = False
    allow_step_split: bool = False
    strict_terminal_phase_only: bool = True
    max_total_failures: int = 3
    max_total_repairs: int = 3


@dataclass(slots=True)
class CheckpointPolicy:
    persist_phase_checkpoint: bool = True
    persist_workflow_checkpoint: bool = True
    store_step_raw_outputs: bool = True
    store_step_compact_outputs: bool = True
    cross_phase_handoff_mode: str = "compact"


@dataclass(slots=True)
class WorkflowSpec:
    workflow_id: str
    phases: list[BasePhase]
    description: str = ""
    start_phase_id: str | None = None
    terminal_phase_ids: tuple[str, ...] = ()
    max_total_steps: int = 100
    max_total_rollbacks: int = 20
    policy: WorkflowPolicy = field(default_factory=WorkflowPolicy)
    checkpoint_policy: CheckpointPolicy = field(default_factory=CheckpointPolicy)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowCheckpoint:
    workflow_id: str
    status: WorkflowStatus
    current_phase_id: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    phase_checkpoints: dict[str, PhaseCheckpoint] = field(default_factory=dict)
    global_artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TransitionInput:
    source: str = "normal_handoff"
    artifacts: dict[str, Any] = field(default_factory=dict)
    exception: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WorkflowRunState:
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_phase_id: str | None = None
    current_step_id: str | None = None
    total_steps_executed: int = 0
    total_rollbacks: int = 0
    total_failures: int = 0
    total_repairs: int = 0
    phase_states: dict[str, PhaseState] = field(default_factory=dict)
    global_artifacts: dict[str, Any] = field(default_factory=dict)
    phase_checkpoints: dict[str, PhaseCheckpoint] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    transition_input: TransitionInput = field(default_factory=TransitionInput)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StepTransition:
    action: str
    target_step_id: str | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PhaseTransition:
    action: str
    next_phase_id: str | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)


class WorkflowRuntime:
    """Workflow-level runtime kernel for Phase-Step orchestration.

    This runtime is spec-driven rather than config-file-driven. It does not assume
    any concrete LLM/provider/tool adapter. Concrete step implementations are
    responsible for their own execution details via BaseStep.run(...).
    """

    def __init__(self, spec: WorkflowSpec) -> None:
        if not spec.phases:
            raise ValueError("workflow spec must contain at least one phase")
        self.spec = spec
        self._phase_map = {phase.phase_id: phase for phase in spec.phases}
        if len(self._phase_map) != len(spec.phases):
            raise ValueError("workflow spec contains duplicate phase ids")

    def start(self, initial_artifacts: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> WorkflowRunState:
        start_phase_id = self.spec.start_phase_id or self.spec.phases[0].phase_id
        if start_phase_id not in self._phase_map:
            raise ValueError(f"unknown start phase id: {start_phase_id}")
        state = WorkflowRunState(
            workflow_id=self.spec.workflow_id,
            status=WorkflowStatus.RUNNING,
            current_phase_id=start_phase_id,
            global_artifacts=dict(initial_artifacts or {}),
            metadata=dict(metadata or {}),
        )
        for phase in self.spec.phases:
            state.phase_states[phase.phase_id] = PhaseState(phase_id=phase.phase_id)
        state.phase_states[start_phase_id].status = PhaseStatus.RUNNING
        return state

    def run(self, initial_artifacts: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> WorkflowRunState:
        state = self.start(initial_artifacts=initial_artifacts, metadata=metadata)
        while state.status == WorkflowStatus.RUNNING:
            phase_id = state.current_phase_id
            if phase_id is None:
                state.status = WorkflowStatus.FAILED
                state.errors.append({"code": "missing_current_phase", "message": "workflow running without a current phase"})
                break
            phase = self._phase_map[phase_id]
            self.run_phase(phase, state)
        return state

    def run_phase(self, phase: BasePhase, state: WorkflowRunState) -> None:
        phase_state = state.phase_states[phase.phase_id]
        phase_state.status = PhaseStatus.RUNNING
        steps = phase.steps()
        while phase_state.status == PhaseStatus.RUNNING:
            if phase_state.step_index >= len(steps):
                if phase.phase_exit_check(phase_state):
                    phase_state.status = PhaseStatus.COMPLETED
                    checkpoint = self.build_phase_handoff(phase, phase_state)
                    state.phase_checkpoints[phase.phase_id] = checkpoint
                    transition = self.resolve_phase_transition(phase, state)
                    self._apply_phase_transition(phase, state, transition)
                else:
                    phase_state.status = PhaseStatus.BLOCKED
                    state.status = WorkflowStatus.BLOCKED
                    state.errors.append({
                        "code": "phase_exit_check_failed",
                        "phase_id": phase.phase_id,
                        "message": "phase exit check failed",
                    })
                continue

            step = steps[phase_state.step_index]
            state.current_step_id = step.step_id
            result = self.run_step(phase, step, state)
            transition = self.resolve_step_transition(phase, step, result, state)
            self.handle_step_result(phase, step, result, transition, state)

    def run_step(self, phase: BasePhase, step: BaseStep, state: WorkflowRunState) -> StepResult:
        phase_state = state.phase_states[phase.phase_id]
        phase_state.step_attempts[step.step_id] = phase_state.step_attempts.get(step.step_id, 0) + 1
        state.total_steps_executed += 1
        ctx = self.build_step_context(phase, step, state)
        result = step.run(ctx)
        return step.mark_exit_ready(result, ctx)

    def build_step_context(self, phase: BasePhase, step: BaseStep, state: WorkflowRunState) -> StepContext:
        phase_state = state.phase_states[phase.phase_id]
        allowed_tool_families = step.allowed_tool_families(
            StepContext(phase_id=phase.phase_id, step_id=step.step_id)
        )
        allowed_tools = step.allowed_tools(
            StepContext(phase_id=phase.phase_id, step_id=step.step_id)
        )
        return StepContext(
            phase_id=phase.phase_id,
            step_id=step.step_id,
            attempt=phase_state.step_attempts.get(step.step_id, 0) + 1,
            inputs=dict(state.global_artifacts),
            shared_state=phase_state.shared_state,
            available_artifacts=state.global_artifacts,
            allowed_tool_families=allowed_tool_families or phase.allowed_tool_families(),
            allowed_tools=allowed_tools or phase.allowed_tools(),
            tool_budget_snapshot=dict(phase_state.budget_usage or phase.tool_budget()),
            metadata={
                "workflow_id": state.workflow_id,
                "transition_source": state.transition_input.source,
                "transition_notes": list(state.transition_input.notes),
            },
        )

    def resolve_step_transition(self, phase: BasePhase, step: BaseStep, result: StepResult, state: WorkflowRunState) -> StepTransition:
        phase_state = state.phase_states[phase.phase_id]
        if result.status == StepStatus.COMPLETED and result.exit_ready:
            return StepTransition(action="advance_to_next_step", reason="step exit-condition satisfied")
        if result.status in {StepStatus.INCOMPLETE, StepStatus.INVALID}:
            if phase.can_rerun_step(phase_state, step.step_id):
                return StepTransition(action="rerun_same_step", reason="step may rerun inside current phase")
            rollback = phase.select_rollback_target(phase_state, step.step_id)
            if rollback.allowed and rollback.target_step_id is not None:
                return StepTransition(
                    action="rollback_to_anchor_step",
                    target_step_id=rollback.target_step_id,
                    reason=rollback.reason,
                    notes=list(rollback.notes),
                )
            if result.status == StepStatus.INVALID:
                return StepTransition(action="phase_failed", reason="step invalid and no recovery path available")
            return StepTransition(action="phase_blocked", reason="step incomplete and no recovery path available")
        if result.status == StepStatus.BLOCKED:
            return StepTransition(action="phase_blocked", reason="step reported blocked")
        if result.status == StepStatus.FAILED:
            return StepTransition(action="phase_failed", reason="step reported failed")
        return StepTransition(action="phase_failed", reason="unexpected step status")

    def handle_step_result(
        self,
        phase: BasePhase,
        step: BaseStep,
        result: StepResult,
        transition: StepTransition,
        state: WorkflowRunState,
    ) -> None:
        phase_state = state.phase_states[phase.phase_id]
        phase.mark_step_result(phase_state, result)
        if result.compact_output is not None:
            state.global_artifacts[f"step:{step.step_id}:compact"] = result.compact_output
        if result.output is not None:
            state.global_artifacts[f"step:{step.step_id}:output"] = result.output
        if result.produced_artifacts:
            state.global_artifacts.update(result.produced_artifacts)
        if result.error is not None:
            state.errors.append({
                "step_id": step.step_id,
                "code": result.error.code,
                "message": result.error.message,
                "details": result.error.details,
            })

        if transition.action == "advance_to_next_step":
            return
        if transition.action == "rerun_same_step":
            phase_state.step_index = max(phase_state.step_index - 1, 0)
            state.transition_input = TransitionInput(source="rerun", artifacts=dict(result.produced_artifacts), notes=[transition.reason])
            return
        if transition.action == "rollback_to_anchor_step":
            target = transition.target_step_id
            if target is None:
                phase_state.status = PhaseStatus.FAILED
                state.status = WorkflowStatus.FAILED
                state.errors.append({"code": "missing_rollback_target", "phase_id": phase.phase_id})
                return
            target_index = self._find_step_index(phase, target)
            phase_state.step_index = target_index
            phase_state.rollback_count += 1
            state.total_rollbacks += 1
            state.transition_input = TransitionInput(source="rollback", artifacts=dict(result.produced_artifacts), notes=[transition.reason])
            return
        if transition.action == "phase_blocked":
            phase_state.status = PhaseStatus.BLOCKED
            state.status = WorkflowStatus.BLOCKED
            state.transition_input = TransitionInput(source="exception", artifacts=dict(result.produced_artifacts), notes=[transition.reason])
            return
        if transition.action == "phase_failed":
            phase_state.status = PhaseStatus.FAILED
            state.status = WorkflowStatus.FAILED
            state.total_failures += 1
            state.transition_input = TransitionInput(source="exception", artifacts=dict(result.produced_artifacts), notes=[transition.reason])
            return
        phase_state.status = PhaseStatus.FAILED
        state.status = WorkflowStatus.FAILED
        state.errors.append({"code": "unknown_step_transition", "step_id": step.step_id, "transition": transition.action})

    def resolve_phase_transition(self, phase: BasePhase, state: WorkflowRunState) -> PhaseTransition:
        next_phase_id = phase.next_phase()
        if next_phase_id is None:
            if self.spec.policy.strict_terminal_phase_only and phase.phase_id not in self.spec.terminal_phase_ids:
                return PhaseTransition(action="workflow_blocked", reason="phase completed but is not terminal and has no next phase")
            return PhaseTransition(action="workflow_completed", reason="terminal phase completed")
        if next_phase_id not in self._phase_map:
            return PhaseTransition(action="workflow_failed", reason=f"unknown next phase: {next_phase_id}")
        return PhaseTransition(action="advance_to_next_phase", next_phase_id=next_phase_id, reason="phase completed successfully")

    def build_phase_handoff(self, phase: BasePhase, phase_state: PhaseState) -> PhaseCheckpoint:
        checkpoint = phase.finalize_phase(phase_state)
        if self.spec.checkpoint_policy.store_step_compact_outputs:
            for step_id, compact in checkpoint.compact_bundle.items():
                pass
        return checkpoint

    def finalize_workflow(self, state: WorkflowRunState) -> WorkflowCheckpoint:
        return WorkflowCheckpoint(
            workflow_id=state.workflow_id,
            status=state.status,
            current_phase_id=state.current_phase_id,
            summary={"notes": list(state.notes), "errors": list(state.errors)},
            phase_checkpoints=dict(state.phase_checkpoints),
            global_artifacts=dict(state.global_artifacts),
            metadata=dict(state.metadata),
        )

    def _apply_phase_transition(self, phase: BasePhase, state: WorkflowRunState, transition: PhaseTransition) -> None:
        if transition.action == "advance_to_next_phase":
            next_phase_id = transition.next_phase_id
            if next_phase_id is None:
                state.status = WorkflowStatus.FAILED
                state.errors.append({"code": "missing_next_phase", "phase_id": phase.phase_id})
                return
            state.current_phase_id = next_phase_id
            state.current_step_id = None
            next_phase_state = state.phase_states[next_phase_id]
            next_phase_state.status = PhaseStatus.RUNNING
            state.transition_input = TransitionInput(source="normal_handoff", artifacts=dict(state.global_artifacts), notes=[transition.reason])
            return
        if transition.action == "workflow_completed":
            state.status = WorkflowStatus.COMPLETED
            state.current_step_id = None
            state.transition_input = TransitionInput(source="normal_handoff", artifacts=dict(state.global_artifacts), notes=[transition.reason])
            return
        if transition.action == "workflow_blocked":
            state.status = WorkflowStatus.BLOCKED
            state.current_step_id = None
            state.errors.append({"code": "workflow_blocked", "phase_id": phase.phase_id, "message": transition.reason})
            return
        state.status = WorkflowStatus.FAILED
        state.current_step_id = None
        state.errors.append({"code": "workflow_failed", "phase_id": phase.phase_id, "message": transition.reason})

    def _find_step_index(self, phase: BasePhase, step_id: str) -> int:
        steps = phase.steps()
        for idx, step in enumerate(steps):
            if step.step_id == step_id:
                return idx
        raise ValueError(f"unknown step id '{step_id}' in phase '{phase.phase_id}'")
