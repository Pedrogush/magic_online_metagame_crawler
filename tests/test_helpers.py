"""Test helper utilities for managing global state in tests.

This module provides utilities for resetting global service and repository
instances to ensure test isolation and prevent state leakage between tests.
"""

import sys
from pathlib import Path

# Add parent directory to sys.path to enable imports from repositories and services
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# ruff: noqa: E402
from repositories.card_repository import reset_card_repository
from repositories.deck_repository import reset_deck_repository
from repositories.metagame_repository import reset_metagame_repository
from services.collection_service import reset_collection_service
from services.deck_service import reset_deck_service
from services.image_service import reset_image_service
from services.search_service import reset_search_service


def reset_all_services() -> None:
    """Reset all global service instances."""
    reset_collection_service()
    reset_deck_service()
    reset_search_service()
    reset_image_service()


def reset_all_repositories() -> None:
    """Reset all global repository instances."""
    reset_card_repository()
    reset_deck_repository()
    reset_metagame_repository()


def reset_all_globals() -> None:
    """Reset all global service and repository instances.

    This is the recommended function to call in test teardown or setup
    to ensure complete isolation between tests.
    """
    reset_all_services()
    reset_all_repositories()
