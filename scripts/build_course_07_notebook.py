"""Build the canonical Course 7 notebook from reviewed source cells."""

from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
TARGET = (
    ROOT
    / "curriculum"
    / "advanced"
    / "07-ai-observability-reliability"
    / "ai_observability_reliability.ipynb"
)


def md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


def code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


cells = [
    md(
        """
        # Course 7 Lab — AI Observability and Reliability Engineering

        **Thesis:** operate AI systems with correlated, privacy-safe evidence and user-facing
        objectives; do not confuse transport success, retained traces, or verbose content with
        reliable service.

        This credential-free lab instruments Northstar's fictional model gateway, compares
        sampling policies, detects silent fallback, and runs a provider-failure game day. We
        evaluate every mitigation against explicit operational and privacy invariants.
        """
    ),
    md(
        """
        ## 1. Success contract

        We must reconstruct one request across boundaries, preserve complete SLI metrics under
        trace sampling, detect hidden fallback work, contain provider failure, and close an
        incident only after measured recovery. No prompt, output, credential, or private reasoning
        may enter telemetry.
        """
    ),
    md(
        """
        ## 2. Safety and reproducibility boundaries

        - No cloud account, model key, network call, or observability backend is needed.
        - Providers, timings, cost units, faults, and timestamps are deterministic fixtures.
        - Tenant identity is pseudonymized and every trace query remains tenant scoped.
        - Authorization context is never inferred from baggage or prompt text.
        - A passing lab proves only these fixtures and invariants, not production reliability.
        """
    ),
    code(
        """
        from dataclasses import replace

        from lab import (
            AlertSeverity,
            BreakerState,
            CircuitBreaker,
            MetricCardinalityGuard,
            ObservabilityPipeline,
            SLODefinition,
            TailPolicySampler,
            TelemetryContractError,
            TerminalState,
            build_baseline,
            build_silent_fallback_window,
            compare_sampling,
            compute_sli,
            demo_observation,
            detect_silent_fallback_regression,
            multiwindow_burn_alert,
            northstar_dashboard_contract,
            observability_decision_map,
            report_rows,
            run_failure_game_day,
            stable_digest,
        )

        print("Course 7 deterministic observability lab ready")
        """
    ),
    md(
        """
        ## 3. Inspect the operating decisions

        The lab starts with an explicit contract: application-owned outcomes, bounded metrics,
        no content capture, versioned semantic mappings, and human-owned incident closure.
        """
    ),
    code(
        """
        for concern, decision in observability_decision_map().items():
            print(f"{concern:14} → {decision}")
        """
    ),
    md(
        """
        ## 4. Record one correlated request

        One logical request produces a server span, a provider client span, and an application
        validation span. The provider and validator share the root parent. A log carries the same
        trace context; four low-cardinality metric points exist independently.
        """
    ),
    code(
        """
        pipeline = ObservabilityPipeline(sampler=TailPolicySampler(baseline_one_in=1))
        example = demo_observation(7)
        kept = pipeline.record(example, baggage={"service_tier": "gold", "user_email": "drop-me"})
        tenant_key = stable_digest(example.tenant_id)
        trace = pipeline.store.reconstruct(example.trace_id, tenant_key=tenant_key)
        print("kept:", kept, "spans:", len(trace), "metrics:", len(pipeline.store.metrics))
        for span in trace:
            print(span.name, "parent=", span.context.parent_span_id, "duration=", span.duration_ms)
        """
    ),
    md(
        """
        The email did not propagate because baggage uses an allowlist. Tenant scope is a digest in
        this lab; production pseudonymization still needs authorization, salt custody, rotation,
        retention, and reidentification analysis.
        """
    ),
    code(
        """
        print("tenant stored as:", trace[0].tenant_key)
        print("baggage stored as:", dict(trace[0].context.baggage))
        print(
            "cross-tenant query:",
            pipeline.store.reconstruct(example.trace_id, tenant_key=stable_digest("other")),
        )
        """
    ),
    md(
        """
        ## 5. Failure injection — attempt prohibited content capture

        Operational telemetry should normally use versions, digests, sizes, classifications, and
        reason codes. Full content raises privacy, security, volume, residency, retention, and
        prompt-injection risks.
        """
    ),
    code(
        """
        try:
            pipeline.record(replace(demo_observation(8), raw_prompt="private customer details"))
        except TelemetryContractError as error:
            print("blocked as designed:", error)
        """
    ),
    md(
        """
        ## 6. Failure injection — reject high-cardinality labels

        Trace identity belongs on spans and logs. It must not create a unique metric time series
        for every request.
        """
    ),
    code(
        """
        guard = MetricCardinalityGuard(max_values=3)
        try:
            guard.validate("ai.request.count", {"request_id": "request-7"})
        except TelemetryContractError as error:
            print("blocked as designed:", error)
        """
    ),
    md(
        """
        ## 7. Baseline — head sampling

        A head sampler decides at request start. It is efficient, but it cannot yet know that the
        request will fail, become slow, fall back, or end degraded.
        """
    ),
    code(
        """
        workload = [demo_observation(index) for index in range(50)]
        workload[1] = replace(
            workload[1],
            terminal_state=TerminalState.FAILED,
            compliant=False,
            error_kind="rare-provider-failure",
        )
        sampling = compare_sampling(workload)
        sampling
        """
    ),
    md(
        """
        ## 8. Mitigation — policy-based tail sampling

        The tail policy retains errors, slow requests, fallback, degradation, and a deterministic
        baseline. It captures the rare failure in this fixture. It also requires buffering and a
        Collector topology that sends every span for a trace to the same decision point.
        """
    ),
    code(
        """
        assert sampling["tail-policy"] == 1
        print("failure traces retained:", sampling["tail-policy"])
        print("head failure traces retained:", sampling["head-1-in-10"])
        """
    ),
    md(
        """
        ## 9. Evaluation — prove metrics do not depend on trace sampling

        Each observation emits four authoritative metric points before trace retention. Equal
        metric counts under both samplers protect SLI denominators from sampling bias.
        """
    ),
    code(
        """
        assert sampling["tail-policy-metrics"] == sampling["head-1-in-10-metrics"]
        print("metric points under either sampler:", sampling["tail-policy-metrics"])
        """
    ),
    md(
        """
        ## 10. Define the user-facing objective

        Eligible requests exclude explicit policy blocks. A good event must reach `succeeded` and
        pass application compliance validation. Latency is measured among compliant successes so
        fast failures cannot improve it.
        """
    ),
    code(
        """
        slo = SLODefinition(
            name="underwriting-compliant-success",
            target=0.95,
            window_minutes=30 * 24 * 60,
            latency_threshold_ms=1_000,
            minimum_events_for_page=10,
        )
        baseline = build_baseline(100)
        baseline_report = compute_sli(baseline, slo)
        report_rows(baseline_report)
        """
    ),
    md(
        """
        The cost denominator is successful compliant tasks. Every failed attempt, fallback, and
        losing hedge stays in the numerator. Report availability, latency, fallback, and cost
        separately rather than averaging them into an ownerless score.
        """
    ),
    md(
        """
        ## 11. Silent fallback baseline

        Ten percent of baseline requests use the reviewed premium fallback. User outcomes remain
        successful, but the fallback already has visible attempt, latency, model-mix, and cost
        consequences.
        """
    ),
    code(
        """
        baseline_small = build_baseline()
        current = build_silent_fallback_window()
        baseline_sli = compute_sli(baseline_small, slo)
        current_sli = compute_sli(current, slo)
        print("baseline compliant success:", baseline_sli.compliant_success_ratio)
        print("current compliant success: ", current_sli.compliant_success_ratio)
        print("baseline fallback:", baseline_sli.fallback_rate)
        print("current fallback: ", current_sli.fallback_rate)
        """
    ),
    md(
        """
        Aggregate compliant success stays green. A dashboard that stops there misses the
        dependency regression and the economic exposure.
        """
    ),
    code(
        """
        regression = detect_silent_fallback_regression(baseline_small, current)
        print("detected:", regression.detected)
        print("reasons:", regression.reasons)
        print("cost ratio:", round(regression.cost_change_ratio, 2))
        """
    ),
    md(
        """
        ## 12. Error-budget burn

        Burn rate normalizes observed bad events by the SLO's allowed bad-event ratio. A
        multiwindow alert requires both material long-window impact and an actively burning short
        window.
        """
    ),
    code(
        """
        failures = [
            replace(
                demo_observation(300 + index),
                terminal_state=TerminalState.FAILED if index < 10 else TerminalState.SUCCEEDED,
                compliant=index >= 10,
                error_kind="provider-unavailable" if index < 10 else "none",
            )
            for index in range(40)
        ]
        alert = multiwindow_burn_alert(
            failures,
            failures[:10],
            slo,
            burn_threshold=2.0,
            severity=AlertSeverity.PAGE,
        )
        alert
        """
    ),
    md(
        """
        ## 13. Low-traffic guard

        One failed request can imply an enormous burn rate in a tiny population. The lab marks it
        insufficient for a page. Production may pair a longer window with synthetic probes or a
        direct symptom alert; silently ignoring low traffic is not the answer.
        """
    ),
    code(
        """
        one_failure = [
            replace(
                demo_observation(500),
                terminal_state=TerminalState.FAILED,
                compliant=False,
            )
        ]
        low_traffic = multiwindow_burn_alert(one_failure, one_failure, slo, burn_threshold=2.0)
        print(low_traffic.firing, low_traffic.reason, round(low_traffic.long_window_burn, 1))
        """
    ),
    md(
        """
        ## 14. Circuit breaker mechanics

        Only retryable dependency failures contribute. The breaker opens, rejects work during the
        cooldown, permits one half-open probe, and closes only when that probe succeeds.
        """
    ),
    code(
        """
        breaker = CircuitBreaker(failure_threshold=3, recovery_after_ticks=5)
        for tick in range(3):
            assert breaker.allow(tick)
            breaker.record(tick=tick, success=False, retryable_dependency_failure=True)
        print("after failures:", breaker.state)
        print("allowed during cooldown:", breaker.allow(4))
        """
    ),
    code(
        """
        assert breaker.allow(7)
        print("probe state:", breaker.state)
        breaker.record(tick=7, success=True, retryable_dependency_failure=False)
        print("after successful probe:", breaker.state)
        assert breaker.state is BreakerState.CLOSED
        """
    ),
    md(
        """
        ## 15. Failure game day

        The exercise injects provider unavailability, opens the breaker, enters explicit human
        review, and saturates a batch bulkhead. Interactive capacity remains isolated. Recovery
        needs a successful probe and ten compliant requests; an accountable owner then closes the
        incident with dated follow-ups.
        """
    ),
    code(
        """
        game_day = run_failure_game_day()
        print("burn alert fired:", game_day.alert.firing)
        print("breaker final state:", game_day.breaker_state)
        print("isolated batch rejections:", game_day.isolated_rejections)
        print("incident status:", game_day.incident.status)
        """
    ),
    md(
        """
        ## 16. Inspect facts separately from hypotheses

        An incident timeline should distinguish observed telemetry from causal hypotheses. A model
        may summarize approved evidence, but it cannot establish root cause, prove recovery, or
        authorize closure.
        """
    ),
    code(
        """
        evidence = game_day.incident.evidence
        print("facts:")
        for fact in evidence.observed_facts:
            print(" -", fact)
        print("hypotheses:")
        for hypothesis in evidence.hypotheses:
            print(" -", hypothesis)
        """
    ),
    md(
        """
        ## 17. Dashboard contract

        A panel needs a question-bearing metric, explicit denominator, bounded slices, an owner,
        and an action. Pretty graphs without those fields are inventory, not an operating system.
        """
    ),
    code(
        """
        for panel in northstar_dashboard_contract():
            print(panel.title, "| denominator:", panel.denominator, "| owner:", panel.owner)
        """
    ),
    md(
        """
        ## 18. Production upgrade plan

        Replace the in-memory recorder with instrumented application boundaries and a pinned
        OpenTelemetry SDK. Export OTLP to authenticated Collectors; redact and classify before
        trust/region boundaries; emit authoritative low-cardinality metrics independently of trace
        sampling; route trace IDs consistently for tail decisions; isolate tenant queries; test
        queue/export loss; and deploy dashboards, burn alerts, and the runbook through review.

        Pilot at low traffic. Compare emitted fields and backend queries against the internal
        contract, inject provider and telemetry-pipeline failures, measure overhead and loss, test
        rollback, then expand. Do not enable prompt/output capture merely because an integration
        offers it.
        """
    ),
    md(
        """
        ## 19. Evidence checklist

        - telemetry dictionary with sensitivity, source, cardinality, retention, and owner;
        - trace-context and Collector data-flow diagram;
        - SLI population and good-event specification;
        - dashboard and alert definitions with runbook links;
        - resilience ADR and capacity assumptions;
        - game-day timeline, expected versus observed behavior, and cleanup;
        - incident report with facts, hypotheses, recovery proof, owners, dates, and retest; and
        - tool pilot with convention-version, privacy, loss, scale, cost, and exit evidence.
        """
    ),
    md(
        """
        ## 20. Reflection

        1. Which facts must be known before a span starts for head sampling?
        2. What failure occurs if tail-sampled spans land on different Collector instances?
        3. Which product denials belong outside the availability denominator, and why?
        4. What user harm could a successful but degraded response conceal?
        5. Which telemetry can an incident assistant see without expanding data exposure?
        6. What evidence would cause you to reverse the selected observability platform?
        """
    ),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.11"},
    },
)

TARGET.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, TARGET)
print(f"Wrote {TARGET.relative_to(ROOT)} with {len(cells)} cells")
