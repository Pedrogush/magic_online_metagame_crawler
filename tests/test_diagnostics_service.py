from __future__ import annotations

import json
import zipfile

from services.diagnostics_service import DiagnosticsService


def test_event_logging_opt_in_and_export(tmp_path):
    logs_dir = tmp_path / "logs"
    config_file = tmp_path / "config" / "diagnostics_settings.json"
    event_log = logs_dir / "events.jsonl"

    service = DiagnosticsService(
        logs_dir=logs_dir,
        settings_path=config_file,
        event_log_path=event_log,
    )

    # Logging is disabled by default
    service.log_event("should_not_persist")
    assert not event_log.exists()

    # Opt-in and record an event
    service.set_event_logging_enabled(True)
    service.log_event("test_event", metadata={"foo": "bar"})
    lines = event_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == "test_event"
    assert payload["data"] == {"foo": "bar"}

    # Include an app log and export diagnostics
    log_file = logs_dir / "app.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("log contents", encoding="utf-8")

    archive_path = service.export_diagnostics(
        feedback="This broke when clicking save.",
        include_logs=True,
        include_event_log=True,
        destination=tmp_path / "diag.zip",
    )

    with zipfile.ZipFile(archive_path) as zf:
        names = set(zf.namelist())
        assert "feedback.txt" in names
        assert "metadata.json" in names
        assert "logs/app.log" in names
        assert "events/event_log.jsonl" in names
        feedback = zf.read("feedback.txt").decode("utf-8")
        assert "clicking save" in feedback

    saved_settings = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_settings["event_logging_enabled"] is True
