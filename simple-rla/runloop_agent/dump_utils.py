"""Dump utilities for runloop debug mode."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass(frozen=True)
class DumpManager:
    root: Path

    @classmethod
    def create(cls, base_dir: Path | None = None) -> "DumpManager":
        if base_dir is None:
            base = Path(os.getcwd()) / "dumps"
            tag = _now_tag()
            root = (base / tag).resolve()
        else:
            root = Path(base_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return cls(root=root)

    def write_meta(self, payload: dict) -> None:
        self._write_json("meta.json", payload)

    def write_round(self, round_idx: int, payload: dict) -> None:
        self._write_json(f"iteration_{round_idx:03d}.json", payload)

    def _write_json(self, filename: str, payload: dict) -> None:
        path = self.root / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def last_user_message(messages: list[dict]) -> str | None:
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            return m.get("content")
    return None


def last_user_input(input_items: list[dict]) -> str | None:
    for item in reversed(input_items):
        if not isinstance(item, dict):
            continue
        if item.get("role") != "user":
            continue
        content = item.get("content")
        if isinstance(content, list) and content:
            c0 = content[0]
            if isinstance(c0, dict):
                return c0.get("text")
        elif isinstance(content, str):
            return content
    return None
