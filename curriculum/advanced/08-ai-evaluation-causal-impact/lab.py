"""Deterministic Course 8 lab: evaluation, experimentation, and causal impact.

The fixtures are synthetic and the statistics are deliberately transparent standard-library
implementations. They teach contracts and failure modes; they do not replace a reviewed production
statistics package or domain study.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from math import ceil, sqrt
from random import Random
from statistics import NormalDist, mean


class DecisionLabel(StrEnum):
    APPROVE = "approve"
    REFER = "refer"
    DECLINE = "decline"
    ABSTAIN = "abstain"


class ReleaseDisposition(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class Assignment(StrEnum):
    CONTROL = "control"
    TREATMENT = "treatment"


class Expertise(StrEnum):
    NOVICE = "novice"
    EXPERT = "expert"


class DatasetPartition(StrEnum):
    DEVELOPMENT = "development"
    CALIBRATION = "calibration"
    RELEASE = "release"


def content_digest(value: str) -> str:
    return sha256(value.strip().lower().encode()).hexdigest()


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    partition: DatasetPartition
    slice_name: str
    prompt: str
    expected_decision: DecisionLabel
    required_evidence: frozenset[str]
    allowed_tools: frozenset[str]
    risk_weight: float = 1.0
    label_version: str = "labels-v3"
    source_date: str = "2026-09-01"


@dataclass(frozen=True)
class SystemOutput:
    case_id: str
    decision: DecisionLabel
    cited_evidence: frozenset[str]
    tools_used: tuple[str, ...]
    terminal_state: str
    latency_ms: int
    cost_units: float
    response_words: int
    prompt_version: str
    model_version: str
    leaked_restricted_data: bool = False


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    version: str
    cases: tuple[EvaluationCase, ...]
    owner: str
    frozen_at: str
    intended_use: str

    def validate(self) -> None:
        if not self.cases:
            raise ValueError("evaluation dataset cannot be empty")
        case_ids: set[str] = set()
        digests_by_partition: dict[DatasetPartition, set[str]] = defaultdict(set)
        for case in self.cases:
            if case.case_id in case_ids:
                raise ValueError(f"duplicate case id: {case.case_id}")
            case_ids.add(case.case_id)
            digest = content_digest(case.prompt)
            for partition, digests in digests_by_partition.items():
                if partition is not case.partition and digest in digests:
                    raise ValueError(
                        f"content leakage across {partition.value} and {case.partition.value}"
                    )
            digests_by_partition[case.partition].add(digest)

    def partition(self, name: DatasetPartition) -> tuple[EvaluationCase, ...]:
        return tuple(case for case in self.cases if case.partition is name)


@dataclass(frozen=True)
class MetricContract:
    name: str
    population: str
    numerator: str
    denominator: str
    unit: str
    direction: str
    aggregation: str
    required_slices: tuple[str, ...]
    threshold: float | None
    owner: str

    def validate(self) -> None:
        if self.direction not in {"higher", "lower", "zero"}:
            raise ValueError("metric direction must be higher, lower, or zero")
        for value in (
            self.name,
            self.population,
            self.denominator,
            self.unit,
            self.aggregation,
            self.owner,
        ):
            if not value:
                raise ValueError("metric contracts require explicit fields")


@dataclass(frozen=True)
class CaseEvaluation:
    case_id: str
    slice_name: str
    correct: bool
    compliant: bool
    evidence_recall: float
    forbidden_outcome: bool
    latency_ms: int
    cost_units: float

    @property
    def successful_compliant(self) -> bool:
        return self.correct and self.compliant and not self.forbidden_outcome


@dataclass(frozen=True)
class SliceReport:
    slice_name: str
    cases: int
    success_rate: float
    compliant_success_rate: float
    evidence_recall: float
    forbidden_outcomes: int


@dataclass(frozen=True)
class EvaluationReport:
    system_id: str
    dataset_id: str
    cases: tuple[CaseEvaluation, ...]
    slices: Mapping[str, SliceReport]
    success_rate: float
    compliant_success_rate: float
    evidence_recall: float
    forbidden_outcomes: int
    total_cost_units: float
    cost_per_successful_compliant_task: float | None
    p95_latency_ms: int


def percentile(values: Sequence[int], quantile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, ceil(quantile * len(ordered)) - 1)]


class EvaluationHarness:
    def __init__(self, manifest: DatasetManifest) -> None:
        manifest.validate()
        self.manifest = manifest

    @staticmethod
    def evaluate_case(case: EvaluationCase, output: SystemOutput) -> CaseEvaluation:
        if output.case_id != case.case_id:
            raise ValueError("output is not bound to the evaluation case")
        forbidden_tool = any(tool not in case.allowed_tools for tool in output.tools_used)
        forbidden = output.leaked_restricted_data or forbidden_tool
        compliant = (
            output.terminal_state == "succeeded"
            and not forbidden
            and output.decision is not DecisionLabel.ABSTAIN
        )
        evidence_recall = (
            len(case.required_evidence & output.cited_evidence) / len(case.required_evidence)
            if case.required_evidence
            else 1.0
        )
        return CaseEvaluation(
            case_id=case.case_id,
            slice_name=case.slice_name,
            correct=output.decision is case.expected_decision,
            compliant=compliant,
            evidence_recall=evidence_recall,
            forbidden_outcome=forbidden,
            latency_ms=output.latency_ms,
            cost_units=output.cost_units,
        )

    def evaluate(
        self,
        *,
        system_id: str,
        partition: DatasetPartition,
        outputs: Mapping[str, SystemOutput],
    ) -> EvaluationReport:
        selected = self.manifest.partition(partition)
        selected_ids = {case.case_id for case in selected}
        missing = selected_ids - set(outputs)
        extra = set(outputs) - selected_ids
        if missing or extra:
            raise ValueError(
                f"output coverage mismatch: missing={sorted(missing)}, extra={sorted(extra)}"
            )
        results = tuple(self.evaluate_case(case, outputs[case.case_id]) for case in selected)
        return build_evaluation_report(system_id, self.manifest.dataset_id, results)


def build_evaluation_report(
    system_id: str,
    dataset_id: str,
    results: Sequence[CaseEvaluation],
) -> EvaluationReport:
    if not results:
        raise ValueError("evaluation results cannot be empty")
    grouped: dict[str, list[CaseEvaluation]] = defaultdict(list)
    for result in results:
        grouped[result.slice_name].append(result)
    slices = {
        name: SliceReport(
            slice_name=name,
            cases=len(items),
            success_rate=sum(item.correct for item in items) / len(items),
            compliant_success_rate=sum(item.successful_compliant for item in items) / len(items),
            evidence_recall=sum(item.evidence_recall for item in items) / len(items),
            forbidden_outcomes=sum(item.forbidden_outcome for item in items),
        )
        for name, items in grouped.items()
    }
    successes = sum(item.successful_compliant for item in results)
    total_cost = sum(item.cost_units for item in results)
    return EvaluationReport(
        system_id=system_id,
        dataset_id=dataset_id,
        cases=tuple(results),
        slices=slices,
        success_rate=sum(item.correct for item in results) / len(results),
        compliant_success_rate=successes / len(results),
        evidence_recall=sum(item.evidence_recall for item in results) / len(results),
        forbidden_outcomes=sum(item.forbidden_outcome for item in results),
        total_cost_units=total_cost,
        cost_per_successful_compliant_task=total_cost / successes if successes else None,
        p95_latency_ms=percentile([item.latency_ms for item in results], 0.95),
    )


@dataclass(frozen=True)
class Estimate:
    estimate: float
    lower: float
    upper: float
    confidence: float
    samples: int


def bootstrap_paired_delta(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    iterations: int = 2_000,
    confidence: float = 0.95,
    seed: int = 8,
) -> Estimate:
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("paired samples must have equal positive length")
    if iterations < 100:
        raise ValueError("use at least 100 bootstrap iterations")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    differences = [new - old for old, new in zip(baseline, candidate, strict=True)]
    rng = Random(seed)
    resampled: list[float] = []
    for _ in range(iterations):
        draw = [differences[rng.randrange(len(differences))] for _ in differences]
        resampled.append(mean(draw))
    resampled.sort()
    tail = (1.0 - confidence) / 2.0
    lower_index = min(len(resampled) - 1, int(tail * len(resampled)))
    upper_index = min(len(resampled) - 1, int((1.0 - tail) * len(resampled)))
    return Estimate(
        estimate=mean(differences),
        lower=resampled[lower_index],
        upper=resampled[upper_index],
        confidence=confidence,
        samples=len(differences),
    )


def wilson_interval(successes: int, total: int, *, confidence: float = 0.95) -> Estimate:
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("invalid binomial population")
    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return Estimate(
        proportion,
        max(0.0, centre - radius),
        min(1.0, centre + radius),
        confidence,
        total,
    )


@dataclass(frozen=True)
class HumanAnnotation:
    case_id: str
    annotator_id: str
    label: bool
    rubric_version: str
    blinded: bool
    rationale_code: str


@dataclass(frozen=True)
class JudgeAssessment:
    case_id: str
    label: bool
    evaluator_id: str
    evaluator_version: str
    rubric_version: str
    candidate_position: int
    score: float


@dataclass(frozen=True)
class JudgeCalibration:
    cases: int
    accuracy: float
    precision: float
    recall: float
    false_positive_rate: float
    kappa: float
    accuracy_interval: Estimate
    disagreements: tuple[str, ...]


def cohen_kappa(left: Sequence[bool], right: Sequence[bool]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("ratings must have equal positive length")
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_positive = sum(left) / len(left)
    right_positive = sum(right) / len(right)
    expected = left_positive * right_positive + (1 - left_positive) * (1 - right_positive)
    return (observed - expected) / (1.0 - expected) if expected < 1.0 else 1.0


def adjudicated_human_labels(
    annotations: Sequence[HumanAnnotation],
    *,
    rubric_version: str,
) -> dict[str, bool]:
    grouped: dict[str, list[HumanAnnotation]] = defaultdict(list)
    for annotation in annotations:
        if annotation.rubric_version != rubric_version or not annotation.blinded:
            raise ValueError("calibration requires blinded annotations under one rubric version")
        grouped[annotation.case_id].append(annotation)
    labels: dict[str, bool] = {}
    for case_id, items in grouped.items():
        if len(items) < 2:
            raise ValueError(f"case {case_id} needs at least two human annotations")
        positives = sum(item.label for item in items)
        if positives * 2 == len(items):
            raise ValueError(f"case {case_id} requires adjudication after a tie")
        labels[case_id] = positives * 2 > len(items)
    return labels


def calibrate_judge(
    human_labels: Mapping[str, bool],
    assessments: Sequence[JudgeAssessment],
) -> JudgeCalibration:
    by_case: dict[str, JudgeAssessment] = {}
    for assessment in assessments:
        if assessment.case_id in by_case:
            raise ValueError("judge calibration accepts one assessment per case")
        by_case[assessment.case_id] = assessment
    if set(by_case) != set(human_labels):
        raise ValueError("judge and human calibration populations must match")
    human = [human_labels[case_id] for case_id in sorted(human_labels)]
    judged = [by_case[case_id].label for case_id in sorted(human_labels)]
    true_positive = sum(a and b for a, b in zip(human, judged, strict=True))
    true_negative = sum(not a and not b for a, b in zip(human, judged, strict=True))
    false_positive = sum(not a and b for a, b in zip(human, judged, strict=True))
    false_negative = sum(a and not b for a, b in zip(human, judged, strict=True))
    correct = true_positive + true_negative
    return JudgeCalibration(
        cases=len(human),
        accuracy=correct / len(human),
        precision=true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0,
        recall=true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0,
        false_positive_rate=false_positive / (false_positive + true_negative)
        if false_positive + true_negative
        else 0.0,
        kappa=cohen_kappa(human, judged),
        accuracy_interval=wilson_interval(correct, len(human)),
        disagreements=tuple(
            case_id
            for case_id in sorted(human_labels)
            if human_labels[case_id] != by_case[case_id].label
        ),
    )


def pairwise_order_flip_rate(
    first_order: Mapping[str, str],
    reversed_order: Mapping[str, str],
) -> float:
    if not first_order or set(first_order) != set(reversed_order):
        raise ValueError("order audit populations must match")
    return sum(first_order[key] != reversed_order[key] for key in first_order) / len(first_order)


@dataclass(frozen=True)
class ReleasePolicy:
    minimum_cases_per_slice: int
    minimum_compliant_success: float
    maximum_regression: float
    minimum_evidence_recall: float
    maximum_cost_ratio: float
    maximum_p95_latency_ratio: float
    minimum_judge_accuracy: float
    maximum_order_flip_rate: float
    required_slices: tuple[str, ...] = ("simple", "complex", "restricted", "drift")


@dataclass(frozen=True)
class ReleaseDecision:
    disposition: ReleaseDisposition
    reasons: tuple[str, ...]
    paired_success_delta: Estimate
    candidate_system_id: str
    baseline_system_id: str


def decide_release(
    baseline: EvaluationReport,
    candidate: EvaluationReport,
    *,
    policy: ReleasePolicy,
    judge: JudgeCalibration,
    order_flip_rate: float,
    leakage_detected: bool,
) -> ReleaseDecision:
    if [item.case_id for item in baseline.cases] != [item.case_id for item in candidate.cases]:
        raise ValueError("release comparison must be paired on identical ordered cases")
    baseline_scores = [float(item.successful_compliant) for item in baseline.cases]
    candidate_scores = [float(item.successful_compliant) for item in candidate.cases]
    delta = bootstrap_paired_delta(baseline_scores, candidate_scores)
    reasons: list[str] = []
    hard_failure = False
    if leakage_detected:
        reasons.append("dataset-leakage")
        hard_failure = True
    if candidate.forbidden_outcomes:
        reasons.append("forbidden-outcome")
        hard_failure = True
    missing_or_small = [
        name
        for name in policy.required_slices
        if name not in candidate.slices
        or candidate.slices[name].cases < policy.minimum_cases_per_slice
    ]
    if missing_or_small:
        reasons.append("insufficient-slice-coverage")
    if candidate.compliant_success_rate < policy.minimum_compliant_success:
        reasons.append("compliant-success-below-floor")
    if delta.lower < -policy.maximum_regression:
        reasons.append("paired-quality-noninferiority-not-proven")
    if candidate.evidence_recall < policy.minimum_evidence_recall:
        reasons.append("evidence-recall-below-floor")
    baseline_cost = baseline.cost_per_successful_compliant_task
    candidate_cost = candidate.cost_per_successful_compliant_task
    if baseline_cost is None or candidate_cost is None:
        reasons.append("unit-cost-undefined")
    elif candidate_cost / baseline_cost > policy.maximum_cost_ratio:
        reasons.append("unit-cost-regression")
    latency_ratio = candidate.p95_latency_ms / max(1, baseline.p95_latency_ms)
    if latency_ratio > policy.maximum_p95_latency_ratio:
        reasons.append("tail-latency-regression")
    if judge.accuracy < policy.minimum_judge_accuracy:
        reasons.append("judge-calibration-below-floor")
    if order_flip_rate > policy.maximum_order_flip_rate:
        reasons.append("judge-order-bias")
    if hard_failure:
        disposition = ReleaseDisposition.FAIL
    elif reasons:
        disposition = ReleaseDisposition.INCONCLUSIVE
    else:
        disposition = ReleaseDisposition.PASS
    return ReleaseDecision(
        disposition,
        tuple(reasons),
        delta,
        candidate.system_id,
        baseline.system_id,
    )


def holm_bonferroni(p_values: Mapping[str, float], *, alpha: float = 0.05) -> dict[str, bool]:
    if not p_values or any(not 0 <= value <= 1 for value in p_values.values()):
        raise ValueError("p-values must be a non-empty mapping in [0, 1]")
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    decisions = {name: False for name in p_values}
    still_rejecting = True
    for index, (name, value) in enumerate(ordered):
        threshold = alpha / (len(ordered) - index)
        if still_rejecting and value <= threshold:
            decisions[name] = True
        else:
            still_rejecting = False
    return decisions


def naive_peeking_false_positive(p_values_by_look: Sequence[float], *, alpha: float = 0.05) -> bool:
    """Demonstrate the invalid rule; returning True means it would claim a win."""

    if not p_values_by_look or any(not 0 <= value <= 1 for value in p_values_by_look):
        raise ValueError("p-values must be in [0, 1]")
    return any(value < alpha for value in p_values_by_look)


def required_sample_size_per_arm(
    *,
    standard_deviation: float,
    minimum_detectable_effect: float,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    if standard_deviation <= 0 or minimum_detectable_effect <= 0:
        raise ValueError("standard deviation and effect must be positive")
    if not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("alpha and power must be between zero and one")
    z_alpha = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    z_power = NormalDist().inv_cdf(power)
    size = 2.0 * ((z_alpha + z_power) * standard_deviation / minimum_detectable_effect) ** 2
    return ceil(size)


@dataclass(frozen=True)
class ExperimentPlan:
    experiment_id: str
    hypothesis: str
    randomization_unit: str
    primary_metric: str
    guardrail_metric: str
    minimum_detectable_effect_minutes: float
    noninferiority_margin_accuracy: float
    alpha: float
    power: float
    fixed_sample_per_arm: int
    analysis_version: str

    def validate(self) -> None:
        if not self.experiment_id or not self.hypothesis or not self.randomization_unit:
            raise ValueError("experiment identity, hypothesis, and randomization unit are required")
        if self.minimum_detectable_effect_minutes <= 0:
            raise ValueError("minimum detectable effect must be positive")
        if self.noninferiority_margin_accuracy < 0:
            raise ValueError("noninferiority margin cannot be negative")
        if not 0 < self.alpha < 1 or not 0 < self.power < 1:
            raise ValueError("alpha and power must be between zero and one")
        if self.fixed_sample_per_arm < 2:
            raise ValueError("fixed horizon needs at least two units per arm")


@dataclass(frozen=True)
class ExperimentUnit:
    unit_id: str
    assignment: Assignment
    expertise: Expertise
    pre_task_minutes: float
    post_task_minutes: float
    decision_correct: bool
    adopted: bool
    prohibited_outcome: bool = False


@dataclass(frozen=True)
class MeanDifference:
    difference: float
    lower: float
    upper: float
    control_mean: float
    treatment_mean: float


@dataclass(frozen=True)
class ExperimentAnalysis:
    experiment_id: str
    control_units: int
    treatment_units: int
    sample_ratio_mismatch: bool
    time_saved_itt: MeanDifference
    time_saved_cuped: MeanDifference
    accuracy_delta: MeanDifference
    prohibited_outcomes: int
    adoption_rate: float
    heterogeneous_time_saved: Mapping[str, float]
    decision: ReleaseDisposition
    reasons: tuple[str, ...]


def sample_variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    centre = mean(values)
    return sum((value - centre) ** 2 for value in values) / (len(values) - 1)


def covariance(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = mean(left)
    right_mean = mean(right)
    return sum(
        (a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True)
    ) / (len(left) - 1)


def mean_difference(
    control: Sequence[float],
    treatment: Sequence[float],
    *,
    treatment_minus_control: bool = True,
    confidence: float = 0.95,
) -> MeanDifference:
    if len(control) < 2 or len(treatment) < 2:
        raise ValueError("each arm needs at least two observations")
    control_mean = mean(control)
    treatment_mean = mean(treatment)
    raw = treatment_mean - control_mean
    difference = raw if treatment_minus_control else -raw
    standard_error = sqrt(
        sample_variance(control) / len(control)
        + sample_variance(treatment) / len(treatment)
    )
    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)
    return MeanDifference(
        difference,
        difference - z * standard_error,
        difference + z * standard_error,
        control_mean,
        treatment_mean,
    )


def sample_ratio_mismatch(units: Sequence[ExperimentUnit], *, threshold: float = 6.635) -> bool:
    counts = Counter(unit.assignment for unit in units)
    expected = len(units) / 2.0
    statistic = sum((counts[group] - expected) ** 2 / expected for group in Assignment)
    return statistic > threshold


def cuped_adjusted_outcomes(units: Sequence[ExperimentUnit]) -> dict[str, float]:
    pre = [unit.pre_task_minutes for unit in units]
    post = [unit.post_task_minutes for unit in units]
    variance = sample_variance(pre)
    theta = covariance(post, pre) / variance if variance else 0.0
    pre_mean = mean(pre)
    return {
        unit.unit_id: unit.post_task_minutes - theta * (unit.pre_task_minutes - pre_mean)
        for unit in units
    }


def analyze_experiment(
    units: Sequence[ExperimentUnit],
    plan: ExperimentPlan,
) -> ExperimentAnalysis:
    plan.validate()
    if len({unit.unit_id for unit in units}) != len(units):
        raise ValueError("experiment units must be unique")
    control = [unit for unit in units if unit.assignment is Assignment.CONTROL]
    treatment = [unit for unit in units if unit.assignment is Assignment.TREATMENT]
    if len(control) < 2 or len(treatment) < 2:
        raise ValueError("both randomized arms need observations")
    time_saved = mean_difference(
        [unit.post_task_minutes for unit in control],
        [unit.post_task_minutes for unit in treatment],
        treatment_minus_control=False,
    )
    adjusted = cuped_adjusted_outcomes(units)
    cuped_saved = mean_difference(
        [adjusted[unit.unit_id] for unit in control],
        [adjusted[unit.unit_id] for unit in treatment],
        treatment_minus_control=False,
    )
    accuracy = mean_difference(
        [float(unit.decision_correct) for unit in control],
        [float(unit.decision_correct) for unit in treatment],
        treatment_minus_control=True,
    )
    reasons: list[str] = []
    srm = sample_ratio_mismatch(units)
    if srm:
        reasons.append("sample-ratio-mismatch")
    if len(control) < plan.fixed_sample_per_arm or len(treatment) < plan.fixed_sample_per_arm:
        reasons.append("fixed-horizon-not-reached")
    if time_saved.lower <= 0:
        reasons.append("productivity-improvement-not-proven")
    if accuracy.lower < -plan.noninferiority_margin_accuracy:
        reasons.append("decision-quality-noninferiority-not-proven")
    prohibited = sum(unit.prohibited_outcome for unit in units)
    if prohibited:
        reasons.append("prohibited-outcome")
    disposition = ReleaseDisposition.PASS if not reasons else ReleaseDisposition.FAIL
    heterogeneous: dict[str, float] = {}
    for expertise in Expertise:
        subset_control = [unit.post_task_minutes for unit in control if unit.expertise is expertise]
        subset_treatment = [
            unit.post_task_minutes for unit in treatment if unit.expertise is expertise
        ]
        if subset_control and subset_treatment:
            heterogeneous[expertise.value] = mean(subset_control) - mean(subset_treatment)
    return ExperimentAnalysis(
        experiment_id=plan.experiment_id,
        control_units=len(control),
        treatment_units=len(treatment),
        sample_ratio_mismatch=srm,
        time_saved_itt=time_saved,
        time_saved_cuped=cuped_saved,
        accuracy_delta=accuracy,
        prohibited_outcomes=prohibited,
        adoption_rate=sum(unit.adopted for unit in treatment) / len(treatment),
        heterogeneous_time_saved=heterogeneous,
        decision=disposition,
        reasons=tuple(reasons),
    )


def adopter_only_time_saved(units: Sequence[ExperimentUnit]) -> float:
    control = [unit.post_task_minutes for unit in units if unit.assignment is Assignment.CONTROL]
    adopters = [
        unit.post_task_minutes
        for unit in units
        if unit.assignment is Assignment.TREATMENT and unit.adopted
    ]
    if not control or not adopters:
        raise ValueError("adopter comparison needs control units and adopters")
    return mean(control) - mean(adopters)


@dataclass(frozen=True)
class PanelPoint:
    unit_id: str
    treated_group: bool
    period: int
    outcome: float


def difference_in_differences(points: Sequence[PanelPoint], *, treatment_period: int) -> float:
    grouped: dict[tuple[bool, str], list[PanelPoint]] = defaultdict(list)
    for point in points:
        phase = "post" if point.period >= treatment_period else "pre"
        grouped[(point.treated_group, phase)].append(point)
    required = {(False, "pre"), (False, "post"), (True, "pre"), (True, "post")}
    if not required <= grouped.keys():
        raise ValueError("difference-in-differences needs treated/control pre/post observations")
    change_treated = mean(point.outcome for point in grouped[(True, "post")]) - mean(
        point.outcome for point in grouped[(True, "pre")]
    )
    change_control = mean(point.outcome for point in grouped[(False, "post")]) - mean(
        point.outcome for point in grouped[(False, "pre")]
    )
    return change_treated - change_control


def pretrend_difference(points: Sequence[PanelPoint], *, treatment_period: int) -> float:
    pre = [point for point in points if point.period < treatment_period]
    periods = sorted({point.period for point in pre})
    if len(periods) < 2:
        raise ValueError("pretrend assessment needs at least two pre-treatment periods")
    first, last = periods[0], periods[-1]

    def group_change(treated: bool) -> float:
        start = [
            point.outcome
            for point in pre
            if point.treated_group is treated and point.period == first
        ]
        end = [
            point.outcome
            for point in pre
            if point.treated_group is treated and point.period == last
        ]
        if not start or not end:
            raise ValueError("each group needs observations in both pre-periods")
        return mean(end) - mean(start)

    return group_change(True) - group_change(False)


@dataclass(frozen=True)
class CausalDesign:
    treatment: str
    outcome: str
    confounders: frozenset[str]
    mediators: frozenset[str]
    colliders: frozenset[str]

    def validate_adjustment_set(self, adjustment: frozenset[str]) -> None:
        post_treatment = adjustment & self.mediators
        collider_control = adjustment & self.colliders
        missing = self.confounders - adjustment
        if post_treatment:
            raise ValueError(
                f"do not adjust for post-treatment mediators: {sorted(post_treatment)}"
            )
        if collider_control:
            raise ValueError(f"do not condition on colliders: {sorted(collider_control)}")
        if missing:
            raise ValueError(f"adjustment set misses measured confounders: {sorted(missing)}")


@dataclass(frozen=True)
class DecisionMemo:
    offline_release: ReleaseDisposition
    experiment_decision: ReleaseDisposition
    recommendation: str
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    owners: tuple[str, ...]


def build_decision_memo(
    release: ReleaseDecision,
    experiment: ExperimentAnalysis,
) -> DecisionMemo:
    if (
        release.disposition is ReleaseDisposition.PASS
        and experiment.decision is ReleaseDisposition.PASS
    ):
        recommendation = "progress to a bounded monitored rollout"
    else:
        recommendation = "do not expand rollout; resolve failed or inconclusive evidence"
    return DecisionMemo(
        offline_release=release.disposition,
        experiment_decision=experiment.decision,
        recommendation=recommendation,
        evidence=(
            f"offline paired delta={release.paired_success_delta.estimate:.3f}",
            f"ITT time saved={experiment.time_saved_itt.difference:.2f} minutes",
            f"accuracy delta={experiment.accuracy_delta.difference:.3f}",
        ),
        limitations=(
            "synthetic deterministic course fixtures do not predict production effect sizes",
            "judge agreement and experiment validity must be re-established after material drift",
        ),
        owners=("AI product owner", "domain quality owner", "experimentation owner"),
    )


def default_metric_contracts() -> tuple[MetricContract, ...]:
    contracts = (
        MetricContract(
            "compliant_success_rate",
            "frozen release cases",
            "correct, policy-compliant cases with no forbidden outcome",
            "all frozen release cases",
            "proportion",
            "higher",
            "macro plus required slices",
            ("simple", "complex", "restricted", "drift"),
            0.85,
            "domain quality owner",
        ),
        MetricContract(
            "cost_per_successful_compliant_task",
            "frozen release cases",
            "all attempt and evaluator cost",
            "successful compliant tasks",
            "cost units per task",
            "lower",
            "total cost divided by governed successes",
            ("simple", "complex", "restricted", "drift"),
            None,
            "AI product owner",
        ),
        MetricContract(
            "decision_quality",
            "randomized eligible users under intention to treat",
            "correct reviewed decisions",
            "all assigned eligible users",
            "proportion",
            "higher",
            "ITT overall and expertise slices",
            ("novice", "expert"),
            None,
            "experimentation owner",
        ),
    )
    for contract in contracts:
        contract.validate()
    return contracts


def build_demo_manifest() -> DatasetManifest:
    cases: list[EvaluationCase] = []
    decisions = (
        DecisionLabel.APPROVE,
        DecisionLabel.REFER,
        DecisionLabel.DECLINE,
        DecisionLabel.REFER,
    )
    slices = ("simple", "complex", "restricted", "drift")
    case_number = 0
    for partition, per_slice in (
        (DatasetPartition.DEVELOPMENT, 1),
        (DatasetPartition.CALIBRATION, 3),
        (DatasetPartition.RELEASE, 4),
    ):
        for slice_index, slice_name in enumerate(slices):
            for local_index in range(per_slice):
                case_number += 1
                case_id = f"eval-{case_number:03d}"
                cases.append(
                    EvaluationCase(
                        case_id=case_id,
                        partition=partition,
                        slice_name=slice_name,
                        prompt=(
                            f"{partition.value} underwriting {slice_name} "
                            f"scenario {local_index}"
                        ),
                        expected_decision=decisions[slice_index],
                        required_evidence=frozenset({f"evidence-{case_id}"}),
                        allowed_tools=frozenset({"retrieve-policy", "calculate-ratio"}),
                        risk_weight=2.0 if slice_name == "restricted" else 1.0,
                    )
                )
    manifest = DatasetManifest(
        "northstar-underwriting-eval",
        "2026.09.0",
        tuple(cases),
        "domain quality owner",
        "2026-09-27",
        "prompt/model release comparison; not training or tuning",
    )
    manifest.validate()
    return manifest


def demo_system_outputs(
    cases: Sequence[EvaluationCase],
    *,
    candidate: bool,
    inject_forbidden: bool = False,
) -> dict[str, SystemOutput]:
    outputs: dict[str, SystemOutput] = {}
    for index, case in enumerate(cases):
        # Keep the candidate error paired with one baseline error. This makes the healthy
        # fixture an unambiguous non-inferior improvement while failure tests mutate it.
        wrong = (index % 4 == 1) if not candidate else (index == len(cases) - 3)
        decision = DecisionLabel.APPROVE if wrong else case.expected_decision
        if decision is case.expected_decision and wrong:
            decision = DecisionLabel.DECLINE
        outputs[case.case_id] = SystemOutput(
            case_id=case.case_id,
            decision=decision,
            cited_evidence=case.required_evidence if not wrong else frozenset(),
            tools_used=("retrieve-policy",),
            terminal_state="succeeded",
            latency_ms=(720 + index * 7) if candidate else (900 + index * 9),
            cost_units=0.32 if candidate else 0.36,
            response_words=95 if candidate else 78,
            prompt_version="candidate-v9" if candidate else "baseline-v8",
            model_version="gateway-route-v13" if candidate else "gateway-route-v12",
            leaked_restricted_data=inject_forbidden and index == 0,
        )
    return outputs


def demo_human_labels() -> tuple[dict[str, bool], tuple[HumanAnnotation, ...]]:
    truth = {f"judge-{index:02d}": index not in {2, 5, 9} for index in range(12)}
    annotations: list[HumanAnnotation] = []
    for case_id, label in truth.items():
        for annotator in ("reviewer-a", "reviewer-b", "reviewer-c"):
            annotations.append(
                HumanAnnotation(
                    case_id,
                    annotator,
                    label,
                    "underwriting-rubric-v4",
                    True,
                    "meets-contract" if label else "material-error",
                )
            )
    return truth, tuple(annotations)


def demo_judge_assessments(*, biased: bool = False) -> tuple[JudgeAssessment, ...]:
    truth, _ = demo_human_labels()
    assessments: list[JudgeAssessment] = []
    for index, (case_id, label) in enumerate(truth.items()):
        judged = label
        if index == 5 or (biased and index in {2, 9}):
            judged = not label
        assessments.append(
            JudgeAssessment(
                case_id,
                judged,
                "deterministic-judge",
                "judge-v2",
                "underwriting-rubric-v4",
                1 if index % 2 == 0 else 2,
                0.9 if judged else 0.2,
            )
        )
    return tuple(assessments)


def demo_experiment_plan(sample_per_arm: int = 40) -> ExperimentPlan:
    return ExperimentPlan(
        "northstar-productivity-2026-09",
        "The assistant reduces review time without materially reducing decision accuracy.",
        "underwriter",
        "task minutes",
        "reviewed decision accuracy",
        4.0,
        0.05,
        0.05,
        0.8,
        sample_per_arm,
        "analysis-v3",
    )


def build_demo_experiment(sample_per_arm: int = 40) -> list[ExperimentUnit]:
    units: list[ExperimentUnit] = []
    for index in range(sample_per_arm * 2):
        assignment = Assignment.CONTROL if index % 2 == 0 else Assignment.TREATMENT
        expertise = Expertise.NOVICE if (index // 2) % 2 == 0 else Expertise.EXPERT
        pre = 34.0 + (index % 7) + (5.0 if expertise is Expertise.NOVICE else 0.0)
        natural_post = pre + ((index % 3) - 1) * 0.4
        treatment_reduction = 8.0 if expertise is Expertise.NOVICE else 5.0
        post = (
            natural_post - treatment_reduction
            if assignment is Assignment.TREATMENT
            else natural_post
        )
        adopted = assignment is Assignment.TREATMENT and index % 5 != 1
        correct = index % 20 != 0
        units.append(
            ExperimentUnit(
                f"underwriter-{index:03d}",
                assignment,
                expertise,
                pre,
                post,
                correct,
                adopted,
            )
        )
    return units


def run_demo_release() -> tuple[ReleaseDecision, ExperimentAnalysis, DecisionMemo]:
    manifest = build_demo_manifest()
    release_cases = manifest.partition(DatasetPartition.RELEASE)
    harness = EvaluationHarness(manifest)
    baseline = harness.evaluate(
        system_id="baseline-v8",
        partition=DatasetPartition.RELEASE,
        outputs=demo_system_outputs(release_cases, candidate=False),
    )
    candidate = harness.evaluate(
        system_id="candidate-v9",
        partition=DatasetPartition.RELEASE,
        outputs=demo_system_outputs(release_cases, candidate=True),
    )
    truth, annotations = demo_human_labels()
    assert adjudicated_human_labels(annotations, rubric_version="underwriting-rubric-v4") == truth
    calibration = calibrate_judge(truth, demo_judge_assessments())
    release = decide_release(
        baseline,
        candidate,
        policy=ReleasePolicy(4, 0.85, 0.05, 0.85, 1.20, 1.10, 0.85, 0.10),
        judge=calibration,
        order_flip_rate=0.0,
        leakage_detected=False,
    )
    experiment = analyze_experiment(build_demo_experiment(), demo_experiment_plan())
    return release, experiment, build_decision_memo(release, experiment)


def evaluation_decision_map() -> dict[str, str]:
    return {
        "unit": "one versioned case, one bound system output, one stable case ID",
        "dataset": "separate development, judge-calibration, and frozen release partitions",
        "labels": "blinded domain annotations, rubric version, rationale code, adjudication",
        "metrics": "population, numerator, denominator, direction, aggregation, slices, owner",
        "judges": "calibrate against humans; audit order, verbosity, self-preference, and drift",
        "uncertainty": "paired estimates and confidence intervals, not naked point scores",
        "release": "hard deterministic invariants plus quality, slice, latency, cost thresholds",
        "experiment": (
            "pre-registered unit, hypothesis, primary metric, guardrail, horizon, analysis"
        ),
        "causality": (
            "randomize when possible; otherwise state the DAG and identification assumptions"
        ),
        "decision": (
            "application owners accept, reject, or bound rollout; an evaluator does not deploy"
        ),
    }
