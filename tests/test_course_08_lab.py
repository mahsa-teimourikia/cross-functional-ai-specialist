from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_course_module() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "curriculum"
        / "advanced"
        / "08-ai-evaluation-causal-impact"
        / "lab.py"
    )
    spec = importlib.util.spec_from_file_location("course_08_lab", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lab = _load_course_module()


def _release_reports() -> tuple[Any, Any, Any, Any]:
    manifest = lab.build_demo_manifest()
    cases = manifest.partition(lab.DatasetPartition.RELEASE)
    harness = lab.EvaluationHarness(manifest)
    baseline = harness.evaluate(
        system_id="baseline-v8",
        partition=lab.DatasetPartition.RELEASE,
        outputs=lab.demo_system_outputs(cases, candidate=False),
    )
    candidate = harness.evaluate(
        system_id="candidate-v9",
        partition=lab.DatasetPartition.RELEASE,
        outputs=lab.demo_system_outputs(cases, candidate=True),
    )
    truth, annotations = lab.demo_human_labels()
    assert lab.adjudicated_human_labels(
        annotations, rubric_version="underwriting-rubric-v4"
    ) == truth
    judge = lab.calibrate_judge(truth, lab.demo_judge_assessments())
    return manifest, baseline, candidate, judge


def _policy(**overrides: object) -> object:
    policy = lab.ReleasePolicy(4, 0.85, 0.05, 0.85, 1.20, 1.10, 0.85, 0.10)
    return replace(policy, **overrides)


def test_manifest_has_isolated_partitions_and_expected_sizes() -> None:
    manifest = lab.build_demo_manifest()

    assert len(manifest.partition(lab.DatasetPartition.DEVELOPMENT)) == 4
    assert len(manifest.partition(lab.DatasetPartition.CALIBRATION)) == 12
    assert len(manifest.partition(lab.DatasetPartition.RELEASE)) == 16
    assert len({case.case_id for case in manifest.cases}) == 32


def test_manifest_rejects_duplicate_case_ids() -> None:
    manifest = lab.build_demo_manifest()
    duplicated = replace(manifest, cases=(*manifest.cases, manifest.cases[0]))

    with pytest.raises(ValueError, match="duplicate case id"):
        duplicated.validate()


def test_manifest_rejects_content_leakage_between_partitions() -> None:
    manifest = lab.build_demo_manifest()
    leaked = replace(manifest.cases[-1], prompt=manifest.cases[0].prompt)
    changed = replace(manifest, cases=(*manifest.cases[:-1], leaked))

    with pytest.raises(ValueError, match="content leakage"):
        changed.validate()


def test_metric_contracts_make_denominators_and_owners_explicit() -> None:
    contracts = lab.default_metric_contracts()

    assert {contract.name for contract in contracts} == {
        "compliant_success_rate",
        "cost_per_successful_compliant_task",
        "decision_quality",
    }
    assert all(contract.denominator and contract.owner for contract in contracts)


def test_metric_contract_rejects_unknown_direction() -> None:
    contract = replace(lab.default_metric_contracts()[0], direction="sideways")

    with pytest.raises(ValueError, match="metric direction"):
        contract.validate()


def test_case_evaluation_is_bound_to_case_id() -> None:
    manifest = lab.build_demo_manifest()
    case = manifest.cases[0]
    output = next(iter(lab.demo_system_outputs((case,), candidate=True).values()))

    with pytest.raises(ValueError, match="not bound"):
        lab.EvaluationHarness.evaluate_case(case, replace(output, case_id="different"))


def test_harness_rejects_missing_and_extra_outputs() -> None:
    manifest = lab.build_demo_manifest()
    harness = lab.EvaluationHarness(manifest)
    cases = manifest.partition(lab.DatasetPartition.RELEASE)
    outputs = lab.demo_system_outputs(cases, candidate=True)
    outputs.pop(cases[0].case_id)
    outputs["extra"] = replace(next(iter(outputs.values())), case_id="extra")

    with pytest.raises(ValueError, match="coverage mismatch"):
        harness.evaluate(
            system_id="candidate-v9",
            partition=lab.DatasetPartition.RELEASE,
            outputs=outputs,
        )


def test_forbidden_tool_is_a_forbidden_outcome() -> None:
    manifest = lab.build_demo_manifest()
    case = manifest.cases[0]
    output = next(iter(lab.demo_system_outputs((case,), candidate=True).values()))

    result = lab.EvaluationHarness.evaluate_case(
        case, replace(output, tools_used=("unapproved-export",))
    )

    assert result.forbidden_outcome
    assert not result.compliant


def test_evidence_recall_uses_required_evidence_denominator() -> None:
    manifest = lab.build_demo_manifest()
    case = replace(manifest.cases[0], required_evidence=frozenset({"a", "b"}))
    output = next(iter(lab.demo_system_outputs((case,), candidate=True).values()))
    output = replace(output, cited_evidence=frozenset({"a"}))

    assert lab.EvaluationHarness.evaluate_case(case, output).evidence_recall == 0.5


def test_report_preserves_slices_and_cost_per_governed_success() -> None:
    _, _, candidate, _ = _release_reports()

    assert set(candidate.slices) == {"simple", "complex", "restricted", "drift"}
    assert all(report.cases == 4 for report in candidate.slices.values())
    assert candidate.cost_per_successful_compliant_task == pytest.approx(5.12 / 15)
    assert candidate.p95_latency_ms > 0


def test_paired_bootstrap_is_deterministic_and_positive() -> None:
    estimate = lab.bootstrap_paired_delta([0, 0, 1, 1], [1, 1, 1, 1], seed=8)

    assert estimate.estimate == 0.5
    assert estimate.lower >= 0
    assert estimate == lab.bootstrap_paired_delta([0, 0, 1, 1], [1, 1, 1, 1], seed=8)


def test_paired_bootstrap_rejects_unpaired_populations() -> None:
    with pytest.raises(ValueError, match="paired samples"):
        lab.bootstrap_paired_delta([0, 1], [1])


def test_wilson_interval_is_bounded() -> None:
    interval = lab.wilson_interval(9, 10)

    assert 0 <= interval.lower < interval.estimate < interval.upper <= 1


def test_human_labels_require_blinding_and_one_rubric() -> None:
    _, annotations = lab.demo_human_labels()
    unblinded = (replace(annotations[0], blinded=False), *annotations[1:])

    with pytest.raises(ValueError, match="blinded annotations"):
        lab.adjudicated_human_labels(
            unblinded, rubric_version="underwriting-rubric-v4"
        )


def test_human_labels_reject_ties_instead_of_hiding_adjudication() -> None:
    tied = (
        lab.HumanAnnotation("x", "a", True, "r1", True, "yes"),
        lab.HumanAnnotation("x", "b", False, "r1", True, "no"),
    )

    with pytest.raises(ValueError, match="requires adjudication"):
        lab.adjudicated_human_labels(tied, rubric_version="r1")


def test_judge_calibration_reports_disagreement_and_kappa() -> None:
    truth, _ = lab.demo_human_labels()
    calibration = lab.calibrate_judge(truth, lab.demo_judge_assessments())

    assert calibration.cases == 12
    assert calibration.accuracy == pytest.approx(11 / 12)
    assert len(calibration.disagreements) == 1
    assert calibration.kappa > 0.7


def test_biased_judge_fails_accuracy_floor() -> None:
    truth, _ = lab.demo_human_labels()
    calibration = lab.calibrate_judge(truth, lab.demo_judge_assessments(biased=True))

    assert calibration.accuracy == 0.75


def test_judge_and_human_populations_must_match() -> None:
    truth, _ = lab.demo_human_labels()

    with pytest.raises(ValueError, match="populations must match"):
        lab.calibrate_judge(truth, lab.demo_judge_assessments()[:-1])


def test_pairwise_order_audit_measures_flip_rate() -> None:
    first = {"a": "left", "b": "right", "c": "tie"}
    reversed_order = {"a": "left", "b": "left", "c": "tie"}

    assert lab.pairwise_order_flip_rate(first, reversed_order) == pytest.approx(1 / 3)


def test_healthy_offline_release_passes_all_gates() -> None:
    _, baseline, candidate, judge = _release_reports()

    decision = lab.decide_release(
        baseline,
        candidate,
        policy=_policy(),
        judge=judge,
        order_flip_rate=0,
        leakage_detected=False,
    )

    assert decision.disposition is lab.ReleaseDisposition.PASS
    assert decision.reasons == ()
    assert decision.paired_success_delta.lower >= -0.05


@pytest.mark.parametrize("leakage,forbidden", [(True, False), (False, True)])
def test_hard_invariants_fail_release(leakage: bool, forbidden: bool) -> None:
    manifest, baseline, candidate, judge = _release_reports()
    if forbidden:
        cases = manifest.partition(lab.DatasetPartition.RELEASE)
        candidate = lab.EvaluationHarness(manifest).evaluate(
            system_id="unsafe",
            partition=lab.DatasetPartition.RELEASE,
            outputs=lab.demo_system_outputs(cases, candidate=True, inject_forbidden=True),
        )

    decision = lab.decide_release(
        baseline,
        candidate,
        policy=_policy(),
        judge=judge,
        order_flip_rate=0,
        leakage_detected=leakage,
    )

    assert decision.disposition is lab.ReleaseDisposition.FAIL


def test_insufficient_slice_coverage_is_inconclusive() -> None:
    _, baseline, candidate, judge = _release_reports()

    decision = lab.decide_release(
        baseline,
        candidate,
        policy=_policy(minimum_cases_per_slice=5),
        judge=judge,
        order_flip_rate=0,
        leakage_detected=False,
    )

    assert decision.disposition is lab.ReleaseDisposition.INCONCLUSIVE
    assert "insufficient-slice-coverage" in decision.reasons


def test_missing_required_slice_is_inconclusive() -> None:
    _, baseline, candidate, judge = _release_reports()
    candidate = replace(
        candidate,
        slices={name: report for name, report in candidate.slices.items() if name != "drift"},
    )

    decision = lab.decide_release(
        baseline,
        candidate,
        policy=_policy(),
        judge=judge,
        order_flip_rate=0,
        leakage_detected=False,
    )

    assert decision.disposition is lab.ReleaseDisposition.INCONCLUSIVE
    assert "insufficient-slice-coverage" in decision.reasons


def test_uncalibrated_or_order_sensitive_judge_blocks_release() -> None:
    _, baseline, candidate, _ = _release_reports()
    truth, _ = lab.demo_human_labels()
    biased = lab.calibrate_judge(truth, lab.demo_judge_assessments(biased=True))

    decision = lab.decide_release(
        baseline,
        candidate,
        policy=_policy(),
        judge=biased,
        order_flip_rate=0.25,
        leakage_detected=False,
    )

    assert decision.disposition is lab.ReleaseDisposition.INCONCLUSIVE
    assert {"judge-calibration-below-floor", "judge-order-bias"} <= set(decision.reasons)


def test_holm_bonferroni_controls_a_family_of_tests() -> None:
    decisions = lab.holm_bonferroni({"a": 0.01, "b": 0.03, "c": 0.04})

    assert decisions == {"a": True, "b": False, "c": False}


def test_naive_repeated_peeking_can_claim_a_false_win() -> None:
    assert lab.naive_peeking_false_positive([0.40, 0.18, 0.049, 0.22])


def test_power_contract_computes_positive_fixed_horizon() -> None:
    size = lab.required_sample_size_per_arm(
        standard_deviation=10, minimum_detectable_effect=4
    )

    assert size == 99


def test_experiment_plan_rejects_invalid_inference_contract() -> None:
    plan = replace(lab.demo_experiment_plan(), power=1.2)

    with pytest.raises(ValueError, match="alpha and power"):
        lab.analyze_experiment(lab.build_demo_experiment(), plan)


def test_balanced_demo_has_no_sample_ratio_mismatch() -> None:
    units = lab.build_demo_experiment()

    assert not lab.sample_ratio_mismatch(units)


def test_healthy_experiment_passes_itt_and_guardrail() -> None:
    analysis = lab.analyze_experiment(
        lab.build_demo_experiment(), lab.demo_experiment_plan()
    )

    assert analysis.decision is lab.ReleaseDisposition.PASS
    assert analysis.time_saved_itt.lower > 0
    assert analysis.accuracy_delta.lower > -0.05
    assert analysis.adoption_rate == 0.8


def test_experiment_requires_fixed_horizon() -> None:
    units = lab.build_demo_experiment(sample_per_arm=6)
    analysis = lab.analyze_experiment(units, lab.demo_experiment_plan(sample_per_arm=40))

    assert analysis.decision is lab.ReleaseDisposition.FAIL
    assert "fixed-horizon-not-reached" in analysis.reasons


def test_prohibited_experiment_outcome_is_a_hard_stop() -> None:
    units = lab.build_demo_experiment()
    units[0] = replace(units[0], prohibited_outcome=True)

    analysis = lab.analyze_experiment(units, lab.demo_experiment_plan())

    assert analysis.decision is lab.ReleaseDisposition.FAIL
    assert "prohibited-outcome" in analysis.reasons


def test_cuped_reduces_interval_width_in_correlated_fixture() -> None:
    analysis = lab.analyze_experiment(
        lab.build_demo_experiment(), lab.demo_experiment_plan()
    )
    raw_width = analysis.time_saved_itt.upper - analysis.time_saved_itt.lower
    cuped_width = analysis.time_saved_cuped.upper - analysis.time_saved_cuped.lower

    assert cuped_width < raw_width


def test_heterogeneous_effects_do_not_replace_overall_itt() -> None:
    analysis = lab.analyze_experiment(
        lab.build_demo_experiment(), lab.demo_experiment_plan()
    )

    assert analysis.heterogeneous_time_saved["novice"] > 7
    assert analysis.heterogeneous_time_saved["expert"] > 4
    assert analysis.time_saved_itt.difference > 6


def test_adopter_only_estimate_differs_from_randomized_itt() -> None:
    units = lab.build_demo_experiment()
    analysis = lab.analyze_experiment(units, lab.demo_experiment_plan())

    assert lab.adopter_only_time_saved(units) != pytest.approx(
        analysis.time_saved_itt.difference
    )


def test_difference_in_differences_removes_shared_trend() -> None:
    points = [
        lab.PanelPoint("c", False, 0, 10),
        lab.PanelPoint("c", False, 1, 12),
        lab.PanelPoint("t", True, 0, 14),
        lab.PanelPoint("t", True, 1, 11),
    ]

    assert lab.difference_in_differences(points, treatment_period=1) == -5


def test_pretrend_difference_surfaces_parallel_trend_risk() -> None:
    points = [
        lab.PanelPoint("c", False, 0, 10),
        lab.PanelPoint("c", False, 1, 11),
        lab.PanelPoint("t", True, 0, 10),
        lab.PanelPoint("t", True, 1, 14),
    ]

    assert lab.pretrend_difference(points, treatment_period=2) == 3


@pytest.mark.parametrize(
    "adjustment,match",
    [
        (frozenset({"experience", "adoption"}), "post-treatment"),
        (frozenset({"experience", "reviewed"}), "colliders"),
        (frozenset(), "misses measured confounders"),
    ],
)
def test_causal_design_rejects_invalid_adjustment_sets(
    adjustment: frozenset[str], match: str
) -> None:
    design = lab.CausalDesign(
        "assistant",
        "decision quality",
        frozenset({"experience"}),
        frozenset({"adoption"}),
        frozenset({"reviewed"}),
    )

    with pytest.raises(ValueError, match=match):
        design.validate_adjustment_set(adjustment)


def test_decision_memo_keeps_release_authority_with_owners() -> None:
    release, experiment, memo = lab.run_demo_release()

    assert release.disposition is lab.ReleaseDisposition.PASS
    assert experiment.decision is lab.ReleaseDisposition.PASS
    assert memo.recommendation == "progress to a bounded monitored rollout"
    assert "AI product owner" in memo.owners
    assert len(memo.limitations) == 2


def test_decision_map_covers_the_full_evidence_chain() -> None:
    decision_map = lab.evaluation_decision_map()

    assert set(decision_map) == {
        "unit",
        "dataset",
        "labels",
        "metrics",
        "judges",
        "uncertainty",
        "release",
        "experiment",
        "causality",
        "decision",
    }
