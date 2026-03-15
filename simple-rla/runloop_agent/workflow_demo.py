from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Allow running as a script from inside the runloop_agent/ directory.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runloop_agent.runtime_config import apply_runtime_config, load_runtime_config
from runloop_agent.workflow_loader import load_workflow
from runloop_agent.workflow_runtime import WorkflowRuntime


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase-Step workflow runtime demo")
    parser.add_argument("--config", default=str(Path(__file__).with_name("demo.yaml")), help="Path to demo yaml")
    parser.add_argument("--runtime-config", default=None, help="Path to runtime toml config")
    parser.add_argument("--initial-artifact", action="append", default=[], help="Extra initial artifact in key=value form")
    parser.add_argument("--log-level", default="INFO", help="DEBUG|INFO|WARNING|ERROR")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("simple_rla.workflow_demo")

    runtime_cfg = load_runtime_config(args.runtime_config)
    apply_runtime_config(runtime_cfg)

    spec = load_workflow(args.config)

    initial_artifacts: dict[str, str] = {}
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
