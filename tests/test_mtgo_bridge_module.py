import os
from pathlib import Path

import pytest

from utils import mtgo_bridge


def test_missing_bridge_path_raises(tmp_path):
    fake_exe = tmp_path / "mtgo_bridge.exe"
    with pytest.raises(FileNotFoundError):
        mtgo_bridge.get_game_state(None, bridge_path=str(fake_exe))


def test_resolve_bridge_from_env(monkeypatch, tmp_path):
    fake_bridge = tmp_path / "mtgo_bridge.exe"
    fake_bridge.write_text("stub")
    monkeypatch.setenv("MTGO_BRIDGE_PATH", str(fake_bridge))
    resolved = mtgo_bridge._resolve_bridge_path(None)  # type: ignore[attr-defined]
    assert resolved == fake_bridge
