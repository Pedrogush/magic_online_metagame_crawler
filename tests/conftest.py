"""Root-level pytest fixtures for all tests.

This module provides fixtures that are available to all tests in the project.
"""

import sys
from unittest import mock

# Mock wx before any imports that might need it (for Linux/headless environments)
if "wx" not in sys.modules:
    wx_mock = mock.MagicMock()
    wx_mock.CAPTION = 1
    wx_mock.CLOSE_BOX = 2
    wx_mock.MINIMIZE_BOX = 4
    wx_mock.STAY_ON_TOP = 8
    wx_mock.RESIZE_BORDER = 16
    wx_mock.VSCROLL = 32
    wx_mock.TE_MULTILINE = 64
    wx_mock.TE_READONLY = 128
    wx_mock.TE_WORDWRAP = 256
    wx_mock.BORDER_NONE = 512
    wx_mock.ALL = 1024
    wx_mock.EXPAND = 2048
    wx_mock.ALIGN_CENTER_VERTICAL = 4096
    wx_mock.RIGHT = 8192
    wx_mock.LEFT = 16384
    wx_mock.TOP = 32768
    wx_mock.BOTTOM = 65536
    wx_mock.OK = 131072
    wx_mock.ICON_INFORMATION = 262144
    wx_mock.ICON_WARNING = 524288
    wx_mock.ICON_ERROR = 1048576
    wx_mock.YES_NO = 2097152
    wx_mock.YES = 4194304
    wx_mock.NO = 8388608
    wx_mock.CANCEL = 16777216
    wx_mock.Colour = mock.Mock(return_value=mock.MagicMock())
    sys.modules["wx"] = wx_mock

import pytest
from test_helpers import reset_all_globals


@pytest.fixture(autouse=True)
def reset_global_state():
    """Automatically reset all global service and repository instances after each test.

    This fixture ensures test isolation by resetting all singleton instances
    to None after each test completes, preventing state leakage between tests.
    """
    yield
    reset_all_globals()
