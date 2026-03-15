from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from runloop_agent.workflow_runtime import WorkflowCheckpoint, WorkflowRunState


def default_dump_dir(workflow_id: str, base_dir: str | Path = "./artifacts/runloop") -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return (Path(base_dir) / workflow_id / ts).resolve()


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "value") and isinstance(getattr(value, "value"), (str, int, float, bool, type(None))):
        return value.value
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def dump_workflow_run(dump_dir: str | Path, state: WorkflowRunState, checkpoint: WorkflowCheckpoint) -> Path:
    root = Path(dump_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow_summary = {
        "workflow_id": state.workflow_id,
        "status": state.status,
        "current_phase_id": state.current_phase_id,
        "current_step_id": state.current_step_id,
        "errors": list(state.errors),
        "global_artifact_keys": sorted(state.global_artifacts.keys()),
        "phase_ids": sorted(state.phase_states.keys()),
        "metadata": dict(state.metadata),
    }
    _write_json(root / "workflow_summary.json", workflow_summary)

    workflow_checkpoint_payload = {
        "workflow_id": checkpoint.workflow_id,
        "status": checkpoint.status,
        "current_phase_id": checkpoint.current_phase_id,
        "summary": checkpoint.summary,
        "phase_checkpoints": checkpoint.phase_checkpoints,
        "global_artifacts": checkpoint.global_artifacts,
        "metadata": checkpoint.metadata,
    }
    _write_json(root / "workflow_checkpoint.json", workflow_checkpoint_payload)

    phase_states_payload: dict[str, Any] = {}
    for phase_id, phase_state in state.phase_states.items():
        phase_states_payload[phase_id] = {
            "status": phase_state.status,
            "step_index": phase_state.step_index,
            "rollback_count": phase_state.rollback_count,
            "step_attempts": dict(phase_state.step_attempts),
            "notes": list(phase_state.notes),
            "completed_step_ids": sorted(phase_state.completed_step_results.keys()),
            "shared_state": dict(phase_state.shared_state),
            "available_artifacts": dict(phase_state.available_artifacts),
        }
    _write_json(root / "phase_states.json", phase_states_payload)

    step_results_dir = root / "step_results"
    for phase_id, phase_state in state.phase_states.items():
        for step_id, result in phase_state.completed_step_results.items():
            payload = {
                "phase_id": phase_id,
                "step_id": step_id,
                "result": result,
            }
            _write_json(step_results_dir / f"{phase_id}__{step_id}.json", payload)

    return root
