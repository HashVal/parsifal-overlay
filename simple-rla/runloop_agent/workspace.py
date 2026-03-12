from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunWorkspace:
    run_id: str
    root: Path
    dumps_dir: Path
    attachments_dir: Path
    log_path: Path
    meta_path: Path


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _safe_part(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in (value or "").strip())
    return safe or "adhoc"


def create_run_workspace(*, artifacts_root: Path, jira_key: str = "") -> RunWorkspace:
    issue_part = _safe_part(jira_key or "adhoc")
    run_id = _now_tag()
    root = (artifacts_root / "runs" / issue_part / run_id).resolve()
    dumps_dir = root / "dumps"
    attachments_dir = root / "attachments"
    log_path = root / "session.log"
    meta_path = root / "meta.json"

    attachments_dir.mkdir(parents=True, exist_ok=True)
    return RunWorkspace(
        run_id=run_id,
        root=root,
        dumps_dir=dumps_dir,
        attachments_dir=attachments_dir,
        log_path=log_path,
        meta_path=meta_path,
    )


def write_workspace_meta(ws: RunWorkspace, payload: dict[str, Any]) -> None:
    ws.root.mkdir(parents=True, exist_ok=True)
    ws.meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def workspace_env(ws: RunWorkspace) -> dict[str, str]:
    return {
        "SIMPLE_RLA_WORKSPACE_DIR": str(ws.root),
        "SIMPLE_RLA_ATTACHMENTS_DIR": str(ws.attachments_dir),
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
