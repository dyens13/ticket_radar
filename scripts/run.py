#!/usr/bin/env python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    py = root / ".venv" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    cmd = [str(py), str(root / "src/main.py"), "--config", str(root / "config.yaml"), "--mode", "run"]
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
