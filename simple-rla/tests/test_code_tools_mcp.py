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
                "code_search_text",
                "code_read_file_range",
                "code_read_symbol_context",
                "code_check_symbol_exists",
            },
        )

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
