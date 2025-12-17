from __future__ import annotations

import threading
import time

from utils.background_worker import BackgroundWorker


def test_background_worker_submit():
    worker = BackgroundWorker()
    result = []

    def task():
        result.append(1)

    worker.submit(task)
    time.sleep(0.1)

    assert result == [1]
    worker.shutdown()


def test_background_worker_is_stopped():
    worker = BackgroundWorker()

    assert not worker.is_stopped()

    worker.shutdown()

    assert worker.is_stopped()


def test_background_worker_stops_loop():
    worker = BackgroundWorker()
    iterations = []

    def loop_task():
        while not worker.is_stopped():
            iterations.append(1)
            time.sleep(0.05)

    worker.submit(loop_task)
    time.sleep(0.2)

    worker.shutdown(timeout=2.0)

    initial_count = len(iterations)
    time.sleep(0.2)
    final_count = len(iterations)

    assert initial_count > 0
    assert initial_count == final_count


def test_background_worker_context_manager():
    result = []

    with BackgroundWorker() as worker:

        def task():
            result.append(1)

        worker.submit(task)
        time.sleep(0.1)

    assert result == [1]
    assert worker.is_stopped()


def test_background_worker_shutdown_waits_for_threads():
    worker = BackgroundWorker()
    completed = []

    def slow_task():
        while not worker.is_stopped():
            time.sleep(0.1)
        completed.append(1)

    worker.submit(slow_task)
    time.sleep(0.1)

    worker.shutdown(timeout=2.0)

    assert completed == [1]


def test_background_worker_multiple_threads():
    worker = BackgroundWorker()
    results = []

    def task(value):
        results.append(value)

    worker.submit(task, 1)
    worker.submit(task, 2)
    worker.submit(task, 3)

    time.sleep(0.2)
    worker.shutdown()

    assert sorted(results) == [1, 2, 3]


def test_background_worker_shutdown_timeout():
    worker = BackgroundWorker()
    started = threading.Event()

    def blocking_task():
        started.set()
        while True:
            time.sleep(0.1)

    worker.submit(blocking_task)
    started.wait(timeout=1.0)

    worker.shutdown(timeout=0.2)

    assert worker.is_stopped()
