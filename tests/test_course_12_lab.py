from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "curriculum/advanced/12-enterprise-ai-operating-model-leadership/lab.py"
    )
    spec = importlib.util.spec_from_file_location("course_12_lab", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lab = _load()
TRUSTED = frozenset({"portfolio-evidence-office"})


def _candidate(candidate_id: str = "poc-01") -> Any:
    return next(item for item in lab.demo_candidates() if item.candidate_id == candidate_id)


def _assessment(candidate: Any | None = None, evidence: Any | None = None) -> Any:
    item = _candidate() if candidate is None else candidate
    proof = lab.demo_evidence((item,)) if evidence is None else evidence
    return lab.assess_candidate(item, proof, trusted_producers=TRUSTED, now=1_300)


def test_demo_contains_seventy_candidates() -> None:
    assert len(lab.demo_candidates()) == 70


def test_eligible_candidate_is_funded() -> None:
    assessment = _assessment()
    assert assessment.disposition is lab.PortfolioDisposition.FUND
    assert assessment.score is not None and assessment.score > 0


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("owner", "", "missing-owner"),
        ("sponsor", "", "missing-sponsor"),
        ("outcome", "", "missing-outcome"),
        ("risk_tier", lab.RiskTier.PROHIBITED, "prohibited-use"),
        ("annual_cost", 0.0, "invalid-resource-request"),
        ("team_capacity", 0, "invalid-resource-request"),
    ],
)
def test_hard_portfolio_gates_stop_candidate(field: str, value: object, reason: str) -> None:
    candidate = replace(_candidate(), **{field: value})
    assessment = _assessment(candidate)
    assert assessment.disposition is lab.PortfolioDisposition.STOP
    assert reason in assessment.reasons


def test_unapproved_sensitive_data_stops_moderate_risk() -> None:
    candidate = replace(_candidate(), risk_tier=lab.RiskTier.MODERATE, data_approved=False)
    assert "unapproved-data" in _assessment(candidate).reasons


def test_missing_evidence_refers_instead_of_inventing_zero() -> None:
    proof = tuple(
        item for item in lab.demo_evidence((_candidate(),)) if item.metric != "feasibility"
    )
    assessment = _assessment(evidence=proof)
    assert assessment.disposition is lab.PortfolioDisposition.REFER
    assert "missing-evidence:feasibility" in assessment.reasons


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("producer", "vendor-sales", "untrusted-evidence:annual-value"),
        ("expires_at", 1_200, "stale-evidence:annual-value"),
        ("unit", "percent", "unit-mismatch:annual-value"),
    ],
)
def test_evidence_contract_fails_closed(field: str, value: object, reason: str) -> None:
    proof = list(lab.demo_evidence((_candidate(),)))
    index = next(i for i, item in enumerate(proof) if item.metric == "annual-value")
    proof[index] = replace(proof[index], **{field: value})
    assert reason in _assessment(evidence=proof).reasons


def test_outcome_confidence_requires_independence() -> None:
    proof = tuple(
        replace(item, independent=False) if item.metric == "outcome-confidence" else item
        for item in lab.demo_evidence((_candidate(),))
    )
    assert "independent-evidence-required:outcome-confidence" in _assessment(evidence=proof).reasons


def test_evidence_for_another_version_is_not_reused() -> None:
    proof = tuple(
        replace(item, candidate_version="v2") for item in lab.demo_evidence((_candidate(),))
    )
    assert "missing-evidence:annual-value" in _assessment(evidence=proof).reasons


def test_duplicate_evidence_is_referred() -> None:
    proof = lab.demo_evidence((_candidate(),))
    assessment = _assessment(evidence=(*proof, proof[0]))
    assert "duplicate-evidence:annual-value" in assessment.reasons


def test_value_claim_must_match_evidence() -> None:
    candidate = replace(_candidate(), expected_annual_value=999_999.0)
    proof = lab.demo_evidence((_candidate(),))
    assert "value-evidence-mismatch" in _assessment(candidate, proof).reasons


def test_low_confidence_creates_bounded_experiment() -> None:
    candidate = replace(_candidate(), feasibility=0.5)
    proof = list(lab.demo_evidence((candidate,)))
    result = _assessment(candidate, proof)
    assert result.disposition is lab.PortfolioDisposition.EXPERIMENT


def test_selection_obeys_budget_and_capacity() -> None:
    candidates = lab.demo_candidates(12)
    evidence = lab.demo_evidence(candidates)
    assessments = tuple(
        lab.assess_candidate(item, evidence, trusted_producers=TRUSTED, now=1_300)
        for item in candidates
    )
    selection = lab.select_portfolio(candidates, assessments, budget=500_000, capacity=8)
    assert selection.annual_cost <= 500_000
    assert selection.team_capacity <= 8


