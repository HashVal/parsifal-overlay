from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib  # py311
except Exception:  # pragma: no cover
    tomllib = None


@dataclass(frozen=True)
class RuntimeConfig:
    model: str | None = None
    timeout_s: int | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None


def load_runtime_config(path: str | Path | None) -> RuntimeConfig:
    data: dict = {}
    if path:
        if tomllib is None:
            raise RuntimeError("tomllib not available (requires Python 3.11+)")
        p = Path(path).expanduser().resolve()
        data = tomllib.loads(p.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("runtime config top-level must be a mapping")

    runtime = data.get("runtime") or {}
    openai = data.get("openai") or {}

    model = os.environ.get("OPENAI_MODEL") or runtime.get("model")
    timeout_raw = os.environ.get("OPENAI_TIMEOUT_S") or runtime.get("timeout_s")
    timeout_s = int(timeout_raw) if timeout_raw not in (None, "") else None

    openai_api_key = os.environ.get("OPENAI_API_KEY") or openai.get("api_key")
    openai_base_url = os.environ.get("OPENAI_BASE_URL") or openai.get("base_url")

    return RuntimeConfig(
        model=str(model) if model else None,
        timeout_s=timeout_s,
        openai_api_key=str(openai_api_key) if openai_api_key else None,
        openai_base_url=str(openai_base_url) if openai_base_url else None,
    )


def apply_runtime_config(cfg: RuntimeConfig) -> None:
    if cfg.openai_api_key:
        os.environ["OPENAI_API_KEY"] = cfg.openai_api_key
    if cfg.openai_base_url:
        os.environ["OPENAI_BASE_URL"] = cfg.openai_base_url
    if cfg.model:
        os.environ.setdefault("OPENAI_MODEL", cfg.model)
    if cfg.timeout_s is not None:
        os.environ.setdefault("OPENAI_TIMEOUT_S", str(cfg.timeout_s))
