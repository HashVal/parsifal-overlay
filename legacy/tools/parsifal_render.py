"""Parsifal render tool: render templates to DEBUG_STEPS.md / KEY_EVIDENCE.md / JIRA comment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

try:
    from .lib import templates as templates_lib
except Exception:
    import sys
    from pathlib import Path as _Path

    _TOOLS_DIR = _Path(__file__).resolve().parent
    if str(_TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(_TOOLS_DIR))
    from lib import templates as templates_lib


@dataclass
class RenderResult:
    debug_steps_path: str | None = None
    key_evidence_path: str | None = None
    jira_comment_path: str | None = None


class Tool:
    """Minimal shim for nanobot Tool interface.

    This file is intended to be copied into nanobot/agent/tools and inherit
    the real Tool base class. The interface here mirrors nanobot Tool usage.
    """

    name: str = "parsifal_render"
    description: str = "Render Parsifal templates into markdown outputs."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "debug_steps": {"type": "object", "description": "Structured DEBUG_STEPS data"},
                "key_evidence": {"type": "object", "description": "Structured KEY_EVIDENCE data"},
                "jira_comment": {"type": "object", "description": "Structured JIRA comment data"},
                "out_dir": {"type": "string", "description": "Directory to write outputs"},
                "debug_steps_path": {"type": "string", "description": "Path to DEBUG_STEPS.md"},
                "key_evidence_path": {"type": "string", "description": "Path to KEY_EVIDENCE.md"},
                "jira_comment_path": {"type": "string", "description": "Path to jira-comment.txt"},
                "jira_key": {"type": "string", "description": "JIRA key (for ID generation)"},
                "round": {"type": "integer", "description": "Round number", "minimum": 1},
                "evidence_index": {"type": "integer", "description": "Evidence index", "minimum": 1},
            },
        }

    async def execute(self, **kwargs: Any) -> str:
        renderer = ParsifalRenderer()
        result = renderer.render(**kwargs)
        return yaml.safe_dump(result.__dict__, sort_keys=False)


class ParsifalRenderer:
    """Render Parsifal templates using structured data and PyYAML."""

    def __init__(self) -> None:
        self.overlay_root = Path(__file__).resolve().parents[1]

    def render(
        self,
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
    ) -> RenderResult:
        if not (debug_steps or key_evidence or jira_comment):
            raise ValueError("Provide at least one of debug_steps, key_evidence, jira_comment")

        now = templates_lib.utc_now()

        if debug_steps:
            debug_steps = dict(debug_steps)
            templates_lib.apply_debug_steps_defaults(debug_steps, jira_key, round, now)

        if key_evidence:
            key_evidence = dict(key_evidence)
            templates_lib.apply_key_evidence_defaults(key_evidence, jira_key, round, evidence_index, now)

        out_dir_path = Path(out_dir).expanduser() if out_dir else None
        if out_dir_path:
            out_dir_path.mkdir(parents=True, exist_ok=True)

        result = RenderResult()

        if debug_steps:
            path = _resolve_path(out_dir_path, debug_steps_path, "DEBUG_STEPS.md")
            content = self._render_markdown("DEBUG_STEPS.md", debug_steps)
            _write_text(path, content)
            result.debug_steps_path = str(path)

        if key_evidence:
            path = _resolve_path(out_dir_path, key_evidence_path, "KEY_EVIDENCE.md")
            content = self._render_markdown("KEY_EVIDENCE.md", key_evidence)
            _write_text(path, content)
            result.key_evidence_path = str(path)

        if jira_comment:
            path = _resolve_path(out_dir_path, jira_comment_path, "jira-comment.txt")
            content = self._render_jira_comment(jira_comment)
            _write_text(path, content)
            result.jira_comment_path = str(path)

        return result

    def _render_markdown(self, template_name: str, data: dict) -> str:
        template = templates_lib.load_template(template_name)
        frontmatter, body = _split_frontmatter(template)
        rendered = _render_frontmatter(data)
        return f"---\n{rendered}---\n\n{body.strip()}\n"

    def _render_jira_comment(self, data: dict) -> str:
        template = templates_lib.load_template("jira-comment.txt")
        return _render_comment_template(template, data)


def _resolve_path(out_dir: Path | None, explicit: str | None, default_name: str) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    if out_dir:
        return out_dir / default_name
    return Path(default_name)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---"):
        return "", content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return "", content
    return parts[1], parts[2]


def _render_frontmatter(data: dict) -> str:
    # Stable key ordering is preserved by insertion order.
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _render_comment_template(template: str, data: dict) -> str:
    text = template

    replacements = {
        "<RESOLVED_RCA|NEED_MORE_INFO|BLOCKED>": data.get("status"),
        "<0.00-1.00>": _fmt_confidence(data.get("confidence")),
        "<soc>/<board>/<sku> ; kernel <branch>@<commit>": data.get("scope"),
        "<one-line root cause>": data.get("rca"),
        "<PROJ-1234>": data.get("jira_key"),
        "<DS-...>": data.get("debug_steps_id"),
        "<EV-...>": data.get("evidence_id"),
    }

    kernel = data.get("kernel", {}) if isinstance(data.get("kernel"), dict) else {}
    replacements.update({
        "<...>": kernel.get("repo"),
        "<branch/tag>": kernel.get("branch"),
        "<commit>": kernel.get("commit"),
        "<dtb>": kernel.get("dtb"),
    })

    platform = data.get("platform")
    if isinstance(platform, (list, tuple)) and platform:
        replacements["<soc>/<board>/<sku>"] = platform[0]

    for placeholder, value in replacements.items():
        if value:
            text = text.replace(placeholder, str(value))

    text = _render_bullets(text, "<action 1>", data.get("next_actions"))
    text = _render_evidence(text, data.get("key_evidence"))

    return text


def _fmt_confidence(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return None


def _render_bullets(text: str, placeholder: str, items: Iterable[str] | None) -> str:
    if not items:
        return text
    items = list(items)
    if not items:
        return text
    text = text.replace(placeholder, items[0])
    if len(items) > 1:
        text = text.replace("<action 2>", items[1])
    return text


def _render_evidence(text: str, items: Iterable[dict] | None) -> str:
    if not items:
        return text
    items = list(items)
    if not items:
        return text

    def _format(item: dict) -> str:
        t = item.get("type", "")
        excerpt = item.get("excerpt", "")
        ref = item.get("ref", "")
        return f"- {t}: {excerpt} (ref: {ref})"

    lines = text.splitlines()
    out = []
    inserted = False
    for line in lines:
        if line.strip().startswith("- <type>:") and not inserted:
            for entry in items[:2]:
                out.append(_format(entry))
            inserted = True
            continue
        out.append(line)
    return "\n".join(out)
