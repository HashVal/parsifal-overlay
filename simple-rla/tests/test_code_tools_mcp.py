from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from test_support import SIMPLE_RLA_ROOT, init_git_repo

from runloop_agent.mcp_client import McpClient
from runloop_agent.runtime_config import McpServerConfig, RuntimeConfig


class CodeToolsMcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.kernel_repo = init_git_repo(
            self.root / "kernel",
            branch="dev",
            files={
                "drivers/net/netstack.py": (
                    "def panic_guard(packet):\n"
                    "    return packet is None\n"
                    "\n"
                    "class NetWatcher:\n"
                    "    pass\n"
                ),
                "drivers/gpu/render.py": "def render_frame():\n    return 'ok'\n",
                "docs/notes.txt": "panic_guard should only be searched inside drivers/net\n",
            },
        )
        (self.kernel_repo / "drivers/net/netstack.py").write_text(
            "def panic_guard(packet):\n"
            "    return packet is None\n"
            "\n"
            "class NetWatcher:\n"
            "    pass\n"
            "\n"
            "def slow_path(packet):\n"
            "    return packet\n",
            encoding="utf-8",
        )
        (self.kernel_repo / "drivers/net/debug_helper.py").write_text(
            "def helper_flag(value):\n"
            "    return value\n",
            encoding="utf-8",
        )
        (self.kernel_repo / "drivers/gpu/render.py").write_text(
            "def render_frame():\n"
            "    return 'frame'\n",
            encoding="utf-8",
        )
        from test_support import run_git
        run_git(self.kernel_repo, "add", ".")
        run_git(self.kernel_repo, "-c", "user.email=test@example.com", "-c", "user.name=Test User", "commit", "-qm", "second")
        cfg = RuntimeConfig(
            protocol_version="2024-11-05",
            mcp_servers=(
                McpServerConfig(
                    name="code",
                    command=sys.executable,
                    args=("-m", "mcp_servers.code_tools_server"),
                    cwd=str(SIMPLE_RLA_ROOT),
                ),
            ),
        )
        self.client = McpClient(cfg, workspace_root=self._tmp.name)
        self.client.start()

    def tearDown(self) -> None:
        self.client.close()
        self._tmp.cleanup()

    def _scope(self, **extra: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "repo": "kernel",
            "repo_path": str(self.kernel_repo.resolve()),
            "ref": "dev",
        }
        payload.update(extra)
        return payload

    def test_tool_discovery_exposes_code_family_surface(self) -> None:
        tool_names = {tool.name for tool in self.client.list_tools()}
        self.assertEqual(
            tool_names,
            {
                "code_list_files",
                "code_check_path_exists",
                "code_check_path_changed_between_refs",
                "code_search_text",
                "code_read_file_range",
                "code_read_symbol_context",
                "code_check_symbol_exists",
            },
        )

    def test_code_list_files_returns_scoped_repo_relative_paths(self) -> None:
        result = self.client.call_tool(
            "code_list_files",
            self._scope(path_filters=["drivers/net/**"], language="python"),
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.content["total_count"], 2)
        self.assertEqual(
            result.content["files"],
            ["drivers/net/debug_helper.py", "drivers/net/netstack.py"],
        )
        self.assertFalse(result.content["truncated"])
        self.assertEqual(result.content["provenance"]["repo"], "kernel")

    def test_code_check_path_exists_reports_file_dir_and_missing(self) -> None:
        file_result = self.client.call_tool(
            "code_check_path_exists",
            self._scope(path="drivers/net/netstack.py"),
        )
        dir_result = self.client.call_tool(
            "code_check_path_exists",
            self._scope(path="drivers/net"),
        )
        missing_result = self.client.call_tool(
            "code_check_path_exists",
            self._scope(path="drivers/net/missing.py"),
        )

        self.assertFalse(file_result.is_error)
        self.assertTrue(file_result.content["exists"])
        self.assertEqual(file_result.content["path_type"], "file")
        self.assertFalse(dir_result.is_error)
        self.assertTrue(dir_result.content["exists"])
        self.assertEqual(dir_result.content["path_type"], "dir")
        self.assertFalse(missing_result.is_error)
        self.assertFalse(missing_result.content["exists"])
        self.assertEqual(missing_result.content["path_type"], "missing")

    def test_code_check_path_changed_between_refs_reports_changed_and_unchanged(self) -> None:
        changed_result = self.client.call_tool(
            "code_check_path_changed_between_refs",
            {
                "repo": "kernel",
                "repo_path": str(self.kernel_repo.resolve()),
                "base_ref": "HEAD~1",
                "target_ref": "dev",
                "path": "drivers/net",
            },
        )
        unchanged_result = self.client.call_tool(
            "code_check_path_changed_between_refs",
            {
                "repo": "kernel",
                "repo_path": str(self.kernel_repo.resolve()),
                "base_ref": "HEAD~1",
                "target_ref": "dev",
                "path": "docs",
            },
        )

        self.assertFalse(changed_result.is_error)
        self.assertTrue(changed_result.content["changed"])
        self.assertEqual(changed_result.content["changed_count"], 2)
        self.assertEqual(
            changed_result.content["changed_files"],
            [
                {"path": "drivers/net/debug_helper.py", "status": "A"},
                {"path": "drivers/net/netstack.py", "status": "M"},
            ],
        )
        self.assertFalse(unchanged_result.is_error)
        self.assertFalse(unchanged_result.content["changed"])
        self.assertEqual(unchanged_result.content["changed_files"], [])

    def test_code_search_text_returns_matches_with_provenance(self) -> None:
        result = self.client.call_tool(
            "code_search_text",
            self._scope(query="panic_guard", path_filters=["drivers/net/**"], mode="literal"),
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.content["match_count"], 1)
        self.assertEqual(result.content["matches"][0]["file_path"], "drivers/net/netstack.py")
        self.assertEqual(result.content["matches"][0]["line_number"], 1)
        self.assertEqual(result.content["provenance"]["repo"], "kernel")
        self.assertEqual(result.content["provenance"]["ref"], "dev")

    def test_code_search_text_respects_path_filters(self) -> None:
        result = self.client.call_tool(
            "code_search_text",
            self._scope(query="render_frame", path_filters=["drivers/net/**"]),
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.content["match_count"], 0)
        self.assertEqual(result.content["matches"], [])

    def test_code_read_file_range_returns_exact_lines(self) -> None:
        result = self.client.call_tool(
            "code_read_file_range",
            self._scope(file_path="drivers/net/netstack.py", start_line=1, end_line=2),
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.content["lines"][0], {"line_number": 1, "text": "def panic_guard(packet):"})
        self.assertEqual(result.content["lines"][1], {"line_number": 2, "text": "    return packet is None"})
        self.assertEqual(result.content["provenance"]["repo_path"], str(self.kernel_repo.resolve()))

    def test_code_read_file_range_rejects_out_of_bounds_range(self) -> None:
        result = self.client.call_tool(
            "code_read_file_range",
            self._scope(file_path="drivers/net/netstack.py", start_line=1, end_line=99),
        )

        self.assertTrue(result.is_error)
        self.assertIn("requested range exceeds file length", result.content)

    def test_code_read_symbol_context_returns_locator_and_context(self) -> None:
        result = self.client.call_tool(
            "code_read_symbol_context",
            self._scope(symbol="panic_guard", path_filters=["drivers/net/**"], language="python"),
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.content["match_count"], 1)
        match = result.content["matches"][0]
        self.assertEqual(match["kind"], "function")
        self.assertEqual(match["file_path"], "drivers/net/netstack.py")
        self.assertEqual(match["line_number"], 1)
        self.assertEqual(match["context_lines"][0]["line_number"], 1)

    def test_code_check_symbol_exists_reports_true_and_false(self) -> None:
        exists_result = self.client.call_tool(
            "code_check_symbol_exists",
            self._scope(symbol="NetWatcher", path_filters=["drivers/net/**"], language="python"),
        )
        missing_result = self.client.call_tool(
            "code_check_symbol_exists",
            self._scope(symbol="MissingSymbol", path_filters=["drivers/net/**"], language="python"),
        )

        self.assertFalse(exists_result.is_error)
        self.assertTrue(exists_result.content["exists"])
        self.assertEqual(exists_result.content["matches"][0]["file_path"], "drivers/net/netstack.py")
        self.assertFalse(missing_result.is_error)
        self.assertFalse(missing_result.content["exists"])
        self.assertEqual(missing_result.content["matches"], [])


if __name__ == "__main__":
    unittest.main()
