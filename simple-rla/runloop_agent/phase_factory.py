from __future__ import annotations

from typing import Any

from runloop_agent.mcp_client import McpClient
from runloop_agent.phase import BasePhase, PhaseSpec, PhaseState
from runloop_agent.step import BaseStep
from runloop_agent.step_factory import build_step


class StandardPhase(BasePhase):
    def __init__(
        self,
        *,
        phase_id: str,
        steps: list[BaseStep],
        next_phase_id: str | None,
        max_rollbacks: int = 0,
        max_step_attempts: int = 1,
    ) -> None:
        super().__init__(PhaseSpec(
            phase_id=phase_id,
            max_rollbacks=max_rollbacks,
            max_step_attempts=max_step_attempts,
        ))
        self._steps = steps
        self._next_phase_id = next_phase_id

    def steps(self) -> list[BaseStep]:
        return self._steps

    def phase_exit_check(self, state: PhaseState) -> bool:
        if len(state.completed_step_results) != len(self._steps):
            return False
        return all(result.exit_ready for result in state.completed_step_results.values())

    def next_phase(self) -> str | None:
        return self._next_phase_id


def build_phase(phase_cfg: dict[str, Any], *, mcp_client: McpClient | None = None) -> BasePhase:
    if not isinstance(phase_cfg, dict):
        raise ValueError(f"invalid phase config: {phase_cfg!r}")

    phase_type = str(phase_cfg.get("type") or "standard_phase").strip()
    if phase_type != "standard_phase":
        raise ValueError(f"unknown phase type: {phase_type}")

    phase_id = str(phase_cfg.get("id") or "").strip()
    if not phase_id:
        raise ValueError(f"phase missing id: {phase_cfg!r}")

    raw_steps = phase_cfg.get("steps") or []
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError(f"phase '{phase_id}' must define a non-empty steps list")

    steps = [build_step(step_cfg, mcp_client=mcp_client) for step_cfg in raw_steps]
    next_phase_id = str(phase_cfg.get("next_phase") or "").strip() or None
    max_rollbacks = int(phase_cfg.get("max_rollbacks", 0) or 0)
    max_step_attempts = int(phase_cfg.get("max_step_attempts", 1) or 1)

    return StandardPhase(
        phase_id=phase_id,
        steps=steps,
        next_phase_id=next_phase_id,
        max_rollbacks=max_rollbacks,
        max_step_attempts=max_step_attempts,
    )
