"""Parsifal MCP server exposing overlay tools to nanobot via MCP.

Usage (stdio):
  python3 /home/node/.openclaw/workspace/parsifal/parsifal-overlay/mcp_server.py

Env overrides:
  PARSIFAL_SPEC_ROOT        (default: ../kernel-rca-bot)
  PARSIFAL_ARTIFACTS_ROOT   (default: ../artifacts)
  PARSIFAL_TEMPLATES_ROOT   (default: ./templates)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "mcp is required. Install with: pip install mcp\n"
        f"Import error: {exc}"
    )


# Ensure overlay root is importable so `tools.*` works when run as a script.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.parsifal_render import ParsifalRenderer
from tools.parsifal_artifacts import ParsifalArtifacts
from tools.parsifal_validate import ParsifalValidator


mcp = FastMCP("parsifal")


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


@mcp.tool()
def parsifal_render(
    debug_steps: dict | None = None,
    key_evidence: dict | None = None,
    jira_comment: dict | None = None,
    out_dir: str | None = None,
    debug_steps_path: str | None = None,
    key_evidence_path: str | None = None,
    jira_comment_path: str | None = None,
    jira_key: str | None = None,
    round: int | None = None,
    evidence_index: int | None = None,
) -> str:
    renderer = ParsifalRenderer()
    result = renderer.render(
        debug_steps=debug_steps,
        key_evidence=key_evidence,
        jira_comment=jira_comment,
        out_dir=out_dir,
        debug_steps_path=debug_steps_path,
        key_evidence_path=key_evidence_path,
        jira_comment_path=jira_comment_path,
        jira_key=jira_key,
        round=round,
        evidence_index=evidence_index,
    )
    return _dump(result.__dict__)


@mcp.tool()
def parsifal_artifacts(
    action: str,
    issue_id: str | None = None,
    run_dir: str | None = None,
    timestamp: str | None = None,
    device_id: str | None = None,
    log_path: str | None = None,
    log_paths: list[str] | None = None,
    log_name: str | None = None,
    content: str | None = None,
    filename: str | None = None,
) -> str:
    manager = ParsifalArtifacts()
    result = manager.handle(
        action=action,
        issue_id=issue_id,
        run_dir=run_dir,
        timestamp=timestamp,
        device_id=device_id,
        log_path=log_path,
        log_paths=log_paths,
        log_name=log_name,
        content=content,
        filename=filename,
    )
    payload = {
        "run_dir": result.run_dir,
        "refs": [r.__dict__ for r in result.refs],
    }
    return _dump(payload)


@mcp.tool()
def parsifal_validate(
    path: str | None = None,
    paths: list[str] | None = None,
    kind: str = "auto",
    schema_dir: str | None = None,
    require_schema: bool = False,
) -> str:
    validator = ParsifalValidator()
    results = validator.handle(
        action="validate",
        path=path,
        paths=paths,
        kind=kind,
        schema_dir=schema_dir,
        require_schema=require_schema,
    )
    ok = all(r.ok for r in results)
    return _dump({"ok": ok, "results": [r.__dict__ for r in results]})


if __name__ == "__main__":
    mcp.run()
