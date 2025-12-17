"""Tests for ImageService business logic."""

import importlib.util
import threading
from pathlib import Path
from typing import Any

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "services" / "image_service.py"
spec = importlib.util.spec_from_file_location("image_service_for_tests", MODULE_PATH)
assert spec and spec.loader  # noqa: S101
image_service_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image_service_module)
ImageService = image_service_module.ImageService

TIMEOUT = 2.0


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> ImageService:
    monkeypatch.setattr(image_service_module, "get_cache", lambda: object())
    return ImageService()


def test_check_bulk_data_exists_when_missing(
    service: ImageService, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "bulk.json"
    monkeypatch.setattr(image_service_module, "BULK_DATA_CACHE", cache_path)

    exists, reason = service.check_bulk_data_exists()

    assert exists is False
    assert "not found" in reason.lower()


def test_check_bulk_data_exists_when_present(
    service: ImageService, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "bulk.json"
    cache_path.write_text("{}")
    monkeypatch.setattr(image_service_module, "BULK_DATA_CACHE", cache_path)

    exists, reason = service.check_bulk_data_exists()

    assert exists is True
    assert "exists" in reason.lower()


def test_download_bulk_metadata_async_uses_force(service: ImageService) -> None:
    completed = threading.Event()
    force_values: list[bool] = []

    class FakeDownloader:
        def download_bulk_metadata(self, force: bool = False) -> tuple[bool, str]:
            force_values.append(force)
            return True, "ok"

    service.image_downloader = FakeDownloader()

    def on_success(msg: str) -> None:
        assert msg == "ok"
        completed.set()

    service.download_bulk_metadata_async(on_success, lambda msg: None, force=True)

    assert completed.wait(TIMEOUT)
    assert force_values == [True]
    assert service.bulk_download_in_progress is False


def test_concurrent_download_requests_are_guarded(service: ImageService) -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    first_completed = threading.Event()
    second_failed = threading.Event()
    second_errors: list[str] = []

    class BlockingDownloader:
        def download_bulk_metadata(self, force: bool = False) -> tuple[bool, str]:
            first_started.set()
            release_first.wait(2.0)
            return True, "done"

    service.image_downloader = BlockingDownloader()

    def first_success(_: str) -> None:
        first_completed.set()

    service.download_bulk_metadata_async(first_success, first_success)

    assert first_started.wait(TIMEOUT)

    def second_success(_: str) -> None:
        return

    def second_error(msg: str) -> None:
        second_errors.append(msg)
        second_failed.set()

    service.download_bulk_metadata_async(second_success, second_error)

    assert second_failed.wait(TIMEOUT)
    assert second_errors == [image_service_module.DOWNLOAD_IN_PROGRESS_MSG]

    release_first.set()
    assert first_completed.wait(TIMEOUT)
    assert service.bulk_download_in_progress is False


def test_download_errors_surface_and_reset_state(service: ImageService) -> None:
    completed = threading.Event()
    errors: list[str] = []

    class ErrorDownloader:
        def download_bulk_metadata(self, force: bool = False) -> tuple[bool, str]:
            raise RuntimeError("boom")

    service.image_downloader = ErrorDownloader()

    def on_error(msg: str) -> None:
        errors.append(msg)
        completed.set()

    service.download_bulk_metadata_async(lambda msg: None, on_error)

    assert completed.wait(TIMEOUT)
    assert errors == ["boom"]
    assert service.bulk_download_in_progress is False


def test_load_printing_index_async_sets_data_and_clears_flag(
    service: ImageService, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed = threading.Event()
    payload = {
        "data": {"Island": [{"name": "Island"}]},
        "unique_names": 1,
        "total_printings": 1,
    }
    monkeypatch.setattr(
        image_service_module, "ensure_printing_index_cache", lambda force=False: payload
    )

    results: list[dict[str, list[dict[str, Any]]]] = []

    def on_success(data: dict[str, list[dict[str, Any]]], stats: dict[str, Any]) -> None:
        results.append(data)
        completed.set()

    def on_error(_: str) -> None:
        completed.set()

    started = service.load_printing_index_async(
        force=True,
        on_success=on_success,
        on_error=on_error,
    )

    assert started is True
    assert completed.wait(TIMEOUT)
    assert service.bulk_data_by_name == payload["data"]
    assert service.printing_index_loading is False
    assert results == [payload["data"]]


def test_load_printing_index_async_error_resets_flag(
    service: ImageService, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed = threading.Event()
    errors: list[str] = []

    def raise_error(force: bool = False) -> None:
        raise ValueError("load failed")

    monkeypatch.setattr(image_service_module, "ensure_printing_index_cache", raise_error)

    def on_error(msg: str) -> None:
        errors.append(msg)
        completed.set()

    def on_success(_: dict[str, list[dict[str, Any]]], __: dict[str, Any]) -> None:
        completed.set()

    started = service.load_printing_index_async(
        force=True,
        on_success=on_success,
        on_error=on_error,
    )

    assert started is True
    assert completed.wait(TIMEOUT)
    assert errors == ["load failed"]
    assert service.printing_index_loading is False
