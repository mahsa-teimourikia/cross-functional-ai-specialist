"""Rebuild the canonical Course 2 notebook from reviewable cell sources."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
COURSE = ROOT / "curriculum" / "advanced" / "02-cloud-distributed-ai-systems"
TARGET = COURSE / "cloud_distributed_ai_systems.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Course 2 Lab — Resilient Cloud and Distributed AI Systems

- **Scenario:** Northstar asynchronous document analysis
- **Mode:** deterministic, credential-free virtual time
- **Expected time:** 3-4 hours plus the architecture decision record

You will cross the reliable application boundary from Course 1, then prove what happens under
duplicate delivery, throttling, an unknown write outcome, out-of-order versions, poison work, and
sustained overload.
"""
    ),
    md(
        """
## 0. Outcomes, safety, and evidence boundaries

- No AWS account, credentials, network, paid model, or real waiting is used.
- All data and service behavior are fictional and deterministic.
- The lab proves application invariants, not AWS performance or availability.
- Tenant and authorization context still come from trusted application state; an event field does
  not grant authority.
- Counts, reasons, and identifiers are observable; sensitive document content and private model
  reasoning do not belong in telemetry.

Every assertion below is part of the evaluation path.
"""
    ),
    code(
        """
# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

course_dir = Path.cwd()
if not (course_dir / "lab.py").exists():
    course_dir = Path.cwd() / "curriculum" / "advanced" / "02-cloud-distributed-ai-systems"
assert (course_dir / "lab.py").exists(), "Run from the repository or course directory"
sys.path.insert(0, str(course_dir.resolve()))

from lab import (
    AtLeastOnceQueue,
    DeterministicAnalyzer,
    DocumentWorker,
    JobRequest,
    VersionedResultStore,
    build_reference_scenario,
    run_until_idle,
    simulate_capacity,
    unsafe_synchronous_retry,
)
"""
    ),
    md(
        """
## 1. Start with the failure, not the cloud service

The original synchronous design performs a write and returns a response. If the response is lost,
the client observes a timeout—not whether the write committed. Retrying without a stable logical
operation record can repeat the external effect.

```text
client ── request ──> service ── write ──> state
client <─ X response lost
client ── retry ────> service ── write again
```
"""
    ),
    code(
        """
baseline_request = JobRequest(
    operation_id="op-sync-001",
    tenant_id="northstar",
    document_id="policy-101",
    document_version=1,
    text="standard debt ratio guidance",
)
unsafe = unsafe_synchronous_retry(baseline_request)
print(unsafe)
assert unsafe.attempts == 2
assert unsafe.external_writes == 2
"""
    ),
    md(
        """
The retry was understandable, but unsafe. “Make it asynchronous” is not yet a solution: queues can
redeliver too. We need a stable operation identity, conditional state, failure classification, and
reconciliation.
"""
    ),
    md(
        """
## 2. Separate logical operations from delivery attempts

`JobRequest.operation_id` identifies one intended business effect. `payload_digest` binds that ID
to canonical business input. The queue creates its own message ID, and every receive creates a new
attempt identity. Only the operation ID remains stable across a client retry or duplicate message.
"""
    ),
    code(
        """
same_request = JobRequest(
    "op-001", "northstar", "policy-101", 1, "standard debt ratio guidance"
)
changed_request = JobRequest(
    "op-001", "northstar", "policy-101", 1, "changed content"
)
print("same digest:", same_request.payload_digest == baseline_request.payload_digest)
print("changed digest:", changed_request.payload_digest)
assert same_request.payload_digest == baseline_request.payload_digest
assert changed_request.payload_digest != same_request.payload_digest
"""
    ),
    md(
        """
## 3. Build the durable boundary

The simulator represents an SQS-like at-least-once queue, a trusted worker, a deterministic
analyzer, and a result store that doubles as an operation ledger. Virtual time makes visibility and
retry behavior reproducible.

```text
accept → queue → bounded worker → analyzer → conditional operation/result commit
                    │                                │
                    └── retry / quarantine           └── reconcile before repeat
```
"""
    ),
    code(
        """
queue = AtLeastOnceQueue(visibility_timeout=4.0, max_receive_count=3)
message_id = queue.send(same_request)
store = VersionedResultStore()
analyzer = DeterministicAnalyzer()
worker = DocumentWorker(queue, store, analyzer)

print("message:", message_id, "operation:", same_request.operation_id)
assert message_id != same_request.operation_id
"""
    ),
    md(
        """
## 4. Happy path: transport acknowledgement follows the commit

The worker first checks the operation ledger, analyzes only new work, conditionally commits, and
then acknowledges the queue record. A crash before acknowledgement may cause redelivery; the
ledger makes that redelivery safe.
"""
    ),
    code(
        """
happy = run_until_idle(worker)
print(happy)
print(happy.events)
assert happy.result_writes == 1
assert happy.successful_operations == 1
assert happy.pending_messages == 0
assert happy.events[0].reason_code == "WRITTEN"
"""
    ),
    md(
        """
## 5. Failure injection A — duplicate delivery

A transport duplicate has a different message ID but the same operation ID and digest. The second
delivery must reconcile recorded success without calling the analyzer or writing again.
"""
    ),
    code(
        """
duplicate_queue = AtLeastOnceQueue()
first_message = duplicate_queue.send(same_request)
duplicate_queue.inject_duplicate(first_message)
duplicate_store = VersionedResultStore()
duplicate_analyzer = DeterministicAnalyzer()
duplicate_worker = DocumentWorker(duplicate_queue, duplicate_store, duplicate_analyzer)

duplicate_report = run_until_idle(duplicate_worker)
print([event.reason_code for event in duplicate_report.events])
assert duplicate_report.delivery_attempts == 2
assert duplicate_report.result_writes == 1
assert duplicate_report.reconciliation_count == 1
assert duplicate_analyzer.calls["op-001"] == 1
"""
    ),
    md(
        """
Idempotency is not “ignore every repeated key.” A repeated key with changed content is ambiguous and
must fail closed. Silently returning the old result would apply one operation's outcome to another
intent.
"""
    ),
    code(
        """
conflict_queue = AtLeastOnceQueue()
conflict_queue.send(same_request)
conflict_queue.send(changed_request)
conflict_worker = DocumentWorker(
    conflict_queue, VersionedResultStore(), DeterministicAnalyzer()
)
conflict_report = run_until_idle(conflict_worker)
print(conflict_worker.queue.dead_letters)
assert conflict_report.result_writes == 1
assert conflict_report.dead_letters == 1
assert conflict_worker.queue.dead_letters[0].reason_code == "IDEMPOTENCY_CONFLICT"
"""
    ),
    md(
        """
## 6. Failure injection B — transient and persistent throttling

The application classifies throttling as retryable but gives it a finite receive budget. One
operation recovers; a persistent failure reaches quarantine exactly at the bound. No retry policy
creates capacity—backoff only spaces demand.
"""
    ),
    code(
        """
retry_queue = AtLeastOnceQueue(max_receive_count=3)
retry_queue.send(JobRequest("op-recover", "northstar", "doc-a", 1, "recovering input"))
retry_queue.send(JobRequest("op-poison", "northstar", "doc-b", 1, "persistent input"))
retry_analyzer = DeterministicAnalyzer(
    transient_failures={"op-recover": 1},
    always_throttle=frozenset({"op-poison"}),
)
retry_worker = DocumentWorker(
    retry_queue, VersionedResultStore(), retry_analyzer, retry_delay=2.0
)
retry_report = run_until_idle(retry_worker)
for event in retry_report.events:
    print(event.attempt_id, event.reason_code)

assert retry_analyzer.calls["op-recover"] == 2
assert retry_analyzer.calls["op-poison"] == 3
assert retry_report.dead_letters == 1
assert retry_report.pending_messages == 0
"""
    ),
    md(
        """
## 7. Failure injection C — write committed, acknowledgement lost

This is the critical unknown outcome. The first attempt commits the operation and result, then the
simulator loses the acknowledgement. On redelivery, the worker reconciles authoritative state
before doing analysis or another write.
"""
    ),
    code(
        """
unknown_queue = AtLeastOnceQueue(max_receive_count=3)
unknown_queue.send(JobRequest("op-unknown", "northstar", "doc-c", 1, "uncertain write"))
unknown_store = VersionedResultStore()
unknown_analyzer = DeterministicAnalyzer()
unknown_worker = DocumentWorker(
    unknown_queue,
    unknown_store,
    unknown_analyzer,
    unknown_outcome_once=frozenset({"op-unknown"}),
)
unknown_report = run_until_idle(unknown_worker)
print([event.reason_code for event in unknown_report.events])
assert unknown_report.delivery_attempts == 2
assert unknown_report.result_writes == 1
assert unknown_analyzer.calls["op-unknown"] == 1
assert unknown_report.events[-1].reason_code == "RECONCILED_SUCCEEDED"
"""
    ),
    md(
        """
## 8. Failure injection D — out-of-order and conflicting versions

Arrival order is not business order. We deliver version 2 first, then version 1. A domain-version
condition keeps the newer projection. Different content claiming the same current version is also
terminal; worker clock time and last-writer-wins would make the answer nondeterministic.
"""
    ),
    code(
        """
version_queue = AtLeastOnceQueue()
version_queue.send(JobRequest("op-v2", "northstar", "doc-versioned", 2, "new guidance"))
version_queue.send(JobRequest("op-v1", "northstar", "doc-versioned", 1, "old guidance"))
version_store = VersionedResultStore()
version_worker = DocumentWorker(version_queue, version_store, DeterministicAnalyzer())
version_report = run_until_idle(version_worker)
latest = version_store.latest("northstar", "doc-versioned")

print([event.reason_code for event in version_report.events])
print(latest)
assert latest is not None and latest.document_version == 2
assert version_report.result_writes == 1
assert version_report.events[-1].reason_code == "STALE"
"""
    ),
    md(
        """
## 9. Integrated recovery experiment

The reference scenario mixes a normal operation, a duplicate, one transient throttle, an unknown
write outcome, a newer event followed by a stale event, and a persistent throttle. Evaluate unique
business outcomes separately from delivery attempts.
"""
    ),
    code(
        """
reference_worker, submitted_message_ids = build_reference_scenario()
reference_report = run_until_idle(reference_worker)

print("submitted messages before injected duplicate:", len(submitted_message_ids))
print("delivery attempts:", reference_report.delivery_attempts)
print("successful logical operations:", reference_report.successful_operations)
print("result writes:", reference_report.result_writes)
print("reconciliations:", reference_report.reconciliation_count)
print("dead letters:", reference_report.dead_letters)
print("work amplification:", round(reference_report.work_amplification, 2))
for event in reference_report.events:
    print(event.operation_id, event.receive_count, event.reason_code)

assert reference_report.pending_messages == 0
assert reference_report.successful_operations == 4
assert reference_report.result_writes == 4
assert reference_report.reconciliation_count == 2
assert reference_report.dead_letters == 1
"""
    ),
    md(
        """
`delivery_attempts / successful_operations` is a provider-neutral work-amplification proxy. It is
not currency. In production, add compute duration, model tokens, storage, data transfer, telemetry,
idle reservation, and operational labor, then divide by successful **compliant** operations.
"""
    ),
    md(
        """
## 10. Capacity experiment — stable versus overloaded

The virtual capacity model admits arrivals, completes at most a fixed number per tick, and records
backlog and queue wait. It intentionally avoids randomness so the overload invariant is reviewable.
"""
    ),
    code(
        """
stable = simulate_capacity([3] * 10, capacity_per_tick=4)
overloaded = simulate_capacity([5] * 10, capacity_per_tick=4)

print("stable:", stable)
print("overloaded:", overloaded)
assert stable.final_backlog == 0
assert overloaded.final_backlog == 10
assert overloaded.maximum_backlog == 10
assert overloaded.utilization == 1.0
assert overloaded.little_law_wait_estimate > stable.little_law_wait_estimate
"""
    ),
    md(
        """
This experiment proves that sustained arrival above capacity grows backlog. It does **not** predict
Lambda concurrency, SQS latency, model throughput, or cloud cost. A production load test needs a
representative payload mix, warm/cold behavior, downstream quotas, error injection, tail latency,
queue age, and an explicit stop condition.
"""
    ),
    md(
        """
## 11. Architecture decision exercise

Write an ADR for Northstar. Start from requirements, not products:

1. define acceptance and terminal-state APIs;
2. quantify arrival distribution, item duration/size, completion SLO, retention, RPO, and RTO;
3. compare synchronous, SQS + Lambda, SQS + ECS/Fargate, and Step Functions options;
4. choose the authoritative operation ledger and versioned projection;
5. name retry ownership, concurrency limits, DLQ/redrive, reconciliation, and rollback;
6. preserve trusted tenant/authorization context and least privilege at the worker;
7. define queue-age, completion, saturation, amplification, failure, and cost evidence.

Reject at least two credible alternatives and state what evidence would reverse the decision.
"""
    ),
    md(
        """
## 12. Production gap analysis

The local lab deliberately omits provider and organizational mechanics. Before deployment add:

- authenticated acceptance and worker-side authorization revalidation;
- durable conditional writes, retention/TTL, backup, restore, and regional recovery;
- exponential backoff with jitter, lease extension/heartbeat, cancellation, and graceful shutdown;
- partial batch failure, poison-message controls, DLQ alarms, repair, and rate-limited redrive;
- event schemas, compatibility rules, outbox/inbox or reconciliation for dual writes;
- encryption, secret handling, network/egress control, tenant-safe cache keys, and data
  minimization;
- traces linking operation/message/attempt IDs without logging document content;
- production load, chaos/failure, restore, and rollback evidence.

The trusted application owns policy and side-effect validation. A model response, event payload, or
workflow name never grants authorization.
"""
    ),
    md(
        """
## 13. Final evidence checklist

- [x] Unsafe synchronous retry duplicated a side effect.
- [x] Duplicate delivery produced one result write.
- [x] Changed input under the same operation ID was quarantined.
- [x] Transient retry recovered; persistent retry reached a bounded DLQ state.
- [x] Unknown outcome reconciled without repeat analysis or write.
- [x] Stale state could not overwrite a newer version.
- [x] Overload produced measurable backlog and queue wait.
- [ ] Your ADR records service selection, failure model, cost/operability, migration, and rollback.
- [ ] Your production plan names owners, SLOs, alarms, recovery, and validation evidence.

Complete the Course 2 checkpoint after defending your ADR to a reviewer.
"""
    ),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.11"},
    },
)
TARGET.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, TARGET)
print(f"Wrote {TARGET.relative_to(ROOT)} with {len(cells)} cells")
