from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ParseResult:
    ok: bool
    parsed: Any = None
    error: str | None = None
    raw_text: str = ""


def parse_model_output(text: str) -> ParseResult:
    raw_text = text or ""
    stripped = raw_text.strip()
    if not stripped:
        return ParseResult(ok=False, error="empty model output", raw_text=raw_text)

    try:
        return ParseResult(ok=True, parsed=json.loads(stripped), raw_text=raw_text)
    except json.JSONDecodeError as exc:
        return ParseResult(ok=False, error=f"invalid json: {exc}", raw_text=raw_text)
