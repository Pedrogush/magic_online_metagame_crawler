"""Root-level pytest fixtures for all tests.

This module provides fixtures that are available to all tests in the project.
"""

import pytest

from tests.test_helpers import reset_all_globals


@pytest.fixture(autouse=True)
def reset_global_state():
    """Automatically reset all global service and repository instances after each test.

    This fixture ensures test isolation by resetting all singleton instances
    to None after each test completes, preventing state leakage between tests.
    """
    yield
    reset_all_globals()
