from __future__ import annotations

import datetime as _dt
import subprocess
import sys
from pathlib import Path

LOG_PATH = Path("agent_command_log.txt")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python3 scripts/run_logged.py <command> [args...]", file=sys.stderr)
        return 1

    command = argv[1:]
    timestamp = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    log_entry = f"{timestamp} | {' '.join(command)}\n"
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(log_entry)
    except OSError as exc:
        print(f"Failed to write log entry: {exc}", file=sys.stderr)
        return 1

    result = subprocess.run(command)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
