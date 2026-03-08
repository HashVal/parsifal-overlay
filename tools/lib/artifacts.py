"""Artifact helpers for Parsifal tools."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os


def overlay_root() -> Path:
    # tools/lib/artifacts.py -> tools -> parsifal-overlay
    return Path(__file__).resolve().parents[2]


def get_artifacts_root() -> Path:
    env_root = os.environ.get("PARSIFAL_ARTIFACTS_ROOT")
    if env_root:
        return Path(env_root).expanduser()
    return overlay_root().parent / "artifacts"


def utc_dir_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_run_dir(issue_id: str, timestamp: str | None = None, root: Path | None = None) -> Path:
    base = root or get_artifacts_root()
    ts = timestamp or utc_dir_tag()
    return base / issue_id / ts


def ensure_under_root(path: Path, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise ValueError("run_dir must be under artifacts_root") from None
    return resolved


def to_ref(path: Path, root: Path | None = None) -> str:
    base = root or get_artifacts_root()
    rel = path.resolve().relative_to(base.resolve())
    return str(Path("artifacts") / rel)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    i = 1
    while True:
        candidate = path.with_name(f"{stem}__{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def prefix_device(name: str, device_id: str | None) -> str:
    if not device_id:
        return name
    return f"{device_id}__{name}"
