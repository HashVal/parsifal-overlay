from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Allow running as a script from inside the runloop_agent/ directory.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from runloop_agent.phase import BasePhase, PhaseSpec, PhaseState
from runloop_agent.step import BaseStep, StepContext, StepResult, StepSpec, StepStatus
from runloop_agent.workflow_runtime import WorkflowRuntime, WorkflowSpec


class EchoStep(BaseStep):
    def build_prompt(self, ctx: StepContext) -> str | dict[str, Any]:
        return {"step_id": self.step_id, "mode": "echo"}

    def run(self, ctx: StepContext) -> StepResult:
        output = {
            "step_id": self.step_id,
            "phase_id": ctx.phase_id,
            "attempt": ctx.attempt,
            "inputs": sorted(ctx.inputs.keys()),
        }
        return StepResult(
            step_id=self.step_id,
            status=StepStatus.COMPLETED,
            output=output,
            compact_output={"step_id": self.step_id, "attempt": ctx.attempt},
            produced_artifacts={f"artifact:{self.step_id}": output},
            notes=["echo step completed"],
        )

    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        return True


class IncompleteOnceStep(BaseStep):
    def build_prompt(self, ctx: StepContext) -> str | dict[str, Any]:
        return {"step_id": self.step_id, "mode": "incomplete_once"}

    def run(self, ctx: StepContext) -> StepResult:
        if ctx.attempt == 1:
            return StepResult(
                step_id=self.step_id,
                status=StepStatus.INCOMPLETE,
                output={"step_id": self.step_id, "attempt": ctx.attempt, "status": "needs_rerun"},
                compact_output={"step_id": self.step_id, "attempt": ctx.attempt, "status": "needs_rerun"},
                notes=["first attempt intentionally incomplete"],
            )
        output = {
            "step_id": self.step_id,
            "attempt": ctx.attempt,
            "status": "completed_after_rerun",
        }
        return StepResult(
            step_id=self.step_id,
            status=StepStatus.COMPLETED,
            output=output,
            compact_output={"step_id": self.step_id, "status": output["status"]},
            produced_artifacts={f"artifact:{self.step_id}": output},
            notes=["completed on rerun"],
        )

    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        return result.status == StepStatus.COMPLETED


class ArtifactReportStep(BaseStep):
    def build_prompt(self, ctx: StepContext) -> str | dict[str, Any]:
        return {"step_id": self.step_id, "mode": "artifact_report"}

    def run(self, ctx: StepContext) -> StepResult:
        artifact_keys = sorted(ctx.available_artifacts.keys())
        output = {
            "step_id": self.step_id,
            "artifact_keys": artifact_keys,
            "artifact_count": len(artifact_keys),
        }
        return StepResult(
            step_id=self.step_id,
            status=StepStatus.COMPLETED,
            output=output,
            compact_output={"artifact_count": len(artifact_keys)},
            produced_artifacts={f"artifact:{self.step_id}": output},
            notes=["artifact report generated"],
        )

    def validate_exit(self, result: StepResult, ctx: StepContext) -> bool:
        return True


STEP_TYPES: dict[str, type[BaseStep]] = {
    "echo_step": EchoStep,
    "incomplete_once_step": IncompleteOnceStep,
    "artifact_report_step": ArtifactReportStep,
}


class DemoPhase(BasePhase):
    def __init__(
        self,
        *,
        phase_id: str,
        step_defs: list[dict[str, Any]],
        next_phase_id: str | None,
        max_rollbacks: int = 0,
        max_step_attempts: int = 1,
    ) -> None:
        super().__init__(PhaseSpec(
            phase_id=phase_id,
            max_rollbacks=max_rollbacks,
            max_step_attempts=max_step_attempts,
        ))
        self._next_phase_id = next_phase_id
        self._steps = [self._build_step(sd) for sd in step_defs]

    def _build_step(self, step_def: dict[str, Any]) -> BaseStep:
        step_type = str(step_def.get("type") or "").strip()
        step_id = str(step_def.get("id") or "").strip()
        if not step_type or not step_id:
            raise ValueError(f"invalid demo step definition: {step_def}")
        step_cls = STEP_TYPES.get(step_type)
        if step_cls is None:
            raise ValueError(f"unknown demo step type: {step_type}")
        return step_cls(StepSpec(step_id=step_id, metadata=dict(step_def.get("config") or {})))

    def steps(self) -> list[BaseStep]:
        return self._steps

    def phase_exit_check(self, state: PhaseState) -> bool:
        if len(state.completed_step_results) != len(self._steps):
            return False
        return all(result.exit_ready for result in state.completed_step_results.values())

    def next_phase(self) -> str | None:
        return self._next_phase_id


