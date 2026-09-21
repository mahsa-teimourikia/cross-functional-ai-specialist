"""Deterministic distributed-systems lab for Course 2.

The module models an asynchronous document-analysis service without cloud credentials,
network calls, sleeps, or randomness. It makes delivery attempts, logical operations,
idempotency, conditional writes, unknown outcomes, retries, and dead-letter state visible.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class OperationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    STALE = "stale"


class CommitOutcome(StrEnum):
    WRITTEN = "written"
    REPLAYED = "replayed"
    STALE = "stale"


class DistributedSystemError(Exception):
    """Base class for failures classified by the trusted worker."""


class DependencyThrottled(DistributedSystemError):
    """A retryable downstream capacity failure."""


class InvalidDocument(DistributedSystemError):
    """A terminal validation failure."""


class UnknownWriteOutcome(DistributedSystemError):
    """The write may have committed even though the caller did not receive an acknowledgement."""


class IdempotencyConflict(DistributedSystemError):
    """One logical operation ID was reused for different input."""


class VersionConflict(DistributedSystemError):
    """Two different payloads claim the same document version."""


@dataclass(frozen=True, slots=True)
class JobRequest:
    operation_id: str
    tenant_id: str
    document_id: str
    document_version: int
    text: str

    def __post_init__(self) -> None:
        if not self.operation_id or not self.tenant_id or not self.document_id:
            raise ValueError("operation, tenant, and document IDs are required")
        if self.document_version < 1:
            raise ValueError("document_version must be positive")
        if not self.text.strip():
            raise ValueError("document text is required")

    @property
    def payload_digest(self) -> str:
        canonical = "\x1f".join(
            (self.tenant_id, self.document_id, str(self.document_version), self.text)
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(slots=True)
class QueueEntry:
    message_id: str
    request: JobRequest
    enqueued_at: float
    visible_at: float
    receive_count: int = 0


@dataclass(frozen=True, slots=True)
class DeadLetter:
    message_id: str
    operation_id: str
    receive_count: int
    reason_code: str


class AtLeastOnceQueue:
    """A small SQS-like queue with visibility, redelivery, and a dead-letter sink."""

    def __init__(self, visibility_timeout: float = 4.0, max_receive_count: int = 3) -> None:
        if visibility_timeout <= 0 or max_receive_count < 1:
            raise ValueError("queue limits must be positive")
        self.visibility_timeout = visibility_timeout
        self.max_receive_count = max_receive_count
        self._entries: dict[str, QueueEntry] = {}
        self._next_message_number = 1
        self.dead_letters: list[DeadLetter] = []

    def send(self, request: JobRequest, now: float = 0.0, delay: float = 0.0) -> str:
        message_id = f"msg-{self._next_message_number:04d}"
        self._next_message_number += 1
        self._entries[message_id] = QueueEntry(
            message_id=message_id,
            request=request,
            enqueued_at=now,
            visible_at=now + delay,
        )
        return message_id

    def inject_duplicate(self, message_id: str, now: float = 0.0) -> str:
        return self.send(self._entries[message_id].request, now=now)

    def receive(self, now: float) -> QueueEntry | None:
        visible = [entry for entry in self._entries.values() if entry.visible_at <= now]
        if not visible:
            return None
        entry = min(visible, key=lambda item: (item.visible_at, item.message_id))
        entry.receive_count += 1
        entry.visible_at = now + self.visibility_timeout
        return entry

    def acknowledge(self, message_id: str) -> None:
        self._entries.pop(message_id, None)

    def fail(
        self,
        entry: QueueEntry,
        *,
        now: float,
        reason_code: str,
        retryable: bool,
        retry_delay: float,
    ) -> bool:
        """Release for retry or move to the DLQ. Return True when dead-lettered."""

        if not retryable or entry.receive_count >= self.max_receive_count:
            self._entries.pop(entry.message_id, None)
            self.dead_letters.append(
                DeadLetter(
                    message_id=entry.message_id,
                    operation_id=entry.request.operation_id,
                    receive_count=entry.receive_count,
                    reason_code=reason_code,
                )
            )
            return True
        entry.visible_at = now + retry_delay
        return False

    @property
    def pending_count(self) -> int:
        return len(self._entries)

    @property
    def next_visible_at(self) -> float | None:
        if not self._entries:
            return None
        return min(entry.visible_at for entry in self._entries.values())


@dataclass(frozen=True, slots=True)
class OperationRecord:
    operation_id: str
    payload_digest: str
    status: OperationStatus
    result: str | None


@dataclass(frozen=True, slots=True)
class DocumentResult:
    tenant_id: str
    document_id: str
    document_version: int
    payload_digest: str
    result: str


class VersionedResultStore:
    """Idempotency ledger plus a conditional latest-version document projection."""

    def __init__(self) -> None:
        self._operations: dict[str, OperationRecord] = {}
        self._documents: dict[tuple[str, str], DocumentResult] = {}
        self.write_count = 0

    def lookup(self, request: JobRequest) -> OperationRecord | None:
        record = self._operations.get(request.operation_id)
        if record is not None and record.payload_digest != request.payload_digest:
            raise IdempotencyConflict(
                "operation ID already belongs to a different request digest"
            )
        return record

    def latest(self, tenant_id: str, document_id: str) -> DocumentResult | None:
        return self._documents.get((tenant_id, document_id))

    def commit(self, request: JobRequest, result: str) -> CommitOutcome:
        existing_operation = self.lookup(request)
        if existing_operation is not None:
            return CommitOutcome.REPLAYED

        key = (request.tenant_id, request.document_id)
        current = self._documents.get(key)
        if current is not None and request.document_version < current.document_version:
            self._operations[request.operation_id] = OperationRecord(
                operation_id=request.operation_id,
                payload_digest=request.payload_digest,
                status=OperationStatus.STALE,
                result=None,
            )
            return CommitOutcome.STALE

        if (
            current is not None
            and request.document_version == current.document_version
            and request.payload_digest != current.payload_digest
        ):
            raise VersionConflict("different content claims the current document version")

        if current is not None and request.payload_digest == current.payload_digest:
            self._operations[request.operation_id] = OperationRecord(
                operation_id=request.operation_id,
                payload_digest=request.payload_digest,
                status=OperationStatus.SUCCEEDED,
                result=current.result,
            )
            return CommitOutcome.REPLAYED

        document_result = DocumentResult(
            tenant_id=request.tenant_id,
            document_id=request.document_id,
            document_version=request.document_version,
            payload_digest=request.payload_digest,
            result=result,
        )
        self._documents[key] = document_result
        self._operations[request.operation_id] = OperationRecord(
            operation_id=request.operation_id,
            payload_digest=request.payload_digest,
            status=OperationStatus.SUCCEEDED,
            result=result,
        )
        self.write_count += 1
        return CommitOutcome.WRITTEN

    @property
    def successful_operations(self) -> int:
        return sum(
            record.status is OperationStatus.SUCCEEDED
            for record in self._operations.values()
        )


class DeterministicAnalyzer:
    """Local analyzer with explicit transient and terminal failure injection."""

    def __init__(
        self,
        *,
        transient_failures: Mapping[str, int] | None = None,
        always_throttle: frozenset[str] = frozenset(),
        invalid_operations: frozenset[str] = frozenset(),
    ) -> None:
        self._remaining_transient = dict(transient_failures or {})
        self._always_throttle = always_throttle
        self._invalid_operations = invalid_operations
        self.calls: dict[str, int] = {}

    def analyze(self, request: JobRequest) -> str:
        operation_id = request.operation_id
        self.calls[operation_id] = self.calls.get(operation_id, 0) + 1
        if operation_id in self._invalid_operations:
            raise InvalidDocument("document failed deterministic validation")
        if operation_id in self._always_throttle:
            raise DependencyThrottled("dependency remained throttled")
        remaining = self._remaining_transient.get(operation_id, 0)
        if remaining > 0:
            self._remaining_transient[operation_id] = remaining - 1
            raise DependencyThrottled("dependency asked the worker to retry later")
        word_count = len(request.text.split())
        return (
            f"document={request.document_id};"
            f"version={request.document_version};words={word_count}"
        )


@dataclass(frozen=True, slots=True)
class AttemptEvent:
    attempt_id: str
    message_id: str
    operation_id: str
    receive_count: int
    started_at: float
    terminal: bool
    reason_code: str


class DocumentWorker:
    """Trusted application worker that owns classification and side-effect policy."""

    def __init__(
        self,
        queue: AtLeastOnceQueue,
        store: VersionedResultStore,
        analyzer: DeterministicAnalyzer,
        *,
        retry_delay: float = 2.0,
        unknown_outcome_once: frozenset[str] = frozenset(),
    ) -> None:
        self.queue = queue
        self.store = store
        self.analyzer = analyzer
        self.retry_delay = retry_delay
        self._unknown_outcome_once = unknown_outcome_once
        self._unknown_outcome_triggered: set[str] = set()

    def process_one(self, now: float) -> AttemptEvent | None:
        entry = self.queue.receive(now)
        if entry is None:
            return None
        request = entry.request
        attempt_id = f"{entry.message_id}:attempt:{entry.receive_count}"
        try:
            existing = self.store.lookup(request)
            if existing is not None:
                self.queue.acknowledge(entry.message_id)
                return AttemptEvent(
                    attempt_id,
                    entry.message_id,
                    request.operation_id,
                    entry.receive_count,
                    now,
                    True,
                    f"RECONCILED_{existing.status.value.upper()}",
                )

            result = self.analyzer.analyze(request)
            outcome = self.store.commit(request, result)
            if (
                outcome is CommitOutcome.WRITTEN
                and request.operation_id in self._unknown_outcome_once
                and request.operation_id not in self._unknown_outcome_triggered
            ):
                self._unknown_outcome_triggered.add(request.operation_id)
                raise UnknownWriteOutcome("result committed but acknowledgement was lost")

            self.queue.acknowledge(entry.message_id)
            return AttemptEvent(
                attempt_id,
                entry.message_id,
                request.operation_id,
                entry.receive_count,
                now,
                True,
                outcome.value.upper(),
            )
        except DependencyThrottled:
            dead_lettered = self.queue.fail(
                entry,
                now=now,
                reason_code="DEPENDENCY_THROTTLED",
                retryable=True,
                retry_delay=self.retry_delay,
            )
            return AttemptEvent(
                attempt_id,
                entry.message_id,
                request.operation_id,
                entry.receive_count,
                now,
                dead_lettered,
                "DLQ_RETRY_EXHAUSTED" if dead_lettered else "RETRY_THROTTLED",
            )
        except UnknownWriteOutcome:
            dead_lettered = self.queue.fail(
                entry,
                now=now,
                reason_code="UNKNOWN_WRITE_OUTCOME",
                retryable=True,
                retry_delay=self.retry_delay,
            )
            return AttemptEvent(
                attempt_id,
                entry.message_id,
                request.operation_id,
                entry.receive_count,
                now,
                dead_lettered,
                "DLQ_UNKNOWN_OUTCOME" if dead_lettered else "RETRY_UNKNOWN_OUTCOME",
            )
        except (IdempotencyConflict, VersionConflict, InvalidDocument) as error:
            reason_codes = {
                IdempotencyConflict: "IDEMPOTENCY_CONFLICT",
                VersionConflict: "VERSION_CONFLICT",
                InvalidDocument: "INVALID_DOCUMENT",
            }
            reason_code = reason_codes[type(error)]
            self.queue.fail(
                entry,
                now=now,
                reason_code=reason_code,
                retryable=False,
                retry_delay=0.0,
            )
            return AttemptEvent(
                attempt_id,
                entry.message_id,
                request.operation_id,
                entry.receive_count,
                now,
                True,
                f"DLQ_{reason_code}",
            )


@dataclass(frozen=True, slots=True)
class SimulationReport:
    events: tuple[AttemptEvent, ...]
    elapsed_ticks: float
    result_writes: int
    successful_operations: int
    dead_letters: int
    pending_messages: int

    @property
    def delivery_attempts(self) -> int:
        return len(self.events)

    @property
    def reconciliation_count(self) -> int:
        return sum(event.reason_code.startswith("RECONCILED") for event in self.events)

    @property
    def work_amplification(self) -> float:
        denominator = max(1, self.successful_operations)
        return self.delivery_attempts / denominator


def run_until_idle(
    worker: DocumentWorker, *, start_at: float = 0.0, max_attempts: int = 100
) -> SimulationReport:
    """Run the virtual queue until empty; jump time instead of sleeping."""

    now = start_at
    events: list[AttemptEvent] = []
    while worker.queue.pending_count and len(events) < max_attempts:
        event = worker.process_one(now)
        if event is None:
            next_visible = worker.queue.next_visible_at
            if next_visible is None:
                break
            now = max(now, next_visible)
            continue
        events.append(event)
        now += 1.0
    return SimulationReport(
        events=tuple(events),
        elapsed_ticks=now - start_at,
        result_writes=worker.store.write_count,
        successful_operations=worker.store.successful_operations,
        dead_letters=len(worker.queue.dead_letters),
        pending_messages=worker.queue.pending_count,
    )


@dataclass(frozen=True, slots=True)
class CapacityReport:
    arrivals: int
    completed: int
    final_backlog: int
    maximum_backlog: int
    average_backlog: float
    utilization: float
    p95_queue_wait_ticks: float
    little_law_wait_estimate: float


def _nearest_rank_percentile(values: Sequence[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return float(ordered[rank - 1])


def simulate_capacity(arrivals_per_tick: Sequence[int], capacity_per_tick: int) -> CapacityReport:
    """Measure backlog and queue wait for a finite virtual load experiment."""

    if not arrivals_per_tick or capacity_per_tick < 1:
        raise ValueError("the experiment needs arrivals and positive capacity")
    queue: list[int] = []
    waits: list[int] = []
    backlog_samples: list[int] = []
    completed = 0
    for tick, arrivals in enumerate(arrivals_per_tick):
        if arrivals < 0:
            raise ValueError("arrivals cannot be negative")
        queue.extend([tick] * arrivals)
        processed = min(capacity_per_tick, len(queue))
        for _ in range(processed):
            arrival_tick = queue.pop(0)
            waits.append(tick - arrival_tick)
        completed += processed
        backlog_samples.append(len(queue))

    duration = len(arrivals_per_tick)
    total_arrivals = sum(arrivals_per_tick)
    average_backlog = sum(backlog_samples) / duration
    throughput = completed / duration
    return CapacityReport(
        arrivals=total_arrivals,
        completed=completed,
        final_backlog=len(queue),
        maximum_backlog=max(backlog_samples),
        average_backlog=average_backlog,
        utilization=completed / (capacity_per_tick * duration),
        p95_queue_wait_ticks=_nearest_rank_percentile(waits, 0.95),
        little_law_wait_estimate=average_backlog / throughput if throughput else math.inf,
    )


@dataclass(frozen=True, slots=True)
class SynchronousRetryReport:
    attempts: int
    external_writes: int
    final_result: str


def unsafe_synchronous_retry(request: JobRequest) -> SynchronousRetryReport:
    """Show how a timeout-after-write creates a duplicate without an operation ledger."""

    analyzer = DeterministicAnalyzer()
    writes: list[str] = []
    attempts = 0
    try:
        attempts += 1
        writes.append(analyzer.analyze(request))
        raise UnknownWriteOutcome("response was lost after the write")
    except UnknownWriteOutcome:
        attempts += 1
        writes.append(analyzer.analyze(request))
    return SynchronousRetryReport(
        attempts=attempts,
        external_writes=len(writes),
        final_result=writes[-1],
    )


def build_reference_scenario() -> tuple[DocumentWorker, tuple[str, ...]]:
    """Create the notebook's failure-rich, deterministic scenario."""

    queue = AtLeastOnceQueue(visibility_timeout=4.0, max_receive_count=3)
    store = VersionedResultStore()
    requests = (
        JobRequest("op-normal", "tenant-a", "policy-1", 1, "standard underwriting policy"),
        JobRequest("op-transient", "tenant-a", "policy-2", 1, "flood coverage policy"),
        JobRequest("op-unknown", "tenant-a", "policy-3", 1, "commercial vehicle policy"),
        JobRequest("op-newer", "tenant-a", "policy-4", 2, "new policy version"),
        JobRequest("op-stale", "tenant-a", "policy-4", 1, "old policy version"),
        JobRequest("op-poison", "tenant-a", "policy-5", 1, "dependency never recovers"),
    )
    message_ids = tuple(queue.send(request) for request in requests)
    queue.inject_duplicate(message_ids[0])
    worker = DocumentWorker(
        queue,
        store,
        DeterministicAnalyzer(
            transient_failures={"op-transient": 1},
            always_throttle=frozenset({"op-poison"}),
        ),
        retry_delay=2.0,
        unknown_outcome_once=frozenset({"op-unknown"}),
    )
    return worker, message_ids
