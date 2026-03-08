"""Parsifal kernel RCA fingerprint helpers.

This module normalizes platform keys and kernel fingerprint fields for Parsifal tools.
It is not a cryptographic hash; it standardizes identifiers like
platform=<soc>/<board>/<sku> and kernel repo/branch/commit/localversion/dtb.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class KernelFingerprint:
    repo: str
    branch: str
    commit: str
    localversion: str
    dtb: str
    config_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_platform_key(platform: str) -> str:
    parts = [p for p in platform.strip().split("/") if p]
    if len(parts) == 2:
        parts.append("default")
    if len(parts) != 3:
        raise ValueError("platform must be <soc>/<board>/<sku>")
    return "/".join(_norm_part(p) for p in parts)


def normalize_platform(soc: str, board: str, sku: str) -> str:
    return "/".join((_norm_part(soc), _norm_part(board), _norm_part(sku)))


def normalize_kernel_fingerprint(
    repo: str,
    branch: str,
    commit: str,
    localversion: str,
    dtb: str,
    config_hash: str | None = None,
) -> KernelFingerprint:
    return KernelFingerprint(
        repo=_norm_text(repo),
        branch=_norm_text(branch),
        commit=_norm_commit(commit),
        localversion=_norm_text(localversion),
        dtb=_norm_text(dtb),
        config_hash=_norm_text(config_hash) if config_hash else None,
    )


def _norm_part(value: str) -> str:
    return _norm_text(value).replace(" ", "_")


def _norm_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _norm_commit(value: str) -> str:
    return _norm_text(value).lower()
