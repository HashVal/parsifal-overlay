from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_support import init_git_repo, write_runtime_config

from runloop_agent.code_repo import RepoRegistry, RepoRegistryError, build_code_tool_arguments
from runloop_agent.runtime_config import load_runtime_config


class RepoRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.app_repo = init_git_repo(
            self.root / "app",
            branch="main",
            files={
                "pkg/service.py": "def app_entry():\n    return 'app'\n",
                "README.md": "app repo\n",
            },
        )
        self.kernel_repo = init_git_repo(
            self.root / "kernel",
            branch="dev",
            files={
                "drivers/net/netstack.py": "def panic_guard(packet):\n    return packet is None\n",
                "drivers/gpu/render.py": "def render_frame():\n    return 'ok'\n",
            },
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _config_path(
        self,
        *,
        default_repo: str | None = "app",
        app_repo_path: Path | None = None,
        kernel_repo_path: Path | None = None,
        app_default_ref: str = "main",
        kernel_default_ref: str = "dev",
        app_force_fetch: bool = False,
        kernel_force_fetch: bool = False,
    ) -> Path:
        return write_runtime_config(
            self.root / "runtime.toml",
            default_repo=default_repo,
            repos={
                "app": {
                    "repo_url": "git@example.com/org/app.git",
                    "default_ref": app_default_ref,
                    "repo_path": str(app_repo_path or self.app_repo),
                    "require_force_fetch": app_force_fetch,
                },
                "kernel": {
                    "repo_url": "git@example.com/org/kernel.git",
                    "default_ref": kernel_default_ref,
                    "repo_path": str(kernel_repo_path or self.kernel_repo),
                    "require_force_fetch": kernel_force_fetch,
                },
            },
        )

    def test_loads_multiple_repos_and_resolves_default_scope(self) -> None:
        cfg = load_runtime_config(self._config_path())
        self.assertEqual(cfg.code_default_repo, "app")
        self.assertEqual({repo.name for repo in cfg.repos}, {"app", "kernel"})

        registry = RepoRegistry.from_runtime_config(cfg)
        scope = registry.resolve_scope({"path_filters": ["pkg/**"], "language": "python"})

        self.assertEqual(scope.repo, "app")
        self.assertEqual(scope.repo_path, str(self.app_repo.resolve()))
        self.assertEqual(scope.effective_ref, "main")
        self.assertEqual(scope.path_filters, ("pkg/**",))
        self.assertEqual(scope.language, "python")

    def test_build_code_tool_arguments_uses_resolved_scope_only(self) -> None:
        cfg = load_runtime_config(self._config_path())
        registry = RepoRegistry.from_runtime_config(cfg)
        scope = registry.resolve_scope({"repo": "kernel", "path_filters": ["drivers/**"]})

        args = build_code_tool_arguments(scope, {"symbol": "panic_guard"})

        self.assertEqual(args["repo"], "kernel")
        self.assertEqual(args["repo_path"], str(self.kernel_repo.resolve()))
        self.assertEqual(args["ref"], "dev")
        self.assertEqual(args["path_filters"], ["drivers/**"])
        self.assertEqual(args["symbol"], "panic_guard")
        self.assertNotIn("repo_url", args)

    def test_build_code_tool_arguments_rejects_reserved_keys(self) -> None:
        cfg = load_runtime_config(self._config_path())
        registry = RepoRegistry.from_runtime_config(cfg)
        scope = registry.resolve_scope({"repo": "kernel"})

        with self.assertRaises(RepoRegistryError) as ctx:
            build_code_tool_arguments(scope, {"repo_path": "/tmp/override", "symbol": "panic_guard"})

        self.assertEqual(ctx.exception.code, "reserved_tool_arg_keys")

    def test_unknown_repo_alias_raises(self) -> None:
        cfg = load_runtime_config(self._config_path())
        registry = RepoRegistry.from_runtime_config(cfg)

        with self.assertRaises(RepoRegistryError) as ctx:
            registry.resolve_scope({"repo": "missing"})

        self.assertEqual(ctx.exception.code, "unknown_repo")

    def test_missing_repo_path_raises(self) -> None:
        missing_path = self.root / "missing-repo"
        cfg = load_runtime_config(self._config_path(kernel_repo_path=missing_path))

        with self.assertRaises(RepoRegistryError) as ctx:
            RepoRegistry.from_runtime_config(cfg)

        self.assertEqual(ctx.exception.code, "repo_path_not_found")

    def test_non_git_repo_raises(self) -> None:
        non_git = self.root / "plain-dir"
        non_git.mkdir()
        cfg = load_runtime_config(self._config_path(kernel_repo_path=non_git))

        with self.assertRaises(RepoRegistryError) as ctx:
            RepoRegistry.from_runtime_config(cfg)

        self.assertEqual(ctx.exception.code, "not_git_repo")

    def test_unresolvable_default_ref_raises(self) -> None:
        cfg = load_runtime_config(self._config_path(kernel_default_ref="origin/dev"))

        with self.assertRaises(RepoRegistryError) as ctx:
            RepoRegistry.from_runtime_config(cfg)

        self.assertEqual(ctx.exception.code, "unresolvable_default_ref")

    def test_require_force_fetch_false_does_not_call_fetcher(self) -> None:
        cfg = load_runtime_config(self._config_path(kernel_force_fetch=False))
        registry = RepoRegistry.from_runtime_config(cfg)
        calls: list[str] = []

        scope = registry.resolve_scope({"repo": "kernel"}, fetcher=lambda entry: calls.append(entry.repo))

        self.assertEqual(scope.repo, "kernel")
        self.assertEqual(calls, [])

    def test_require_force_fetch_true_calls_fetcher(self) -> None:
        cfg = load_runtime_config(self._config_path(kernel_force_fetch=True))
        registry = RepoRegistry.from_runtime_config(cfg)
        calls: list[str] = []

        scope = registry.resolve_scope({"repo": "kernel"}, fetcher=lambda entry: calls.append(entry.repo))

        self.assertEqual(scope.repo, "kernel")
        self.assertEqual(calls, ["kernel"])


if __name__ == "__main__":
    unittest.main()