PHASE_TYPES = {
    "demo_phase": DemoPhase,
}


def load_demo_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("demo yaml top-level must be a mapping")
    return data


def build_workflow_spec(data: dict[str, Any]) -> WorkflowSpec:
    workflow_id = str(data.get("workflow_id") or "demo_workflow")
    start_phase_id = str(data.get("start_phase") or "").strip() or None
    terminal_phases = tuple(str(x) for x in (data.get("terminal_phases") or []) if str(x).strip())
    phases_raw = data.get("phases") or []
    if not isinstance(phases_raw, list) or not phases_raw:
        raise ValueError("demo yaml must define a non-empty phases list")

    phases: list[BasePhase] = []
    for item in phases_raw:
        if not isinstance(item, dict):
            raise ValueError(f"invalid phase entry: {item!r}")
        phase_type = str(item.get("type") or "demo_phase").strip()
        phase_cls = PHASE_TYPES.get(phase_type)
        if phase_cls is None:
            raise ValueError(f"unknown demo phase type: {phase_type}")
        phase_id = str(item.get("id") or "").strip()
        if not phase_id:
            raise ValueError(f"phase missing id: {item}")
        steps = item.get("steps") or []
        if not isinstance(steps, list) or not steps:
            raise ValueError(f"phase '{phase_id}' must define a non-empty steps list")
        next_phase_id = str(item.get("next_phase") or "").strip() or None
        phases.append(
            phase_cls(
                phase_id=phase_id,
                step_defs=steps,
                next_phase_id=next_phase_id,
                max_rollbacks=int(item.get("max_rollbacks", 0) or 0),
                max_step_attempts=int(item.get("max_step_attempts", 1) or 1),
            )
        )

    if not start_phase_id:
        start_phase_id = phases[0].phase_id
    if not terminal_phases:
        last_phase = phases[-1].phase_id
        terminal_phases = (last_phase,)

    return WorkflowSpec(
        workflow_id=workflow_id,
        phases=phases,
        start_phase_id=start_phase_id,
        terminal_phase_ids=terminal_phases,
        metadata={"source": "workflow_demo"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase-Step workflow runtime demo")
    parser.add_argument("--config", default=str(Path(__file__).with_name("demo.yaml")), help="Path to demo yaml")
    parser.add_argument("--initial-artifact", action="append", default=[], help="Extra initial artifact in key=value form")
    parser.add_argument("--log-level", default="INFO", help="DEBUG|INFO|WARNING|ERROR")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("simple_rla.workflow_demo")

    demo = load_demo_yaml(args.config)
    spec = build_workflow_spec(demo)

    initial_artifacts: dict[str, Any] = {}
    for item in args.initial_artifact:
        if "=" not in item:
            raise ValueError(f"invalid --initial-artifact: {item!r}")
        key, value = item.split("=", 1)
        initial_artifacts[key] = value

    log.info(
        "workflow_demo.start config=%s workflow_id=%s initial_artifacts=%s",
        args.config,
        spec.workflow_id,
        sorted(initial_artifacts.keys()),
    )
    runtime = WorkflowRuntime(spec)
    state = runtime.run(initial_artifacts=initial_artifacts, metadata={"entry": "workflow_demo.py"})
    checkpoint = runtime.finalize_workflow(state)
    log.info(
        "workflow_demo.done workflow_id=%s status=%s current_phase=%s errors=%d",
        spec.workflow_id,
        state.status.value,
        state.current_phase_id,
        len(state.errors),
    )

    print("=== WORKFLOW STATUS ===")
    print(state.status.value)
    print("=== CURRENT PHASE ===")
    print(state.current_phase_id)
    print("=== CURRENT STEP ===")
    print(state.current_step_id)
    print("=== GLOBAL ARTIFACTS ===")
    print(json.dumps(state.global_artifacts, ensure_ascii=False, indent=2, default=str))
    print("=== PHASE CHECKPOINTS ===")
    print(json.dumps({k: v.summary for k, v in state.phase_checkpoints.items()}, ensure_ascii=False, indent=2, default=str))
    print("=== WORKFLOW CHECKPOINT ===")
    print(json.dumps({
        "workflow_id": checkpoint.workflow_id,
        "status": checkpoint.status.value,
        "current_phase_id": checkpoint.current_phase_id,
        "summary": checkpoint.summary,
        "phase_ids": list(checkpoint.phase_checkpoints.keys()),
    }, ensure_ascii=False, indent=2, default=str))
    if state.errors:
        print("=== ERRORS ===")
        print(json.dumps(state.errors, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