def test_selection_does_not_reward_sunk_cost() -> None:
    candidate = _candidate()
    assessment = _assessment()
    high = replace(candidate, candidate_id="poc-high-sunk", sunk_cost=10_000_000)
    high_assessment = replace(assessment, candidate_id=high.candidate_id)
    first = lab.select_portfolio(
        (candidate, high), (assessment, high_assessment), budget=1_000_000, capacity=10
    )
    low = replace(high, sunk_cost=0)
    second = lab.select_portfolio(
        (candidate, low), (assessment, high_assessment), budget=1_000_000, capacity=10
    )
    assert first.funded == second.funded


def test_duplicate_capability_is_not_double_funded() -> None:
    first = replace(_candidate(), duplicate_group="same")
    second = replace(first, candidate_id="poc-duplicate")
    first_result = _assessment(first)
    second_result = replace(first_result, candidate_id=second.candidate_id)
    selection = lab.select_portfolio(
        (first, second), (first_result, second_result), budget=1_000_000, capacity=20
    )
    assert len(selection.funded) == 1
    assert "duplicate-capability" in selection.reasons.values()


def test_unfunded_dependency_holds_candidate() -> None:
    candidate = replace(_candidate(), dependencies=("not-present",))
    assessment = _assessment(candidate)
    selection = lab.select_portfolio((candidate,), (assessment,), budget=1_000_000, capacity=20)
    assert selection.held == (candidate.candidate_id,)
    assert selection.reasons[candidate.candidate_id] == "dependency-not-funded"


def test_selection_requires_complete_assessments() -> None:
    with pytest.raises(ValueError, match="every candidate"):
        lab.select_portfolio((_candidate(),), (), budget=1, capacity=1)


def test_risk_maps_to_proportionate_controls() -> None:
    assert lab.control_profile(lab.RiskTier.LOW).mode is lab.ControlMode.SELF_SERVICE
    assert lab.control_profile(lab.RiskTier.HIGH).independent_review
    assert lab.control_profile(lab.RiskTier.PROHIBITED).mode is lab.ControlMode.PROHIBITED


def _exception_request() -> Any:
    return lab.ExceptionRequest(
        "request-1",
        "requester",
        "poc-01",
        "v1",
        "policy-7",
        "logging",
        "temporary migration gap",
        ("manual-audit",),
    )


def _exception_receipt() -> Any:
    return lab.issue_exception(
        _exception_request(),
        approver="control-owner",
        authorized_approvers=frozenset({"control-owner"}),
        policy_version="p7",
        now=1_000,
        ttl=100,
    )


def test_exception_is_bound_and_expiring() -> None:
    receipt = _exception_receipt()
    lab.validate_exception(_exception_request(), receipt, current_policy_version="p7", now=1_050)
    assert receipt.expires_at == 1_100


def test_self_approval_is_rejected() -> None:
    with pytest.raises(PermissionError, match="independent"):
        lab.issue_exception(
            _exception_request(),
            approver="requester",
            authorized_approvers=frozenset({"requester"}),
            policy_version="p7",
            now=1_000,
            ttl=100,
        )


def test_non_waivable_control_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-waivable"):
        lab.issue_exception(
            _exception_request(),
            approver="control-owner",
            authorized_approvers=frozenset({"control-owner"}),
            policy_version="p7",
            now=1_000,
            ttl=100,
            prohibited_controls=frozenset({"logging"}),
        )


@pytest.mark.parametrize("failure", ["expired", "stale", "changed", "used"])
def test_exception_validation_rejects_invalid_receipt(failure: str) -> None:
    request = _exception_request()
    receipt = _exception_receipt()
    if failure == "expired":
        with pytest.raises(ValueError, match="expired"):
            lab.validate_exception(request, receipt, current_policy_version="p7", now=1_101)
    elif failure == "stale":
        with pytest.raises(ValueError, match="stale"):
            lab.validate_exception(request, receipt, current_policy_version="p8", now=1_050)
    elif failure == "changed":
        with pytest.raises(ValueError, match="changed"):
            lab.validate_exception(
                replace(request, candidate_version="v2"),
                receipt,
                current_policy_version="p7",
                now=1_050,
            )
    else:
        with pytest.raises(ValueError, match="consumed"):
            lab.validate_exception(
                request, replace(receipt, used=True), current_policy_version="p7", now=1_050
            )


def test_decision_matrix_covers_each_decision_once() -> None:
    lab.validate_decision_rights(lab.demo_decision_rights())


def test_missing_decision_right_is_rejected() -> None:
    with pytest.raises(ValueError, match="cover each"):
        lab.validate_decision_rights(lab.demo_decision_rights()[:-1])


def test_accountable_owner_cannot_be_informed_only() -> None:
    rights = list(lab.demo_decision_rights())
    rights[0] = replace(rights[0], informed=(rights[0].accountable,))
    with pytest.raises(ValueError, match="informed-only"):
        lab.validate_decision_rights(rights)


def test_service_catalog_has_executable_contracts() -> None:
    lab.validate_service_catalog(lab.demo_services())


def test_service_without_exit_path_is_rejected() -> None:
    service = replace(lab.demo_services()[0], exit_path="")
    with pytest.raises(ValueError, match="incomplete"):
        lab.validate_service_catalog((service,))


