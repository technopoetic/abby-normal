"""Tests for the abby-normal MCP server module.

The server shells out to memory-query, so these tests only exercise what can
be checked without touching the database: that the module imports against the
installed mcp SDK version and that both tools register.
"""

import os
import sys
import unittest
from pathlib import Path

# server.py re-executes itself under the project venv unless this flag is set;
# without it, importing the module would spawn a subprocess and sys.exit() the
# test process.
os.environ.setdefault("ABBY_NORMAL_IN_VENV", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

import server  # noqa: E402


class TestMCPServerModule(unittest.TestCase):
    def test_module_imports_and_registers_tools(self):
        self.assertTrue(hasattr(server, "mcp"), "server must expose an mcp instance")
        tools = server.mcp._tool_manager._tools
        self.assertIn("abby_recall", tools)
        self.assertIn("abby_save", tools)


if __name__ == "__main__":
    unittest.main()
