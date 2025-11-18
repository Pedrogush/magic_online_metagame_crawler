"""Tests for the mtgo_bridge module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import mtgo_bridge


def test_check_mtgo_connection_no_bridge(tmp_path: Path) -> None:
    """Test that check_mtgo_connection returns False when bridge is not found."""
    fake_path = str(tmp_path / "nonexistent.exe")
    result = mtgo_bridge.check_mtgo_connection(bridge_path=fake_path)
    assert result is False


def test_check_mtgo_connection_bridge_fails() -> None:
    """Test that check_mtgo_connection returns False when bridge command fails."""
    with patch("utils.mtgo_bridge.mtgo_bridge_client.run_bridge_command") as mock_cmd:
        mock_cmd.side_effect = Exception("MTGO not running")
        result = mtgo_bridge.check_mtgo_connection()
        assert result is False


def test_check_mtgo_connection_no_username() -> None:
    """Test that check_mtgo_connection returns False when no username in response."""
    with patch("utils.mtgo_bridge.mtgo_bridge_client.run_bridge_command") as mock_cmd:
        mock_cmd.return_value = {"error": "Not logged in"}
        result = mtgo_bridge.check_mtgo_connection()
        assert result is False


def test_check_mtgo_connection_success() -> None:
    """Test that check_mtgo_connection returns True when username is returned."""
    with patch("utils.mtgo_bridge.mtgo_bridge_client.run_bridge_command") as mock_cmd:
        mock_cmd.return_value = {"username": "TestUser"}
        result = mtgo_bridge.check_mtgo_connection()
        assert result is True


def test_check_mtgo_connection_invalid_response() -> None:
    """Test that check_mtgo_connection returns False for invalid response types."""
    with patch("utils.mtgo_bridge.mtgo_bridge_client.run_bridge_command") as mock_cmd:
        # Test with string response instead of dict
        mock_cmd.return_value = "invalid"
        result = mtgo_bridge.check_mtgo_connection()
        assert result is False

        # Test with None
        mock_cmd.return_value = None
        result = mtgo_bridge.check_mtgo_connection()
        assert result is False


def test_runtime_status_bridge_available(tmp_path: Path) -> None:
    """Test runtime_status returns True when bridge exists."""
    fake_bridge = tmp_path / "MTGOBridge.exe"
    fake_bridge.write_text("stub")

    ready, message = mtgo_bridge.runtime_status(bridge_path=str(fake_bridge))
    assert ready is True
    assert message is None


def test_runtime_status_bridge_not_found() -> None:
    """Test runtime_status returns False when bridge is not found."""
    ready, message = mtgo_bridge.runtime_status(bridge_path="/nonexistent/path.exe")
    assert ready is False
    assert message is not None
    assert "not found" in message.lower()
