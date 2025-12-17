from __future__ import annotations

import threading
import time

from utils.managed_executor import ManagedExecutor


def test_managed_executor_submit():
    executor = ManagedExecutor()
    result = []

    def task():
        result.append(1)

    executor.submit(task)
    time.sleep(0.1)

    assert result == [1]
    executor.shutdown()


def test_managed_executor_is_stopped():
    executor = ManagedExecutor()

    assert not executor.is_stopped()

    executor.shutdown()

    assert executor.is_stopped()


def test_managed_executor_stops_loop():
    executor = ManagedExecutor()
    iterations = []

    def loop_task():
        while not executor.is_stopped():
            iterations.append(1)
            time.sleep(0.05)

    executor.submit(loop_task)
    time.sleep(0.2)

    executor.shutdown(timeout=2.0)

    initial_count = len(iterations)
    time.sleep(0.2)
    final_count = len(iterations)

    assert initial_count > 0
    assert initial_count == final_count


def test_managed_executor_context_manager():
    result = []

    with ManagedExecutor() as executor:

        def task():
            result.append(1)

        executor.submit(task)
        time.sleep(0.1)

    assert result == [1]
    assert executor.is_stopped()


def test_managed_executor_shutdown_waits_for_threads():
    executor = ManagedExecutor()
    completed = []

    def slow_task():
        while not executor.is_stopped():
            time.sleep(0.1)
        completed.append(1)

    executor.submit(slow_task)
    time.sleep(0.1)

    executor.shutdown(timeout=2.0)

    assert completed == [1]


def test_managed_executor_multiple_threads():
    executor = ManagedExecutor()
    results = []

    def task(value):
        results.append(value)

    executor.submit(task, 1)
    executor.submit(task, 2)
    executor.submit(task, 3)

    time.sleep(0.2)
    executor.shutdown()

    assert sorted(results) == [1, 2, 3]


def test_managed_executor_shutdown_timeout():
    executor = ManagedExecutor()
    started = threading.Event()

    def blocking_task():
        started.set()
        while True:
            time.sleep(0.1)

    executor.submit(blocking_task)
    started.wait(timeout=1.0)

    executor.shutdown(timeout=0.2)

    assert executor.is_stopped()
