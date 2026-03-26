from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SIMPLE_RLA_ROOT = Path(__file__).resolve().parents[1]
if str(SIMPLE_RLA_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMPLE_RLA_ROOT))


def run_git(repo_path: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git command failed: {' '.join(args)}")
    return (proc.stdout or "").strip()


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def init_git_repo(repo_path: Path, *, branch: str, files: dict[str, str]) -> Path:
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    run_git(repo_path, "checkout", "-q", "-b", branch)
    for rel_path, text in files.items():
        write_file(repo_path / rel_path, text)
    run_git(repo_path, "add", ".")
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test User",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    return repo_path


def write_runtime_config(
    path: Path,
    *,
    default_repo: str | None,
    repos: dict[str, dict[str, object]],
) -> Path:
    lines: list[str] = []
    if default_repo is not None:
        lines.extend([
            "[code]",
            f'default_repo = "{default_repo}"',
            "",
        ])
    for alias, cfg in repos.items():
        lines.append(f"[repos.{alias}]")
        if "repo_url" in cfg and cfg["repo_url"] is not None:
            lines.append(f'repo_url = "{cfg["repo_url"]}"')
        if "default_ref" in cfg and cfg["default_ref"] is not None:
            lines.append(f'default_ref = "{cfg["default_ref"]}"')
        if "repo_path" in cfg and cfg["repo_path"] is not None:
            lines.append(f'repo_path = "{cfg["repo_path"]}"')
        if "require_force_fetch" in cfg:
            flag = "true" if bool(cfg["require_force_fetch"]) else "false"
            lines.append(f"require_force_fetch = {flag}")
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path
