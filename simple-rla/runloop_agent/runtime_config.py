from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # py311
except Exception:  # pragma: no cover
    tomllib = None


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None


@dataclass(frozen=True)
class RuntimeConfig:
    model: str | None = None
    timeout_s: int | None = None
    protocol_version: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    artifacts_root: str | None = None
    mcp_servers: tuple[McpServerConfig, ...] = ()


def _load_toml(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    if tomllib is None:
        raise RuntimeError("tomllib not available (requires Python 3.11+)")
    p = Path(path).expanduser().resolve()
    data = tomllib.loads(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("runtime config top-level must be a mapping")
    return data


def _parse_mcp_servers(data: dict[str, Any]) -> tuple[McpServerConfig, ...]:
    mcp = data.get("mcp") or {}
    servers = mcp.get("servers") or {}
    if not isinstance(servers, dict):
        return ()

    out: list[McpServerConfig] = []
    for name, raw in servers.items():
        if not isinstance(raw, dict):
            continue
        command = str(raw.get("command") or "").strip()
        if not command:
            continue
        args = tuple(str(x) for x in (raw.get("args") or []))
        env = {str(k): str(v) for k, v in (raw.get("env") or {}).items()}
        cwd = str(raw.get("cwd")).strip() if raw.get("cwd") is not None else None
        out.append(McpServerConfig(name=str(name), command=command, args=args, env=env, cwd=cwd or None))
    return tuple(out)


def load_runtime_config(path: str | Path | None) -> RuntimeConfig:
    data = _load_toml(path)

    runtime = data.get("runtime") or {}
    openai = data.get("openai") or {}
    mcp = data.get("mcp") or {}

    model = os.environ.get("OPENAI_MODEL") or runtime.get("model")
    timeout_raw = os.environ.get("OPENAI_TIMEOUT_S") or runtime.get("timeout_s")
    timeout_s = int(timeout_raw) if timeout_raw not in (None, "") else None
    protocol_version = runtime.get("protocol_version")

    openai_api_key = os.environ.get("OPENAI_API_KEY") or openai.get("api_key")
    openai_base_url = os.environ.get("OPENAI_BASE_URL") or openai.get("base_url")
    artifacts_root = os.environ.get("SIMPLE_RLA_ARTIFACTS_ROOT") or mcp.get("artifacts_root")

    return RuntimeConfig(
        model=str(model) if model else None,
        timeout_s=timeout_s,
        protocol_version=str(protocol_version) if protocol_version else None,
        openai_api_key=str(openai_api_key) if openai_api_key else None,
        openai_base_url=str(openai_base_url) if openai_base_url else None,
        artifacts_root=str(artifacts_root) if artifacts_root else None,
        mcp_servers=_parse_mcp_servers(data),
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
    if cfg.artifacts_root:
        os.environ.setdefault("SIMPLE_RLA_ARTIFACTS_ROOT", cfg.artifacts_root)
