#!/usr/bin/env python
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

# Set the interpreter that should run src/main.py.
# Change this path to match your server environment.
TARGET_PYTHON = '/home/azureuser/miniconda3/envs/py311/bin/python'

# Internal log file path (relative to repository root).
LOG_FILE_RELATIVE = "logs/cron_hourly.log"

# Always run both jobs. Execution time is controlled by crontab.
MODES = ["new-alert-once", "preopen-alert-once"]


def _write_log(log_file: Path, message: str) -> None:
    stamped = f"[{datetime.now().isoformat()}] {message}"
    print(stamped)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(stamped + "\n")


def _run_mode(py: str, main_script: Path, config_path: Path, mode: str, log_file: Path) -> None:
    cmd = [py, str(main_script), "--config", str(config_path), "--mode", mode]
    _write_log(log_file, f"start mode={mode} cmd={' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        for line in result.stdout.splitlines():
            _write_log(log_file, f"[{mode}] {line}")
    if result.stderr:
        for line in result.stderr.splitlines():
            _write_log(log_file, f"[{mode}][stderr] {line}")

    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)

    _write_log(log_file, f"done mode={mode} exit=0")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    main_script = root / "src" / "main.py"
    config_path = root / "config.yaml"
    log_file = root / LOG_FILE_RELATIVE
    log_file.parent.mkdir(parents=True, exist_ok=True)

    _write_log(log_file, f"running modes: {', '.join(MODES)}")
    for mode in MODES:
        _run_mode(TARGET_PYTHON, main_script, config_path, mode, log_file)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
