"""Integration helpers for the MTGO bridge CLI built on MTGOSDK."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

DEFAULT_CANDIDATES = [
    Path("dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/mtgo_bridge.exe"),
    Path("dotnet/MTGOBridge/bin/Debug/net9.0-windows7.0/mtgo_bridge.exe"),
    Path("dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/mtgo_bridge"),
    Path("dotnet/MTGOBridge/bin/Debug/net9.0-windows7.0/mtgo_bridge"),
]


def _resolve_bridge_path(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None

    env_path = os.environ.get("MTGO_BRIDGE_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    for candidate in DEFAULT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _run_bridge(subcommand: str, *args: str, bridge_path: str | None = None, timeout: int = 10) -> dict[str, Any]:
    bridge = _resolve_bridge_path(bridge_path)
    if bridge is None:
        raise FileNotFoundError(
            "MTGO bridge executable not found. "
            "Build dotnet/MTGOBridge (dotnet publish) or set MTGO_BRIDGE_PATH."
        )

    command = [str(bridge), subcommand, *args]
    logger.debug("Running MTGO bridge: {}", " ".join(command))
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        logger.error("Bridge command failed ({}): {}", proc.returncode, proc.stderr.strip())
        raise RuntimeError(f"Bridge command '{subcommand}' failed: {proc.stderr.strip()}")

    stdout = proc.stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        logger.error("Bridge returned invalid JSON: {}", stdout)
        raise RuntimeError("Invalid JSON from bridge") from exc


def get_game_state(self_name: str | None, bridge_path: str | None = None) -> dict[str, Any]:
    args: list[str] = []
    if self_name:
        args.extend(["--self", self_name])
    return _run_bridge("game-state", *args, bridge_path=bridge_path)


def accept_pending_trades(bridge_path: str | None = None) -> dict[str, Any]:
    return _run_bridge("accept-trades", bridge_path=bridge_path)
