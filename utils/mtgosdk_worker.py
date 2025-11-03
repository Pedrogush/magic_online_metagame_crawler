"""Background worker process for MTGOSDK operations."""

from __future__ import annotations

import multiprocessing as mp
from multiprocessing.connection import Connection
from typing import Any, Dict

from loguru import logger

from utils import mtgosdk_runtime

COMMAND_FETCH_BINDER = "fetch_binder"
COMMAND_EXIT = "exit"


def _handle_fetch_binder(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = payload.get("name", "")
    binder = mtgosdk_runtime.get_frozen_collection()
    if binder is None:
        return {"status": "not_found", "message": f"Binder '{name}' not found"}
    return {"status": "ok", "binder": binder}


def worker_main(conn: Connection) -> None:
    logger.debug("MTGOSDK worker starting")
    mtgosdk_runtime.initialize()
    while True:
        try:
            message = conn.recv()
        except EOFError:
            break
        if not isinstance(message, dict):
            conn.send({"status": "error", "message": "Invalid message"})
            continue
        command = message.get("command")
        payload = message.get("payload", {}) or {}
        if command == COMMAND_EXIT:
            conn.send({"status": "ok"})
            break
        if command == COMMAND_FETCH_BINDER:
            try:
                result = _handle_fetch_binder(payload)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Worker failed to fetch binder")
                result = {"status": "error", "message": str(exc)}
            conn.send(result)
            continue
        conn.send({"status": "error", "message": f"Unknown command '{command}'"})
    logger.debug("MTGOSDK worker exiting")


def start_worker() -> tuple[Connection, mp.Process]:
    parent_conn, child_conn = mp.Pipe()
    process = mp.Process(target=worker_main, args=(child_conn,), daemon=True)
    process.start()
    return parent_conn, process
