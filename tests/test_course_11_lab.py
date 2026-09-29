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
        / "curriculum/advanced/11-solution-architecture-technical-strategy/lab.py"
    )
    spec = importlib.util.spec_from_file_location("course_11_lab", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lab = _load()
TRUSTED = frozenset({"architecture-review-office"})


def _option(option_id: str = "hybrid-platform") -> Any:
    return next(item for item in lab.demo_options() if item.option_id == option_id)


def _evaluate(option_id: str = "hybrid-platform", evidence: Any | None = None) -> Any:
    proof = lab.demo_evidence() if evidence is None else evidence
    return lab.evaluate_option(
        _option(option_id),
        lab.demo_criteria(),
        proof,
        trusted_producers=TRUSTED,
        now=1_300,
    )


def test_hybrid_option_is_eligible() -> None:
    decision = _evaluate()

    assert decision.disposition is lab.DecisionDisposition.ELIGIBLE
    assert decision.utility_score is not None and decision.utility_score > 0.7


def test_hard_threshold_disqualifies_point_solution() -> None:
    decision = _evaluate("point-solutions")

    assert decision.disposition is lab.DecisionDisposition.DISQUALIFIED
    assert "hard-threshold-failed:tenant-isolation" in decision.reasons


def test_hard_time_constraint_disqualifies_central_build() -> None:
    decision = _evaluate("central-build")

    assert "hard-threshold-failed:time-to-first-use" in decision.reasons


def test_missing_evidence_is_inconclusive_not_zero_score() -> None:
    proof = tuple(
        item
        for item in lab.demo_evidence()
        if not (item.option_id == "hybrid-platform" and item.criterion_id == "portability")
    )
    decision = _evaluate(evidence=proof)

    assert decision.disposition is lab.DecisionDisposition.INCONCLUSIVE
    assert decision.utility_score is None
    assert "missing-evidence:portability" in decision.reasons


def test_stale_evidence_is_inconclusive() -> None:
    proof = tuple(
        replace(item, expires_at=1_200) if item.option_id == "hybrid-platform" else item
        for item in lab.demo_evidence()
    )

    assert _evaluate(evidence=proof).disposition is lab.DecisionDisposition.INCONCLUSIVE


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("producer", "vendor-sales", "untrusted-evidence:compliant-success"),
        ("unit", "percent", "unit-mismatch:compliant-success"),
        ("confidence", 1.5, "invalid-confidence:compliant-success"),
        ("independent", False, "independent-evidence-required:compliant-success"),
    ],
)
def test_evidence_contract_fails_closed(field: str, value: object, reason: str) -> None:
    proof = list(lab.demo_evidence())
    index = next(
        i
        for i, item in enumerate(proof)
        if item.option_id == "hybrid-platform" and item.criterion_id == "compliant-success"
    )
    proof[index] = replace(proof[index], **{field: value})

    assert reason in _evaluate(evidence=proof).reasons


def test_evidence_for_another_option_version_is_not_reused() -> None:
    proof = tuple(
        replace(item, option_version="v2") if item.option_id == "hybrid-platform" else item
        for item in lab.demo_evidence()
    )

    assert "missing-evidence:availability" in _evaluate(evidence=proof).reasons


def test_duplicate_evidence_is_rejected() -> None:
    proof = lab.demo_evidence()
    duplicate = next(
        item
        for item in proof
        if item.option_id == "hybrid-platform" and item.criterion_id == "portability"
    )

    assert "duplicate-evidence:portability" in _evaluate(evidence=(*proof, duplicate)).reasons


def test_uncertainty_reduces_score_without_inventing_failure() -> None:
    option = _option()
    proof = lab.demo_evidence()
    low_penalty = lab.evaluate_option(
        option,
        lab.demo_criteria(),
        proof,
        trusted_producers=TRUSTED,
        now=1_300,
        uncertainty_penalty=0.0,
    )
    high_penalty = lab.evaluate_option(
        option,
        lab.demo_criteria(),
        proof,
        trusted_producers=TRUSTED,
        now=1_300,
        uncertainty_penalty=0.5,
    )

    assert low_penalty.utility_score > high_penalty.utility_score


def test_ranking_excludes_disqualified_options() -> None:
    decisions = tuple(_evaluate(option.option_id) for option in lab.demo_options())
    ranking = lab.rank_options(decisions)

    assert [item.option_id for item in ranking] == ["hybrid-platform"]


def test_no_eligible_options_returns_empty_ranking() -> None:
    decision = replace(_evaluate(), disposition=lab.DecisionDisposition.DISQUALIFIED)

    assert lab.rank_options((decision,)) == ()


