# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Charles Bine
"""Console commands for the standalone tools, so a pinned install can run them:

  uvx --from loupe-cad==X.Y.Z loupe-slice part.stl

Each command runs the bundled PEP 723 script through `uv run`, the same way the
MCP server does, so the script's inline dependencies resolve as usual.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _tool(script: str) -> None:
    sys.exit(subprocess.run(["uv", "run", str(ROOT / script), *sys.argv[1:]]).returncode)


def check() -> None:
    _tool("check.py")


def sheet() -> None:
    _tool("sheet.py")


def viewer() -> None:
    _tool("viewer.py")


def slice_() -> None:
    _tool("slice.py")
