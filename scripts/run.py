#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _is_conda_env() -> bool:
    return bool(os.environ.get("CONDA_PREFIX") or os.environ.get("CONDA_DEFAULT_ENV"))


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    if _is_conda_env():
        py = Path(sys.executable)
    else:
        py = root / ".venv" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")

    cmd = [str(py), str(root / "src/main.py"), "--config", str(root / "config.yaml"), "--mode", "run"]
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
