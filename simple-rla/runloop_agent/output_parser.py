from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ParseResult:
    ok: bool
    parsed: Any = None
    error: str | None = None
    raw_text: str = ""
    mode: str = "full"
    extracted_text: str | None = None


def _extract_last_json_object(text: str) -> str | None:
    end = text.rfind("}")
    if end < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    start: int | None = None

    for idx in range(end, -1, -1):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == '}':
            depth += 1
            continue
        if ch == '{':
            depth -= 1
            if depth == 0:
                start = idx
                break

    if start is None:
        return None

    candidate = text[start:end + 1]
    trailing = text[end + 1:].strip()
    if trailing:
        return None
    return candidate


def _extract_fenced_json(text: str) -> str | None:
    patterns = [
        r"```json\s*(\{.*?\})\s*```",
        r"```\s*(\{.*?\})\s*```",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        for candidate in reversed(matches):
            candidate = candidate.strip()
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
    return None


def _extract_first_parseable_json_object(text: str) -> str | None:
    for start, ch in enumerate(text):
        if ch != "{":
            continue

        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            cur = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif cur == "\\":
                    escape = True
                elif cur == '"':
                    in_string = False
                continue

            if cur == '"':
                in_string = True
                continue
            if cur == "{":
                depth += 1
                continue
            if cur == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:idx + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break
    return None


def parse_model_output(text: str) -> ParseResult:
    raw_text = text or ""
    stripped = raw_text.strip()
    if not stripped:
        return ParseResult(ok=False, error="empty model output", raw_text=raw_text)

    try:
        return ParseResult(ok=True, parsed=json.loads(stripped), raw_text=raw_text, mode="full")
    except json.JSONDecodeError as exc:
        full_error = exc

    extracted = _extract_last_json_object(stripped)
    if extracted is not None:
        try:
            parsed = json.loads(extracted)
            return ParseResult(
                ok=True,
                parsed=parsed,
                raw_text=raw_text,
                mode="fallback_last_json",
                extracted_text=extracted,
            )
        except json.JSONDecodeError:
            pass

    fenced = _extract_fenced_json(stripped)
    if fenced is not None:
        return ParseResult(
            ok=True,
            parsed=json.loads(fenced),
            raw_text=raw_text,
            mode="fallback_fenced_json",
            extracted_text=fenced,
        )

    first_obj = _extract_first_parseable_json_object(stripped)
    if first_obj is not None:
        return ParseResult(
            ok=True,
            parsed=json.loads(first_obj),
            raw_text=raw_text,
            mode="fallback_first_json",
            extracted_text=first_obj,
        )

    return ParseResult(ok=False, error=f"invalid json: {full_error}", raw_text=raw_text, mode="full")
