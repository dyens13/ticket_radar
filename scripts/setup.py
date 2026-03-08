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
        print(f"Detected conda environment at {sys.prefix}. Installing into current env.")
    else:
        venv_dir = root / ".venv"
        py = venv_dir / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(root / "requirements.txt")])

    print("Setup complete. Copy config.example.yaml to config.yaml and fill token/chat id.")


if __name__ == "__main__":
    main()
