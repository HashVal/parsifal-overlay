from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from runloop_agent.mcp_client import McpClient
from runloop_agent.phase import BasePhase
from runloop_agent.phase_factory import build_phase
from runloop_agent.workflow_runtime import WorkflowSpec


def load_workflow(path: str | Path, *, mcp_client: McpClient | None = None) -> WorkflowSpec:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("workflow yaml top-level must be a mapping")

    workflow_id = str(data.get("workflow_id") or "demo_workflow")
    start_phase_id = str(data.get("start_phase") or "").strip() or None
    terminal_phases = tuple(str(x) for x in (data.get("terminal_phases") or []) if str(x).strip())
    raw_phases = data.get("phases") or []
    if not isinstance(raw_phases, list) or not raw_phases:
        raise ValueError("workflow yaml must define a non-empty phases list")

    phases: list[BasePhase] = [build_phase(phase_cfg, mcp_client=mcp_client) for phase_cfg in raw_phases]

    if not start_phase_id:
        start_phase_id = phases[0].phase_id
    if not terminal_phases:
        terminal_phases = (phases[-1].phase_id,)

    return WorkflowSpec(
        workflow_id=workflow_id,
        phases=phases,
        start_phase_id=start_phase_id,
        terminal_phase_ids=terminal_phases,
        metadata={"source": "workflow_loader"},
    )
