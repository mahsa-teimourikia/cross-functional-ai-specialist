from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest


def _load_course_module() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "curriculum"
        / "advanced"
        / "07-ai-observability-reliability"
        / "lab.py"
    )
    spec = importlib.util.spec_from_file_location("course_07_lab", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lab = _load_course_module()


def test_trace_has_stable_parent_child_correlation() -> None:
    pipeline = lab.ObservabilityPipeline(sampler=lab.TailPolicySampler(baseline_one_in=1))
    observation = lab.demo_observation(1)

    assert pipeline.record(observation)
    tenant_key = lab.stable_digest(observation.tenant_id)
    spans = pipeline.store.reconstruct(observation.trace_id, tenant_key=tenant_key)

    assert len(spans) == 3
    root = next(span for span in spans if span.context.parent_span_id is None)
    children = [span for span in spans if span.context.parent_span_id == root.context.span_id]
    assert len(children) == 2
    assert {span.context.trace_id for span in spans} == {observation.trace_id}


def test_cross_tenant_trace_query_returns_nothing() -> None:
    pipeline = lab.ObservabilityPipeline(sampler=lab.TailPolicySampler(baseline_one_in=1))
    observation = lab.demo_observation(2)
    pipeline.record(observation)

    spans = pipeline.store.reconstruct(
        observation.trace_id,
        tenant_key=lab.stable_digest("southstar"),
    )

    assert spans == []


def test_tenant_is_pseudonymized() -> None:
    pipeline = lab.ObservabilityPipeline(sampler=lab.TailPolicySampler(baseline_one_in=1))
    pipeline.record(lab.demo_observation(3))

    assert pipeline.store.spans
    assert all(span.tenant_key != "northstar" for span in pipeline.store.spans)


def test_raw_prompt_and_output_are_rejected_by_default() -> None:
    pipeline = lab.ObservabilityPipeline()
    observation = replace(
        lab.demo_observation(4),
        raw_prompt="customer private details",
        raw_output="private model response",
    )

    with pytest.raises(lab.TelemetryContractError, match="content capture is disabled"):
        pipeline.record(observation)


def test_even_content_capture_mode_does_not_record_raw_content_in_lab() -> None:
    policy = lab.TelemetryPolicy(content_capture=True)
    pipeline = lab.ObservabilityPipeline(policy=policy)

    with pytest.raises(lab.TelemetryContractError, match="never records raw model content"):
        pipeline.record(replace(lab.demo_observation(5), raw_prompt="do not log"))


def test_redactor_blocks_secrets_and_private_reasoning_fields() -> None:
    redactor = lab.Redactor(lab.TelemetryPolicy())

    for key in ("authorization", "provider.api_key", "private_reasoning", "raw_output"):
        with pytest.raises(lab.TelemetryContractError):
            redactor.sanitize_attributes({key: "sensitive"})


def test_baggage_uses_allowlist_and_drops_identity() -> None:
    redactor = lab.Redactor(lab.TelemetryPolicy())

    baggage = redactor.sanitize_baggage(
        {"service_tier": "gold", "region": "ca-central-1", "user_email": "x@example.test"}
    )

    assert baggage == {"service_tier": "gold", "region": "ca-central-1"}


def test_metric_guard_rejects_request_identity() -> None:
    guard = lab.MetricCardinalityGuard(20)

    with pytest.raises(lab.TelemetryContractError, match="high-cardinality"):
        guard.validate("ai.request.count", {"request_id": "request-1"})


def test_metric_guard_bounds_unreviewed_dimension_growth() -> None:
    guard = lab.MetricCardinalityGuard(2)
    guard.validate("ai.request.count", {"model_id": "m1"})
    guard.validate("ai.request.count", {"model_id": "m2"})

    with pytest.raises(lab.TelemetryContractError, match="exceeded"):
        guard.validate("ai.request.count", {"model_id": "m3"})


def test_unsampled_trace_still_emits_authoritative_metrics() -> None:
    class DropAll(lab.TraceSampler):
        def keep(self, spans: object) -> bool:
            return False

    pipeline = lab.ObservabilityPipeline(sampler=DropAll())

    kept = pipeline.record(lab.demo_observation(6))

    assert not kept
    assert pipeline.store.spans == []
    assert len(pipeline.store.metrics) == 4
    assert len(pipeline.outcomes) == 1


def test_tail_sampling_keeps_errors_slow_fallbacks_and_degradation() -> None:
    sampler = lab.TailPolicySampler(latency_threshold_ms=1_000, baseline_one_in=1_000_000)
    pipeline = lab.ObservabilityPipeline(sampler=sampler)
    cases = [
        lab.demo_observation(
            10,
            terminal_state=lab.TerminalState.FAILED,
            compliant=False,
            error_kind="timeout",
        ),
        lab.demo_observation(11, latency_ms=1_100),
        lab.demo_observation(12, fallback_used=True, model_id="premium-ca", attempts=2),
        lab.demo_observation(
            13,
            terminal_state=lab.TerminalState.DEGRADED,
            compliant=False,
            degradation_mode=lab.DegradationMode.HUMAN_REVIEW,
        ),
    ]

    assert all(pipeline.record(item) for item in cases)


def test_tail_sampling_retains_more_failures_than_head_sampling() -> None:
    observations = [lab.demo_observation(index) for index in range(50)]
    observations[1] = replace(
        observations[1],
        terminal_state=lab.TerminalState.FAILED,
        compliant=False,
        error_kind="rare-failure",
    )

    comparison = lab.compare_sampling(observations)

    assert comparison["tail-policy"] == 1
    assert comparison["tail-policy"] >= comparison["head-1-in-10"]
    assert comparison["tail-policy-metrics"] == comparison["head-1-in-10-metrics"] == 200


def test_sli_excludes_policy_blocked_requests_from_eligible_population() -> None:
    observations = [
        lab.demo_observation(1),
        lab.demo_observation(
            2,
            terminal_state=lab.TerminalState.BLOCKED,
            compliant=False,
            error_kind="policy-denied",
        ),
    ]
    slo = lab.SLODefinition("compliant-success", 0.9, 60, 1_000)

    report = lab.compute_sli(observations, slo)

    assert report.eligible_requests == 1
    assert report.compliant_success_ratio == 1.0


def test_transport_success_is_not_compliant_success() -> None:
    observations = [
        lab.demo_observation(1),
        lab.demo_observation(2, compliant=False),
    ]
    report = lab.compute_sli(
        observations,
        lab.SLODefinition("compliant-success", 0.9, 60, 1_000),
    )

    assert report.successful_compliant == 1
    assert report.compliant_success_ratio == 0.5


def test_cost_denominator_is_successful_compliant_tasks() -> None:
    observations = [
        lab.demo_observation(1, cost_units=1.0),
        lab.demo_observation(
            2,
            cost_units=1.0,
            terminal_state=lab.TerminalState.FAILED,
            compliant=False,
        ),
    ]
    report = lab.compute_sli(
        observations,
        lab.SLODefinition("compliant-success", 0.9, 60, 1_000),
    )

    assert report.total_cost_units == 2.0
    assert report.cost_per_successful_compliant_task == 2.0


def test_latency_sli_is_conditioned_on_compliant_success() -> None:
    observations = [
        lab.demo_observation(1, latency_ms=900),
        lab.demo_observation(2, latency_ms=1_100),
        lab.demo_observation(
            3,
            latency_ms=200,
            terminal_state=lab.TerminalState.FAILED,
            compliant=False,
        ),
    ]
    report = lab.compute_sli(
        observations,
        lab.SLODefinition("compliant-success", 0.9, 60, 1_000),
    )

    assert report.latency_success_ratio == 0.5
    assert report.p95_latency_ms == 1_100


def test_error_budget_uses_event_population() -> None:
    observations = lab.build_baseline(100)
    observations = lab.clone_with_failures(observations, {0, 1, 2})
    report = lab.compute_sli(
        observations,
        lab.SLODefinition("compliant-success", 0.95, 60, 1_000),
    )

    assert report.allowed_bad_events == 5
    assert report.consumed_bad_events == 3
    assert report.remaining_bad_events == 2


def test_multiwindow_burn_requires_both_windows() -> None:
    slo = lab.SLODefinition("compliant-success", 0.95, 60, 1_000, minimum_events_for_page=5)
    long_window = lab.clone_with_failures(lab.build_baseline(40), {0, 1, 2, 3, 4})
    recovered_short_window = lab.build_baseline(10)

    alert = lab.multiwindow_burn_alert(
        long_window,
        recovered_short_window,
        slo,
        burn_threshold=2.0,
    )

    assert alert.long_window_burn >= 2.0
    assert alert.short_window_burn == 0.0
    assert not alert.firing


def test_multiwindow_burn_pages_on_sustained_failure() -> None:
    slo = lab.SLODefinition("compliant-success", 0.95, 60, 1_000, minimum_events_for_page=5)
    long_window = lab.clone_with_failures(lab.build_baseline(40), set(range(10)))
    short_window = long_window[-10:]
    short_window = lab.clone_with_failures(short_window, set(range(5)))

    alert = lab.multiwindow_burn_alert(
        long_window,
        short_window,
        slo,
        burn_threshold=2.0,
    )

    assert alert.firing
    assert alert.reason == "sustained-error-budget-burn"


def test_low_traffic_does_not_page_from_one_event() -> None:
    slo = lab.SLODefinition("compliant-success", 0.99, 60, 1_000, minimum_events_for_page=20)
    failed = [
        lab.demo_observation(
            1,
            terminal_state=lab.TerminalState.FAILED,
            compliant=False,
        )
    ]

    alert = lab.multiwindow_burn_alert(failed, failed, slo, burn_threshold=2.0)

    assert not alert.firing
    assert alert.reason == "insufficient-event-volume"


def test_silent_fallback_regression_uses_route_model_mix_and_cost() -> None:
    finding = lab.detect_silent_fallback_regression(
        lab.build_baseline(),
        lab.build_silent_fallback_window(),
    )

    assert finding.detected
    assert set(finding.reasons) == {
        "fallback-rate-shift",
        "model-mix-shift",
        "cost-per-request-shift",
    }


def test_breaker_opens_after_retryable_dependency_failures() -> None:
    breaker = lab.CircuitBreaker(failure_threshold=3, recovery_after_ticks=5)
    for tick in range(3):
        assert breaker.allow(tick)
        breaker.record(tick=tick, success=False, retryable_dependency_failure=True)

    assert breaker.state is lab.BreakerState.OPEN
    assert not breaker.allow(4)


def test_policy_or_safety_failure_does_not_trip_dependency_breaker() -> None:
    breaker = lab.CircuitBreaker(failure_threshold=1)
    assert breaker.allow(0)
    breaker.record(tick=0, success=False, retryable_dependency_failure=False)

    assert breaker.state is lab.BreakerState.CLOSED


def test_breaker_allows_one_half_open_probe_and_recovers() -> None:
    breaker = lab.CircuitBreaker(failure_threshold=1, recovery_after_ticks=2)
    assert breaker.allow(0)
    breaker.record(tick=0, success=False, retryable_dependency_failure=True)

    assert breaker.allow(2)
    assert breaker.state is lab.BreakerState.HALF_OPEN
    assert not breaker.allow(2)
    breaker.record(tick=2, success=True, retryable_dependency_failure=False)

    assert breaker.state is lab.BreakerState.CLOSED


def test_failed_half_open_probe_reopens_breaker() -> None:
    breaker = lab.CircuitBreaker(failure_threshold=1, recovery_after_ticks=2)
    breaker.allow(0)
    breaker.record(tick=0, success=False, retryable_dependency_failure=True)
    breaker.allow(2)
    breaker.record(tick=2, success=False, retryable_dependency_failure=True)

    assert breaker.state is lab.BreakerState.OPEN
    assert not breaker.allow(3)


def test_bulkhead_isolates_pools() -> None:
    bulkhead = lab.Bulkhead({"interactive": 1, "batch": 1})

    assert bulkhead.acquire("batch")
    assert not bulkhead.acquire("batch")
    assert bulkhead.acquire("interactive")


def test_bulkhead_rejects_unknown_pool_and_bad_release() -> None:
    bulkhead = lab.Bulkhead({"interactive": 1})

    assert not bulkhead.acquire("unknown")
    with pytest.raises(RuntimeError):
        bulkhead.release("interactive")


def test_degradation_is_explicit_not_counted_as_full_success() -> None:
    degraded = lab.demo_observation(
        1,
        terminal_state=lab.TerminalState.DEGRADED,
        compliant=False,
        degradation_mode=lab.DegradationMode.HUMAN_REVIEW,
    )
    report = lab.compute_sli(
        [degraded],
        lab.SLODefinition("compliant-success", 0.9, 60, 1_000),
    )

    assert report.degraded_rate == 1.0
    assert report.compliant_success_ratio == 0.0


def test_incident_cannot_close_without_recovery_and_follow_up() -> None:
    incident = lab.IncidentRecord(
        "INC-test",
        "Test incident",
        "on-call",
        lab.IncidentStatus.OPEN,
        0,
        lab.IncidentEvidence((), "test", (), (), ()),
    )

    with pytest.raises(RuntimeError):
        incident.close(minute=1, owner_approved=True)
    incident.begin_mitigation()
    incident.mark_recovered(minute=2, recovery_proven=True)
    with pytest.raises(RuntimeError, match="follow-up"):
        incident.close(minute=3, owner_approved=True)


def test_incident_cannot_be_closed_by_unapproved_model_claim() -> None:
    incident = lab.IncidentRecord(
        "INC-test",
        "Test incident",
        "on-call",
        lab.IncidentStatus.OPEN,
        0,
        lab.IncidentEvidence((), "test", (), (), ()),
    )
    incident.begin_mitigation()

    with pytest.raises(RuntimeError, match="measured proof"):
        incident.mark_recovered(minute=2, recovery_proven=False)


def test_retention_expires_all_signal_types() -> None:
    pipeline = lab.ObservabilityPipeline(sampler=lab.TailPolicySampler(baseline_one_in=1))
    pipeline.record(lab.demo_observation(1, minute=1))
    pipeline.record(lab.demo_observation(2, minute=100))

    pipeline.store.expire(now_minute=101, retention_minutes=10)

    assert {span.context.trace_id for span in pipeline.store.spans} == {f"{3:032x}"}
    assert {log.trace_id for log in pipeline.store.logs} == {f"{3:032x}"}
    assert {metric.timestamp_ms for metric in pipeline.store.metrics} == {100 * 60_000}


def test_dashboard_panels_name_owner_action_and_denominator() -> None:
    panels = lab.northstar_dashboard_contract()

    assert len(panels) == 4
    assert all(panel.owner and panel.action and panel.denominator for panel in panels)
    assert any("successful compliant" in panel.denominator for panel in panels)


def test_failure_game_day_produces_closed_evidence_backed_incident() -> None:
    result = lab.run_failure_game_day()

    assert result.fallback_regression.detected
    assert result.alert.firing
    assert result.breaker_state is lab.BreakerState.CLOSED
    assert result.isolated_rejections == 1
    assert result.incident.status is lab.IncidentStatus.CLOSED
    assert result.incident.evidence.trace_ids
    assert result.incident.follow_ups


def test_observability_decision_map_covers_operational_boundaries() -> None:
    decision_map = lab.observability_decision_map()

    assert {"content", "metrics", "sampling", "objectives", "resilience", "incidents"} <= set(
        decision_map
    )
    assert "never record secrets" in decision_map["content"]
