"""Build the canonical Course 6 notebook from reviewed source cells."""

from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
TARGET = (
    ROOT
    / "curriculum"
    / "advanced"
    / "06-model-gateways-inference-economics"
    / "model_gateways_inference_economics.ipynb"
)


def md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


def code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


cells = [
    md(
        """
        # Course 6 Lab — Model Gateways and Inference Economics

        **Thesis:** model access is a policy and economics boundary balancing task quality,
        latency, availability, privacy, safety, and cost—not one provider SDK call.

        This credential-free lab compares direct, cascade, fallback, and delayed-hedge policies
        for Northstar's underwriting summaries. All providers are deterministic fictional
        simulators, so the notebook proves gateway behavior and metric arithmetic rather than live
        model quality or vendor pricing.
        """
    ),
    md(
        """
        ## 1. Scenario and success contract

        Northstar has an inexpensive fast model and a stronger slower model. Restricted data must
        stay in Canada. A successful task returns the correct labelled decision through an eligible
        model, passes schema and case binding, meets the deadline, and remains inside hard token and
        cost budgets.

        We will select the least expensive policy that satisfies a compliant-success floor and
        p95-latency ceiling. HTTP success and fluent prose do not define success.
        """
    ),
    md(
        """
        ## 2. Safety and reproducibility boundaries

        - No provider account, API key, cloud resource, network call, or paid inference is used.
        - Cost units and model behavior are fictional and deterministic.
        - Authenticated tenant and region come from application context, never the prompt.
        - Every provider result crosses the same schema and resource-binding validator.
        - Failed and losing calls remain in cost and attempt accounting.
        - Observable route decisions are shown; private chain-of-thought is not requested.
        """
    ),
    md(
        """
        ## 3. Learning objectives

        By the end you will be able to normalize provider contracts, enforce model eligibility,
        classify fallback-safe errors, reserve budgets and quotas, design safe cache keys, measure
        cascade and hedge amplification, calculate cost per successful compliant task, and choose a
        route from a quality-latency-cost frontier.
        """
    ),
    md(
        """
        ## 4. Architecture before implementation

        ```text
        authenticated context + normalized task
          → eligibility and version policy
          → response-cache lookup
          → atomic cost/token reservation
          → route and provider adapter
          → normalize usage/error/output
          → validate schema and case binding
          → acceptance/fallback decision
          → settle actual usage + terminal result
        ```

        Provider selection happens only inside the eligible set. A common response shape does not
        erase provider capability, retention, safety, streaming, or quality differences.
        """
    ),
    code(
        """
        from dataclasses import replace

        from lab import (
            DataClass,
            ErrorKind,
            FaultPlan,
            GatewayBoundaryError,
            GatewayStatus,
            ProviderBehavior,
            ProviderFault,
            QuotaLedger,
            SpendLedger,
            build_demo_environment,
            demo_request,
            deployment_decision_map,
            evaluate_policy,
            pareto_frontier,
            recommend_policy,
            report_rows,
            threshold_sweep,
        )

        print("Course 6 deterministic gateway ready")
        """
    ),
    md(
        """
        ## 5. Inspect the normalized model catalogue

        The catalogue contains stable application selection facts: versions, regions, data
        classes, capabilities, context limits, relative price metadata, and retention mode. A real
        platform would reconcile this registry with provider lifecycle and contract data.
        """
    ),
    code(
        """
        env = build_demo_environment()
        for profile in env.profiles.values():
            print(
                profile.model_id,
                "provider=", profile.provider,
                "regions=", sorted(profile.regions),
                "capabilities=", sorted(profile.capabilities),
                "retention=", profile.retention_mode,
            )
        """
    ),
    md(
        """
        The three deployments are deliberately not equivalent. `premium-us` has a useful latency
        profile but is outside the Canadian processing boundary, so it is never a valid fallback
        for the default authenticated context.
        """
    ),
    md(
        """
        ## 6. Baseline A — direct economy model

        Always begin with a simple baseline. The economy route gives us minimum cost and latency,
        but the labelled set—not the model name—determines whether quality is sufficient.
        """
    ),
    code(
        """
        economy_env = build_demo_environment()
        economy_report = evaluate_policy(
            economy_env.gateway,
            economy_env.context,
            economy_env.policies["economy-direct"],
            economy_env.cases,
        )
        report_rows([economy_report])
        """
    ),
    md(
        """
        All requests complete at the transport layer, but only half match the labelled decision.
        This is why availability and HTTP status cannot stand in for task success.
        """
    ),
    md(
        """
        ## 7. Baseline B — direct premium model

        The premium baseline is the quality reference for this tiny fixture. It is not assumed to
        be universally correct; it simply happens to match all four deterministic labels.
        """
    ),
    code(
        """
        premium_env = build_demo_environment()
        premium_report = evaluate_policy(
            premium_env.gateway,
            premium_env.context,
            premium_env.policies["premium-direct"],
            premium_env.cases,
        )
        report_rows([premium_report])
        """
    ),
    md(
        """
        Premium direct reaches the fixture's quality floor at substantially higher cost and p95
        latency. Routing is justified only if it finds a better operating point without hiding
        difficult or restricted slices.
        """
    ),
    md(
        """
        ## 8. Trace a simple cascade acceptance

        A cascade first calls the economy model, validates the output, then asks a separate
        calibrated acceptance estimator whether to stop or escalate. Provider self-confidence is
        carried in the response but is not the acceptance gate.
        """
    ),
    code(
        """
        cascade_env = build_demo_environment()
        simple = cascade_env.gateway.infer(
            cascade_env.context,
            demo_request(request_id="notebook-simple"),
            cascade_env.policies["quality-cascade"],
        )
        print(simple.terminal_reason, simple.selected_model, simple.total_cost_units)
        print(simple.attempts)
        assert simple.provider_calls == 1
        assert simple.attempts[0].quality_score == 0.96
        """
    ),
    md(
        """
        The gate accepts the simple economy result, so the premium cost and serial latency are
        avoided. The gate score is observable evidence, not a correctness certificate.
        """
    ),
    md(
        """
        ## 9. Trace a complex-case escalation

        The economy output is schema-valid but receives a low acceptance score. The gateway then
        reserves the premium call, invokes it, validates it independently, and reports both calls.
        """
    ),
    code(
        """
        complex_result = cascade_env.gateway.infer(
            cascade_env.context,
            demo_request("case-complex", request_id="notebook-complex"),
            cascade_env.policies["quality-cascade"],
        )
        print(complex_result.terminal_reason, complex_result.selected_model)
        for attempt in complex_result.attempts:
            print(attempt)
        assert complex_result.provider_calls == 2
        assert complex_result.output.decision == "refer"
        """
    ),
    md(
        """
        Escalation adds both the economy cost and serial latency. A cascade is not a free selector;
        its economics depend on the escalation rate and gate cost.
        """
    ),
    md(
        """
        ## 10. Threshold sensitivity experiment

        Sweep the acceptance threshold rather than choosing it by intuition. A low threshold accepts
        more cheap output; a high threshold approaches premium quality while retaining the probe
        cost and serial path.
        """
    ),
    code(
        """
        sweep = threshold_sweep((0.40, 0.80, 0.95))
        report_rows(sweep)
        """
    ),
    md(
        """
        On this fixture the stricter threshold improves compliant success and increases cost,
        provider calls, and p95 latency. The right threshold is a release-policy choice tied to
        representative held-out labels.
        """
    ),
    md(
        """
        ## 11. Failure injection — router drift

        The drift case is intentionally dangerous: the gate assigns a high score to the wrong
        economy decision. The gateway is functioning as configured, but the routing model is no
        longer reliable on that slice.
        """
    ),
    code(
        """
        drift_env = build_demo_environment()
        drift = drift_env.gateway.infer(
            drift_env.context,
            demo_request("case-drift", request_id="notebook-drift"),
            drift_env.policies["quality-cascade"],
        )
        print(drift.output, drift.attempts[0].quality_score)
        assert drift.output.decision == "approve"  # labelled truth is decline
        assert drift.attempts[0].quality_score == 0.92
        """
    ),
    md(
        """
        Mitigation is not a prompt saying “be accurate.” Maintain labels, calibration curves,
        difficult slices, route/model version telemetry, drift thresholds, shadow evaluation, and a
        rollback to a known route.
        """
    ),
    md(
        """
        ## 12. Reliability fallback after throttling

        Fallback addresses classified availability failure, not quality. Here the economy provider
        throttles, so the gateway uses the already-admitted Canadian premium model.
        """
    ),
    code(
        """
        throttle_faults = FaultPlan()
        throttle_faults.add(
            "economy-ca",
            "case-simple",
            ProviderFault(ErrorKind.THROTTLED, 35, "simulated 429"),
        )
        fallback_env = build_demo_environment(faults=throttle_faults)
        fallback = fallback_env.gateway.infer(
            fallback_env.context,
            demo_request(request_id="notebook-throttle"),
            fallback_env.policies["reliability-fallback"],
        )
        print(fallback.terminal_reason, [a.model_id for a in fallback.attempts])
        assert fallback.selected_model == "premium-ca"
        """
    ),
    md(
        """
        Both attempts remain in the trace. In production, include any billed tokens from the failed
        attempt and correlate the provider request ID with invoices and incident data.
        """
    ),
    md(
        """
        ## 13. Terminal authentication failure

        A bad provider credential is a platform defect. Trying another provider can conceal broken
        secret rotation or an attack, so authentication is not in the retryable error set.
        """
    ),
    code(
        """
        auth_faults = FaultPlan()
        auth_faults.add(
            "economy-ca",
            "case-simple",
            ProviderFault(ErrorKind.AUTHENTICATION, 10, "simulated bad credential"),
        )
        auth_env = build_demo_environment(faults=auth_faults)
        auth_result = auth_env.gateway.infer(
            auth_env.context,
            demo_request(request_id="notebook-auth"),
            auth_env.policies["reliability-fallback"],
        )
        print(auth_result.status, auth_result.attempts)
        assert auth_result.status is GatewayStatus.FAILED
        assert auth_result.provider_calls == 1
        """
    ),
    md(
        """
        ## 14. Safety refusal is not provider shopping

        A safety refusal has different semantics from throttling. The default route stops; a product
        may define a reviewed human or policy path, but arbitrary fallback would be a safety bypass.
        """
    ),
    code(
        """
        safety_faults = FaultPlan()
        safety_faults.add(
            "economy-ca",
            "case-simple",
            ProviderFault(ErrorKind.SAFETY_REFUSAL, 20, "simulated refusal"),
        )
        safety_env = build_demo_environment(faults=safety_faults)
        safety_result = safety_env.gateway.infer(
            safety_env.context,
            demo_request(request_id="notebook-safety"),
            safety_env.policies["reliability-fallback"],
        )
        print(safety_result.status, safety_result.provider_calls)
        assert safety_result.provider_calls == 1
        """
    ),
    md(
        """
        ## 15. Residency denial on a tempting fallback

        Simulate a Canadian provider outage and configure the faster US premium model as fallback.
        The gateway must reauthorize every candidate, not treat emergency routing as permission.
        """
    ),
    code(
        """
        residency_faults = FaultPlan()
        residency_faults.add(
            "economy-ca",
            "case-restricted",
            ProviderFault(ErrorKind.UNAVAILABLE, 30, "simulated outage"),
        )
        residency_env = build_demo_environment(faults=residency_faults)
        unsafe_route = replace(
            residency_env.policies["reliability-fallback"],
            secondary_model="premium-us",
        )
        residency_result = residency_env.gateway.infer(
            residency_env.context,
            demo_request(
                "case-restricted",
                request_id="notebook-residency",
                data_classification=DataClass.RESTRICTED,
            ),
            unsafe_route,
        )
        print(residency_result.status, residency_result.terminal_reason)
        assert residency_result.terminal_reason == ErrorKind.RESIDENCY_DENIED
        """
    ),
    md(
        """
        Availability is calculated over eligible providers, not every reachable endpoint. The
        denied fallback is valid work blocked, not a forbidden outcome—the policy prevented the
        exposure.
        """
    ),
    md(
        """
        ## 16. Output validation before fallback

        Provider-neutral JSON can still be malformed or refer to the wrong case. Inject a missing
        decision field and observe validation before the fallback is accepted.
        """
    ),
    code(
        """
        output_env = build_demo_environment()
        output_env.gateway.provider.behaviors[("economy-ca", "case-simple")] = ProviderBehavior(
            "approve", 70, 100, 0.9, malformed=True
        )
        output_result = output_env.gateway.infer(
            output_env.context,
            demo_request(request_id="notebook-output"),
            output_env.policies["reliability-fallback"],
        )
        print(output_result.attempts)
        assert output_result.attempts[0].error_kind is ErrorKind.OUTPUT_INVALID
        assert output_result.selected_model == "premium-ca"
        """
    ),
    md(
        """
        The failed output still incurred cost. Structured-output features reduce parsing failure;
        application code still verifies semantic bindings and quality.
        """
    ),
    md(
        """
        ## 17. Hard budget reservation

        Configure a cap that can admit the economy attempt but not the worst-case premium fallback.
        The second call is blocked before inference rather than discovered on the invoice.
        """
    ),
    code(
        """
        budget_faults = FaultPlan()
        budget_faults.add(
            "economy-ca",
            "case-simple",
            ProviderFault(ErrorKind.UNAVAILABLE, 25, "simulated outage"),
        )
        budget_env = build_demo_environment(faults=budget_faults)
        tight_route = replace(
            budget_env.policies["reliability-fallback"],
            max_cost_units=3.0,
        )
        budget_result = budget_env.gateway.infer(
            budget_env.context,
            demo_request(request_id="notebook-budget"),
            tight_route,
        )
        print(budget_result.status, budget_result.terminal_reason)
        assert budget_result.terminal_reason == ErrorKind.BUDGET_EXHAUSTED
        """
    ),
    md(
        """
        Reservation is essential under concurrency. A check against completed spend alone lets many
        simultaneous requests pass before any of them reports actual usage.
        """
    ),
    code(
        """
        spend = SpendLedger()
        spend.reserve("logical-request", "attempt-1", 6.0, 10.0)
        try:
            spend.reserve("logical-request", "attempt-2", 6.0, 10.0)
        except GatewayBoundaryError as error:
            print("second reservation denied:", error.kind)
            assert error.kind is ErrorKind.BUDGET_EXHAUSTED
        """
    ),
    md(
        """
        ## 18. Token quota reservation

        Quotas and budgets are different controls. Reserve the maximum token use for admitted
        in-flight requests, then settle actual usage.
        """
    ),
    code(
        """
        quota = QuotaLedger({"northstar": 2_000})
        quota.reserve("northstar", "minute-1", "attempt-1", 1_200)
        try:
            quota.reserve("northstar", "minute-1", "attempt-2", 1_200)
        except GatewayBoundaryError as error:
            print("second token reservation denied:", error.kind)
            assert error.kind is ErrorKind.QUOTA_EXHAUSTED
        """
    ),
    md(
        """
        ## 19. Validated application response cache

        Enable response caching for an identical tenant-, prompt-, route-, policy-, and model-
        version-scoped request. The second call returns the previously validated output.
        """
    ),
    code(
        """
        cache_env = build_demo_environment()
        cache_route = replace(cache_env.policies["economy-direct"], use_response_cache=True)
        cache_request = demo_request(request_id="notebook-cache")
        first = cache_env.gateway.infer(cache_env.context, cache_request, cache_route)
        second = cache_env.gateway.infer(cache_env.context, cache_request, cache_route)
        print("first", first.cache_hit, first.total_cost_units)
        print("second", second.cache_hit, second.total_cost_units)
        assert second.cache_hit and second.provider_calls == 0
        """
    ),
    md(
        """
        This is not provider prompt caching. Prompt/KV caching reuses prefix computation but still
        generates a new response. Response caching returns an earlier validated output and therefore
        needs stronger authorization, freshness, versioning, and invalidation.
        """
    ),
    md(
        """
        ## 20. Cache isolation and version invalidation

        A different tenant must miss even with identical content. A changed route generation must
        also miss so a policy rollout cannot silently reuse an old decision.
        """
    ),
    code(
        """
        other_tenant = cache_env.gateway.infer(
            cache_env.other_tenant_context,
            cache_request,
            cache_route,
        )
        changed_route = replace(cache_route, policy_version="route-v3")
        changed = cache_env.gateway.infer(cache_env.context, cache_request, changed_route)
        print("other tenant hit:", other_tenant.cache_hit)
        print("changed route hit:", changed.cache_hit)
        assert not other_tenant.cache_hit and not changed.cache_hit
        """
    ),
    md(
        """
        ## 21. Delayed hedging: latency versus total work

        The premium primary takes 210 ms. After 100 ms, the economy hedge starts and completes at
        195 ms. The user sees 195 ms, but both calls are billed and the faster answer may be wrong.
        """
    ),
    code(
        """
        hedge_env = build_demo_environment()
        hedge = hedge_env.gateway.infer(
            hedge_env.context,
            demo_request("case-complex", request_id="notebook-hedge"),
            hedge_env.policies["latency-hedge"],
        )
        print(
            "winner=", hedge.selected_model,
            "wall_ms=", hedge.latency_ms,
            "calls=", hedge.provider_calls,
            "cost=", hedge.total_cost_units,
            "decision=", hedge.output.decision,
        )
        assert hedge.provider_calls == 2 and hedge.latency_ms == 195
        """
    ),
    md(
        """
        Hedging is a latency technique, not a quality strategy. It must be evaluated against a
        product rule for which successful response can win. Counting only the winner would hide
        capacity amplification and a potential quality regression.
        """
    ),
    md(
        """
        ## 22. Deadline failure still has economics

        The application deadline is 50 ms while the economy call takes 75 ms. The output is not
        returned as success, but the work was performed and remains in cost accounting.
        """
    ),
    code(
        """
        deadline_env = build_demo_environment()
        deadline = deadline_env.gateway.infer(
            deadline_env.context,
            demo_request(request_id="notebook-deadline", deadline_ms=50),
            deadline_env.policies["economy-direct"],
        )
        print(deadline.status, deadline.total_cost_units, deadline.attempts)
        assert deadline.status is GatewayStatus.FAILED
        assert deadline.total_cost_units > 0
        """
    ),
    md(
        """
        ## 23. Evaluate complete policy alternatives

        Use fresh environments so cache, faults, budgets, and quota state do not contaminate the
        comparison. Each report uses the same four labelled cases and explicit denominators.
        """
    ),
    code(
        """
        policy_names = (
            "economy-direct",
            "premium-direct",
            "quality-cascade",
            "latency-hedge",
        )
        reports = []
        for name in policy_names:
            policy_env = build_demo_environment()
            reports.append(
                evaluate_policy(
                    policy_env.gateway,
                    policy_env.context,
                    policy_env.policies[name],
                    policy_env.cases,
                )
            )
        report_rows(reports)
        """
    ),
    md(
        """
        `completed` and `correct` are intentionally separate. The cost denominator is compliant
        correct completion, so inexpensive wrong answers do not appear as economic wins.
        """
    ),
    md(
        """
        ## 24. Pareto frontier and release constraints

        The Pareto frontier removes policies that are no better on success, p95 latency, and cost.
        Release constraints then select among the remaining candidates.
        """
    ),
    code(
        """
        print("frontier:", pareto_frontier(reports))
        recommendation = recommend_policy(
            reports,
            minimum_compliant_success_rate=0.95,
            maximum_p95_latency_ms=250,
        )
        print(recommendation)
        assert recommendation.selected_policy == "premium-direct"
        """
    ),
    md(
        """
        On this fixture, only premium direct meets both constraints. If the latency ceiling were
        tighter, no policy would qualify; the honest decision would be to redesign or renegotiate
        the objective, not weaken the metric silently.
        """
    ),
    md(
        """
        ## 25. Current tooling decision map

        A product feature list is not an architecture decision. Compare who owns identity, policy,
        budget state, retry loops, output validation, evaluation, operation, and provider exit.
        """
    ),
    code(
        """
        deployment_decision_map()
        """
    ),
    md(
        """
        Direct SDKs minimize moving parts. Bedrock adds managed multi-model APIs and routing within
        documented constraints. LiteLLM supplies a multi-provider proxy and router. Cloud API
        management centralizes platform controls. Kubernetes/Envoy inference gateways serve teams
        operating model data planes. Every option still needs application workload evidence.
        """
    ),
    md(
        """
        ## 26. Production upgrade plan

        | Lab simplification | Production requirement |
        |---|---|
        | in-memory policy | signed/versioned configuration with staged rollout and rollback |
        | fictional profiles | reconciled provider catalogue, contract and lifecycle data |
        | local reservations | atomic distributed budget, token, and concurrency state |
        | deterministic adapters | provider contract tests, streaming, cancellation, typed errors |
        | fixed cases | representative labelled replay, slices, human review, drift monitoring |
        | local cache | encrypted scoped store, TTL, invalidation, deletion, stampede control |
        | simulated latency | end-to-end p50/p95/p99 plus provider and gateway spans |
        | one process | multi-zone capacity, bulkheads, load tests, game days, incident ownership |

        Preserve the trusted boundary when adding live adapters: providers propose output; the
        application owns authorization, eligibility, budgets, validation, and release evidence.
        """
    ),
    md(
        """
        ## 27. Portfolio deliverables

        1. Routing policy covering eligibility, error classes, retry, fallback, hedge, cache, and
           terminal behavior.
        2. Gateway ADR comparing direct, managed, open-source, and custom options.
        3. Quality-latency-cost frontier with correct metric populations and slices.
        4. Sensitivity report for thresholds, prices, token mix, drift, outages, and quotas.
        """
    ),
    md(
        """
        ## 28. Exercises

        **Implementation**

        1. Add a vision capability and prove that a text-only fallback is ineligible.
        2. Add a fixed gateway fee and cache-write pricing to the economics.
        3. Normalize a mid-stream error and cancel losing provider work.

        **Diagnosis**

        4. Add client and SDK retries, then expose worst-case amplification.
        5. Simulate a correlated identity outage affecting every provider.
        6. Shift the case mix and show threshold regret.

        **Architecture judgment**

        7. Compare Bedrock prompt routing, Foundry model router, LiteLLM, and a direct adapter.
        8. Decide whether the latency objective justifies hedging under the token quota.
        9. Define the Course 7 SLO and telemetry contract from these attempt records.
        """
    ),
    md(
        """
        ## 29. Summary

        A production model gateway is a governed inference boundary. It admits only eligible model
        paths, classifies failures, bounds total work, validates every result, attributes every
        attempt, and chooses a routing policy from representative evidence. Normalization reduces
        integration duplication; it does not make models, providers, regions, or safety behavior
        equivalent.

        The next course turns these request, attempt, route, cost, latency, cache, and error records
        into correlated telemetry, SLOs, alerts, failure game days, and incident response.
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
