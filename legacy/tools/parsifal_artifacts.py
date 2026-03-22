"""Parsifal artifacts tool: persist logs/text and return stable refs."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

try:
    from .lib import artifacts as artifacts_lib
except Exception:
    import sys
    from pathlib import Path as _Path

    _TOOLS_DIR = _Path(__file__).resolve().parent
    if str(_TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(_TOOLS_DIR))
    from lib import artifacts as artifacts_lib


@dataclass
class ArtifactRef:
    name: str
    ref: str
    path: str


@dataclass
class ArtifactResult:
    run_dir: str
    refs: list[ArtifactRef]


class Tool:
    """Minimal shim for nanobot Tool interface.

    This file is intended to be copied into nanobot/agent/tools and inherit
    the real Tool base class. The interface here mirrors nanobot Tool usage.
    """

    name: str = "parsifal_artifacts"
    description: str = "Persist artifacts and return stable refs."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["init_run_dir", "ingest_log", "write_text"],
                },
                "issue_id": {"type": "string"},
                "run_dir": {"type": "string"},
                "timestamp": {"type": "string"},
                "device_id": {"type": "string"},
                "log_path": {"type": "string"},
                "log_paths": {"type": "array", "items": {"type": "string"}},
                "log_name": {"type": "string"},
                "content": {"type": "string"},
                "filename": {"type": "string"},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        manager = ParsifalArtifacts()
        result = manager.handle(**kwargs)
        payload = {
            "run_dir": result.run_dir,
            "refs": [asdict(r) for r in result.refs],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


class ParsifalArtifacts:
    """Create and manage artifact directories and refs."""

    def __init__(self) -> None:
        self.artifacts_root = artifacts_lib.get_artifacts_root()

    def handle(self, **kwargs: Any) -> ArtifactResult:
        action = kwargs.get("action")
        issue_id = kwargs.get("issue_id")
        run_dir = kwargs.get("run_dir")
        timestamp = kwargs.get("timestamp")
        device_id = kwargs.get("device_id")

        if action == "init_run_dir":
            run_path = self._resolve_run_dir(issue_id, run_dir, timestamp)
            run_path.mkdir(parents=True, exist_ok=True)
            return ArtifactResult(str(run_path), [])

        if action == "ingest_log":
            run_path = self._resolve_run_dir(issue_id, run_dir, timestamp)
            run_path.mkdir(parents=True, exist_ok=True)
            refs = []
            for path in _coalesce_paths(kwargs.get("log_path"), kwargs.get("log_paths")):
                refs.append(self._ingest_path(run_path, path, kwargs.get("log_name"), device_id))
            return ArtifactResult(str(run_path), refs)

        if action == "write_text":
            run_path = self._resolve_run_dir(issue_id, run_dir, timestamp)
            run_path.mkdir(parents=True, exist_ok=True)
            content = kwargs.get("content")
            if content is None:
                raise ValueError("content is required for write_text")
            filename = kwargs.get("filename") or "artifact.txt"
            ref = self._write_text(run_path, filename, content, device_id)
            return ArtifactResult(str(run_path), [ref])

        raise ValueError(f"Unknown action: {action}")

    def _resolve_run_dir(self, issue_id: str | None, run_dir: str | None, timestamp: str | None) -> Path:
        if run_dir:
            path = Path(run_dir).expanduser()
        else:
            if not issue_id:
                raise ValueError("issue_id is required when run_dir is not provided")
            path = artifacts_lib.make_run_dir(issue_id, timestamp, root=self.artifacts_root)

        return artifacts_lib.ensure_under_root(path, self.artifacts_root)

    def _ingest_path(self, run_path: Path, src: str, log_name: str | None, device_id: str | None) -> ArtifactRef:
        src_path = Path(src).expanduser()
        if not src_path.exists() or not src_path.is_file():
            raise ValueError(f"log_path not found: {src}")
        name = log_name or src_path.name
        name = artifacts_lib.prefix_device(name, device_id)
        dest = artifacts_lib.unique_path(run_path / name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest)
        return self._to_ref(dest)

    def _write_text(self, run_path: Path, filename: str, content: str, device_id: str | None) -> ArtifactRef:
        name = artifacts_lib.prefix_device(filename, device_id)
        dest = artifacts_lib.unique_path(run_path / name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        return self._to_ref(dest)

    def _to_ref(self, path: Path) -> ArtifactRef:
        ref = artifacts_lib.to_ref(path, root=self.artifacts_root)
        return ArtifactRef(name=path.name, ref=ref, path=str(path))


def _coalesce_paths(path: str | None, paths: Iterable[str] | None) -> list[str]:
    result = []
    if path:
        result.append(path)
    if paths:
        result.extend([p for p in paths if p])
    return result
