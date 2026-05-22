#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动 NiceGUI Web（默认端口 8001）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8001


def main() -> None:
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    elif os.environ.get("PORT"):
        port = int(os.environ["PORT"])

    app = REPO_ROOT / "nicegui_app.py"
    cmd = [sys.executable, str(app), str(port)]
    raise SystemExit(subprocess.call(cmd, cwd=REPO_ROOT))


if __name__ == "__main__":
    main()