def test_service_requires_deprecation_window() -> None:
    service = replace(lab.demo_services()[0], deprecation_days=7)
    with pytest.raises(ValueError, match="lifecycle"):
        lab.validate_service_catalog((service,))


def test_maturity_uses_floor_not_average() -> None:
    assessment = lab.assess_maturity(
        lab.demo_maturity_evidence(), trusted_producers=frozenset({"assurance-office"}), now=1_300
    )
    assert assessment.overall is lab.MaturityLevel.PROVISIONAL


def test_missing_maturity_evidence_is_inconclusive() -> None:
    assessment = lab.assess_maturity(
        lab.demo_maturity_evidence()[:-1],
        trusted_producers=frozenset({"assurance-office"}),
        now=1_300,
    )
    assert assessment.overall is None
    assert "missing-or-duplicate:people" in assessment.gaps


def test_stale_maturity_evidence_is_not_counted() -> None:
    evidence = list(lab.demo_maturity_evidence())
    evidence[0] = replace(evidence[0], expires_at=1_200)
    assessment = lab.assess_maturity(
        evidence, trusted_producers=frozenset({"assurance-office"}), now=1_300
    )
    assert assessment.overall is None


def test_valid_roadmap_sequences_dependencies_and_resources() -> None:
    result = lab.assess_roadmap(
        lab.demo_roadmap(),
        quarterly_budget={1: 200_000, 2: 250_000, 3: 350_000, 4: 250_000},
        quarterly_capacity={1: 3, 2: 4, 3: 6, 4: 4},
    )
    assert result.valid


def test_roadmap_rejects_dependency_in_same_quarter() -> None:
    items = list(lab.demo_roadmap())
    items[1] = replace(items[1], quarter=1)
    result = lab.assess_roadmap(items, quarterly_budget={1: 1_000_000}, quarterly_capacity={1: 20})
    assert "invalid-dependency:portfolio-gate:decision-rights" in result.reasons


def test_roadmap_rejects_over_budget() -> None:
    result = lab.assess_roadmap(
        lab.demo_roadmap(),
        quarterly_budget={1: 1, 2: 1, 3: 1, 4: 1},
        quarterly_capacity={1: 20, 2: 20, 3: 20, 4: 20},
    )
    assert any(reason.startswith("budget-exceeded") for reason in result.reasons)


def test_investment_case_discounts_adoption_and_cost() -> None:
    result = lab.evaluate_investment(lab.demo_investments()[1], discount_rate=0.08)
    assert result.discounted_benefit > 0
    assert result.discounted_cost > 0
    assert result.npv == round(result.discounted_benefit - result.discounted_cost, 2)


def test_investment_sensitivity_orders_scenarios() -> None:
    results = [lab.evaluate_investment(item, discount_rate=0.08) for item in lab.demo_investments()]
    assert results[0].npv < results[1].npv < results[2].npv


def test_investment_requires_matching_horizon() -> None:
    bad = replace(lab.demo_investments()[0], annual_costs=(1.0,))
    with pytest.raises(ValueError, match="horizons"):
        lab.evaluate_investment(bad, discount_rate=0.08)


def _dissent() -> Any:
    return lab.DissentRecord(
        "decision-1",
        "digest",
        "security-lead",
        ("threat-12",),
        "platform-lead",
        "stage rollout with an additional control",
        lab.DissentStatus.ACCEPTED_RISK,
        ("residual supplier risk",),
    )


def test_dissent_preserves_evidence_and_unresolved_risk() -> None:
    lab.validate_dissent(_dissent())


def test_resolved_dissent_cannot_hide_risk() -> None:
    with pytest.raises(ValueError, match="hide"):
        lab.validate_dissent(replace(_dissent(), status=lab.DissentStatus.RESOLVED))


def test_escalated_dissent_requires_owner() -> None:
    with pytest.raises(ValueError, match="owner"):
        lab.validate_dissent(replace(_dissent(), status=lab.DissentStatus.ESCALATED))


def test_delegation_contract_defines_authority_and_learning() -> None:
    lab.validate_delegation(
        lab.DelegationContract(
            "draft service standard",
            "staff-engineer",
            "may propose, not approve",
            ("architect", "policy repository"),
            7,
            "unresolved hard constraint",
            "review-ready standard and test",
            "lead a cross-functional review",
        )
    )


def test_empty_delegation_boundary_is_rejected() -> None:
    with pytest.raises(ValueError, match="delegation"):
        lab.validate_delegation(
            lab.DelegationContract(
                "do work", "delegate", "", ("docs",), 7, "blocked", "done", "learn"
            )
        )


def test_portfolio_metrics_use_correct_denominators() -> None:
    result = lab.run_demo_operating_model()
    metrics = result["metrics"]
    selection = result["selection"]
    assert metrics.total == 70
    assert metrics.funded_rate == round(len(selection.funded) / 70, 4)
    assert metrics.evidence_gap_rate == round(len(selection.referred) / 70, 4)


def test_demo_operating_model_is_complete_and_valid() -> None:
    result = lab.run_demo_operating_model()
    assert result["candidate_count"] == 70
    assert result["roadmap"].valid
    assert len(result["investments"]) == 3
