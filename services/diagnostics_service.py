"""Diagnostics and feedback utilities: opt-in event logging and export packaging."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from utils.constants import (
    DIAGNOSTICS_EVENT_LOG,
    DIAGNOSTICS_SETTINGS_FILE,
    LOGS_DIR,
    ensure_base_dirs,
)


class DiagnosticsService:
    """Manage lightweight event logging and diagnostics export."""

    def __init__(
        self,
        *,
        logs_dir: Path | None = None,
        settings_path: Path | None = None,
        event_log_path: Path | None = None,
    ) -> None:
        ensure_base_dirs()
        self.logs_dir = Path(logs_dir or LOGS_DIR)
        self.settings_path = Path(settings_path or DIAGNOSTICS_SETTINGS_FILE)
        self.event_log_path = Path(event_log_path or DIAGNOSTICS_EVENT_LOG)
        self._settings = self._load_settings()

    # ------------------------------------------------------------------ settings ------------------------------------------------------------------
    def _load_settings(self) -> dict[str, Any]:
        default = {"event_logging_enabled": False}
        if not self.settings_path.exists():
            return default
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return default
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Unable to read diagnostics settings: {exc}")
            return default
        return {**default, **data}

    def _persist_settings(self) -> None:
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(
                json.dumps(self._settings, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning(f"Failed to persist diagnostics settings: {exc}")

    @property
    def event_logging_enabled(self) -> bool:
        return bool(self._settings.get("event_logging_enabled", False))

    def set_event_logging_enabled(self, enabled: bool) -> None:
        if self._settings.get("event_logging_enabled") == enabled:
            return
        self._settings["event_logging_enabled"] = bool(enabled)
        self._persist_settings()

    # ------------------------------------------------------------------ event logging ------------------------------------------------------------------
    def log_event(self, name: str, *, metadata: dict[str, Any] | None = None) -> None:
        """Append an anonymized event entry if opt-in is enabled."""
        if not self.event_logging_enabled:
            return
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": name,
            "data": metadata or {},
        }
        try:
            self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.event_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.debug(f"Failed to write event log: {exc}")

    # ------------------------------------------------------------------ export ------------------------------------------------------------------
    def export_diagnostics(
        self,
        *,
        feedback: str = "",
        include_logs: bool = True,
        include_event_log: bool = True,
        extra_files: Iterable[Path] | None = None,
        destination: Path | None = None,
    ) -> Path:
        """
        Package feedback + diagnostics into a zip file.

        Args:
            feedback: User-provided notes
            include_logs: Whether to include standard log files
            include_event_log: Whether to include anonymized event log
            extra_files: Additional files to include
            destination: Optional destination path for the zip
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = destination or (self.logs_dir / f"mtgo_tools_diagnostics_{timestamp}.zip")

        files_to_add: list[tuple[Path, str]] = []
        if include_logs and self.logs_dir.exists():
            for path in sorted(self.logs_dir.glob("*.log")):
                files_to_add.append((path, f"logs/{path.name}"))
        if include_event_log and self.event_log_path.exists():
            files_to_add.append((self.event_log_path, "events/event_log.jsonl"))
        if extra_files:
            for file_path in extra_files:
                if file_path and Path(file_path).exists():
                    files_to_add.append((Path(file_path), f"extras/{Path(file_path).name}"))

        feedback_body = feedback.strip() or "No feedback provided."
        metadata = {
            "generated_at": timestamp,
            "event_logging_enabled": self.event_logging_enabled,
            "logs_included": include_logs,
            "event_log_included": include_event_log and self.event_log_path.exists(),
        }

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("feedback.txt", feedback_body)
            zf.writestr("metadata.json", json.dumps(metadata, indent=2))
            for file_path, arcname in files_to_add:
                try:
                    zf.write(file_path, arcname)
                except OSError as exc:
                    logger.debug(f"Skipped file {file_path}: {exc}")

        return dest_path


_default_diagnostics_service: DiagnosticsService | None = None


def get_diagnostics_service() -> DiagnosticsService:
    """Return singleton diagnostics service."""
    global _default_diagnostics_service
    if _default_diagnostics_service is None:
        _default_diagnostics_service = DiagnosticsService()
    return _default_diagnostics_service


__all__ = ["DiagnosticsService", "get_diagnostics_service"]
