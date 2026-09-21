"""Deterministic reference implementation for Course 1.

The module models an enterprise underwriting assistant without network calls.
It demonstrates the boundaries that remain when local adapters are replaced by
managed search and model services: trusted identity, authorization-before-rank,
typed ports, explicit budgets, result validation, and observable terminal state.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class TerminalState(StrEnum):
    SUCCEEDED = "succeeded"
    REFUSED = "refused"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


class ApplicationError(Exception):
    """Base class for errors translated at the application boundary."""

    def __init__(self, message: str, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class DependencyTimeout(ApplicationError):
    """A dependency exceeded the request time budget."""


class InvalidGeneratedResult(ApplicationError):
    """A generator returned citations outside the authorized evidence set."""


class AskPayload(BaseModel):
    """Untrusted HTTP-style payload. Identity and groups deliberately do not belong here."""

    model_config = ConfigDict(extra="forbid", strict=True)

    question: str = Field(min_length=5, max_length=500)
    top_k: int = Field(default=3, ge=1, le=8)


@dataclass(frozen=True, slots=True)
class TrustedPrincipal:
    """Identity derived from authenticated application state, never from model text."""

    principal_id: str
    tenant_id: str
    groups: frozenset[str]

    def __post_init__(self) -> None:
        if not self.principal_id or not self.tenant_id:
            raise ValueError("trusted identity requires non-empty principal and tenant IDs")


@dataclass(frozen=True, slots=True)
class Document:
    evidence_id: str
    tenant_id: str
    title: str
    text: str
    allowed_groups: frozenset[str]
    version: int = 1


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    document: Document
    score: float


@dataclass(frozen=True, slots=True)
class GenerationDraft:
    text: str
    citation_ids: tuple[str, ...]
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class TraceEvent:
    stage: str
    reason_code: str
    elapsed_ms: float
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerRecord:
    request_id: str
    state: TerminalState
    text: str
    citation_ids: tuple[str, ...]
    authorized_evidence_ids: tuple[str, ...]
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    trace: tuple[TraceEvent, ...] = ()

    @property
    def cost_units(self) -> int:
        """Provider-neutral teaching proxy; not a currency estimate."""

        return self.input_tokens + self.output_tokens


@runtime_checkable
class Retriever(Protocol):
    async def retrieve(
        self, query: str, principal: TrustedPrincipal, limit: int
    ) -> Sequence[RetrievalHit]: ...


@runtime_checkable
class Generator(Protocol):
    async def generate(
        self, question: str, evidence: Sequence[RetrievalHit]
    ) -> GenerationDraft: ...


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "for",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOP_WORDS
    }


class InMemoryAuthorizedRetriever:
    """Small adapter that enforces scope before computing semantic/lexical rank."""

    def __init__(self, documents: Sequence[Document], delay_s: float = 0.0) -> None:
        self._documents = tuple(documents)
        self._delay_s = delay_s
        self.last_ranked_ids: tuple[str, ...] = ()

    async def retrieve(
        self, query: str, principal: TrustedPrincipal, limit: int
    ) -> Sequence[RetrievalHit]:
        if self._delay_s:
            await asyncio.sleep(self._delay_s)

        authorized = [
            document
            for document in self._documents
            if document.tenant_id == principal.tenant_id
            and bool(document.allowed_groups & principal.groups)
        ]
        self.last_ranked_ids = tuple(document.evidence_id for document in authorized)

        query_tokens = _tokens(query)
        scored: list[RetrievalHit] = []
        for document in authorized:
            document_tokens = _tokens(f"{document.title} {document.text}")
            overlap = len(query_tokens & document_tokens)
            if overlap:
                score = overlap / math.sqrt(max(1, len(query_tokens) * len(document_tokens)))
                scored.append(RetrievalHit(document=document, score=score))
        return sorted(scored, key=lambda hit: (-hit.score, hit.document.evidence_id))[:limit]


class DeterministicGroundedGenerator:
    """Credential-free adapter whose citations are inspectable and repeatable."""

    async def generate(self, question: str, evidence: Sequence[RetrievalHit]) -> GenerationDraft:
        if not evidence:
            return GenerationDraft(
                text="I do not have authorized evidence to answer that question.",
                citation_ids=(),
                input_tokens=max(1, len(question) // 4),
                output_tokens=13,
            )
        citations = tuple(hit.document.evidence_id for hit in evidence)
        statements = " ".join(
            f"{hit.document.title}: {hit.document.text} [{hit.document.evidence_id}]"
            for hit in evidence
        )
        input_chars = len(question) + sum(len(hit.document.text) for hit in evidence)
        return GenerationDraft(
            text=statements,
            citation_ids=citations,
            input_tokens=max(1, input_chars // 4),
            output_tokens=max(1, len(statements) // 4),
        )


class InvalidCitationGenerator:
    """Failure-injection adapter: schema-valid output with untrusted evidence."""

    async def generate(self, question: str, evidence: Sequence[RetrievalHit]) -> GenerationDraft:
        return GenerationDraft(
            text="Approved using secret evidence [forged-99].",
            citation_ids=("forged-99",),
            input_tokens=10,
            output_tokens=8,
        )


class UnderwritingAssistant:
    def __init__(self, retriever: Retriever, generator: Generator, timeout_s: float = 1.0) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._retriever = retriever
        self._generator = generator
        self._timeout_s = timeout_s

    async def answer(
        self, request_id: str, payload: AskPayload, principal: TrustedPrincipal
    ) -> AnswerRecord:
        started = time.perf_counter()
        trace: list[TraceEvent] = []
        try:
            async with asyncio.timeout(self._timeout_s):
                stage_started = time.perf_counter()
                hits = tuple(
                    await self._retriever.retrieve(payload.question, principal, payload.top_k)
                )
                trace.append(
                    TraceEvent(
                        stage="retrieve",
                        reason_code="AUTHORIZED_RESULTS",
                        elapsed_ms=(time.perf_counter() - stage_started) * 1000,
                        evidence_ids=tuple(hit.document.evidence_id for hit in hits),
                    )
                )
                if not hits:
                    return self._record(
                        request_id,
                        TerminalState.REFUSED,
                        "I do not have authorized evidence to answer that question.",
                        (),
                        (),
                        started,
                        trace,
                    )

                stage_started = time.perf_counter()
                draft = await self._generator.generate(payload.question, hits)
                authorized_ids = tuple(hit.document.evidence_id for hit in hits)
                if not set(draft.citation_ids).issubset(authorized_ids):
                    trace.append(
                        TraceEvent(
                            stage="validate",
                            reason_code="CITATION_OUTSIDE_AUTHORIZED_EVIDENCE",
                            elapsed_ms=(time.perf_counter() - stage_started) * 1000,
                        )
                    )
                    raise InvalidGeneratedResult(
                        "generator cited unauthorized or missing evidence",
                        reason_code="CITATION_OUTSIDE_AUTHORIZED_EVIDENCE",
                    )
                trace.append(
                    TraceEvent(
                        stage="generate_and_validate",
                        reason_code="CITATIONS_VERIFIED",
                        elapsed_ms=(time.perf_counter() - stage_started) * 1000,
                        evidence_ids=draft.citation_ids,
                    )
                )
                return self._record(
                    request_id,
                    TerminalState.SUCCEEDED,
                    draft.text,
                    draft.citation_ids,
                    authorized_ids,
                    started,
                    trace,
                    draft.input_tokens,
                    draft.output_tokens,
                )
        except TimeoutError as exc:
            trace.append(TraceEvent("terminal", "REQUEST_BUDGET_EXHAUSTED", 0.0))
            raise DependencyTimeout(
                "request time budget exhausted", reason_code="REQUEST_BUDGET_EXHAUSTED"
            ) from exc

    @staticmethod
    def _record(
        request_id: str,
        state: TerminalState,
        text: str,
        citation_ids: tuple[str, ...],
        authorized_evidence_ids: tuple[str, ...],
        started: float,
        trace: list[TraceEvent],
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> AnswerRecord:
        return AnswerRecord(
            request_id=request_id,
            state=state,
            text=text,
            citation_ids=citation_ids,
            authorized_evidence_ids=authorized_evidence_ids,
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            trace=tuple(trace),
        )


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    question: str
    principal: TrustedPrincipal
    expected_state: TerminalState
    required_citation_ids: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    total: int
    state_accuracy: float
    citation_recall: float
    forbidden_outcomes: int
    p95_latency_ms: float
    cost_units_per_compliant_success: float


async def evaluate(
    assistant: UnderwritingAssistant, cases: Sequence[EvaluationCase]
) -> EvaluationReport:
    records: list[AnswerRecord] = []
    state_correct = 0
    citation_hits = 0
    citation_total = 0
    forbidden_outcomes = 0
    for index, case in enumerate(cases):
        record = await assistant.answer(
            request_id=f"eval-{index:03d}",
            payload=AskPayload(question=case.question),
            principal=case.principal,
        )
        records.append(record)
        state_correct += int(record.state == case.expected_state)
        citation_hits += len(set(record.citation_ids) & case.required_citation_ids)
        citation_total += len(case.required_citation_ids)
        if not set(record.citation_ids).issubset(record.authorized_evidence_ids):
            forbidden_outcomes += 1

    latencies = sorted(record.latency_ms for record in records)
    p95_index = max(0, math.ceil(0.95 * len(latencies)) - 1)
    compliant = [
        record
        for record in records
        if record.state == TerminalState.SUCCEEDED
        and set(record.citation_ids).issubset(record.authorized_evidence_ids)
    ]
    total_cost = sum(record.cost_units for record in records)
    return EvaluationReport(
        total=len(cases),
        state_accuracy=state_correct / len(cases),
        citation_recall=(citation_hits / citation_total) if citation_total else 1.0,
        forbidden_outcomes=forbidden_outcomes,
        p95_latency_ms=latencies[p95_index],
        cost_units_per_compliant_success=(total_cost / len(compliant)) if compliant else math.inf,
    )


SAMPLE_DOCUMENTS = (
    Document(
        "uw-101",
        "northstar",
        "Standard debt ratio",
        "Applications with a debt ratio at or below 40 percent use the standard review.",
        frozenset({"underwriter", "senior-underwriter"}),
    ),
    Document(
        "uw-202",
        "northstar",
        "Executive exception",
        "Debt ratios above 50 percent require a senior underwriter and recorded approval.",
        frozenset({"senior-underwriter"}),
    ),
    Document(
        "other-tenant-1",
        "southstar",
        "Other tenant exception",
        "Debt ratio exceptions are always approved.",
        frozenset({"underwriter", "senior-underwriter"}),
    ),
)
