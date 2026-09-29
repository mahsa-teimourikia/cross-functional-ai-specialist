"""Deterministic Course 11 lab: solution architecture and technical strategy.

The fixtures model evidence, trade-offs, economics, decisions, and migration for a fictional AI
platform. Scores support accountable judgment; they do not generate authority or certainty.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
from typing import cast


def stable_digest(value: str) -> str:
    return f"sha256:{sha256(value.encode()).hexdigest()}"


class Direction(StrEnum):
    HIGHER = "higher-is-better"
    LOWER = "lower-is-better"


class OptionKind(StrEnum):
    BUILD = "build"
    BUY = "buy"
    PARTNER = "partner"
    HYBRID = "hybrid"


class DecisionDisposition(StrEnum):
    ELIGIBLE = "eligible"
    DISQUALIFIED = "disqualified"
    INCONCLUSIVE = "inconclusive"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"


class StageStatus(StrEnum):
    PLANNED = "planned"
    READY = "ready"
    COMPLETE = "complete"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class StakeholderConcern:
    concern_id: str
    stakeholder: str
    outcome: str
    decision_right: str
    success_measure: str


@dataclass(frozen=True)
class QualityScenario:
    scenario_id: str
    attribute: str
    source: str
    stimulus: str
    environment: str
    artifact: str
    response: str
    measure: str
    threshold: float
    unit: str
    direction: Direction


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    description: str
    weight: float
    worst: float
    best: float
    direction: Direction
    hard_threshold: float | None
    unit: str
    requires_independent_evidence: bool = False


@dataclass(frozen=True)
class ArchitectureOption:
    option_id: str
    version: str
    name: str
    kind: OptionKind
    summary: str
    owner: str
    capabilities: frozenset[str]
    provider_dependencies: frozenset[str]
    exit_strategy: str


@dataclass(frozen=True)
class OptionEvidence:
    evidence_id: str
    option_id: str
    option_version: str
    criterion_id: str
    observed_value: float
    unit: str
    source: str
    producer: str
    confidence: float
    independent: bool
    created_at: int
    expires_at: int


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    normalized_score: float | None
    confidence: float | None
    weighted_score: float
    evidence_id: str | None
    reason: str | None


@dataclass(frozen=True)
class OptionDecision:
    option_id: str
    disposition: DecisionDisposition
    utility_score: float | None
    confidence: float | None
    reasons: tuple[str, ...]
    results: tuple[CriterionResult, ...]


def validate_decision_model(criteria: Sequence[Criterion]) -> None:
    if not criteria:
        raise ValueError("decision model requires criteria")
    identifiers = [item.criterion_id for item in criteria]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate criterion")
    if any(item.weight <= 0 for item in criteria):
        raise ValueError("criterion weights must be positive")
    if abs(sum(item.weight for item in criteria) - 1.0) > 1e-9:
        raise ValueError("criterion weights must sum to one")
    if any(item.worst == item.best for item in criteria):
        raise ValueError("criterion range cannot be zero")
    for item in criteria:
        if item.direction is Direction.HIGHER and item.best < item.worst:
            raise ValueError("higher-is-better range is reversed")
        if item.direction is Direction.LOWER and item.best > item.worst:
            raise ValueError("lower-is-better range is reversed")


def _normalize(value: float, criterion: Criterion) -> float:
    if criterion.direction is Direction.HIGHER:
        raw = (value - criterion.worst) / (criterion.best - criterion.worst)
    else:
        raw = (criterion.worst - value) / (criterion.worst - criterion.best)
    return max(0.0, min(1.0, raw))


def _meets_threshold(value: float, criterion: Criterion) -> bool:
    if criterion.hard_threshold is None:
        return True
    if criterion.direction is Direction.HIGHER:
        return value >= criterion.hard_threshold
    return value <= criterion.hard_threshold


def evaluate_option(
    option: ArchitectureOption,
    criteria: Sequence[Criterion],
    evidence: Sequence[OptionEvidence],
    *,
    trusted_producers: frozenset[str],
    now: int,
    uncertainty_penalty: float = 0.20,
) -> OptionDecision:
    """Evaluate an exact option version without converting missing proof into a zero score."""

    validate_decision_model(criteria)
    if not 0.0 <= uncertainty_penalty <= 1.0:
        raise ValueError("uncertainty penalty must be between zero and one")
    reasons: set[str] = set()
    results: list[CriterionResult] = []
    total = 0.0
    confidence_total = 0.0
    for criterion in criteria:
        matching = [
            item
            for item in evidence
            if item.option_id == option.option_id
            and item.option_version == option.version
            and item.criterion_id == criterion.criterion_id
        ]
        if not matching:
            reasons.add(f"missing-evidence:{criterion.criterion_id}")
            results.append(
                CriterionResult(criterion.criterion_id, None, None, 0.0, None, "missing")
            )
            continue
        if len(matching) > 1:
            reasons.add(f"duplicate-evidence:{criterion.criterion_id}")
            results.append(
                CriterionResult(criterion.criterion_id, None, None, 0.0, None, "duplicate")
            )
            continue
        item = matching[0]
        if item.producer not in trusted_producers:
            reasons.add(f"untrusted-evidence:{criterion.criterion_id}")
        if item.expires_at < now:
            reasons.add(f"stale-evidence:{criterion.criterion_id}")
        if item.unit != criterion.unit:
            reasons.add(f"unit-mismatch:{criterion.criterion_id}")
        if not 0.0 <= item.confidence <= 1.0:
            reasons.add(f"invalid-confidence:{criterion.criterion_id}")
        if criterion.requires_independent_evidence and not item.independent:
            reasons.add(f"independent-evidence-required:{criterion.criterion_id}")
        normalized = _normalize(item.observed_value, criterion)
        confidence = max(0.0, min(1.0, item.confidence))
        adjusted = max(0.0, normalized - uncertainty_penalty * (1.0 - confidence))
        weighted = criterion.weight * adjusted
        total += weighted
        confidence_total += criterion.weight * confidence
        threshold_met = _meets_threshold(item.observed_value, criterion)
        if not threshold_met:
            reasons.add(f"hard-threshold-failed:{criterion.criterion_id}")
        results.append(
            CriterionResult(
                criterion.criterion_id,
                round(normalized, 6),
                confidence,
                round(weighted, 6),
                item.evidence_id,
                None if threshold_met else "hard-threshold-failed",
            )
        )

    hard_fail = any(reason.startswith("hard-threshold-failed:") for reason in reasons)
    invalid = any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in (
            "duplicate-evidence:",
            "untrusted-evidence:",
            "unit-mismatch:",
            "invalid-confidence:",
            "independent-evidence-required:",
        )
    )
    missing_or_stale = any(
        reason.startswith(("missing-evidence:", "stale-evidence:")) for reason in reasons
    )
    if hard_fail or invalid:
        disposition = DecisionDisposition.DISQUALIFIED
    elif missing_or_stale:
        disposition = DecisionDisposition.INCONCLUSIVE
    else:
        disposition = DecisionDisposition.ELIGIBLE
    return OptionDecision(
        option.option_id,
        disposition,
        round(total, 6) if disposition is DecisionDisposition.ELIGIBLE else None,
        round(confidence_total, 6) if disposition is DecisionDisposition.ELIGIBLE else None,
        tuple(sorted(reasons)),
        tuple(results),
    )


def rank_options(decisions: Sequence[OptionDecision]) -> tuple[OptionDecision, ...]:
    eligible = [item for item in decisions if item.disposition is DecisionDisposition.ELIGIBLE]
    if not eligible:
        return ()
    return tuple(
        sorted(
            eligible,
            key=lambda item: (
                -(item.utility_score if item.utility_score is not None else -1.0),
                -(item.confidence if item.confidence is not None else -1.0),
                item.option_id,
            ),
        )
    )


@dataclass(frozen=True)
class SensitivityResult:
    winner_counts: Mapping[str, int]
    tested_models: int
    stable_winner: str | None


def sensitivity_analysis(
    options: Sequence[ArchitectureOption],
    criteria: Sequence[Criterion],
    evidence: Sequence[OptionEvidence],
    *,
    trusted_producers: frozenset[str],
    now: int,
    shift: float = 0.15,
) -> SensitivityResult:
    """Perturb each criterion weight and report winner stability, not false precision."""

    if not 0.0 < shift < 1.0:
        raise ValueError("shift must be between zero and one")
    winner_counts: dict[str, int] = {option.option_id: 0 for option in options}
    models = [tuple(criteria)]
    for focus in criteria:
        increased = []
        denominator = 1.0 + focus.weight * shift
        for item in criteria:
            factor = 1.0 + shift if item.criterion_id == focus.criterion_id else 1.0
            increased.append(replace(item, weight=item.weight * factor / denominator))
        models.append(tuple(increased))
    for model in models:
        ranked = rank_options(
            [
                evaluate_option(
                    option,
                    model,
                    evidence,
                    trusted_producers=trusted_producers,
                    now=now,
                )
                for option in options
            ]
        )
        if ranked:
            winner_counts[ranked[0].option_id] += 1
    winning = [key for key, value in winner_counts.items() if value == len(models)]
    return SensitivityResult(winner_counts, len(models), winning[0] if len(winning) == 1 else None)


@dataclass(frozen=True)
class CostRange:
    low: float
    expected: float
    high: float

    def __post_init__(self) -> None:
        if self.low < 0 or not self.low <= self.expected <= self.high:
            raise ValueError("invalid cost range")


@dataclass(frozen=True)
class Economics:
    option_id: str
    horizon_years: int
    migration: CostRange
    annual_platform: CostRange
    annual_people: CostRange
    unit_cost: CostRange
    annual_units: int
    exit_cost: CostRange
    risk_probability: float
    risk_impact: CostRange


@dataclass(frozen=True)
class TCOResult:
    option_id: str
    low: float
    expected: float
    high: float
    expected_risk_loss: float
    cost_per_unit: float


def calculate_tco(model: Economics) -> TCOResult:
    if model.horizon_years <= 0 or model.annual_units <= 0:
        raise ValueError("horizon and annual units must be positive")
    if not 0.0 <= model.risk_probability <= 1.0:
        raise ValueError("risk probability must be between zero and one")
    years = model.horizon_years
    units = model.annual_units * years
    risk = model.risk_probability * model.risk_impact.expected
    low = (
        model.migration.low
        + years * (model.annual_platform.low + model.annual_people.low)
        + units * model.unit_cost.low
        + model.exit_cost.low
    )
    expected = (
        model.migration.expected
        + years * (model.annual_platform.expected + model.annual_people.expected)
        + units * model.unit_cost.expected
        + model.exit_cost.expected
        + risk
    )
    high = (
        model.migration.high
        + years * (model.annual_platform.high + model.annual_people.high)
        + units * model.unit_cost.high
        + model.exit_cost.high
        + model.risk_probability * model.risk_impact.high
    )
    return TCOResult(
        model.option_id,
        round(low, 2),
        round(expected, 2),
        round(high, 2),
        round(risk, 2),
        round(expected / units, 4),
    )


@dataclass(frozen=True)
class ArchitectureDecisionRecord:
    adr_id: str
    title: str
    status: DecisionStatus
    context: str
    decision: str
    selected_option_id: str
    alternatives: tuple[str, ...]
    consequences: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    reversal_triggers: tuple[str, ...]
    owner: str
    approved_by: str | None
    created_at: int
    review_at: int
    decision_digest: str


def canonical_adr_digest(adr: ArchitectureDecisionRecord) -> str:
    return stable_digest(
        "|".join(
            [
                adr.adr_id,
                adr.title,
                adr.status,
                adr.context,
                adr.decision,
                adr.selected_option_id,
                *sorted(adr.alternatives),
                *sorted(adr.consequences),
                *sorted(adr.evidence_ids),
                *sorted(adr.assumptions),
                *sorted(adr.reversal_triggers),
                adr.owner,
                adr.approved_by or "",
                str(adr.created_at),
                str(adr.review_at),
            ]
        )
    )


def validate_adr(
    adr: ArchitectureDecisionRecord,
    *,
    known_options: frozenset[str],
    known_evidence: frozenset[str],
    now: int,
) -> tuple[str, ...]:
    reasons: set[str] = set()
    if adr.selected_option_id not in known_options:
        reasons.add("unknown-selected-option")
    if adr.selected_option_id in adr.alternatives:
        reasons.add("selected-option-listed-as-alternative")
    if len(set(adr.alternatives)) < 2:
        reasons.add("insufficient-alternatives")
    if not adr.evidence_ids or not set(adr.evidence_ids) <= known_evidence:
        reasons.add("unknown-or-missing-evidence")
    if not adr.consequences:
        reasons.add("consequences-required")
    if not adr.assumptions:
        reasons.add("assumptions-required")
    if not adr.reversal_triggers:
        reasons.add("reversal-triggers-required")
    if adr.review_at <= now:
        reasons.add("review-date-not-future")
    if adr.status is DecisionStatus.ACCEPTED and (
        not adr.approved_by or adr.approved_by == adr.owner
    ):
        reasons.add("independent-approval-required")
    if adr.decision_digest != canonical_adr_digest(replace(adr, decision_digest="")):
        reasons.add("decision-digest-mismatch")
    return tuple(sorted(reasons))


@dataclass(frozen=True)
class MigrationStage:
    stage_id: str
    name: str
    depends_on: tuple[str, ...]
    owner: str
    entry_criteria: tuple[str, ...]
    exit_criteria: tuple[str, ...]
    rollback: str
    kill_criteria: tuple[str, ...]
    status: StageStatus


@dataclass(frozen=True)
class MigrationAssessment:
    valid: bool
    reasons: tuple[str, ...]
    ready_stages: tuple[str, ...]


def assess_migration(stages: Sequence[MigrationStage]) -> MigrationAssessment:
    reasons: set[str] = set()
    identifiers = [item.stage_id for item in stages]
    if len(set(identifiers)) != len(identifiers):
        reasons.add("duplicate-stage")
    known = set(identifiers)
    completed = {item.stage_id for item in stages if item.status is StageStatus.COMPLETE}
    ready: list[str] = []
    for stage in stages:
        if not set(stage.depends_on) <= known:
            reasons.add(f"unknown-dependency:{stage.stage_id}")
        if stage.stage_id in stage.depends_on:
            reasons.add(f"self-dependency:{stage.stage_id}")
        if not stage.owner:
            reasons.add(f"owner-required:{stage.stage_id}")
        if not stage.entry_criteria or not stage.exit_criteria:
            reasons.add(f"criteria-required:{stage.stage_id}")
        if not stage.rollback or not stage.kill_criteria:
            reasons.add(f"reversal-required:{stage.stage_id}")
        if stage.status is StageStatus.COMPLETE and not set(stage.depends_on) <= completed:
            reasons.add(f"completed-before-dependency:{stage.stage_id}")
        if stage.status is StageStatus.PLANNED and set(stage.depends_on) <= completed:
            ready.append(stage.stage_id)
    # Detect longer cycles with depth-first traversal.
    dependencies = {item.stage_id: set(item.depends_on) for item in stages}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visiting:
            reasons.add("migration-cycle")
            return
        if stage_id in visited:
            return
        visiting.add(stage_id)
        for dependency in dependencies.get(stage_id, set()):
            if dependency in known:
                visit(dependency)
        visiting.remove(stage_id)
        visited.add(stage_id)

    for stage_id in identifiers:
        visit(stage_id)
    return MigrationAssessment(not reasons, tuple(sorted(reasons)), tuple(sorted(ready)))


def demo_concerns() -> tuple[StakeholderConcern, ...]:
    return (
        StakeholderConcern(
            "c-product",
            "product",
            "faster safe use-case delivery",
            "prioritize outcomes",
            "lead time",
        ),
        StakeholderConcern(
            "c-security",
            "security",
            "bounded data and tool access",
            "approve controls",
            "forbidden outcomes",
        ),
        StakeholderConcern(
            "c-platform",
            "platform",
            "operable shared capabilities",
            "own paved road",
            "adoption and SLO",
        ),
        StakeholderConcern(
            "c-finance",
            "finance",
            "defensible unit economics",
            "challenge forecast",
            "cost per compliant task",
        ),
    )


def demo_quality_scenarios() -> tuple[QualityScenario, ...]:
    return (
        QualityScenario(
            "qa-latency",
            "performance",
            "underwriter",
            "submit case",
            "peak",
            "assistant",
            "grounded answer",
            "p95 latency",
            2.0,
            "seconds",
            Direction.LOWER,
        ),
        QualityScenario(
            "qa-isolation",
            "security",
            "malicious tenant",
            "request another tenant case",
            "normal",
            "knowledge plane",
            "deny before retrieval",
            "forbidden outcomes",
            0.0,
            "count",
            Direction.LOWER,
        ),
        QualityScenario(
            "qa-recovery",
            "reliability",
            "regional outage",
            "region unavailable",
            "production",
            "platform",
            "restore service",
            "RTO",
            30.0,
            "minutes",
            Direction.LOWER,
        ),
    )


def demo_criteria() -> tuple[Criterion, ...]:
    return (
        Criterion(
            "time-to-first-use",
            "months to first governed use case",
            0.12,
            12.0,
            2.0,
            Direction.LOWER,
            9.0,
            "months",
        ),
        Criterion(
            "compliant-success",
            "successful compliant task rate",
            0.22,
            0.70,
            0.98,
            Direction.HIGHER,
            0.90,
            "ratio",
            True,
        ),
        Criterion(
            "tenant-isolation",
            "forbidden cross-tenant outcomes",
            0.18,
            5.0,
            0.0,
            Direction.LOWER,
            0.0,
            "count",
            True,
        ),
        Criterion(
            "availability",
            "monthly availability",
            0.12,
            0.95,
            0.999,
            Direction.HIGHER,
            0.99,
            "ratio",
        ),
        Criterion(
            "annual-tco",
            "expected annualized cost",
            0.14,
            4_000_000.0,
            1_000_000.0,
            Direction.LOWER,
            3_500_000.0,
            "usd",
        ),
        Criterion(
            "portability", "tested exit score", 0.10, 0.0, 1.0, Direction.HIGHER, None, "score"
        ),
        Criterion(
            "team-cognitive-load",
            "survey and on-call load",
            0.07,
            10.0,
            1.0,
            Direction.LOWER,
            None,
            "score",
        ),
        Criterion(
            "strategic-differentiation",
            "business-specific capability score",
            0.05,
            0.0,
            1.0,
            Direction.HIGHER,
            None,
            "score",
        ),
    )


def demo_options() -> tuple[ArchitectureOption, ...]:
    return (
        ArchitectureOption(
            "point-solutions",
            "v1",
            "Team-owned point solutions",
            OptionKind.BUILD,
            "Each domain owns its full stack",
            "domain teams",
            frozenset({"speed", "local-control"}),
            frozenset({"multiple-model-providers"}),
            "standard export contracts",
        ),
        ArchitectureOption(
            "central-build",
            "v1",
            "Central custom AI platform",
            OptionKind.BUILD,
            "Platform team builds the whole control and runtime plane",
            "AI platform",
            frozenset({"governance", "shared-runtime", "customization"}),
            frozenset({"cloud-infrastructure"}),
            "open APIs and artifact export",
        ),
        ArchitectureOption(
            "hybrid-platform",
            "v1",
            "Governed platform with managed primitives",
            OptionKind.HYBRID,
            "Central trust/control plane plus domain-owned experiences and replaceable "
            "managed services",
            "AI platform + domains",
            frozenset({"governance", "shared-contracts", "domain-ownership", "managed-services"}),
            frozenset({"cloud-ai-services"}),
            "provider adapters, open telemetry, data and prompt export",
        ),
    )


def demo_evidence() -> tuple[OptionEvidence, ...]:
    values = {
        "point-solutions": (3.0, 0.88, 1.0, 0.985, 2_700_000.0, 0.70, 7.0, 0.70),
        "central-build": (11.0, 0.95, 0.0, 0.995, 3_600_000.0, 0.90, 8.0, 0.90),
        "hybrid-platform": (5.0, 0.94, 0.0, 0.995, 2_400_000.0, 0.82, 4.0, 0.85),
    }
    criteria = demo_criteria()
    rows: list[OptionEvidence] = []
    for option_id, observations in values.items():
        for criterion, observed in zip(criteria, observations, strict=True):
            rows.append(
                OptionEvidence(
                    f"evidence:{option_id}:{criterion.criterion_id}",
                    option_id,
                    "v1",
                    criterion.criterion_id,
                    observed,
                    criterion.unit,
                    "northstar-pilot-2026-q3",
                    "architecture-review-office",
                    0.85 if option_id != "hybrid-platform" else 0.90,
                    criterion.requires_independent_evidence,
                    1_000,
                    4_000,
                )
            )
    return tuple(rows)


def demo_economics() -> tuple[Economics, ...]:
    options = ("point-solutions", "central-build", "hybrid-platform")
    expected = (
        (350_000, 900_000, 1_000_000, 0.22, 250_000, 0.25, 1_500_000),
        (1_800_000, 650_000, 1_700_000, 0.14, 900_000, 0.20, 2_500_000),
        (900_000, 800_000, 900_000, 0.16, 600_000, 0.15, 1_500_000),
    )
    result = []
    for option_id, row in zip(options, expected, strict=True):
        migration, platform, people, unit, exit_cost, risk_probability, impact = row
        result.append(
            Economics(
                option_id,
                3,
                CostRange(migration * 0.8, migration, migration * 1.4),
                CostRange(platform * 0.85, platform, platform * 1.25),
                CostRange(people * 0.9, people, people * 1.2),
                CostRange(unit * 0.8, unit, unit * 1.4),
                1_000_000,
                CostRange(exit_cost * 0.7, exit_cost, exit_cost * 1.5),
                risk_probability,
                CostRange(impact * 0.5, impact, impact * 1.8),
            )
        )
    return tuple(result)


def demo_adr(evidence: Sequence[OptionEvidence] | None = None) -> ArchitectureDecisionRecord:
    proof = evidence or demo_evidence()
    base = ArchitectureDecisionRecord(
        "ADR-011",
        "Adopt a governed hybrid AI platform",
        DecisionStatus.ACCEPTED,
        "Northstar needs reusable trust controls without centralizing domain product decisions.",
        "Build the control plane and contracts; use replaceable managed runtime primitives.",
        "hybrid-platform",
        ("point-solutions", "central-build"),
        ("shared controls require platform ownership", "domain teams retain experience ownership"),
        tuple(item.evidence_id for item in proof if item.option_id == "hybrid-platform"),
        ("five qualified platform engineers", "provider export remains available"),
        (
            "adoption below 50 percent after two quarters",
            "unit cost above 0.35 USD",
            "exit test fails",
        ),
        "staff-architect",
        "architecture-review-chair",
        1_200,
        2_000,
        "",
    )
    return replace(base, decision_digest=canonical_adr_digest(base))


def demo_migration() -> tuple[MigrationStage, ...]:
    return (
        MigrationStage(
            "foundation",
            "Contracts and trust plane",
            (),
            "platform",
            ("ADR accepted",),
            ("identity, policy, telemetry and release contracts pass",),
            "retain current applications",
            ("critical control gap",),
            StageStatus.COMPLETE,
        ),
        MigrationStage(
            "pilot",
            "Two domain pilots",
            ("foundation",),
            "product + platform",
            ("foundation exit accepted",),
            ("quality, SLO, security and unit economics meet target",),
            "route pilots to existing services",
            ("forbidden outcome", "cost above threshold"),
            StageStatus.COMPLETE,
        ),
        MigrationStage(
            "scale",
            "Self-service paved road",
            ("pilot",),
            "platform",
            ("pilot evidence accepted",),
            ("four domains onboarded with support SLO",),
            "freeze onboarding and keep pilots",
            ("support load exceeds capacity",),
            StageStatus.PLANNED,
        ),
        MigrationStage(
            "consolidate",
            "Retire duplicate controls",
            ("scale",),
            "platform + domains",
            ("adoption and parity confirmed",),
            ("duplicate services decommissioned with data export",),
            "restore supported legacy path",
            ("exit or retention proof missing",),
            StageStatus.PLANNED,
        ),
    )


def run_demo_strategy() -> Mapping[str, object]:
    options = demo_options()
    criteria = demo_criteria()
    evidence = demo_evidence()
    trusted = frozenset({"architecture-review-office"})
    decisions = tuple(
        evaluate_option(option, criteria, evidence, trusted_producers=trusted, now=1_300)
        for option in options
    )
    ranking = rank_options(decisions)
    sensitivity = sensitivity_analysis(
        options, criteria, evidence, trusted_producers=trusted, now=1_300
    )
    economics = tuple(calculate_tco(item) for item in demo_economics())
    adr = demo_adr(evidence)
    adr_reasons = validate_adr(
        adr,
        known_options=frozenset(item.option_id for item in options),
        known_evidence=frozenset(item.evidence_id for item in evidence),
        now=1_300,
    )
    migration = assess_migration(demo_migration())
    return {
        "decisions": decisions,
        "ranking": ranking,
        "sensitivity": sensitivity,
        "economics": economics,
        "adr": adr,
        "adr_reasons": adr_reasons,
        "migration": migration,
    }


if __name__ == "__main__":
    demo = run_demo_strategy()
    ranking = cast(tuple[OptionDecision, ...], demo["ranking"])
    print("recommended:", ranking[0].option_id)
