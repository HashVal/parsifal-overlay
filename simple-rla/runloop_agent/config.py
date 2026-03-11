from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger("simple_rla.config")

try:
    import tomllib  # py311
except Exception:  # pragma: no cover
    tomllib = None


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    command: str
    args: list[str]
    env: dict[str, str]
    cwd: str | None = None


@dataclass(frozen=True)
class RunloopConfig:
    client_name: str
    client_version: str
    protocol_version: str
    artifacts_root: Path
    servers: list[McpServerConfig]


def load_config(path: str) -> RunloopConfig:
    if tomllib is None:
        raise RuntimeError("tomllib not available (requires Python 3.11+)")

    p = Path(path).expanduser().resolve()
    raw = tomllib.loads(p.read_text(encoding="utf-8"))

    config_dir = p.parent
    # Heuristic: use a base dir that contains `mcp_servers/` so `python -m mcp_servers.*` works.
    if (config_dir / "mcp_servers").is_dir():
        base_dir = config_dir
    elif (config_dir.parent / "mcp_servers").is_dir():
        base_dir = config_dir.parent
    else:
        base_dir = config_dir

    client = raw.get("client") or {}
    client_name = str(client.get("name") or "runloop")
    client_version = str(client.get("version") or "0.1")
    protocol_version = str(client.get("protocol_version") or "2024-11-05")

    artifacts_root_raw = Path(str(client.get("artifacts_root") or "artifacts/runloop")).expanduser()
    artifacts_root = artifacts_root_raw
    if not artifacts_root.is_absolute():
        artifacts_root = (base_dir / artifacts_root).resolve()

    logger.info("config.load path=%s base_dir=%s artifacts_root=%s", str(p), str(base_dir), str(artifacts_root))

    servers_raw = raw.get("mcp_servers")
    if not isinstance(servers_raw, dict) or not servers_raw:
        raise ValueError("config is missing [mcp_servers.*] entries")

    servers: list[McpServerConfig] = []
    for name, cfg in servers_raw.items():
        if not isinstance(cfg, dict):
            continue
        command = str(cfg.get("command") or "")
        args = [str(x) for x in (cfg.get("args") or [])]
        env = {str(k): str(v) for k, v in (cfg.get("env") or {}).items()}
        cwd = cfg.get("cwd")
        if cwd is not None:
            cwd = str(cwd)
            # Resolve relative cwd against base_dir.
            if cwd and not Path(cwd).expanduser().is_absolute():
                cwd = str((base_dir / cwd).resolve())
        else:
            # Default cwd makes module-based servers work regardless of caller's cwd.
            cwd = str(base_dir)

        if not command:
            raise ValueError(f"mcp_servers.{name}.command is required")

        servers.append(
            McpServerConfig(
                name=str(name),
                command=command,
                args=args,
                env={**os.environ, **env},
                cwd=cwd,
            )
        )

        logger.info("config.server name=%s cmd=%s args=%s cwd=%s", str(name), command, args, cwd)

    return RunloopConfig(
        client_name=client_name,
        client_version=client_version,
        protocol_version=protocol_version,
        artifacts_root=artifacts_root,
        servers=servers,
    )