@pytest.mark.parametrize(
    "criteria,error",
    [
        ((), "requires criteria"),
        ((replace(lab.demo_criteria()[0], weight=0.0),), "weights must be positive"),
        ((lab.demo_criteria()[0],), "weights must sum to one"),
    ],
)
def test_invalid_decision_models_are_rejected(criteria: Any, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        lab.validate_decision_model(criteria)


def test_sensitivity_analysis_reports_winner_stability() -> None:
    result = lab.sensitivity_analysis(
        lab.demo_options(),
        lab.demo_criteria(),
        lab.demo_evidence(),
        trusted_producers=TRUSTED,
        now=1_300,
    )

    assert result.stable_winner == "hybrid-platform"
    assert result.winner_counts["hybrid-platform"] == result.tested_models


def test_invalid_sensitivity_shift_is_rejected() -> None:
    with pytest.raises(ValueError, match="shift"):
        lab.sensitivity_analysis(
            lab.demo_options(),
            lab.demo_criteria(),
            lab.demo_evidence(),
            trusted_producers=TRUSTED,
            now=1_300,
            shift=1.5,
        )


def test_tco_includes_expected_risk_loss_and_unit_denominator() -> None:
    model = lab.demo_economics()[2]
    result = lab.calculate_tco(model)

    assert result.expected_risk_loss == model.risk_probability * model.risk_impact.expected
    assert result.cost_per_unit == round(
        result.expected / (model.horizon_years * model.annual_units), 4
    )
    assert result.low < result.expected < result.high


@pytest.mark.parametrize(
    "field,value",
    [("horizon_years", 0), ("annual_units", 0), ("risk_probability", 1.2)],
)
def test_invalid_economic_model_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        lab.calculate_tco(replace(lab.demo_economics()[0], **{field: value}))


def test_invalid_cost_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="cost range"):
        lab.CostRange(100.0, 50.0, 200.0)


def _validate_adr(adr: Any) -> tuple[str, ...]:
    return lab.validate_adr(
        adr,
        known_options=frozenset(item.option_id for item in lab.demo_options()),
        known_evidence=frozenset(item.evidence_id for item in lab.demo_evidence()),
        now=1_300,
    )


def test_complete_adr_is_valid() -> None:
    assert _validate_adr(lab.demo_adr()) == ()


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda adr: replace(adr, selected_option_id="unknown"), "unknown-selected-option"),
        (
            lambda adr: replace(adr, alternatives=("hybrid-platform",)),
            "selected-option-listed-as-alternative",
        ),
        (lambda adr: replace(adr, evidence_ids=("fake",)), "unknown-or-missing-evidence"),
        (lambda adr: replace(adr, consequences=()), "consequences-required"),
        (lambda adr: replace(adr, assumptions=()), "assumptions-required"),
        (lambda adr: replace(adr, reversal_triggers=()), "reversal-triggers-required"),
        (lambda adr: replace(adr, review_at=1_200), "review-date-not-future"),
        (lambda adr: replace(adr, approved_by="staff-architect"), "independent-approval-required"),
        (lambda adr: replace(adr, decision="altered"), "decision-digest-mismatch"),
    ],
)
def test_adr_validation_detects_unaccountable_decisions(mutation: Any, reason: str) -> None:
    assert reason in _validate_adr(mutation(lab.demo_adr()))


def test_planned_stage_becomes_ready_only_after_dependencies_complete() -> None:
    assessment = lab.assess_migration(lab.demo_migration())

    assert assessment.valid
    assert assessment.ready_stages == ("scale",)


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda stages: (*stages, stages[0]), "duplicate-stage"),
        (
            lambda stages: (replace(stages[0], depends_on=("missing",)), *stages[1:]),
            "unknown-dependency:foundation",
        ),
        (
            lambda stages: (replace(stages[0], depends_on=("foundation",)), *stages[1:]),
            "self-dependency:foundation",
        ),
        (lambda stages: (replace(stages[0], owner=""), *stages[1:]), "owner-required:foundation"),
        (
            lambda stages: (replace(stages[0], rollback=""), *stages[1:]),
            "reversal-required:foundation",
        ),
    ],
)
def test_migration_contract_detects_invalid_stage(mutation: Any, reason: str) -> None:
    assessment = lab.assess_migration(mutation(lab.demo_migration()))

    assert not assessment.valid
    assert reason in assessment.reasons


def test_migration_cycle_is_detected() -> None:
    stages = lab.demo_migration()
    changed = (
        replace(stages[0], depends_on=("scale",), status=lab.StageStatus.PLANNED),
        stages[1],
        stages[2],
        stages[3],
    )

    assert "migration-cycle" in lab.assess_migration(changed).reasons


def test_end_to_end_strategy_recommends_hybrid_with_valid_artifacts() -> None:
    result = lab.run_demo_strategy()

    assert result["ranking"][0].option_id == "hybrid-platform"
    assert result["sensitivity"].stable_winner == "hybrid-platform"
    assert result["adr_reasons"] == ()
    assert result["migration"].valid
