"""Deterministic Course 12 lab for enterprise AI operating models and leadership."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


def stable_digest(value: object) -> str:
    """Return a stable digest for an auditable decision subject."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


class RiskTier(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    PROHIBITED = "prohibited"


class PortfolioDisposition(StrEnum):
    FUND = "fund"
    EXPERIMENT = "experiment"
    HOLD = "hold"
    STOP = "stop"
    REFER = "refer"


class ControlMode(StrEnum):
    SELF_SERVICE = "self-service"
    GUARDED = "guarded"
    INDEPENDENT_REVIEW = "independent-review"
    PROHIBITED = "prohibited"


class DecisionKind(StrEnum):
    PRODUCT_OUTCOME = "product-outcome"
    PLATFORM_STANDARD = "platform-standard"
    RISK_ACCEPTANCE = "risk-acceptance"
    PRODUCTION_RELEASE = "production-release"
    PROVIDER_CONTRACT = "provider-contract"
    POLICY_EXCEPTION = "policy-exception"


class MaturityLevel(StrEnum):
    PROVISIONAL = "provisional"
    OPERATIONAL = "operational"
    SCALABLE = "scalable"
    OPTIMIZING = "optimizing"


class DissentStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted-risk"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class PortfolioCandidate:
    candidate_id: str
    version: str
    domain: str
    sponsor: str
    owner: str
    outcome: str
    strategic_alignment: float
    expected_annual_value: float
    feasibility: float
    reuse_potential: float
    risk_tier: RiskTier
    data_approved: bool
    annual_cost: float
    team_capacity: int
    duplicate_group: str | None = None
    dependencies: tuple[str, ...] = ()
    sunk_cost: float = 0.0


@dataclass(frozen=True)
class PortfolioEvidence:
    evidence_id: str
    candidate_id: str
    candidate_version: str
    metric: str
    value: float
    unit: str
    producer: str
    observed_at: int
    expires_at: int
    independent: bool = False


@dataclass(frozen=True)
class CandidateAssessment:
    candidate_id: str
    disposition: PortfolioDisposition
    score: float | None
    reasons: tuple[str, ...]


REQUIRED_EVIDENCE: Mapping[str, str] = {
    "annual-value": "usd/year",
    "feasibility": "score",
    "outcome-confidence": "score",
}


def assess_candidate(
    candidate: PortfolioCandidate,
    evidence: Sequence[PortfolioEvidence],
    *,
    trusted_producers: frozenset[str],
    now: int,
) -> CandidateAssessment:
    """Triage one candidate with hard gates before preference scoring."""
    hard: list[str] = []
    if not candidate.candidate_id or not candidate.version:
        hard.append("missing-identity")
    if not candidate.sponsor:
        hard.append("missing-sponsor")
    if not candidate.owner:
        hard.append("missing-owner")
    if not candidate.outcome:
        hard.append("missing-outcome")
    if candidate.risk_tier is RiskTier.PROHIBITED:
        hard.append("prohibited-use")
    if candidate.risk_tier in {RiskTier.MODERATE, RiskTier.HIGH} and not candidate.data_approved:
        hard.append("unapproved-data")
    if candidate.annual_cost <= 0 or candidate.team_capacity <= 0:
        hard.append("invalid-resource-request")
    if hard:
        return CandidateAssessment(
            candidate.candidate_id,
            PortfolioDisposition.STOP,
            None,
            tuple(hard),
        )

    matching = [
        item
        for item in evidence
        if item.candidate_id == candidate.candidate_id
        and item.candidate_version == candidate.version
    ]
    reasons: list[str] = []
    values: dict[str, float] = {}
    for metric, unit in REQUIRED_EVIDENCE.items():
        records = [item for item in matching if item.metric == metric]
        if not records:
            reasons.append(f"missing-evidence:{metric}")
            continue
        if len(records) != 1:
            reasons.append(f"duplicate-evidence:{metric}")
            continue
        record = records[0]
        if record.producer not in trusted_producers:
            reasons.append(f"untrusted-evidence:{metric}")
        elif record.expires_at < now or record.observed_at > now:
            reasons.append(f"stale-evidence:{metric}")
        elif record.unit != unit:
            reasons.append(f"unit-mismatch:{metric}")
        elif not isfinite(record.value):
            reasons.append(f"invalid-evidence:{metric}")
        elif metric == "outcome-confidence" and not record.independent:
            reasons.append("independent-evidence-required:outcome-confidence")
        else:
            values[metric] = record.value
    if reasons:
        return CandidateAssessment(
            candidate.candidate_id,
            PortfolioDisposition.REFER,
            None,
            tuple(reasons),
        )

    confidence = values["outcome-confidence"]
    if not 0 <= confidence <= 1 or not 0 <= values["feasibility"] <= 1:
        return CandidateAssessment(
            candidate.candidate_id,
            PortfolioDisposition.REFER,
            None,
            ("evidence-out-of-range",),
        )
    if values["annual-value"] != candidate.expected_annual_value:
        return CandidateAssessment(
            candidate.candidate_id,
            PortfolioDisposition.REFER,
            None,
            ("value-evidence-mismatch",),
        )
    benefit_cost = min(candidate.expected_annual_value / candidate.annual_cost, 5.0) / 5.0
    score = round(
        0.25 * candidate.strategic_alignment
        + 0.20 * candidate.feasibility
        + 0.15 * candidate.reuse_potential
        + 0.20 * confidence
        + 0.20 * benefit_cost,
        4,
    )
    if confidence < 0.55 or candidate.feasibility < 0.55:
        return CandidateAssessment(
            candidate.candidate_id,
            PortfolioDisposition.EXPERIMENT,
            score,
            ("bounded-learning-needed",),
        )
    return CandidateAssessment(
        candidate.candidate_id,
        PortfolioDisposition.FUND,
        score,
        ("eligible-for-portfolio",),
    )


@dataclass(frozen=True)
class PortfolioSelection:
    funded: tuple[str, ...]
    experiments: tuple[str, ...]
    held: tuple[str, ...]
    stopped: tuple[str, ...]
    referred: tuple[str, ...]
    annual_cost: float
    team_capacity: int
    reasons: Mapping[str, str]


def select_portfolio(
    candidates: Sequence[PortfolioCandidate],
    assessments: Sequence[CandidateAssessment],
    *,
    budget: float,
    capacity: int,
    max_high_risk: int = 2,
) -> PortfolioSelection:
    """Select a deterministic, constrained portfolio without sunk-cost preference."""
    if budget <= 0 or capacity <= 0 or max_high_risk < 0:
        raise ValueError("portfolio constraints must be positive")
    by_id = {item.candidate_id: item for item in candidates}
    if len(by_id) != len(candidates):
        raise ValueError("candidate IDs must be unique")
    assessed = {item.candidate_id: item for item in assessments}
    if set(assessed) != set(by_id):
        raise ValueError("every candidate requires exactly one assessment")

    funded: list[str] = []
    experiments: list[str] = []
    held: list[str] = []
    stopped: list[str] = []
    referred: list[str] = []
    reasons: dict[str, str] = {}
    spent = 0.0
    used_capacity = 0
    high_risk = 0
    funded_groups: set[str] = set()
    ordered = sorted(
        assessments,
        key=lambda item: (-(item.score if item.score is not None else -1), item.candidate_id),
    )
    for assessment in ordered:
        item = by_id[assessment.candidate_id]
        if assessment.disposition is PortfolioDisposition.STOP:
            stopped.append(item.candidate_id)
            reasons[item.candidate_id] = assessment.reasons[0]
            continue
        if assessment.disposition is PortfolioDisposition.REFER:
            referred.append(item.candidate_id)
            reasons[item.candidate_id] = assessment.reasons[0]
            continue
        if assessment.disposition is PortfolioDisposition.EXPERIMENT:
            experiment_cost = round(item.annual_cost * 0.1, 2)
            experiment_capacity = max(1, item.team_capacity // 4)
            if (
                spent + experiment_cost <= budget
                and used_capacity + experiment_capacity <= capacity
            ):
                experiments.append(item.candidate_id)
                spent += experiment_cost
                used_capacity += experiment_capacity
                reasons[item.candidate_id] = "bounded-experiment"
            else:
                held.append(item.candidate_id)
                reasons[item.candidate_id] = "experiment-capacity-unavailable"
            continue
        if any(dependency not in funded for dependency in item.dependencies):
            held.append(item.candidate_id)
            reasons[item.candidate_id] = "dependency-not-funded"
            continue
        if item.duplicate_group and item.duplicate_group in funded_groups:
            held.append(item.candidate_id)
            reasons[item.candidate_id] = "duplicate-capability"
            continue
        if item.risk_tier is RiskTier.HIGH and high_risk >= max_high_risk:
            held.append(item.candidate_id)
            reasons[item.candidate_id] = "high-risk-cap-reached"
            continue
        if spent + item.annual_cost > budget:
            held.append(item.candidate_id)
            reasons[item.candidate_id] = "budget-exhausted"
            continue
        if used_capacity + item.team_capacity > capacity:
            held.append(item.candidate_id)
            reasons[item.candidate_id] = "capacity-exhausted"
            continue
        funded.append(item.candidate_id)
        spent += item.annual_cost
        used_capacity += item.team_capacity
        if item.duplicate_group:
            funded_groups.add(item.duplicate_group)
        if item.risk_tier is RiskTier.HIGH:
            high_risk += 1
        reasons[item.candidate_id] = "selected-by-evidence-and-constraints"
    return PortfolioSelection(
        tuple(funded),
        tuple(experiments),
        tuple(held),
        tuple(stopped),
        tuple(referred),
        round(spent, 2),
        used_capacity,
        reasons,
    )


@dataclass(frozen=True)
class ControlProfile:
    mode: ControlMode
    required_controls: frozenset[str]
    independent_review: bool


def control_profile(risk_tier: RiskTier) -> ControlProfile:
    """Map risk to proportionate governance; risk text never grants authority."""
    profiles = {
        RiskTier.LOW: ControlProfile(
            ControlMode.SELF_SERVICE,
            frozenset({"inventory", "owner", "evaluation"}),
            False,
        ),
        RiskTier.MODERATE: ControlProfile(
            ControlMode.GUARDED,
            frozenset({"inventory", "owner", "evaluation", "threat-model", "monitoring"}),
            False,
        ),
        RiskTier.HIGH: ControlProfile(
            ControlMode.INDEPENDENT_REVIEW,
            frozenset(
                {
                    "inventory",
                    "owner",
                    "evaluation",
                    "threat-model",
                    "monitoring",
                    "human-oversight",
                }
            ),
            True,
        ),
        RiskTier.PROHIBITED: ControlProfile(ControlMode.PROHIBITED, frozenset(), True),
    }
    return profiles[risk_tier]


@dataclass(frozen=True)
class ExceptionRequest:
    request_id: str
    requester: str
    candidate_id: str
    candidate_version: str
    policy_id: str
    control_id: str
    rationale: str
    compensating_controls: tuple[str, ...]


@dataclass(frozen=True)
class ExceptionReceipt:
    receipt_id: str
    request_digest: str
    approver: str
    policy_version: str
    issued_at: int
    expires_at: int
    used: bool = False


def issue_exception(
    request: ExceptionRequest,
    *,
    approver: str,
    authorized_approvers: frozenset[str],
    policy_version: str,
    now: int,
    ttl: int,
    prohibited_controls: frozenset[str] = frozenset(),
) -> ExceptionReceipt:
    if request.control_id in prohibited_controls:
        raise ValueError("control is non-waivable")
    if not request.rationale or not request.compensating_controls:
        raise ValueError("exception requires rationale and compensating controls")
    if approver == request.requester or approver not in authorized_approvers:
        raise PermissionError("independent authorized approver required")
    if ttl <= 0:
        raise ValueError("exception must expire")
    digest = stable_digest(request)
    return ExceptionReceipt(
        f"exception-{digest[:12]}", digest, approver, policy_version, now, now + ttl
    )


def validate_exception(
    request: ExceptionRequest,
    receipt: ExceptionReceipt,
    *,
    current_policy_version: str,
    now: int,
) -> None:
    if receipt.used:
        raise ValueError("exception already consumed")
    if receipt.expires_at < now:
        raise ValueError("exception expired")
    if receipt.policy_version != current_policy_version:
        raise ValueError("exception policy is stale")
    if receipt.request_digest != stable_digest(request):
        raise ValueError("exception subject changed")


@dataclass(frozen=True)
class DecisionRight:
    kind: DecisionKind
    accountable: str
    responsible: tuple[str, ...]
    consulted: tuple[str, ...]
    informed: tuple[str, ...]
    escalation_owner: str
    escalation_hours: int


def validate_decision_rights(rights: Sequence[DecisionRight]) -> None:
    required = set(DecisionKind)
    kinds = [item.kind for item in rights]
    if set(kinds) != required or len(kinds) != len(required):
        raise ValueError("decision matrix must cover each decision once")
    for item in rights:
        if not item.accountable or not item.responsible or not item.escalation_owner:
            raise ValueError(f"incomplete ownership:{item.kind}")
        if item.accountable in item.informed:
            raise ValueError(f"accountable owner cannot be informed-only:{item.kind}")
        if item.escalation_hours <= 0:
            raise ValueError(f"invalid escalation SLA:{item.kind}")


@dataclass(frozen=True)
class ServiceOffering:
    service_id: str
    owner: str
    consumer: str
    outcome: str
    service_level: str
    support_path: str
    eligibility: str
    onboarding: str
    quotas: str
    version: str
    deprecation_days: int
    exit_path: str
    unit_cost: float


def validate_service_catalog(services: Sequence[ServiceOffering]) -> None:
    identifiers: set[str] = set()
    for service in services:
        if service.service_id in identifiers:
            raise ValueError("duplicate service ID")
        identifiers.add(service.service_id)
        required = (
            service.owner,
            service.consumer,
            service.outcome,
            service.service_level,
            service.support_path,
            service.eligibility,
            service.onboarding,
            service.quotas,
            service.version,
            service.exit_path,
        )
        if not all(required):
            raise ValueError(f"incomplete service contract:{service.service_id}")
        if service.deprecation_days < 30 or service.unit_cost < 0:
            raise ValueError(f"invalid lifecycle or cost:{service.service_id}")


@dataclass(frozen=True)
class MaturityEvidence:
    evidence_id: str
    dimension: str
    level: MaturityLevel
    producer: str
    observed_at: int
    expires_at: int


@dataclass(frozen=True)
class MaturityAssessment:
    levels: Mapping[str, MaturityLevel]
    overall: MaturityLevel | None
    gaps: tuple[str, ...]


MATURITY_DIMENSIONS = (
    "strategy",
    "product",
    "data",
    "engineering",
    "evaluation",
    "security",
    "operations",
    "platform",
    "people",
)


def assess_maturity(
    evidence: Sequence[MaturityEvidence],
    *,
    trusted_producers: frozenset[str],
    now: int,
) -> MaturityAssessment:
    levels: dict[str, MaturityLevel] = {}
    gaps: list[str] = []
    for dimension in MATURITY_DIMENSIONS:
        records = [item for item in evidence if item.dimension == dimension]
        if len(records) != 1:
            gaps.append(f"missing-or-duplicate:{dimension}")
            continue
        record = records[0]
        if record.producer not in trusted_producers or record.expires_at < now:
            gaps.append(f"untrusted-or-stale:{dimension}")
            continue
        levels[dimension] = record.level
    if gaps:
        return MaturityAssessment(levels, None, tuple(gaps))
    order = list(MaturityLevel)
    overall = min(levels.values(), key=order.index)
    return MaturityAssessment(levels, overall, ())


@dataclass(frozen=True)
class RoadmapInitiative:
    initiative_id: str
    quarter: int
    owner: str
    outcome_metric: str
    baseline: float
    target: float
    cost: float
    capacity: int
    dependencies: tuple[str, ...]
    exit_criteria: str
    kill_criteria: str


@dataclass(frozen=True)
class RoadmapAssessment:
    valid: bool
    quarterly_cost: Mapping[int, float]
    quarterly_capacity: Mapping[int, int]
    reasons: tuple[str, ...]


def assess_roadmap(
    initiatives: Sequence[RoadmapInitiative],
    *,
    quarterly_budget: Mapping[int, float],
    quarterly_capacity: Mapping[int, int],
) -> RoadmapAssessment:
    by_id = {item.initiative_id: item for item in initiatives}
    reasons: list[str] = []
    if len(by_id) != len(initiatives):
        reasons.append("duplicate-initiative")
    costs: dict[int, float] = {}
    capacities: dict[int, int] = {}
    for item in initiatives:
        if item.quarter not in {1, 2, 3, 4}:
            reasons.append(f"invalid-quarter:{item.initiative_id}")
        if (
            not item.owner
            or not item.outcome_metric
            or not item.exit_criteria
            or not item.kill_criteria
        ):
            reasons.append(f"incomplete-contract:{item.initiative_id}")
        if item.baseline == item.target:
            reasons.append(f"no-outcome-change:{item.initiative_id}")
        for dependency in item.dependencies:
            predecessor = by_id.get(dependency)
            if predecessor is None or predecessor.quarter >= item.quarter:
                reasons.append(f"invalid-dependency:{item.initiative_id}:{dependency}")
        costs[item.quarter] = costs.get(item.quarter, 0.0) + item.cost
        capacities[item.quarter] = capacities.get(item.quarter, 0) + item.capacity
    for quarter, cost in costs.items():
        if cost > quarterly_budget.get(quarter, 0):
            reasons.append(f"budget-exceeded:q{quarter}")
    for quarter, amount in capacities.items():
        if amount > quarterly_capacity.get(quarter, 0):
            reasons.append(f"capacity-exceeded:q{quarter}")
    return RoadmapAssessment(not reasons, costs, capacities, tuple(reasons))


@dataclass(frozen=True)
class InvestmentScenario:
    name: str
    annual_benefits: tuple[float, ...]
    annual_costs: tuple[float, ...]
    adoption_probability: float


@dataclass(frozen=True)
class InvestmentResult:
    name: str
    npv: float
    discounted_benefit: float
    discounted_cost: float
    benefit_cost_ratio: float
    break_even_year: int | None


def evaluate_investment(
    scenario: InvestmentScenario,
    *,
    discount_rate: float,
) -> InvestmentResult:
    if len(scenario.annual_benefits) != len(scenario.annual_costs) or not scenario.annual_costs:
        raise ValueError("benefit and cost horizons must match")
    if not 0 <= scenario.adoption_probability <= 1 or discount_rate <= -1:
        raise ValueError("invalid investment assumptions")
    benefits = 0.0
    costs = 0.0
    cumulative = 0.0
    break_even: int | None = None
    for year, (benefit, cost) in enumerate(
        zip(scenario.annual_benefits, scenario.annual_costs, strict=True), start=1
    ):
        factor = (1 + discount_rate) ** year
        discounted_benefit = benefit * scenario.adoption_probability / factor
        discounted_cost = cost / factor
        benefits += discounted_benefit
        costs += discounted_cost
        cumulative += discounted_benefit - discounted_cost
        if cumulative >= 0 and break_even is None:
            break_even = year
    ratio = benefits / costs if costs else float("inf")
    return InvestmentResult(
        scenario.name,
        round(benefits - costs, 2),
        round(benefits, 2),
        round(costs, 2),
        round(ratio, 4),
        break_even,
    )


@dataclass(frozen=True)
class DissentRecord:
    decision_id: str
    proposal_digest: str
    objector: str
    evidence_ids: tuple[str, ...]
    decision_owner: str
    response: str
    status: DissentStatus
    unresolved_risks: tuple[str, ...]
    escalation_owner: str | None = None


def validate_dissent(record: DissentRecord) -> None:
    if not record.decision_id or not record.proposal_digest or not record.objector:
        raise ValueError("dissent must bind a decision and proposal")
    if not record.evidence_ids:
        raise ValueError("dissent requires inspectable evidence")
    if not record.decision_owner or not record.response:
        raise ValueError("accountable response required")
    if record.status is DissentStatus.RESOLVED and record.unresolved_risks:
        raise ValueError("resolved dissent cannot hide unresolved risks")
    if record.status is DissentStatus.ESCALATED and not record.escalation_owner:
        raise ValueError("escalation requires an owner")


@dataclass(frozen=True)
class DelegationContract:
    objective: str
    delegate: str
    decision_boundary: str
    resources: tuple[str, ...]
    check_in_days: int
    escalation_trigger: str
    definition_of_done: str
    learning_outcome: str


def validate_delegation(contract: DelegationContract) -> None:
    values = (
        contract.objective,
        contract.delegate,
        contract.decision_boundary,
        contract.escalation_trigger,
        contract.definition_of_done,
        contract.learning_outcome,
    )
    if not all(values) or not contract.resources or contract.check_in_days <= 0:
        raise ValueError(
            "delegation needs outcome, authority boundary, support, review and learning"
        )


@dataclass(frozen=True)
class PortfolioMetrics:
    total: int
    funded_rate: float
    stopped_early_rate: float
    evidence_gap_rate: float
    shared_capability_rate: float
    spend_per_funded_outcome: float | None


def portfolio_metrics(
    candidates: Sequence[PortfolioCandidate], selection: PortfolioSelection
) -> PortfolioMetrics:
    total = len(candidates)
    if total == 0:
        raise ValueError("metrics require candidates")
    funded_candidates = [item for item in candidates if item.candidate_id in selection.funded]
    shared = sum(item.reuse_potential >= 0.7 for item in funded_candidates)
    return PortfolioMetrics(
        total,
        round(len(selection.funded) / total, 4),
        round(len(selection.stopped) / total, 4),
        round(len(selection.referred) / total, 4),
        round(shared / len(funded_candidates), 4) if funded_candidates else 0.0,
        round(selection.annual_cost / len(funded_candidates), 2) if funded_candidates else None,
    )


def demo_candidates(count: int = 70) -> tuple[PortfolioCandidate, ...]:
    """Create a deterministic synthetic 70-PoC portfolio."""
    if count <= 0:
        raise ValueError("candidate count must be positive")
    domains = ("underwriting", "claims", "service", "finance", "operations")
    items: list[PortfolioCandidate] = []
    for index in range(1, count + 1):
        risk = (
            RiskTier.HIGH
            if index % 11 == 0
            else RiskTier.MODERATE
            if index % 4 == 0
            else RiskTier.LOW
        )
        if index % 23 == 0:
            risk = RiskTier.PROHIBITED
        items.append(
            PortfolioCandidate(
                candidate_id=f"poc-{index:02d}",
                version="v1",
                domain=domains[(index - 1) % len(domains)],
                sponsor=f"sponsor-{(index - 1) % 8 + 1}",
                owner="" if index % 29 == 0 else f"owner-{(index - 1) % 12 + 1}",
                outcome=f"reduce cycle time for workflow {index}",
                strategic_alignment=round(0.45 + (index % 6) * 0.09, 2),
                expected_annual_value=float(120_000 + (index % 10) * 45_000),
                feasibility=round(0.48 + (index % 7) * 0.07, 2),
                reuse_potential=round(0.35 + (index % 5) * 0.14, 2),
                risk_tier=risk,
                data_approved=index % 17 != 0,
                annual_cost=float(80_000 + (index % 8) * 25_000),
                team_capacity=1 + index % 4,
                duplicate_group=f"capability-{index % 9}" if index % 3 == 0 else None,
                dependencies=("poc-01",) if index in {10, 20, 30} else (),
                sunk_cost=float((index % 5) * 50_000),
            )
        )
    return tuple(items)


def demo_evidence(
    candidates: Sequence[PortfolioCandidate] | None = None,
) -> tuple[PortfolioEvidence, ...]:
    portfolio = demo_candidates() if candidates is None else candidates
    records: list[PortfolioEvidence] = []
    for item in portfolio:
        values = {
            "annual-value": (item.expected_annual_value, "usd/year", False),
            "feasibility": (item.feasibility, "score", False),
            "outcome-confidence": (0.48 + (int(item.candidate_id[-2:]) % 7) * 0.08, "score", True),
        }
        for metric, (value, unit, independent) in values.items():
            records.append(
                PortfolioEvidence(
                    f"ev-{item.candidate_id}-{metric}",
                    item.candidate_id,
                    item.version,
                    metric,
                    float(value),
                    unit,
                    "portfolio-evidence-office",
                    1_000,
                    2_000,
                    independent,
                )
            )
    return tuple(records)


def demo_decision_rights() -> tuple[DecisionRight, ...]:
    return (
        DecisionRight(
            DecisionKind.PRODUCT_OUTCOME,
            "product",
            ("domain-team",),
            ("risk",),
            ("platform",),
            "portfolio-council",
            48,
        ),
        DecisionRight(
            DecisionKind.PLATFORM_STANDARD,
            "platform",
            ("platform-team",),
            ("security", "domains"),
            ("product",),
            "cto",
            72,
        ),
        DecisionRight(
            DecisionKind.RISK_ACCEPTANCE,
            "risk",
            ("risk-office",),
            ("legal", "security"),
            ("product",),
            "cro",
            24,
        ),
        DecisionRight(
            DecisionKind.PRODUCTION_RELEASE,
            "service-owner",
            ("delivery-team",),
            ("security", "sre"),
            ("product",),
            "engineering-vp",
            8,
        ),
        DecisionRight(
            DecisionKind.PROVIDER_CONTRACT,
            "procurement",
            ("vendor-office",),
            ("legal", "platform", "finance"),
            ("domains",),
            "cfo",
            120,
        ),
        DecisionRight(
            DecisionKind.POLICY_EXCEPTION,
            "control-owner",
            ("governance",),
            ("risk", "security"),
            ("requester",),
            "cro",
            24,
        ),
    )


def demo_services() -> tuple[ServiceOffering, ...]:
    return (
        ServiceOffering(
            "model-gateway",
            "platform",
            "AI product teams",
            "governed inference",
            "99.9% monthly",
            "platform-on-call",
            "registered workload",
            "self-service template",
            "budget and rate policy",
            "v1",
            90,
            "direct provider adapter",
            0.012,
        ),
        ServiceOffering(
            "evaluation-service",
            "evaluation-office",
            "AI product teams",
            "release evidence",
            "one business day",
            "evaluation-help",
            "versioned dataset",
            "repository workflow",
            "20 runs/day",
            "v1",
            60,
            "portable evaluation bundle",
            35.0,
        ),
        ServiceOffering(
            "risk-review",
            "risk-office",
            "high-risk owners",
            "independent decision",
            "five business days",
            "risk-intake",
            "complete system card",
            "intake form",
            "10 reviews/month",
            "v2",
            60,
            "external assurance path",
            2_500.0,
        ),
    )


def demo_maturity_evidence() -> tuple[MaturityEvidence, ...]:
    levels = {
        "strategy": MaturityLevel.SCALABLE,
        "product": MaturityLevel.OPERATIONAL,
        "data": MaturityLevel.OPERATIONAL,
        "engineering": MaturityLevel.SCALABLE,
        "evaluation": MaturityLevel.OPERATIONAL,
        "security": MaturityLevel.SCALABLE,
        "operations": MaturityLevel.OPERATIONAL,
        "platform": MaturityLevel.OPERATIONAL,
        "people": MaturityLevel.PROVISIONAL,
    }
    return tuple(
        MaturityEvidence(
            f"maturity-{dimension}", dimension, level, "assurance-office", 1_000, 2_000
        )
        for dimension, level in levels.items()
    )


def demo_roadmap() -> tuple[RoadmapInitiative, ...]:
    return (
        RoadmapInitiative(
            "decision-rights",
            1,
            "cto",
            "decisions with one accountable owner",
            0.4,
            1.0,
            120_000,
            2,
            (),
            "matrix approved and sampled",
            "ownership conflicts remain",
        ),
        RoadmapInitiative(
            "portfolio-gate",
            2,
            "portfolio-lead",
            "PoCs with outcome and evidence",
            0.2,
            0.9,
            180_000,
            3,
            ("decision-rights",),
            "70 PoCs triaged",
            "false-stop rate exceeds 10%",
        ),
        RoadmapInitiative(
            "paved-road",
            3,
            "platform-lead",
            "median compliant path lead days",
            45,
            10,
            300_000,
            5,
            ("portfolio-gate",),
            "three services meet SLO",
            "adoption below 30%",
        ),
        RoadmapInitiative(
            "scale-review",
            4,
            "coo",
            "scaled compliant outcomes",
            0,
            6,
            220_000,
            3,
            ("paved-road",),
            "six outcomes verified",
            "unit value remains negative",
        ),
    )


def demo_investments() -> tuple[InvestmentScenario, ...]:
    return (
        InvestmentScenario("low", (0, 400_000, 700_000), (700_000, 500_000, 450_000), 0.45),
        InvestmentScenario("base", (0, 900_000, 1_500_000), (700_000, 550_000, 500_000), 0.70),
        InvestmentScenario("high", (0, 1_400_000, 2_400_000), (700_000, 600_000, 550_000), 0.85),
    )


def run_demo_operating_model() -> Mapping[str, object]:
    candidates = demo_candidates()
    evidence = demo_evidence(candidates)
    assessments = tuple(
        assess_candidate(
            item,
            evidence,
            trusted_producers=frozenset({"portfolio-evidence-office"}),
            now=1_300,
        )
        for item in candidates
    )
    selection = select_portfolio(candidates, assessments, budget=2_500_000, capacity=45)
    return {
        "candidate_count": len(candidates),
        "selection": selection,
        "metrics": portfolio_metrics(candidates, selection),
        "maturity": assess_maturity(
            demo_maturity_evidence(),
            trusted_producers=frozenset({"assurance-office"}),
            now=1_300,
        ),
        "roadmap": assess_roadmap(
            demo_roadmap(),
            quarterly_budget={1: 200_000, 2: 250_000, 3: 350_000, 4: 250_000},
            quarterly_capacity={1: 3, 2: 4, 3: 6, 4: 4},
        ),
        "investments": tuple(
            evaluate_investment(item, discount_rate=0.08) for item in demo_investments()
        ),
    }
