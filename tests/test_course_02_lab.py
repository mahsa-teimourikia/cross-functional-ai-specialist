from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_course_module() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "curriculum"
        / "advanced"
        / "02-cloud-distributed-ai-systems"
        / "lab.py"
    )
    spec = importlib.util.spec_from_file_location("course_02_lab", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lab = _load_course_module()


def request(operation_id: str = "op-1", *, version: int = 1, text: str = "policy text"):
    return lab.JobRequest(operation_id, "tenant-a", "doc-1", version, text)


def test_payload_digest_is_stable_and_sensitive_to_business_input() -> None:
    first = request()
    same = request()
    changed = request(text="different policy text")

    assert first.payload_digest == same.payload_digest
    assert first.payload_digest != changed.payload_digest


def test_duplicate_delivery_produces_one_external_write() -> None:
    queue = lab.AtLeastOnceQueue()
    message_id = queue.send(request())
    queue.inject_duplicate(message_id)
    worker = lab.DocumentWorker(queue, lab.VersionedResultStore(), lab.DeterministicAnalyzer())

    report = lab.run_until_idle(worker)

    assert report.delivery_attempts == 2
    assert report.result_writes == 1
    assert report.reconciliation_count == 1
    assert report.pending_messages == 0


def test_operation_id_reuse_with_changed_input_is_quarantined() -> None:
    queue = lab.AtLeastOnceQueue()
    queue.send(request(text="first payload"))
    queue.send(request(text="conflicting payload"))
    worker = lab.DocumentWorker(queue, lab.VersionedResultStore(), lab.DeterministicAnalyzer())

    report = lab.run_until_idle(worker)

    assert report.result_writes == 1
    assert report.dead_letters == 1
    assert worker.queue.dead_letters[0].reason_code == "IDEMPOTENCY_CONFLICT"


def test_transient_failure_retries_then_succeeds() -> None:
    queue = lab.AtLeastOnceQueue(max_receive_count=3)
    queue.send(request("op-transient"))
    analyzer = lab.DeterministicAnalyzer(transient_failures={"op-transient": 1})
    worker = lab.DocumentWorker(queue, lab.VersionedResultStore(), analyzer, retry_delay=2.0)

    report = lab.run_until_idle(worker)

    assert [event.reason_code for event in report.events] == ["RETRY_THROTTLED", "WRITTEN"]
    assert report.result_writes == 1
    assert report.dead_letters == 0


def test_persistent_retryable_failure_reaches_dlq_at_bound() -> None:
    queue = lab.AtLeastOnceQueue(max_receive_count=3)
    queue.send(request("op-poison"))
    analyzer = lab.DeterministicAnalyzer(always_throttle=frozenset({"op-poison"}))
    worker = lab.DocumentWorker(queue, lab.VersionedResultStore(), analyzer)

    report = lab.run_until_idle(worker)

    assert report.delivery_attempts == 3
    assert report.dead_letters == 1
    assert report.events[-1].reason_code == "DLQ_RETRY_EXHAUSTED"


def test_unknown_write_outcome_is_reconciled_without_second_write() -> None:
    queue = lab.AtLeastOnceQueue(max_receive_count=3)
    queue.send(request("op-unknown"))
    store = lab.VersionedResultStore()
    analyzer = lab.DeterministicAnalyzer()
    worker = lab.DocumentWorker(
        queue,
        store,
        analyzer,
        unknown_outcome_once=frozenset({"op-unknown"}),
    )

    report = lab.run_until_idle(worker)

    assert [event.reason_code for event in report.events] == [
        "RETRY_UNKNOWN_OUTCOME",
        "RECONCILED_SUCCEEDED",
    ]
    assert store.write_count == 1
    assert analyzer.calls["op-unknown"] == 1


def test_out_of_order_stale_event_cannot_overwrite_newer_version() -> None:
    queue = lab.AtLeastOnceQueue()
    queue.send(request("op-v2", version=2, text="new version"))
    queue.send(request("op-v1", version=1, text="old version"))
    store = lab.VersionedResultStore()
    worker = lab.DocumentWorker(queue, store, lab.DeterministicAnalyzer())

    report = lab.run_until_idle(worker)
    latest = store.latest("tenant-a", "doc-1")

    assert latest is not None
    assert latest.document_version == 2
    assert report.result_writes == 1
    assert report.events[-1].reason_code == "STALE"


def test_same_version_with_different_content_is_not_last_writer_wins() -> None:
    queue = lab.AtLeastOnceQueue()
    queue.send(request("op-a", text="first"))
    queue.send(request("op-b", text="second"))
    worker = lab.DocumentWorker(queue, lab.VersionedResultStore(), lab.DeterministicAnalyzer())

    report = lab.run_until_idle(worker)

    assert report.result_writes == 1
    assert report.dead_letters == 1
    assert report.events[-1].reason_code == "DLQ_VERSION_CONFLICT"


def test_overload_experiment_exposes_growing_backlog() -> None:
    report = lab.simulate_capacity([5] * 10, capacity_per_tick=4)

    assert report.arrivals == 50
    assert report.completed == 40
    assert report.final_backlog == 10
    assert report.maximum_backlog == 10
    assert report.utilization == pytest.approx(1.0)
    assert report.little_law_wait_estimate > 0


def test_synchronous_retry_duplicates_effect_but_reference_scenario_does_not() -> None:
    sync_report = lab.unsafe_synchronous_retry(request("op-sync"))
    worker, _ = lab.build_reference_scenario()
    async_report = lab.run_until_idle(worker)

    assert sync_report.attempts == 2
    assert sync_report.external_writes == 2
    assert async_report.pending_messages == 0
    assert async_report.dead_letters == 1
    assert async_report.result_writes == 4
    assert async_report.reconciliation_count == 2
