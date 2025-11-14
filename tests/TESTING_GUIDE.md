## Testing Guide

This guide explains how to write tests that properly handle global state in the Magic Online Metagame Crawler codebase.

### Problem: Global State and Test Isolation

The codebase uses singleton patterns for services and repositories through global getter functions like `get_collection_service()`, `get_deck_repository()`, etc. Without proper cleanup, these global instances can leak state between tests, causing flaky tests and false positives/negatives.

### Solution: Automatic Reset with Fixtures

The test suite now includes automatic cleanup of all global state. The root `tests/conftest.py` file provides a fixture that runs after every test:

```python
@pytest.fixture(autouse=True)
def reset_global_state():
    yield
    reset_all_globals()
```

This means you don't need to manually clean up global state in most cases. The fixture automatically resets all services and repositories after each test completes.

### Manual Reset (When Needed)

In rare cases where you need to reset state during a test (not just after), you can manually import and call reset functions:

```python
from tests.test_helpers import reset_all_globals, reset_all_services, reset_all_repositories

def test_something_complex():
    # Setup code that creates services
    service = get_collection_service()

    # Do some testing
    assert service.is_loaded() == False

    # Reset mid-test if needed
    reset_all_services()

    # Service is now None, next call creates fresh instance
    service2 = get_collection_service()
    assert service is not service2
```

### Available Reset Functions

The `tests/test_helpers.py` module provides:

- `reset_all_globals()` - Reset everything (services + repositories)
- `reset_all_services()` - Reset only services
- `reset_all_repositories()` - Reset only repositories

Individual reset functions:
- `reset_collection_service()`
- `reset_deck_service()`
- `reset_search_service()`
- `reset_image_service()`
- `reset_card_repository()`
- `reset_deck_repository()`
- `reset_metagame_repository()`

### Best Practices

1. Let the automatic fixture handle cleanup in most cases
2. Use dependency injection when creating new code (pass instances as constructor parameters)
3. Only use manual resets when you need fresh instances mid-test
4. Mock external dependencies (databases, network calls) rather than relying on real implementations
5. For services that depend on other services/repositories, reset in the correct order (dependencies first)

### Example: Testing with Services

```python
from services.collection_service import get_collection_service
from repositories.card_repository import get_card_repository

def test_collection_service_loads_cards():
    # Automatic fixture ensures clean state at start
    service = get_collection_service()

    # Test your logic
    assert service.get_collection_size() == 0
    service.add_cards("Mountain", 4)
    assert service.get_collection_size() == 1

    # No cleanup needed - fixture handles it

def test_another_collection_test():
    # Fresh service instance - previous test's state is gone
    service = get_collection_service()
    assert service.get_collection_size() == 0  # Passes!
```

### Example: Testing with Dependency Injection

When writing new code or refactoring tests, prefer dependency injection over global singletons:

```python
from services.deck_service import DeckService
from repositories.deck_repository import DeckRepository

def test_deck_service_with_mock_repo():
    # Create instances directly without globals
    mock_repo = DeckRepository()
    service = DeckService(deck_repository=mock_repo)

    # Test with your controlled instances
    result = service.analyze_deck("4 Mountain")
    assert result["mainboard_count"] == 4
```

### Parallel Test Execution

With proper test isolation through global state resets, tests can be run in parallel safely:

```bash
pytest -n auto  # Run with pytest-xdist
```

The automatic fixture ensures each test gets a clean environment regardless of execution order.

### Challenge Alarm Testing

The timer alert widget (widgets/timer_alert.py) has comprehensive test coverage in tests/test_timer_alert.py. Tests focus on logic validation rather than full GUI mocking to avoid wx dependencies on Linux. Core logic is tested in isolation including time parsing, threshold detection, alert triggers, and sound mapping. See the test file docstring for extending coverage with new alert scenarios.
