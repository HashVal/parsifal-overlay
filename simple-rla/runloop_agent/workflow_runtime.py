from __future__ import annotations

import logging
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


log = logging.getLogger("simple_rla.workflow_runtime")


def _visible_inputs_for_step(step: BaseStep, artifacts: dict[str, Any]) -> dict[str, Any]:
    step_type = step.__class__.__name__
    if step_type not in {"LLMStep", "LLMToolStep"}:
        return dict(artifacts)
    visible = {
        key: value
        for key, value in artifacts.items()
        if not str(key).startswith("step:")
    }
    allowlist = (step.spec.metadata or {}).get("visible_artifacts")
    if isinstance(allowlist, list) and allowlist:
        selected: dict[str, Any] = {}
        for key in allowlist:
            key_text = str(key)
            if key_text in visible:
                selected[key_text] = visible[key_text]
        return selected
    return visible


class WorkflowRuntime:
    """Workflow-level runtime kernel for Phase-Step orchestration.

    This runtime is spec-driven rather than config-file-driven. It does not assume
    any concrete LLM/provider/tool adapter. Concrete step implementations are
    responsible for their own execution details via BaseStep.run(...).
    """

    def __init__(self, spec: WorkflowSpec, *, incremental_dump_dir: str | None = None) -> None:
        if not spec.phases:
            raise ValueError("workflow spec must contain at least one phase")
        self.spec = spec
        self.incremental_dump_dir = incremental_dump_dir
        self._phase_map = {phase.phase_id: phase for phase in spec.phases}
        if len(self._phase_map) != len(spec.phases):
            raise ValueError("workflow spec contains duplicate phase ids")
        log.info(
            "workflow.init id=%s phases=%s start=%s terminals=%s",
            spec.workflow_id,
            [phase.phase_id for phase in spec.phases],
            spec.start_phase_id or spec.phases[0].phase_id,
            list(spec.terminal_phase_ids),
        )

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
        log.info(
            "workflow.start id=%s start_phase=%s initial_artifacts=%s metadata_keys=%s",
            state.workflow_id,
            start_phase_id,
            sorted(state.global_artifacts.keys()),
            sorted(state.metadata.keys()),
        )
        self._write_incremental_progress(state)
        return state

    def run(self, initial_artifacts: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> WorkflowRunState:
        state = self.start(initial_artifacts=initial_artifacts, metadata=metadata)
        while state.status == WorkflowStatus.RUNNING:
            phase_id = state.current_phase_id
            if phase_id is None:
                state.status = WorkflowStatus.FAILED
                state.errors.append({"code": "missing_current_phase", "message": "workflow running without a current phase"})
                self._write_incremental_progress(state)
                break
            phase = self._phase_map[phase_id]
            self.run_phase(phase, state)
        return state

    def run_phase(self, phase: BasePhase, state: WorkflowRunState) -> None:
        phase_state = state.phase_states[phase.phase_id]
        phase_state.status = PhaseStatus.RUNNING
        steps = phase.steps()
        log.info(
            "phase.start workflow=%s phase=%s step_count=%d rollback_count=%d budget=%s",
            state.workflow_id,
            phase.phase_id,
            len(steps),
            phase_state.rollback_count,
            phase.tool_budget(),
        )
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
                    self._write_incremental_progress(state)
                continue

            step = steps[phase_state.step_index]
            state.current_step_id = step.step_id
            result = self.run_step(phase, step, state)
            transition = self.resolve_step_transition(phase, step, result, state)
            log.info(
                "step.transition workflow=%s phase=%s step=%s status=%s exit_ready=%s action=%s reason=%s",
                state.workflow_id,
                phase.phase_id,
                step.step_id,
                result.status.value,
                result.exit_ready,
                transition.action,
                transition.reason,
            )
            self.handle_step_result(phase, step, result, transition, state)

    def run_step(self, phase: BasePhase, step: BaseStep, state: WorkflowRunState) -> StepResult:
        phase_state = state.phase_states[phase.phase_id]
        phase_state.step_attempts[step.step_id] = phase_state.step_attempts.get(step.step_id, 0) + 1
        state.total_steps_executed += 1
        ctx = self.build_step_context(phase, step, state)
        log.info(
            "step.start workflow=%s phase=%s step=%s attempt=%d input_keys=%s transition_source=%s",
            state.workflow_id,
            phase.phase_id,
            step.step_id,
            ctx.attempt,
            sorted(ctx.inputs.keys()),
            state.transition_input.source,
        )
        result = step.run(ctx)
        result = step.mark_exit_ready(result, ctx)
        log.info(
            "step.end workflow=%s phase=%s step=%s attempt=%d status=%s exit_ready=%s produced_artifacts=%s",
            state.workflow_id,
            phase.phase_id,
            step.step_id,
            ctx.attempt,
            result.status.value,
            result.exit_ready,
            sorted(result.produced_artifacts.keys()),
        )
        return result

    def build_step_context(self, phase: BasePhase, step: BaseStep, state: WorkflowRunState) -> StepContext:
        phase_state = state.phase_states[phase.phase_id]
        allowed_tool_families = step.allowed_tool_families(
            StepContext(phase_id=phase.phase_id, step_id=step.step_id)
        )
        allowed_tools = step.allowed_tools(
            StepContext(phase_id=phase.phase_id, step_id=step.step_id)
        )
        visible_inputs = _visible_inputs_for_step(step, state.global_artifacts)
        return StepContext(
            phase_id=phase.phase_id,
            step_id=step.step_id,
            attempt=phase_state.step_attempts.get(step.step_id, 0),
            inputs=visible_inputs,
            shared_state=phase_state.shared_state,
            available_artifacts=state.global_artifacts,
            allowed_tool_families=allowed_tool_families or phase.allowed_tool_families(),
            allowed_tools=allowed_tools or phase.allowed_tools(),
            tool_budget_snapshot=dict(phase_state.budget_usage or phase.tool_budget()),
            metadata={
                "workflow_id": state.workflow_id,
                "transition_source": state.transition_input.source,
                "transition_notes": list(state.transition_input.notes),
                "run_root": state.metadata.get("run_root"),
                "enable_real_time_output": bool(state.metadata.get("enable_real_time_output")),
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

        self._write_incremental_step_result(phase.phase_id, step.step_id, result)
        self._write_incremental_progress(state)

        if transition.action == "advance_to_next_step":
            return
        if transition.action == "rerun_same_step":
            state.transition_input = TransitionInput(source="rerun", artifacts=dict(result.produced_artifacts), notes=[transition.reason])
            self._write_incremental_progress(state)
            return
        if transition.action == "rollback_to_anchor_step":
            target = transition.target_step_id
            if target is None:
                phase_state.status = PhaseStatus.FAILED
                state.status = WorkflowStatus.FAILED
                state.errors.append({"code": "missing_rollback_target", "phase_id": phase.phase_id})
                self._write_incremental_progress(state)
                return
            target_index = self._find_step_index(phase, target)
            phase_state.step_index = target_index
            phase_state.rollback_count += 1
            state.total_rollbacks += 1
            state.transition_input = TransitionInput(source="rollback", artifacts=dict(result.produced_artifacts), notes=[transition.reason])
            self._write_incremental_progress(state)
            return
        if transition.action == "phase_blocked":
            phase_state.status = PhaseStatus.BLOCKED
            state.status = WorkflowStatus.BLOCKED
            state.transition_input = TransitionInput(source="exception", artifacts=dict(result.produced_artifacts), notes=[transition.reason])
            self._write_incremental_progress(state)
            return
        if transition.action == "phase_failed":
            phase_state.status = PhaseStatus.FAILED
            state.status = WorkflowStatus.FAILED
            state.total_failures += 1
            state.transition_input = TransitionInput(source="exception", artifacts=dict(result.produced_artifacts), notes=[transition.reason])
            self._write_incremental_progress(state)
            return
        phase_state.status = PhaseStatus.FAILED
        state.status = WorkflowStatus.FAILED
        state.errors.append({"code": "unknown_step_transition", "step_id": step.step_id, "transition": transition.action})
        self._write_incremental_progress(state)

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
        log.info(
            "phase.handoff phase=%s status=%s compact_keys=%s step_outputs=%s",
            phase.phase_id,
            checkpoint.status.value,
            sorted(checkpoint.compact_bundle.keys()),
            sorted(checkpoint.step_outputs.keys()),
        )
        if self.spec.checkpoint_policy.store_step_compact_outputs:
            for step_id, compact in checkpoint.compact_bundle.items():
                pass
        return checkpoint

    def finalize_workflow(self, state: WorkflowRunState) -> WorkflowCheckpoint:
        log.info(
            "workflow.finalize id=%s status=%s current_phase=%s errors=%d artifacts=%s",
            state.workflow_id,
            state.status.value,
            state.current_phase_id,
            len(state.errors),
            sorted(state.global_artifacts.keys()),
        )
        self._write_incremental_progress(state)
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
        log.info(
            "phase.transition workflow=%s phase=%s action=%s next=%s reason=%s",
            state.workflow_id,
            phase.phase_id,
            transition.action,
            transition.next_phase_id,
            transition.reason,
        )
        if transition.action == "advance_to_next_phase":
            next_phase_id = transition.next_phase_id
            if next_phase_id is None:
                state.status = WorkflowStatus.FAILED
                state.errors.append({"code": "missing_next_phase", "phase_id": phase.phase_id})
                self._write_incremental_progress(state)
                return
            state.current_phase_id = next_phase_id
            state.current_step_id = None
            next_phase_state = state.phase_states[next_phase_id]
            next_phase_state.status = PhaseStatus.RUNNING
            state.transition_input = TransitionInput(source="normal_handoff", artifacts=dict(state.global_artifacts), notes=[transition.reason])
            self._write_incremental_progress(state)
            return
        if transition.action == "workflow_completed":
            state.status = WorkflowStatus.COMPLETED
            state.current_step_id = None
            state.transition_input = TransitionInput(source="normal_handoff", artifacts=dict(state.global_artifacts), notes=[transition.reason])
            self._write_incremental_progress(state)
            return
        if transition.action == "workflow_blocked":
            state.status = WorkflowStatus.BLOCKED
            state.current_step_id = None
            state.errors.append({"code": "workflow_blocked", "phase_id": phase.phase_id, "message": transition.reason})
            self._write_incremental_progress(state)
            return
        state.status = WorkflowStatus.FAILED
        state.current_step_id = None
        state.errors.append({"code": "workflow_failed", "phase_id": phase.phase_id, "message": transition.reason})
        self._write_incremental_progress(state)

    def _write_incremental_step_result(self, phase_id: str, step_id: str, result: StepResult) -> None:
        if not self.incremental_dump_dir:
            return
        try:
            from runloop_agent.workflow_dump import write_incremental_step_result
            write_incremental_step_result(self.incremental_dump_dir, phase_id=phase_id, step_id=step_id, result=result)
        except Exception as exc:
            log.warning("incremental.step_dump_failed phase=%s step=%s error=%s", phase_id, step_id, exc)

    def _write_incremental_progress(self, state: WorkflowRunState) -> None:
        if not self.incremental_dump_dir:
            return
        try:
            from runloop_agent.workflow_dump import write_workflow_progress
            write_workflow_progress(self.incremental_dump_dir, state)
        except Exception as exc:
            log.warning("incremental.workflow_progress_failed workflow=%s error=%s", state.workflow_id, exc)

    def _find_step_index(self, phase: BasePhase, step_id: str) -> int:
        steps = phase.steps()
        for idx, step in enumerate(steps):
            if step.step_id == step_id:
                return idx
        raise ValueError(f"unknown step id '{step_id}' in phase '{phase.phase_id}'")
