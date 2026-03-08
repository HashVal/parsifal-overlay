"""Template helpers for Parsifal tools."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os


def overlay_root() -> Path:
    # tools/lib/templates.py -> tools -> parsifal-overlay
    return Path(__file__).resolve().parents[2]


def get_templates_dir() -> Path:
    env_root = os.environ.get("PARSIFAL_TEMPLATES_ROOT")
    if env_root:
        return Path(env_root).expanduser()
    return overlay_root() / "templates"


def get_spec_templates_dir() -> Path:
    spec_root = os.environ.get("PARSIFAL_SPEC_ROOT")
    if spec_root:
        return Path(spec_root).expanduser() / "templates"
    return overlay_root().parent / "kernel-rca-bot" / "templates"


def load_template(name: str) -> str:
    primary = get_templates_dir() / name
    if primary.exists():
        return primary.read_text(encoding="utf-8")

    fallback = get_spec_templates_dir() / name
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")

    raise FileNotFoundError(f"Template not found: {name}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_timestamp(now: datetime | None = None) -> str:
    now = now or utc_now()
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def date_tag(now: datetime | None = None) -> str:
    now = now or utc_now()
    return now.strftime("%Y%m%d")


def make_debug_steps_id(jira_key: str, round_num: int, dt_tag: str | None = None) -> str:
    tag = dt_tag or date_tag()
    return f"DS-{tag}-{jira_key}-R{round_num}"


def make_evidence_id(jira_key: str, round_num: int, index: int, dt_tag: str | None = None) -> str:
    tag = dt_tag or date_tag()
    return f"EV-{tag}-{jira_key}-R{round_num}-{index}"


def apply_debug_steps_defaults(
    data: dict[str, Any],
    jira_key: str | None = None,
    round_num: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    if jira_key and not data.get("jira_key"):
        data["jira_key"] = jira_key
    if round_num and not data.get("round"):
        data["round"] = round_num
    if not data.get("created_at"):
        data["created_at"] = utc_timestamp(now)
    if not data.get("debug_steps_id") and data.get("jira_key"):
        r = data.get("round", 1)
        data["debug_steps_id"] = make_debug_steps_id(data["jira_key"], int(r), date_tag(now))
    return data


def apply_key_evidence_defaults(
    data: dict[str, Any],
    jira_key: str | None = None,
    round_num: int | None = None,
    index: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    if jira_key and not data.get("jira_key"):
        data["jira_key"] = jira_key
    if not data.get("created_at"):
        data["created_at"] = utc_timestamp(now)
    if not data.get("evidence_id") and data.get("jira_key"):
        r = round_num or 1
        idx = index or 1
        data["evidence_id"] = make_evidence_id(data["jira_key"], int(r), int(idx), date_tag(now))
    return data
