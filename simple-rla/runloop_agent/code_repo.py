from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from runloop_agent.runtime_config import RepoConfig, RuntimeConfig


class RepoRegistryError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        repo: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.repo = repo
        self.details = details or {}


@dataclass(frozen=True)
class RepoValidationSnapshot:
    repo: str
    repo_path: str
    git_root: str
    default_ref: str
    default_ref_commit: str
    head_commit: str
    repo_url: str | None = None
    require_force_fetch: bool = False


@dataclass(frozen=True)
class ResolvedCodeScope:
    repo: str
    repo_path: str
    effective_ref: str
    path_filters: tuple[str, ...] = ()
    language: str | None = None
    require_force_fetch: bool = False
    repo_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_tool_context(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "repo": self.repo,
            "repo_path": self.repo_path,
            "ref": self.effective_ref,
        }
        if self.path_filters:
            payload["path_filters"] = list(self.path_filters)
        if self.language:
            payload["language"] = self.language
        return payload


def _run_git(repo_path: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RepoRegistryError(
            "git_command_failed",
            stderr or f"git command failed: {' '.join(args)}",
            details={"repo_path": str(repo_path), "args": list(args), "stderr": stderr},
        )
    return (proc.stdout or "").strip()


def _normalize_path_filters(raw: Any) -> tuple[str, ...]:
    if raw in (None, ""):
        return ()
    if not isinstance(raw, list):
        raise RepoRegistryError("invalid_path_filters", "path_filters must be a list of strings")
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return tuple(out)


def _validate_repo_config(repo: RepoConfig) -> RepoValidationSnapshot:
    if not repo.repo_path:
        raise RepoRegistryError(
            "missing_repo_path",
            f"repo {repo.name!r} is missing repo_path",
            repo=repo.name,
        )
    if not repo.default_ref:
        raise RepoRegistryError(
            "missing_default_ref",
            f"repo {repo.name!r} is missing default_ref",
            repo=repo.name,
        )

    repo_path = Path(repo.repo_path).expanduser().resolve()
    if not repo_path.exists():
        raise RepoRegistryError(
            "repo_path_not_found",
            f"repo_path does not exist for repo {repo.name!r}: {repo_path}",
            repo=repo.name,
            details={"repo_path": str(repo_path)},
        )
    if not repo_path.is_dir():
        raise RepoRegistryError(
            "repo_path_not_dir",
            f"repo_path is not a directory for repo {repo.name!r}: {repo_path}",
            repo=repo.name,
            details={"repo_path": str(repo_path)},
        )

    try:
        git_root = _run_git(repo_path, ["rev-parse", "--show-toplevel"])
    except RepoRegistryError as exc:
        raise RepoRegistryError(
            "not_git_repo",
            f"repo_path is not a git repository for repo {repo.name!r}: {repo_path}",
            repo=repo.name,
            details={"repo_path": str(repo_path)},
        ) from exc
    if not git_root:
        raise RepoRegistryError(
            "not_git_repo",
            f"repo_path is not a git repository for repo {repo.name!r}: {repo_path}",
            repo=repo.name,
            details={"repo_path": str(repo_path)},
        )
    if Path(git_root).resolve() != repo_path:
        raise RepoRegistryError(
            "repo_path_not_repo_root",
            f"repo_path must point to the repo/worktree root for repo {repo.name!r}",
            repo=repo.name,
            details={"repo_path": str(repo_path), "git_root": str(Path(git_root).resolve())},
        )

    try:
        default_ref_commit = _run_git(repo_path, ["rev-parse", "--verify", f"{repo.default_ref}^{{commit}}"])
    except RepoRegistryError as exc:
        raise RepoRegistryError(
            "unresolvable_default_ref",
            f"default_ref is not locally resolvable for repo {repo.name!r}: {repo.default_ref}",
            repo=repo.name,
            details={"repo_path": str(repo_path), "default_ref": repo.default_ref},
        ) from exc

    head_commit = _run_git(repo_path, ["rev-parse", "--verify", "HEAD^{commit}"])
    return RepoValidationSnapshot(
        repo=repo.name,
        repo_path=str(repo_path),
        git_root=str(Path(git_root).resolve()),
        default_ref=repo.default_ref,
        default_ref_commit=default_ref_commit,
        head_commit=head_commit,
        repo_url=repo.repo_url,
        require_force_fetch=repo.require_force_fetch,
    )


class RepoRegistry:
    def __init__(
        self,
        *,
        default_repo: str | None,
        repos: dict[str, RepoValidationSnapshot],
    ) -> None:
        self.default_repo = default_repo
        self._repos = dict(repos)

    @classmethod
    def from_runtime_config(cls, cfg: RuntimeConfig) -> "RepoRegistry":
        repos = {_repo.name: _validate_repo_config(_repo) for _repo in cfg.repos}
        if cfg.code_default_repo and cfg.code_default_repo not in repos:
            raise RepoRegistryError(
                "unknown_default_repo",
                f"code.default_repo is not defined under [repos.*]: {cfg.code_default_repo}",
                details={"default_repo": cfg.code_default_repo},
            )
        return cls(default_repo=cfg.code_default_repo, repos=repos)

    def list_repos(self) -> list[RepoValidationSnapshot]:
        return list(self._repos.values())

    def get(self, name: str) -> RepoValidationSnapshot | None:
        return self._repos.get(name)

    def resolve_scope(
        self,
        target: Mapping[str, Any] | None,
        *,
        fetcher: Callable[[RepoValidationSnapshot], None] | None = None,
    ) -> ResolvedCodeScope:
        target = dict(target or {})
        repo_name = str(target.get("repo") or self.default_repo or "").strip()
        if not repo_name:
            raise RepoRegistryError("missing_repo", "code target is missing repo and no code.default_repo is configured")

        entry = self._repos.get(repo_name)
        if entry is None:
            raise RepoRegistryError(
                "unknown_repo",
                f"unknown repo alias: {repo_name}",
                repo=repo_name,
            )

        effective_ref = str(target.get("ref") or entry.default_ref or "").strip()
        if not effective_ref:
            raise RepoRegistryError(
                "missing_ref",
                f"code target for repo {repo_name!r} is missing ref and repo has no default_ref",
                repo=repo_name,
            )

        if entry.require_force_fetch:
            if fetcher is None:
                raise RepoRegistryError(
                    "force_fetch_required",
                    f"repo {repo_name!r} requires force fetch before resolution",
                    repo=repo_name,
                )
            fetcher(entry)

        repo_path = Path(entry.repo_path)
        try:
            _run_git(repo_path, ["rev-parse", "--verify", f"{effective_ref}^{{commit}}"])
        except RepoRegistryError as exc:
            raise RepoRegistryError(
                "unresolvable_effective_ref",
                f"effective ref is not locally resolvable for repo {repo_name!r}: {effective_ref}",
                repo=repo_name,
                details={"repo_path": entry.repo_path, "effective_ref": effective_ref},
            ) from exc

        language = str(target.get("language") or "").strip() or None
        path_filters = _normalize_path_filters(target.get("path_filters"))
        return ResolvedCodeScope(
            repo=repo_name,
            repo_path=entry.repo_path,
            effective_ref=effective_ref,
            path_filters=path_filters,
            language=language,
            require_force_fetch=entry.require_force_fetch,
            repo_url=entry.repo_url,
            metadata={},
        )


_RESERVED_SCOPE_KEYS = {"repo", "repo_path", "ref", "path_filters", "language"}


def build_code_tool_arguments(scope: ResolvedCodeScope, tool_args: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = scope.as_tool_context()
    extras = dict(tool_args or {})
    overlap = sorted(_RESERVED_SCOPE_KEYS.intersection(extras.keys()))
    if overlap:
        raise RepoRegistryError(
            "reserved_tool_arg_keys",
            f"tool args must not override resolved code scope keys: {', '.join(overlap)}",
            repo=scope.repo,
            details={"reserved_keys": overlap},
        )
    payload.update(extras)
    return payload
