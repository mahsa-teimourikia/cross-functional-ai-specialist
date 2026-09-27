"""Deterministic Course 7 lab: privacy-safe AI observability and reliability.

The module intentionally uses the Python standard library.  It models the contracts that an
OpenTelemetry SDK, Collector, metrics backend, tracing backend, and incident system would enforce
without requiring credentials or network services.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from hashlib import sha256
from math import ceil


class TerminalState(StrEnum):
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"
    BLOCKED = "blocked"


class SpanStatus(StrEnum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AlertSeverity(StrEnum):
    PAGE = "page"
    TICKET = "ticket"


class IncidentStatus(StrEnum):
    OPEN = "open"
    MITIGATING = "mitigating"
    RECOVERED = "recovered"
    CLOSED = "closed"


class DegradationMode(StrEnum):
    NONE = "none"
    PREMIUM_FALLBACK = "premium_fallback"
    READ_ONLY_CACHE = "read_only_cache"
    HUMAN_REVIEW = "human_review"


FORBIDDEN_ATTRIBUTE_FRAGMENTS = (
    "authorization",
    "api_key",
    "secret",
    "password",
    "raw_prompt",
    "raw_output",
    "chain_of_thought",
    "private_reasoning",
)
HIGH_CARDINALITY_METRIC_KEYS = {
    "request_id",
    "trace_id",
    "span_id",
    "user_id",
    "session_id",
    "case_id",
    "prompt",
    "output",
}


def stable_digest(value: str, *, salt: str = "northstar-observability-v1") -> str:
    """Return a deterministic pseudonymous digest for lab fixtures.

    Production salts belong in a secret manager and should be rotated under an explicit linkage
    policy. A digest lowers exposure; it is not anonymization when identifiers can be guessed.
    """

    return sha256(f"{salt}:{value}".encode()).hexdigest()[:16]


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    sampled: bool = True
    baggage: Mapping[str, str] = field(default_factory=dict)

    def child(self, span_id: str) -> TraceContext:
        return TraceContext(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=self.span_id,
            sampled=self.sampled,
            baggage=dict(self.baggage),
        )


@dataclass(frozen=True)
class SpanRecord:
    context: TraceContext
    tenant_key: str
    name: str
    kind: str
    start_ms: int
    end_ms: int
    status: SpanStatus
    attributes: Mapping[str, str | int | float | bool]

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass(frozen=True)
class LogRecord:
    timestamp_ms: int
    severity: str
    event_name: str
    trace_id: str
    span_id: str
    tenant_key: str
    attributes: Mapping[str, str | int | float | bool]


@dataclass(frozen=True)
class MetricPoint:
    timestamp_ms: int
    name: str
    value: float
    unit: str
    dimensions: Mapping[str, str]


@dataclass(frozen=True)
class RequestObservation:
    """Authoritative request outcome, recorded before trace sampling."""

    minute: int
    request_id: str
    trace_id: str
    tenant_id: str
    task_type: str
    route_policy: str
    prompt_version: str
    policy_version: str
    model_id: str
    provider: str
    terminal_state: TerminalState
    compliant: bool
    latency_ms: int
    cost_units: float
    attempts: int = 1
    fallback_used: bool = False
    degradation_mode: DegradationMode = DegradationMode.NONE
    error_kind: str = "none"
    raw_prompt: str | None = None
    raw_output: str | None = None

    @property
    def eligible(self) -> bool:
        return self.terminal_state is not TerminalState.BLOCKED

    @property
    def successful_compliant(self) -> bool:
        return self.terminal_state is TerminalState.SUCCEEDED and self.compliant


@dataclass(frozen=True)
class TelemetryPolicy:
    contract_version: str = "northstar.telemetry/v1"
    retention_minutes: int = 43_200
    content_capture: bool = False
    pseudonymize_tenant: bool = True
    max_metric_dimension_values: int = 20


class TelemetryContractError(ValueError):
    """Raised when telemetry would violate the reviewed contract."""


class Redactor:
    def __init__(self, policy: TelemetryPolicy) -> None:
        self.policy = policy

    def tenant_key(self, tenant_id: str) -> str:
        return stable_digest(tenant_id) if self.policy.pseudonymize_tenant else tenant_id

    def sanitize_baggage(self, baggage: Mapping[str, str]) -> dict[str, str]:
        allowed = {"service_tier", "region"}
        return {key: value for key, value in baggage.items() if key in allowed}

    def sanitize_attributes(
        self,
        attributes: Mapping[str, str | int | float | bool | None],
    ) -> dict[str, str | int | float | bool]:
        clean: dict[str, str | int | float | bool] = {}
        for key, value in attributes.items():
            normalized = key.lower()
            if any(fragment in normalized for fragment in FORBIDDEN_ATTRIBUTE_FRAGMENTS):
                raise TelemetryContractError(f"forbidden telemetry attribute: {key}")
            if value is not None:
                clean[key] = value
        return clean


class MetricCardinalityGuard:
    """Reject identity-like labels and bound values per dimension."""

    def __init__(self, max_values: int) -> None:
        self.max_values = max_values
        self._seen: dict[tuple[str, str], set[str]] = defaultdict(set)

    def validate(self, metric_name: str, dimensions: Mapping[str, str]) -> None:
        for key, value in dimensions.items():
            if key in HIGH_CARDINALITY_METRIC_KEYS:
                raise TelemetryContractError(f"high-cardinality metric dimension: {key}")
            bucket = self._seen[(metric_name, key)]
            if value not in bucket and len(bucket) >= self.max_values:
                raise TelemetryContractError(
                    f"metric dimension {key} exceeded {self.max_values} values"
                )
            bucket.add(value)


class TraceSampler:
    def keep(self, spans: Sequence[SpanRecord]) -> bool:
        raise NotImplementedError


class HeadRatioSampler(TraceSampler):
    """Decide from trace identity before the outcome is known."""

    def __init__(self, keep_one_in: int) -> None:
        if keep_one_in < 1:
            raise ValueError("keep_one_in must be positive")
        self.keep_one_in = keep_one_in

    def keep(self, spans: Sequence[SpanRecord]) -> bool:
        if not spans:
            return False
        trace_number = int(sha256(spans[0].context.trace_id.encode()).hexdigest(), 16)
        return trace_number % self.keep_one_in == 0


class TailPolicySampler(TraceSampler):
    """Keep important completed traces plus a deterministic baseline sample."""

    def __init__(self, *, latency_threshold_ms: int = 1_000, baseline_one_in: int = 10) -> None:
        self.latency_threshold_ms = latency_threshold_ms
        self.baseline = HeadRatioSampler(baseline_one_in)

    def keep(self, spans: Sequence[SpanRecord]) -> bool:
        if not spans:
            return False
        if any(span.status is SpanStatus.ERROR for span in spans):
            return True
        root = min(spans, key=lambda item: item.start_ms)
        if root.duration_ms >= self.latency_threshold_ms:
            return True
        if any(bool(span.attributes.get("ai.fallback.used")) for span in spans):
            return True
        if any(
            span.attributes.get("ai.terminal_state") == TerminalState.DEGRADED.value
            for span in spans
        ):
            return True
        return self.baseline.keep(spans)


@dataclass
class TelemetryStore:
    spans: list[SpanRecord] = field(default_factory=list)
    logs: list[LogRecord] = field(default_factory=list)
    metrics: list[MetricPoint] = field(default_factory=list)

    def traces_for_tenant(self, tenant_key: str) -> list[SpanRecord]:
        return [span for span in self.spans if span.tenant_key == tenant_key]

    def reconstruct(self, trace_id: str, *, tenant_key: str) -> list[SpanRecord]:
        selected = [
            span
            for span in self.spans
            if span.context.trace_id == trace_id and span.tenant_key == tenant_key
        ]
        return sorted(selected, key=lambda item: (item.start_ms, item.end_ms, item.name))

    def expire(self, *, now_minute: int, retention_minutes: int) -> None:
        cutoff_ms = (now_minute - retention_minutes) * 60_000
        self.spans = [span for span in self.spans if span.end_ms >= cutoff_ms]
        self.logs = [log for log in self.logs if log.timestamp_ms >= cutoff_ms]
        self.metrics = [metric for metric in self.metrics if metric.timestamp_ms >= cutoff_ms]


class ObservabilityPipeline:
    """Create correlated signals while keeping aggregate metrics independent of trace sampling."""

    def __init__(
        self,
        *,
        policy: TelemetryPolicy | None = None,
        sampler: TraceSampler | None = None,
        store: TelemetryStore | None = None,
    ) -> None:
        self.policy = policy or TelemetryPolicy()
        self.sampler = sampler or TailPolicySampler()
        self.store = store or TelemetryStore()
        self.redactor = Redactor(self.policy)
        self.cardinality = MetricCardinalityGuard(self.policy.max_metric_dimension_values)
        self.outcomes: list[RequestObservation] = []

    def _metric(
        self,
        observation: RequestObservation,
        name: str,
        value: float,
        unit: str,
        dimensions: Mapping[str, str],
    ) -> None:
        self.cardinality.validate(name, dimensions)
        self.store.metrics.append(
            MetricPoint(observation.minute * 60_000, name, value, unit, dict(dimensions))
        )

    def record(
        self,
        observation: RequestObservation,
        *,
        baggage: Mapping[str, str] | None = None,
    ) -> bool:
        """Record one logical request; return whether its trace was retained."""

        if observation.raw_prompt is not None or observation.raw_output is not None:
            if not self.policy.content_capture:
                raise TelemetryContractError(
                    "content capture is disabled by the telemetry contract"
                )
            raise TelemetryContractError("this lab never records raw model content")

        self.outcomes.append(observation)
        tenant_key = self.redactor.tenant_key(observation.tenant_id)
        safe_baggage = self.redactor.sanitize_baggage(baggage or {})
        start = observation.minute * 60_000
        root_context = TraceContext(
            observation.trace_id,
            f"root-{observation.request_id}",
            baggage=safe_baggage,
        )
        provider_context = root_context.child(f"provider-{observation.request_id}")
        result_context = root_context.child(f"result-{observation.request_id}")
        error = observation.terminal_state in {TerminalState.FAILED, TerminalState.BLOCKED}
        common = {
            "telemetry.contract.version": self.policy.contract_version,
            "ai.task.type": observation.task_type,
            "ai.route.policy": observation.route_policy,
            "ai.prompt.version": observation.prompt_version,
            "ai.policy.version": observation.policy_version,
            "ai.model.id": observation.model_id,
            "ai.provider.name": observation.provider,
        }
        root_attributes = self.redactor.sanitize_attributes(
            {
                **common,
                "ai.terminal_state": observation.terminal_state.value,
                "ai.compliant": observation.compliant,
                "ai.attempt.count": observation.attempts,
                "ai.fallback.used": observation.fallback_used,
                "ai.degradation.mode": observation.degradation_mode.value,
                "ai.error.kind": observation.error_kind,
                "ai.cost.units": observation.cost_units,
            }
        )
        spans = [
            SpanRecord(
                root_context,
                tenant_key,
                "northstar.underwriting.request",
                "server",
                start,
                start + observation.latency_ms,
                SpanStatus.ERROR if error else SpanStatus.OK,
                root_attributes,
            ),
            SpanRecord(
                provider_context,
                tenant_key,
                f"chat {observation.model_id}",
                "client",
                start + 10,
                start + max(10, observation.latency_ms - 15),
                (
                    SpanStatus.ERROR
                    if observation.error_kind not in {"none", "fallback"}
                    else SpanStatus.OK
                ),
                self.redactor.sanitize_attributes(
                    {
                        **common,
                        "gen_ai.operation.name": "chat",
                        "ai.attempt.count": observation.attempts,
                        "ai.fallback.used": observation.fallback_used,
                    }
                ),
            ),
            SpanRecord(
                result_context,
                tenant_key,
                "northstar.result.validate",
                "internal",
                start + max(10, observation.latency_ms - 15),
                start + observation.latency_ms,
                SpanStatus.OK if observation.compliant else SpanStatus.ERROR,
                self.redactor.sanitize_attributes(
                    {
                        "ai.result.compliant": observation.compliant,
                        "ai.terminal_state": observation.terminal_state.value,
                    }
                ),
            ),
        ]
        kept = self.sampler.keep(spans)
        if kept:
            self.store.spans.extend(spans)
            self.store.logs.append(
                LogRecord(
                    start + observation.latency_ms,
                    "ERROR" if error else "INFO",
                    "ai.request.completed",
                    observation.trace_id,
                    root_context.span_id,
                    tenant_key,
                    self.redactor.sanitize_attributes(
                        {
                            "ai.terminal_state": observation.terminal_state.value,
                            "ai.error.kind": observation.error_kind,
                            "ai.fallback.used": observation.fallback_used,
                        }
                    ),
                )
            )

        dimensions = {
            "task_type": observation.task_type,
            "route_policy": observation.route_policy,
            "terminal_state": observation.terminal_state.value,
            "model_id": observation.model_id,
        }
        self._metric(observation, "ai.request.count", 1.0, "{request}", dimensions)
        self._metric(
            observation, "ai.request.duration", float(observation.latency_ms), "ms", dimensions
        )
        self._metric(observation, "ai.request.cost", observation.cost_units, "{unit}", dimensions)
        self._metric(
            observation,
            "ai.provider.attempts",
            float(observation.attempts),
            "{attempt}",
            dimensions,
        )
        return kept


@dataclass(frozen=True)
class SLODefinition:
    name: str
    target: float
    window_minutes: int
    latency_threshold_ms: int
    minimum_events_for_page: int = 20

    def __post_init__(self) -> None:
        if not 0 < self.target < 1:
            raise ValueError("SLO target must be between zero and one")
        if self.window_minutes < 1 or self.latency_threshold_ms < 1:
            raise ValueError("SLO windows and thresholds must be positive")


@dataclass(frozen=True)
class SLIReport:
    eligible_requests: int
    successful_compliant: int
    fast_successes: int
    compliant_success_ratio: float
    latency_success_ratio: float
    p95_latency_ms: int
    fallback_rate: float
    degraded_rate: float
    total_cost_units: float
    cost_per_successful_compliant_task: float | None
    allowed_bad_events: int
    consumed_bad_events: int
    remaining_bad_events: int


def percentile(values: Sequence[int], quantile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def compute_sli(
    observations: Iterable[RequestObservation],
    slo: SLODefinition,
) -> SLIReport:
    eligible = [item for item in observations if item.eligible]
    count = len(eligible)
    successes = [item for item in eligible if item.successful_compliant]
    fast = [item for item in successes if item.latency_ms <= slo.latency_threshold_ms]
    fallbacks = sum(item.fallback_used for item in eligible)
    degraded = sum(item.terminal_state is TerminalState.DEGRADED for item in eligible)
    cost = sum(item.cost_units for item in eligible)
    allowed = int(count * (1.0 - slo.target))
    bad = count - len(successes)
    return SLIReport(
        eligible_requests=count,
        successful_compliant=len(successes),
        fast_successes=len(fast),
        compliant_success_ratio=len(successes) / count if count else 0.0,
        latency_success_ratio=len(fast) / len(successes) if successes else 0.0,
        p95_latency_ms=percentile([item.latency_ms for item in eligible], 0.95),
        fallback_rate=fallbacks / count if count else 0.0,
        degraded_rate=degraded / count if count else 0.0,
        total_cost_units=cost,
        cost_per_successful_compliant_task=cost / len(successes) if successes else None,
        allowed_bad_events=allowed,
        consumed_bad_events=bad,
        remaining_bad_events=allowed - bad,
    )


def error_ratio(observations: Iterable[RequestObservation]) -> tuple[float, int]:
    eligible = [item for item in observations if item.eligible]
    if not eligible:
        return 0.0, 0
    bad = sum(not item.successful_compliant for item in eligible)
    return bad / len(eligible), len(eligible)


@dataclass(frozen=True)
class BurnAlert:
    severity: AlertSeverity
    firing: bool
    long_window_burn: float
    short_window_burn: float
    long_window_events: int
    short_window_events: int
    reason: str


def multiwindow_burn_alert(
    long_window: Iterable[RequestObservation],
    short_window: Iterable[RequestObservation],
    slo: SLODefinition,
    *,
    burn_threshold: float,
    severity: AlertSeverity = AlertSeverity.PAGE,
) -> BurnAlert:
    long_ratio, long_count = error_ratio(long_window)
    short_ratio, short_count = error_ratio(short_window)
    budget_ratio = 1.0 - slo.target
    long_burn = long_ratio / budget_ratio
    short_burn = short_ratio / budget_ratio
    enough = min(long_count, short_count) >= slo.minimum_events_for_page
    firing = enough and long_burn >= burn_threshold and short_burn >= burn_threshold
    if not enough:
        reason = "insufficient-event-volume"
    elif firing:
        reason = "sustained-error-budget-burn"
    else:
        reason = "within-burn-threshold"
    return BurnAlert(
        severity,
        firing,
        long_burn,
        short_burn,
        long_count,
        short_count,
        reason,
    )


@dataclass(frozen=True)
class RegressionFinding:
    detected: bool
    baseline_fallback_rate: float
    current_fallback_rate: float
    baseline_premium_share: float
    current_premium_share: float
    cost_change_ratio: float
    reasons: tuple[str, ...]


def detect_silent_fallback_regression(
    baseline: Sequence[RequestObservation],
    current: Sequence[RequestObservation],
    *,
    fallback_rate_delta: float = 0.15,
    premium_share_delta: float = 0.15,
    cost_ratio_threshold: float = 1.25,
) -> RegressionFinding:
    def rate(items: Sequence[RequestObservation], predicate: object) -> float:
        if not items:
            return 0.0
        if predicate == "fallback":
            return sum(item.fallback_used for item in items) / len(items)
        return sum(item.model_id.startswith("premium") for item in items) / len(items)

    baseline_fallback = rate(baseline, "fallback")
    current_fallback = rate(current, "fallback")
    baseline_premium = rate(baseline, "premium")
    current_premium = rate(current, "premium")
    baseline_cost = sum(item.cost_units for item in baseline) / max(1, len(baseline))
    current_cost = sum(item.cost_units for item in current) / max(1, len(current))
    cost_ratio = current_cost / baseline_cost if baseline_cost else float("inf")
    reasons: list[str] = []
    if current_fallback - baseline_fallback >= fallback_rate_delta:
        reasons.append("fallback-rate-shift")
    if current_premium - baseline_premium >= premium_share_delta:
        reasons.append("model-mix-shift")
    if cost_ratio >= cost_ratio_threshold:
        reasons.append("cost-per-request-shift")
    return RegressionFinding(
        detected=len(reasons) >= 2,
        baseline_fallback_rate=baseline_fallback,
        current_fallback_rate=current_fallback,
        baseline_premium_share=baseline_premium,
        current_premium_share=current_premium,
        cost_change_ratio=cost_ratio,
        reasons=tuple(reasons),
    )


class CircuitBreaker:
    """Small deterministic closed/open/half-open breaker for retryable dependency failures."""

    def __init__(self, *, failure_threshold: int = 3, recovery_after_ticks: int = 5) -> None:
        if failure_threshold < 1 or recovery_after_ticks < 1:
            raise ValueError("breaker thresholds must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_after_ticks = recovery_after_ticks
        self.state = BreakerState.CLOSED
        self.consecutive_failures = 0
        self.opened_at: int | None = None
        self.probe_in_flight = False

    def allow(self, tick: int) -> bool:
        if self.state is BreakerState.OPEN:
            assert self.opened_at is not None
            if tick - self.opened_at < self.recovery_after_ticks:
                return False
            self.state = BreakerState.HALF_OPEN
        if self.state is BreakerState.HALF_OPEN:
            if self.probe_in_flight:
                return False
            self.probe_in_flight = True
        return True

    def record(self, *, tick: int, success: bool, retryable_dependency_failure: bool) -> None:
        if success:
            self.state = BreakerState.CLOSED
            self.consecutive_failures = 0
            self.opened_at = None
            self.probe_in_flight = False
            return
        if not retryable_dependency_failure:
            self.probe_in_flight = False
            return
        self.consecutive_failures += 1
        self.probe_in_flight = False
        if (
            self.state is BreakerState.HALF_OPEN
            or self.consecutive_failures >= self.failure_threshold
        ):
            self.state = BreakerState.OPEN
            self.opened_at = tick


class Bulkhead:
    """Per-pool concurrency admission; callers must release accepted work."""

    def __init__(self, limits: Mapping[str, int]) -> None:
        if not limits or any(value < 1 for value in limits.values()):
            raise ValueError("bulkhead limits must be positive")
        self.limits = dict(limits)
        self.active: Counter[str] = Counter()

    def acquire(self, pool: str) -> bool:
        if pool not in self.limits:
            return False
        if self.active[pool] >= self.limits[pool]:
            return False
        self.active[pool] += 1
        return True

    def release(self, pool: str) -> None:
        if self.active[pool] <= 0:
            raise RuntimeError("cannot release an inactive bulkhead slot")
        self.active[pool] -= 1


@dataclass(frozen=True)
class DashboardPanel:
    title: str
    metric: str
    denominator: str
    slices: tuple[str, ...]
    owner: str
    action: str


def northstar_dashboard_contract() -> tuple[DashboardPanel, ...]:
    return (
        DashboardPanel(
            "Compliant task success",
            "successful compliant / eligible requests",
            "eligible logical requests",
            ("task_type", "route_policy", "model_id"),
            "AI platform on-call",
            "Follow the SLO burn runbook",
        ),
        DashboardPanel(
            "Tail latency",
            "p95 and p99 logical request duration",
            "eligible logical requests",
            ("task_type", "route_policy", "terminal_state"),
            "AI platform on-call",
            "Inspect dependency and fallback spans",
        ),
        DashboardPanel(
            "Fallback and work amplification",
            "fallback requests and provider attempts / logical request",
            "eligible logical requests",
            ("provider", "model_id", "error_kind"),
            "Model gateway owner",
            "Check provider health, quotas, and routing versions",
        ),
        DashboardPanel(
            "Governed unit economics",
            "total cost / successful compliant task",
            "successful compliant tasks",
            ("task_type", "route_policy", "model_id"),
            "AI product owner",
            "Review route policy and workload mix",
        ),
    )


@dataclass(frozen=True)
class IncidentEvidence:
    trace_ids: tuple[str, ...]
    alert_reason: str
    observed_facts: tuple[str, ...]
    hypotheses: tuple[str, ...]
    actions: tuple[str, ...]


@dataclass
class IncidentRecord:
    incident_id: str
    title: str
    commander: str
    status: IncidentStatus
    opened_minute: int
    evidence: IncidentEvidence
    recovered_minute: int | None = None
    closed_minute: int | None = None
    follow_ups: list[str] = field(default_factory=list)

    def begin_mitigation(self) -> None:
        if self.status is not IncidentStatus.OPEN:
            raise RuntimeError("only an open incident can begin mitigation")
        self.status = IncidentStatus.MITIGATING

    def mark_recovered(self, *, minute: int, recovery_proven: bool) -> None:
        if self.status is not IncidentStatus.MITIGATING or not recovery_proven:
            raise RuntimeError("recovery requires mitigation state and measured proof")
        self.status = IncidentStatus.RECOVERED
        self.recovered_minute = minute

    def close(self, *, minute: int, owner_approved: bool) -> None:
        if self.status is not IncidentStatus.RECOVERED or not owner_approved:
            raise RuntimeError("closure requires proven recovery and accountable approval")
        if not self.follow_ups:
            raise RuntimeError("closure requires owned follow-up work")
        self.status = IncidentStatus.CLOSED
        self.closed_minute = minute


@dataclass(frozen=True)
class GameDayResult:
    observations: tuple[RequestObservation, ...]
    fallback_regression: RegressionFinding
    alert: BurnAlert
    breaker_state: BreakerState
    isolated_rejections: int
    incident: IncidentRecord


def demo_observation(
    index: int,
    *,
    minute: int | None = None,
    terminal_state: TerminalState = TerminalState.SUCCEEDED,
    compliant: bool = True,
    latency_ms: int = 420,
    cost_units: float = 0.25,
    model_id: str = "economy-ca",
    fallback_used: bool = False,
    attempts: int = 1,
    error_kind: str = "none",
    tenant_id: str = "northstar",
    degradation_mode: DegradationMode = DegradationMode.NONE,
) -> RequestObservation:
    return RequestObservation(
        minute=index if minute is None else minute,
        request_id=f"request-{index:04d}",
        trace_id=f"{index + 1:032x}",
        tenant_id=tenant_id,
        task_type="underwriting-summary",
        route_policy="economy-with-premium-fallback-v3",
        prompt_version="underwriting-summary-v8",
        policy_version="gateway-policy-v12",
        model_id=model_id,
        provider="fictional-provider",
        terminal_state=terminal_state,
        compliant=compliant,
        latency_ms=latency_ms,
        cost_units=cost_units,
        attempts=attempts,
        fallback_used=fallback_used,
        degradation_mode=degradation_mode,
        error_kind=error_kind,
    )


def build_baseline(count: int = 40) -> list[RequestObservation]:
    items: list[RequestObservation] = []
    for index in range(count):
        fallback = index % 10 == 0
        items.append(
            demo_observation(
                index,
                model_id="premium-ca" if fallback else "economy-ca",
                fallback_used=fallback,
                attempts=2 if fallback else 1,
                latency_ms=780 if fallback else 390 + index % 5 * 10,
                cost_units=0.72 if fallback else 0.22,
                error_kind="fallback" if fallback else "none",
            )
        )
    return items


def build_silent_fallback_window(count: int = 40, *, start: int = 100) -> list[RequestObservation]:
    items: list[RequestObservation] = []
    for offset in range(count):
        fallback = offset < 20
        items.append(
            demo_observation(
                start + offset,
                model_id="premium-ca" if fallback else "economy-ca",
                fallback_used=fallback,
                attempts=2 if fallback else 1,
                latency_ms=920 if fallback else 410,
                cost_units=0.82 if fallback else 0.22,
                error_kind="fallback" if fallback else "none",
            )
        )
    return items


def run_failure_game_day() -> GameDayResult:
    """Inject provider failure, exercise containment, alerting, and app-owned incident closure."""

    baseline = build_baseline()
    current = build_silent_fallback_window()
    breaker = CircuitBreaker(failure_threshold=3, recovery_after_ticks=5)
    bulkhead = Bulkhead({"interactive": 2, "batch": 1})
    observations: list[RequestObservation] = []
    rejected = 0

    # Two interactive requests remain isolated while a burst overwhelms the batch pool.
    assert bulkhead.acquire("interactive")
    assert bulkhead.acquire("interactive")
    assert bulkhead.acquire("batch")
    if not bulkhead.acquire("batch"):
        rejected += 1
    bulkhead.release("batch")
    bulkhead.release("interactive")
    bulkhead.release("interactive")

    for tick in range(30):
        if not breaker.allow(tick):
            observations.append(
                demo_observation(
                    200 + tick,
                    terminal_state=TerminalState.DEGRADED,
                    compliant=False,
                    latency_ms=90,
                    cost_units=0.02,
                    error_kind="circuit-open",
                    degradation_mode=DegradationMode.HUMAN_REVIEW,
                )
            )
            continue
        dependency_ok = tick >= 10
        breaker.record(
            tick=tick,
            success=dependency_ok,
            retryable_dependency_failure=not dependency_ok,
        )
        if dependency_ok:
            observations.append(demo_observation(200 + tick, latency_ms=430))
        else:
            observations.append(
                demo_observation(
                    200 + tick,
                    terminal_state=TerminalState.FAILED,
                    compliant=False,
                    latency_ms=1_100,
                    cost_units=0.25,
                    error_kind="provider-unavailable",
                )
            )

    slo = SLODefinition(
        "underwriting-compliant-success",
        target=0.95,
        window_minutes=30 * 24 * 60,
        latency_threshold_ms=1_000,
        minimum_events_for_page=5,
    )
    alert = multiwindow_burn_alert(
        observations[:10],
        observations[:5],
        slo,
        burn_threshold=2.0,
    )
    failed_trace_ids = tuple(
        item.trace_id for item in observations if not item.successful_compliant
    )[:5]
    incident = IncidentRecord(
        incident_id="INC-007",
        title="Underwriting provider failure and degraded review path",
        commander="AI platform on-call",
        status=IncidentStatus.OPEN,
        opened_minute=203,
        evidence=IncidentEvidence(
            trace_ids=failed_trace_ids,
            alert_reason=alert.reason,
            observed_facts=(
                "provider-unavailable errors crossed the burn threshold",
                "the circuit opened after three retryable failures",
                "batch overload did not consume interactive capacity",
            ),
            hypotheses=("primary provider regional impairment",),
            actions=("freeze gateway changes", "use explicit human-review degradation"),
        ),
    )
    incident.begin_mitigation()
    recovered = breaker.state is BreakerState.CLOSED and all(
        item.successful_compliant for item in observations[-10:]
    )
    incident.mark_recovered(minute=229, recovery_proven=recovered)
    incident.follow_ups.extend(
        [
            "Owner: gateway team — add provider saturation signal by 2026-10-15",
            "Owner: SRE — repeat the game day after alert tuning by 2026-10-22",
        ]
    )
    incident.close(minute=235, owner_approved=True)
    return GameDayResult(
        observations=tuple(observations),
        fallback_regression=detect_silent_fallback_regression(baseline, current),
        alert=alert,
        breaker_state=breaker.state,
        isolated_rejections=rejected,
        incident=incident,
    )


def compare_sampling(
    observations: Sequence[RequestObservation],
) -> dict[str, int]:
    results: dict[str, int] = {}
    for name, sampler in (
        ("head-1-in-10", HeadRatioSampler(10)),
        ("tail-policy", TailPolicySampler(latency_threshold_ms=1_000, baseline_one_in=10)),
    ):
        pipeline = ObservabilityPipeline(sampler=sampler)
        kept_failures = 0
        for observation in observations:
            kept = pipeline.record(observation)
            if kept and not observation.successful_compliant:
                kept_failures += 1
        results[name] = kept_failures
        results[f"{name}-traces"] = len({span.context.trace_id for span in pipeline.store.spans})
        results[f"{name}-metrics"] = len(pipeline.store.metrics)
    return results


def observability_decision_map() -> dict[str, str]:
    return {
        "signal source": "instrument application-owned outcomes before adapters",
        "correlation": "W3C-compatible trace identity plus explicit logical request/run IDs",
        "content": "off by default; never record secrets or private reasoning",
        "metrics": "low-cardinality dimensions and authoritative unsampled counters",
        "sampling": "tail-keep errors, slow traces, fallback, and degradation plus baseline",
        "objectives": "eligible population, compliant success, latency, cost, and error budget",
        "alerts": "multiwindow burn with a low-traffic rule and owned runbook",
        "resilience": "bounded retry, breaker, bulkhead, and typed degradation",
        "incidents": "facts separate from hypotheses; application owners prove recovery/closure",
        "portability": "pin and map evolving GenAI semantic-convention versions",
    }


def report_rows(report: SLIReport) -> list[dict[str, str | int | float]]:
    return [
        {"metric": "eligible requests", "value": report.eligible_requests},
        {"metric": "compliant success", "value": round(report.compliant_success_ratio, 4)},
        {"metric": "latency success", "value": round(report.latency_success_ratio, 4)},
        {"metric": "p95 latency ms", "value": report.p95_latency_ms},
        {"metric": "fallback rate", "value": round(report.fallback_rate, 4)},
        {"metric": "remaining bad events", "value": report.remaining_bad_events},
        {
            "metric": "cost / compliant success",
            "value": round(report.cost_per_successful_compliant_task or 0.0, 4),
        },
    ]


def clone_with_failures(
    observations: Sequence[RequestObservation],
    failure_indexes: set[int],
) -> list[RequestObservation]:
    return [
        replace(
            item,
            terminal_state=TerminalState.FAILED,
            compliant=False,
            error_kind="injected-failure",
        )
        if index in failure_indexes
        else item
        for index, item in enumerate(observations)
    ]
