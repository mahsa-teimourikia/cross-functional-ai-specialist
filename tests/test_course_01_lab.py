from __future__ import annotations

import pytest
from lab import (
    SAMPLE_DOCUMENTS,
    AskPayload,
    DependencyTimeout,
    DeterministicGroundedGenerator,
    EvaluationCase,
    InMemoryAuthorizedRetriever,
    InvalidCitationGenerator,
    InvalidGeneratedResult,
    TerminalState,
    TrustedPrincipal,
    UnderwritingAssistant,
    evaluate,
)
from pydantic import ValidationError


@pytest.fixture
def underwriter() -> TrustedPrincipal:
    return TrustedPrincipal("user-7", "northstar", frozenset({"underwriter"}))


@pytest.fixture
def senior() -> TrustedPrincipal:
    return TrustedPrincipal("user-9", "northstar", frozenset({"senior-underwriter"}))


def test_boundary_schema_rejects_identity_claims_and_coercion() -> None:
    with pytest.raises(ValidationError):
        AskPayload.model_validate(
            {"question": "What is the debt ratio?", "top_k": "3", "user_groups": ["admin"]}
        )


@pytest.mark.asyncio
async def test_authorization_happens_before_ranking(underwriter: TrustedPrincipal) -> None:
    retriever = InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS)
    await retriever.retrieve("executive debt exception", underwriter, 3)

    assert "uw-202" not in retriever.last_ranked_ids
    assert "other-tenant-1" not in retriever.last_ranked_ids


@pytest.mark.asyncio
async def test_regular_underwriter_never_receives_senior_evidence(
    underwriter: TrustedPrincipal,
) -> None:
    assistant = UnderwritingAssistant(
        InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS), DeterministicGroundedGenerator()
    )
    result = await assistant.answer(
        "req-1", AskPayload(question="What is the executive exception process?"), underwriter
    )

    assert "uw-202" not in result.authorized_evidence_ids
    assert set(result.citation_ids) <= set(result.authorized_evidence_ids)


@pytest.mark.asyncio
async def test_senior_receives_cited_authorized_evidence(senior: TrustedPrincipal) -> None:
    assistant = UnderwritingAssistant(
        InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS), DeterministicGroundedGenerator()
    )
    result = await assistant.answer(
        "req-2", AskPayload(question="What is the executive debt ratio exception?"), senior
    )

    assert result.state == TerminalState.SUCCEEDED
    assert "uw-202" in result.citation_ids
    assert any(event.reason_code == "CITATIONS_VERIFIED" for event in result.trace)


@pytest.mark.asyncio
async def test_no_evidence_fails_closed(underwriter: TrustedPrincipal) -> None:
    assistant = UnderwritingAssistant(
        InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS), DeterministicGroundedGenerator()
    )
    result = await assistant.answer(
        "req-3", AskPayload(question="What is the lunar collateral policy?"), underwriter
    )

    assert result.state == TerminalState.REFUSED
    assert result.citation_ids == ()


@pytest.mark.asyncio
async def test_schema_valid_but_forged_citation_is_rejected(senior: TrustedPrincipal) -> None:
    assistant = UnderwritingAssistant(
        InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS), InvalidCitationGenerator()
    )

    with pytest.raises(InvalidGeneratedResult) as captured:
        await assistant.answer(
            "req-4", AskPayload(question="What is the standard debt ratio?"), senior
        )
    assert captured.value.reason_code == "CITATION_OUTSIDE_AUTHORIZED_EVIDENCE"


@pytest.mark.asyncio
async def test_request_budget_is_enforced(underwriter: TrustedPrincipal) -> None:
    assistant = UnderwritingAssistant(
        InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS, delay_s=0.05),
        DeterministicGroundedGenerator(),
        timeout_s=0.005,
    )

    with pytest.raises(DependencyTimeout) as captured:
        await assistant.answer(
            "req-5", AskPayload(question="What is the standard debt ratio?"), underwriter
        )
    assert captured.value.reason_code == "REQUEST_BUDGET_EXHAUSTED"


@pytest.mark.asyncio
async def test_evaluation_uses_correct_denominators(
    underwriter: TrustedPrincipal, senior: TrustedPrincipal
) -> None:
    assistant = UnderwritingAssistant(
        InMemoryAuthorizedRetriever(SAMPLE_DOCUMENTS), DeterministicGroundedGenerator()
    )
    report = await evaluate(
        assistant,
        [
            EvaluationCase(
                "standard",
                "What is the standard debt ratio?",
                underwriter,
                TerminalState.SUCCEEDED,
                frozenset({"uw-101"}),
            ),
            EvaluationCase(
                "senior",
                "What is the executive debt ratio exception?",
                senior,
                TerminalState.SUCCEEDED,
                frozenset({"uw-202"}),
            ),
            EvaluationCase(
                "unknown",
                "What is the lunar collateral policy?",
                underwriter,
                TerminalState.REFUSED,
            ),
        ],
    )

    assert report.total == 3
    assert report.state_accuracy == 1.0
    assert report.citation_recall == 1.0
    assert report.forbidden_outcomes == 0
    assert report.cost_units_per_compliant_success > 0
