"""Rebuild the canonical Course 1 notebook from reviewable cell sources."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
COURSE = ROOT / "curriculum" / "advanced" / "01-production-ai-development"
TARGET = COURSE / "production_ai_development.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Course 1 Lab — From AI Prototype to Production Application Core

**Scenario:** Northstar Underwriting Guideline Assistant
**Mode:** deterministic and credential-free
**Expected time:** 3-4 hours plus portfolio exercises

This notebook teaches application boundaries. The retriever and generator are deliberately small
so you can observe authorization, result validation, budgets, traces, metrics, and failure behavior
without confusing provider variability with software correctness.
"""
    ),
    md(
        """
## 0. Outcomes, safety boundaries, and reproducibility

You will compare an unsafe baseline with a typed application service, inspect trusted identity and
authorization-before-rank, inject timeout and forged-citation failures, and evaluate the system.

- No network or cloud calls occur.
- The example data is fictional.
- Local deterministic output is **not** evidence of live-model quality.
- Identity comes from a trusted fixture standing in for authentication middleware—not the request.
- Observable traces expose decisions and reason codes, never private model reasoning.

Run from the repository root with `uv run jupyter execute ... --inplace`, or interactively with the
uv-managed kernel. Every assertion is part of the lesson.
"""
    ),
    code(
        """
# ruff: noqa: E402,I001
from __future__ import annotations

import sys
from pathlib import Path

course_dir = Path.cwd()
if not (course_dir / "lab.py").exists():
    course_dir = (
        Path.cwd() / "curriculum" / "advanced" / "01-production-ai-development"
    )
assert (course_dir / "lab.py").exists(), "Run from the repository or course directory"
sys.path.insert(0, str(course_dir.resolve()))

from pydantic import ValidationError

from lab import (
    AskPayload,
    DependencyTimeout,
    DeterministicGroundedGenerator,
    EvaluationCase,
    InMemoryAuthorizedRetriever,
    InvalidCitationGenerator,
    InvalidGeneratedResult,
    SAMPLE_DOCUMENTS,
    TerminalState,
    TrustedPrincipal,
    UnderwritingAssistant,
    evaluate,
)
"""
    ),
    md(
        """
## 1. Architecture before code

```text
untrusted payload ──> strict boundary model ─┐
                                             ├─> application service
authenticated state ──> trusted principal ──┘          │
                                                       ├─> authorized retriever
                                                       └─> generator
                                                               │
                                   trusted result validator <──┘
                                               │
                                answer / refusal / typed failure
```

The model or retriever proposes data. The application establishes identity, filters scope, verifies
evidence, owns the deadline, and determines completion.
"""
    ),
    md(
        """
## 2. Start with the failure-prone prototype

The baseline below resembles a notebook demo: it ranks all text, accepts group labels as ordinary
arguments, and concatenates results. It has no tenant boundary, evidence validation, deadline,
terminal state, or trace. We keep it local and deterministic so the unsafe behavior is visible.
"""
    ),
    code(
        """
import re


def unsafe_prototype(question: str, claimed_groups: set[str]) -> tuple[str, tuple[str, ...]]:
    query_terms = set(re.findall(r"[a-z0-9]+", question.lower()))
    # Anti-pattern: score every tenant and restricted document before a late group check.
    ranked = sorted(
        SAMPLE_DOCUMENTS,
        key=lambda doc: -len(query_terms & set(re.findall(r"[a-z0-9]+", doc.text.lower()))),
    )
    visible = [doc for doc in ranked if doc.allowed_groups & claimed_groups]
    return " ".join(doc.text for doc in visible[:2]), tuple(doc.evidence_id for doc in ranked)


baseline_answer, baseline_ranked_ids = unsafe_prototype(
    "What is the executive debt ratio exception?", {"senior-underwriter"}
)
print("Claimed-role answer:", baseline_answer)
print("Every document ranked before filtering:", baseline_ranked_ids)
assert "other-tenant-1" in baseline_ranked_ids
"""
    ),
    md(
        """
The caller self-assigned a senior group, and another tenant's document entered ranking. Even if the
last response omitted that document, scores, timing, logs, or caches could reveal it. “Filter later”
is not an authorization design.
"""
    ),
    md(
        """
## 3. Make the untrusted boundary narrow and strict

`AskPayload` accepts only the question and a bounded `top_k`. It forbids extra fields and implicit
coercion. This prevents accidental identity plumbing through the body; authentication middleware
would create `TrustedPrincipal` separately.
"""
    ),
    code(
        """
payload = AskPayload(question="What is the standard debt ratio?", top_k=3)
print(payload)

try:
    AskPayload.model_validate(
        {
            "question": "What is the executive exception?",
            "top_k": "3",
            "user_groups": ["senior-underwriter"],
        }
    )
except ValidationError as error:
    print("Rejected as designed:", error.errors())
else:
    raise AssertionError("Untrusted identity/coercion should not pass")
"""
    ),
    md(
        """
Strict schema validation is useful but not magical. If `user_groups` were intentionally added to
the schema, Pydantic would validate its shape—not whether an identity provider granted those groups.
"""
    ),
    md(
        """
## 4. Compose the application from explicit ports

The application depends on `Retriever` and `Generator` Protocols. Local adapters make invariants
fast and repeatable. In production, provider adapters would implement the same contracts while
owning SDK translation, client reuse, provider errors, and telemetry.
"""
    ),
    code(
        """
regular = TrustedPrincipal("user-7", "northstar", frozenset({"underwriter"}))
senior = TrustedPrincipal("user-9", "northstar", frozenset({"senior-underwriter"}))

retriever = InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS)
assistant = UnderwritingAssistant(
    retriever=retriever,
    generator=DeterministicGroundedGenerator(),
    timeout_s=1.0,
)
"""
    ),
    md(
        """
## 5. Run the happy path and inspect observable state

Do not stop at answer text. Inspect evidence, terminal state, trace stages, reason codes, token
proxy, and latency. These are the externally useful facts for debugging and evaluation.
"""
    ),
    code(
        """
record = await assistant.answer(
    request_id="demo-001",
    payload=AskPayload(question="What is the standard debt ratio?"),
    principal=regular,
)
print("state:", record.state)
print("answer:", record.text)
print("citations:", record.citation_ids)
print("authorized evidence:", record.authorized_evidence_ids)
print("trace:")
for event in record.trace:
    print(" ", event)

assert record.state == TerminalState.SUCCEEDED
assert set(record.citation_ids) <= set(record.authorized_evidence_ids)
"""
    ),
    md(
        """
## 6. Experiment A — authorization changes retrieval, not just final formatting

Run the same exception question for two principals. The regular underwriter must not rank `uw-202`;
the senior underwriter may retrieve and cite it. Another tenant must never enter either ranked set.
"""
    ),
    code(
        """
question = AskPayload(question="What is the executive debt ratio exception?")

regular_result = await assistant.answer("demo-regular", question, regular)
regular_ranked = retriever.last_ranked_ids

senior_result = await assistant.answer("demo-senior", question, senior)
senior_ranked = retriever.last_ranked_ids

print("regular:", regular_result.state, regular_result.citation_ids, regular_ranked)
print("senior:", senior_result.state, senior_result.citation_ids, senior_ranked)

assert "uw-202" not in regular_ranked
assert "uw-202" in senior_ranked
assert "other-tenant-1" not in regular_ranked
assert "other-tenant-1" not in senior_ranked
"""
    ),
    md(
        """
The regular result may still answer from general guidance when lexical terms overlap. That is a
product/evaluation question: should restricted intent force refusal instead? Add an intent/policy
rule only if requirements and labelled cases justify it; do not hide the ambiguity in a prompt.
"""
    ),
    md(
        """
## 7. Experiment B — no evidence produces a refusal

Absence of authorized evidence is an application-owned terminal condition. Calling a model anyway
would invite unsupported output and unnecessary cost.
"""
    ),
    code(
        """
no_evidence = await assistant.answer(
    "demo-none",
    AskPayload(question="What is the lunar collateral policy?"),
    regular,
)
print(no_evidence)
assert no_evidence.state == TerminalState.REFUSED
assert no_evidence.citation_ids == ()
assert no_evidence.cost_units == 0
"""
    ),
    md(
        """
## 8. Failure injection A — enforce the end-to-end deadline

The delayed retriever exceeds the shared operation budget. The expected result is a typed timeout,
not an invented answer, silent infinite retry, or “success” string.
"""
    ),
    code(
        """
slow_assistant = UnderwritingAssistant(
    InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS, delay_s=0.05),
    DeterministicGroundedGenerator(),
    timeout_s=0.005,
)

try:
    await slow_assistant.answer(
        "demo-timeout",
        AskPayload(question="What is the standard debt ratio?"),
        regular,
    )
except DependencyTimeout as error:
    print("Expected timeout:", error.reason_code, error)
else:
    raise AssertionError("The deadline should terminate the request")
"""
    ),
    md(
        """
Production design question: translate this to a stable API error and telemetry reason code. Retry
only when the dependency failure is transient, within the caller deadline, and the operation is
safe. A later course adds stable logical operation IDs and unknown-outcome reconciliation.
"""
    ),
    md(
        """
## 9. Failure injection B — reject schema-valid but forged evidence

Structured output can have the correct fields and still be untrusted. This adapter cites an ID that
was never retrieved. The application must reject it after generation.
"""
    ),
    code(
        """
forging_assistant = UnderwritingAssistant(
    InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS),
    InvalidCitationGenerator(),
)

try:
    await forging_assistant.answer(
        "demo-forgery",
        AskPayload(question="What is the standard debt ratio?"),
        senior,
    )
except InvalidGeneratedResult as error:
    print("Expected validation failure:", error.reason_code, error)
else:
    raise AssertionError("A forged citation must not become a successful answer")
"""
    ),
    md(
        """
## 10. Evaluate representative positive, refusal, and scope cases

Define the population before the metric. State accuracy uses all cases. Citation recall uses all
required evidence IDs. Forbidden outcomes count citations outside each record's authorized set.
The cost proxy sums all work—including refusals—and divides by compliant successes.
"""
    ),
    code(
        """
cases = [
    EvaluationCase(
        "standard-regular",
        "What is the standard debt ratio?",
        regular,
        TerminalState.SUCCEEDED,
        frozenset({"uw-101"}),
    ),
    EvaluationCase(
        "exception-senior",
        "What is the executive debt ratio exception?",
        senior,
        TerminalState.SUCCEEDED,
        frozenset({"uw-202"}),
    ),
    EvaluationCase(
        "unknown-regular",
        "What is the lunar collateral policy?",
        regular,
        TerminalState.REFUSED,
    ),
]

report = await evaluate(assistant, cases)
print(report)
assert report.state_accuracy == 1.0
assert report.citation_recall == 1.0
assert report.forbidden_outcomes == 0
"""
    ),
    md(
        """
Interpretation: these assertions prove the small labelled fixtures behaved as expected. They do not
prove production quality, capacity, fairness, source truth, or live-model reliability. Expand cases,
slices, human labels, load conditions, and provider runs before a release decision.
"""
    ),
    md(
        """
## 11. Baseline comparison

| Property | Unsafe prototype | Application core |
|---|---|---|
| Identity | caller-claimed groups | trusted principal supplied separately |
| Authorization | after global ranking; no tenant | tenant/group before ranking |
| Evidence | concatenated text | stable IDs, versioned document records |
| Generation | output trusted | citations checked against authorized results |
| Failure | implicit | refusal or typed exception |
| Budget | none | operation deadline |
| Tests | output example | positive, negative, boundary, and injected failures |
| Telemetry | print/answer | reason-coded trace and terminal record |

The layered version is more code. Its value is not “cleanliness”; it makes critical policies
explicit, independently testable, and replaceable. For a disposable local analysis, the extra
architecture may not be justified.
"""
    ),
    md(
        """
## 12. Production upgrade decisions

| Local artifact | Production decision |
|---|---|
| principal fixture | validate issuer/audience/signature; map claims; workload/user delegation |
| memory documents | index lifecycle, provenance, ACL consistency, freshness and deletion |
| keyword score | sparse/dense/hybrid baseline plus labelled retrieval evaluation |
| deterministic generator | provider adapter, model evaluation, rate limits, safety and residency |
| local timeout | downstream budgets, cancellation propagation, retry and circuit-breaker policy |
| trace tuple | OpenTelemetry correlation, sampling, privacy, retention and backend |
| token proxy | provider usage, currency rates, retry/cache allocation, cost per compliant success |

Do not upgrade all components at once. Preserve the application invariants while replacing one
adapter, add integration/evaluation evidence, then decide whether the added infrastructure earns its
operating cost.
"""
    ),
    md(
        """
## 13. Exercises

1. Add another-tenant and empty-group cases. Prove those document IDs never enter ranking.
2. Add a `Generator` that returns an empty citation list with fluent text. Decide whether to refuse
   or reject, implement the policy, and test it.
3. Add six cases and one new metric. Document population, numerator, denominator, unit, direction,
   slice, and release interpretation before coding it.
4. Write the HTTP error translation for validation, timeout, invalid result, and unexpected internal
   failure. Specify what the client sees and what telemetry records.
5. Package the core under `src/`, build a wheel, install it in a clean environment, and prove tests
   import the installed artifact.
6. Write a one-page ADR comparing uv, Poetry, PDM, and pip-tools for this deployed application.
7. Review the source as if approving a production PR. Identify what is intentionally educational,
   what is production-ready, and what blocks deployment.
"""
    ),
    md(
        """
## 14. Summary

- The application—not the model—owns identity, authorization, evidence validation, budgets, and
  terminal state.
- Pydantic and type checkers enforce contracts, not truth or authority.
- Ports isolate meaningful volatility; adapters contain provider mechanics.
- Async requires deadline, cancellation, and blocking-I/O discipline.
- Deterministic tests and AI evaluation answer different questions.
- Metrics need explicit populations and denominators.
- Architecture should be the smallest design that makes required invariants enforceable.

Continue with the focused checkpoint and portfolio exercises in the course chapter.
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
nbf.write(notebook, TARGET)
print(f"Wrote {TARGET.relative_to(ROOT)} with {len(cells)} cells")
