"""Build the canonical Course 5 notebook from reviewed source cells."""

from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
TARGET = (
    ROOT
    / "curriculum"
    / "advanced"
    / "05-agentic-ai-architecture-agentcore"
    / "agentic_ai_architecture_agentcore.ipynb"
)


def md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


def code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


cells = [
    md(
        """
        # Course 5 Lab — Agentic AI Architecture and AgentCore

        **Thesis:** use the least autonomous architecture that meets the requirement. If a model
        chooses actions, application code still owns identity, authorization, tools, budgets,
        approvals, state, recovery, effects, and termination.

        This credential-free lab compares a deterministic workflow with a bounded tool agent for
        Northstar's underwriting exception review. Both use exactly the same trusted gateway and
        state stores, so the comparison isolates the cost of model-directed control flow.
        """
    ),
    md(
        """
        ## 1. Scenario and success contract

        A valid exception review must load the current case, retrieve authorized current policy,
        calculate risk from authoritative fields, prepare a `refer` or `decline` recommendation,
        obtain independent approval, and publish exactly one review.

        Success is not fluent text. Trusted state must contain a policy-compliant terminal status,
        the approved proposal digest, current case/evidence versions, and one reconciled effect.
        """
    ),
    md(
        """
        ## 2. Safety and reproducibility boundaries

        - No model, cloud, MCP server, API key, or network call is required.
        - The planner is deterministic and exposes actions, never private chain-of-thought.
        - Simulated latency and cost compare architectures; they are not vendor benchmarks.
        - The application derives tenant scope from trusted principal state.
        - Tools cannot receive credentials or widen their own capability.
        - A local store proves logic, not distributed atomicity or production durability.
        """
    ),
    md(
        """
        ## 3. Control flow before framework

        ```text
        authenticated request
          → create bounded run
          → propose or select next action
          → validate + authorize + reserve budget
          → execute narrow tool
          → verify/reconcile + checkpoint
          → trusted stop, approval pause, or next action
        ```

        The workflow selects known actions in code. The agent's planner selects them dynamically.
        Everything after selection is shared.
        """
    ),
    code(
        """
        from dataclasses import replace

        from lab import (
            AgentBoundaryError,
            AgentRuntime,
            Architecture,
            BoundedPlanner,
            FaultKind,
            InjectionFollowingPlanner,
            RunLimits,
            RunStatus,
            RunUsage,
            ToolCall,
            agentcore_deployment_map,
            approve_waiting_run,
            build_demo_environment,
            demo_request,
            evaluate_architecture,
            recommend_architecture,
        )


        def denied_reason(operation):
            try:
                operation()
            except AgentBoundaryError as error:
                return error.reason_code
            raise AssertionError("operation unexpectedly succeeded")


        print("Course 5 imports ready")
        """
    ),
    md(
        """
        ## 4. Inspect the trusted tool catalogue

        A schema states shape. The catalogue also records risk, scope, retry ownership, cost,
        latency, protocol surface, and approval requirement. `export_customer_data` exists in the
        estate but is intentionally absent from this workload's allowed-tool manifest.
        """
    ),
    code(
        """
        env = build_demo_environment()
        for spec in env.gateway.specs.values():
            print(
                spec.name,
                "risk=", spec.risk,
                "scope=", spec.required_scope,
                "protocol=", spec.protocol,
                "approval=", spec.requires_approval,
            )

        print("workload tools:", sorted(env.workload.allowed_tools))
        assert "export_customer_data" not in env.workload.allowed_tools
        """
    ),
    md(
        """
        ## 5. Baseline — fixed workflow

        The business path is known, so the baseline calls three read/compute tools in a fixed order
        and pauses before publication. No model call is needed to decide the sequence.
        """
    ),
    code(
        """
        workflow_env = build_demo_environment()
        workflow_waiting = workflow_env.workflow.start(
            run_id="notebook-workflow",
            request=demo_request(),
            principal=workflow_env.principals["alice"],
            workload=workflow_env.workload,
            now=workflow_env.now,
        )
        print(workflow_waiting.status, workflow_waiting.usage)
        assert workflow_waiting.status is RunStatus.WAITING_APPROVAL
        assert workflow_waiting.usage.model_calls == 0
        assert workflow_waiting.usage.tool_calls == 3
        assert workflow_env.effects.count == 0
        """
    ),
    md(
        """
        The trace contains observable actions and reason codes. It does not log credentials, full
        prompts, or private reasoning. The pause is durable state, not a boolean hidden in text.
        """
    ),
    code(
        """
        for event in workflow_waiting.trace:
            print(event)
        assert workflow_waiting.trace[-1].reason_code == "APPROVAL_REQUIRED"
        """
    ),
    md(
        """
        ## 6. Approval is bound to one exact proposal

        The approver is a different authenticated principal. The receipt binds run, tenant,
        requester, approver, action, target, canonical proposal digest, policy version, issue time,
        and expiry. Publication consumes it once.
        """
    ),
    code(
        """
        workflow_receipt = approve_waiting_run(workflow_env, workflow_waiting)
        workflow_done = workflow_env.workflow.resume_with_approval(
            workflow_waiting.run_id,
            workflow_receipt,
            now=workflow_env.now + 1,
        )
        print(workflow_done.status, workflow_done.published_review)
        assert workflow_done.status is RunStatus.SUCCEEDED
        assert workflow_env.effects.count == 1
        assert workflow_env.approvals.is_consumed(workflow_receipt.receipt_id)
        """
    ),
    md(
        """
        ## 7. Bounded agent — inspect one action at a time

        The planner proposes a typed action. The first cycle does not execute an unrestricted loop;
        it consumes one model budget unit, passes the action through policy, executes one tool, and
        checkpoints the result.
        """
    ),
    code(
        """
        agent_env = build_demo_environment()
        first = agent_env.agent.start(
            run_id="notebook-agent",
            request=demo_request(),
            principal=agent_env.principals["alice"],
            workload=agent_env.workload,
            max_cycles=1,
            now=agent_env.now,
        )
        print(first.status, first.next_step, first.case, first.usage)
        assert first.status is RunStatus.RUNNING
        assert first.case is not None
        assert first.usage.model_calls == first.usage.tool_calls == 1
        """
    ),
    md(
        """
        Continue one cycle. The checkpoint revision increases, completed work remains in structured
        state, and the policy result—not prompt history—decides whether the next call may execute.
        """
    ),
    code(
        """
        second = agent_env.agent.continue_run(
            first.run_id, max_cycles=1, now=agent_env.now
        )
        print("revision:", first.revision, "→", second.revision)
        print("evidence:", second.evidence.evidence_id if second.evidence else None)
        assert second.status is RunStatus.RUNNING
        assert second.evidence is not None
        assert second.revision > first.revision
        """
    ),
    md(
        """
        The remaining cycles calculate authoritative risk and propose publication. The agent cannot
        execute the consequential tool until a trusted receipt arrives.
        """
    ),
    code(
        """
        agent_waiting = agent_env.agent.continue_run(second.run_id, now=agent_env.now)
        print(agent_waiting.status, agent_waiting.recommendation, agent_waiting.usage)
        assert agent_waiting.status is RunStatus.WAITING_APPROVAL
        assert agent_waiting.usage.model_calls == 4
        assert agent_waiting.usage.tool_calls == 3
        assert agent_env.effects.count == 0
        """
    ),
    code(
        """
        agent_receipt = approve_waiting_run(agent_env, agent_waiting)
        agent_done = agent_env.agent.resume_with_approval(
            agent_waiting.run_id,
            agent_receipt,
            now=agent_env.now + 1,
        )
        print(agent_done.status, agent_done.usage)
        assert agent_done.status is RunStatus.SUCCEEDED
        assert agent_env.effects.count == 1
        """
    ),
    md(
        """
        ## 8. Compare architectures on the same labelled cases

        The evaluation population is two valid Northstar cases. Successful compliant tasks are the
        denominator for unit cost. Tool attempts divided by logical calls measures retry
        amplification. Forbidden outcomes count actual cross-boundary effects, not rejected calls.
        """
    ),
    code(
        """
        cases = (("case-101", 3), ("case-102", 1))
        workflow_report = evaluate_architecture(Architecture.WORKFLOW, cases)
        agent_report = evaluate_architecture(Architecture.BOUNDED_AGENT, cases)
        print(workflow_report)
        print(agent_report)
        decision = recommend_architecture(workflow_report, agent_report)
        print("recommended:", decision)

        assert workflow_report.task_success_rate == agent_report.task_success_rate == 1.0
        assert workflow_report.forbidden_outcomes == agent_report.forbidden_outcomes == 0
        assert workflow_report.model_calls == 0
        assert agent_report.model_calls == 8
        assert workflow_report.cost_per_successful_compliant_task < (
            agent_report.cost_per_successful_compliant_task
        )
        assert decision is Architecture.WORKFLOW
        """
    ),
    md(
        """
        This fixture supports the workflow: task success is equal and the agent adds planning calls,
        simulated latency, and cost. It does not prove that workflows always win. Add a labelled
        variable-path case before claiming agency provides value.
        """
    ),
    md(
        """
        ## 9. Failure injection — tool arguments cannot create tenant authority

        The model supplies an extra `tenant_id`. The schema rejects it. Production tools should
        derive tenant and resource ownership from authenticated application state.
        """
    ),
    code(
        """
        schema_env = build_demo_environment()
        schema_state = schema_env.agent.start(
            run_id="schema-attack",
            request=demo_request(),
            principal=schema_env.principals["alice"],
            workload=schema_env.workload,
            max_cycles=0,
            now=schema_env.now,
        )
        forged_scope = ToolCall(
            "load_case",
            {"case_id": "case-101", "expected_version": 3, "tenant_id": "southstar"},
            "schema-attack:load",
        )
        reason = denied_reason(
            lambda: schema_env.gateway.invoke(schema_state, forged_scope, now=schema_env.now)
        )
        print(reason)
        assert reason == "UNKNOWN_TOOL_ARGUMENT"
        """
    ),
    md(
        """
        ## 10. Failure injection — malicious retrieved content

        An educational anti-pattern follows an instruction embedded in retrieved policy and proposes
        `export_customer_data`. Authorization runs before asking for approval or executing the tool.
        """
    ),
    code(
        """
        injection_env = build_demo_environment(
            planner=InjectionFollowingPlanner(),
            malicious_policy=True,
        )
        injected = injection_env.agent.start(
            run_id="injection",
            request=demo_request(),
            principal=injection_env.principals["alice"],
            workload=injection_env.workload,
            now=injection_env.now,
        )
        print(injected.status, injected.terminal_reason)
        assert injected.status is RunStatus.FAILED
        assert injected.terminal_reason == "TOOL_NOT_ALLOWED"
        assert injection_env.effects.count == 0
        """
    ),
    md(
        """
        The normal planner treats the same content as data. This is defense in depth: even if model
        behavior regresses, the gateway remains the enforcement point.
        """
    ),
    code(
        """
        safe_content_env = build_demo_environment(malicious_policy=True)
        safe_content = safe_content_env.agent.start(
            run_id="safe-content",
            request=demo_request(),
            principal=safe_content_env.principals["alice"],
            workload=safe_content_env.workload,
            now=safe_content_env.now,
        )
        print(safe_content.status, safe_content.pending_call.name)
        assert safe_content.status is RunStatus.WAITING_APPROVAL
        assert safe_content.pending_call.name == "publish_recommendation"
        """
    ),
    md(
        """
        ## 11. Failure injection — bounded transient retry

        The gateway owns `retrieve_policy` retries. Two timeouts consume three physical attempts for
        one logical call. The global attempt, cost, and deadline budgets still apply.
        """
    ),
    code(
        """
        retry_env = build_demo_environment()
        retry_env.faults.schedule(
            "retrieve_policy",
            "retry:retrieve-policy",
            (FaultKind.TIMEOUT_BEFORE_EFFECT, FaultKind.TIMEOUT_BEFORE_EFFECT),
        )
        retried = retry_env.agent.start(
            run_id="retry",
            request=demo_request(),
            principal=retry_env.principals["alice"],
            workload=retry_env.workload,
            now=retry_env.now,
        )
        print(retried.status, retried.usage)
        assert retried.status is RunStatus.WAITING_APPROVAL
        assert retried.usage.tool_calls == 3
        assert retried.usage.tool_attempts == 5
        """
    ),
    md(
        """
        Three timeouts exhaust the tool's owned retry policy. Authorization and invalid input would
        not be retried at all.
        """
    ),
    code(
        """
        retry_fail_env = build_demo_environment()
        retry_fail_env.faults.schedule(
            "retrieve_policy",
            "retry-fail:retrieve-policy",
            (FaultKind.TIMEOUT_BEFORE_EFFECT,) * 3,
        )
        retry_failed = retry_fail_env.agent.start(
            run_id="retry-fail",
            request=demo_request(),
            principal=retry_fail_env.principals["alice"],
            workload=retry_fail_env.workload,
            now=retry_fail_env.now,
        )
        print(retry_failed.status, retry_failed.terminal_reason)
        assert retry_failed.terminal_reason == "TOOL_RETRY_EXHAUSTED"
        assert retry_fail_env.effects.count == 0
        """
    ),
    md(
        """
        ## 12. Failure injection — budget exhaustion

        A two-call model budget cannot reach proposal. The application stops before an unbudgeted
        third call and records an explicit terminal reason.
        """
    ),
    code(
        """
        budget_env = build_demo_environment()
        exhausted = budget_env.agent.start(
            run_id="budget",
            request=demo_request(),
            principal=budget_env.principals["alice"],
            workload=budget_env.workload,
            limits=RunLimits(max_model_calls=2),
            now=budget_env.now,
        )
        print(exhausted.status, exhausted.terminal_reason, exhausted.usage)
        assert exhausted.terminal_reason == "MODEL_CALL_BUDGET_EXHAUSTED"
        assert exhausted.usage.model_calls == 2
        assert budget_env.effects.count == 0
        """
    ),
    md(
        """
        Cost is reserved before a consequential effect. This run can prepare a proposal with 17
        simulated units, but its limit of 19 cannot admit a three-unit publication.
        """
    ),
    code(
        """
        effect_budget_env = build_demo_environment()
        budget_waiting = effect_budget_env.agent.start(
            run_id="effect-budget",
            request=demo_request(),
            principal=effect_budget_env.principals["alice"],
            workload=effect_budget_env.workload,
            limits=RunLimits(max_cost_units=19),
            now=effect_budget_env.now,
        )
        budget_receipt = approve_waiting_run(effect_budget_env, budget_waiting)
        budget_done = effect_budget_env.agent.resume_with_approval(
            budget_waiting.run_id,
            budget_receipt,
            now=effect_budget_env.now + 1,
        )
        print(budget_done.status, budget_done.terminal_reason)
        assert budget_done.terminal_reason == "COST_BUDGET_EXHAUSTED"
        assert effect_budget_env.effects.count == 0
        assert not effect_budget_env.approvals.is_consumed(budget_receipt.receipt_id)
        """
    ),
    md(
        """
        ## 13. Failure injection — cancellation

        Cancellation is checked before spending model or tool budget. An external effect already in
        progress would need its own cancellation or reconciliation contract.
        """
    ),
    code(
        """
        cancel_env = build_demo_environment()
        cancel_env.cancellations.cancel("cancelled")
        cancelled = cancel_env.agent.start(
            run_id="cancelled",
            request=demo_request(),
            principal=cancel_env.principals["alice"],
            workload=cancel_env.workload,
            now=cancel_env.now,
        )
        print(cancelled.status, cancelled.usage)
        assert cancelled.status is RunStatus.CANCELLED
        assert cancelled.usage == RunUsage()
        assert cancel_env.effects.count == 0
        """
    ),
    md(
        """
        ## 14. Restart from a durable checkpoint

        Stop after two cycles, create a fresh runtime object, then continue from the shared
        checkpoint store. Completed case and evidence reads are not repeated.
        """
    ),
    code(
        """
        restart_env = build_demo_environment()
        partial = restart_env.agent.start(
            run_id="restart",
            request=demo_request(),
            principal=restart_env.principals["alice"],
            workload=restart_env.workload,
            max_cycles=2,
            now=restart_env.now,
        )
        print(partial.status, partial.revision, partial.usage)
        assert partial.status is RunStatus.RUNNING
        assert partial.case is not None and partial.evidence is not None
        """
    ),
    code(
        """
        fresh_runtime = AgentRuntime(
            gateway=restart_env.gateway,
            checkpoints=restart_env.checkpoints,
            planner=BoundedPlanner(),
            cancellations=restart_env.cancellations,
        )
        restarted_waiting = fresh_runtime.continue_run("restart", now=restart_env.now)
        restarted_receipt = approve_waiting_run(restart_env, restarted_waiting)
        restarted_done = fresh_runtime.resume_with_approval(
            "restart",
            restarted_receipt,
            now=restart_env.now + 1,
        )
        print(restarted_done.status, restarted_done.usage)
        assert restarted_done.status is RunStatus.SUCCEEDED
        assert restarted_done.usage.model_calls == 4
        assert restart_env.effects.count == 1
        """
    ),
    md(
        """
        ## 15. Failure injection — concurrent stale checkpoint writer

        Optimistic revision prevents a stale worker from overwriting newer state. Production needs
        the equivalent atomic compare-and-set transition in its durable store.
        """
    ),
    code(
        """
        conflict_env = build_demo_environment()
        conflict_state = conflict_env.agent.start(
            run_id="checkpoint-conflict",
            request=demo_request(),
            principal=conflict_env.principals["alice"],
            workload=conflict_env.workload,
            max_cycles=1,
            now=conflict_env.now,
        )
        current = conflict_env.checkpoints.load(conflict_state.run_id)
        conflict_env.checkpoints.save(current, expected_revision=current.revision)
        conflict_reason = denied_reason(
            lambda: conflict_env.checkpoints.save(
                current, expected_revision=current.revision
            )
        )
        print(conflict_reason)
        assert conflict_reason == "CHECKPOINT_CONFLICT"
        """
    ),
    md(
        """
        ## 16. Failure injection — unknown write outcome

        Publication commits, but the simulated response is lost. The gateway does not blindly
        write again. It reconciles the stable operation ID and digest, observes one existing effect,
        and returns a verified success.
        """
    ),
    code(
        """
        unknown_env = build_demo_environment()
        unknown_waiting = unknown_env.agent.start(
            run_id="unknown",
            request=demo_request(),
            principal=unknown_env.principals["alice"],
            workload=unknown_env.workload,
            now=unknown_env.now,
        )
        unknown_receipt = approve_waiting_run(unknown_env, unknown_waiting)
        unknown_env.faults.schedule(
            "publish_recommendation",
            "unknown:publish-review",
            (FaultKind.UNKNOWN_AFTER_EFFECT,),
        )
        reconciled = unknown_env.agent.resume_with_approval(
            "unknown", unknown_receipt, now=unknown_env.now + 1
        )
        print(reconciled.status, reconciled.trace[-1])
        assert reconciled.status is RunStatus.SUCCEEDED
        assert reconciled.trace[-1].reason_code == "TOOL_RECONCILED"
        assert unknown_env.effects.count == 1
        """
    ),
    md(
        """
        Replaying the same operation and digest returns the existing result even though the receipt
        is consumed. A different operation cannot reuse that receipt.
        """
    ),
    code(
        """
        duplicate = unknown_env.gateway.invoke(
            unknown_waiting,
            unknown_waiting.pending_call,
            receipt=unknown_receipt,
            now=unknown_env.now + 2,
        )
        changed_operation = replace(
            unknown_waiting.pending_call,
            logical_operation_id="unknown:publish-review-again",
        )
        replay_reason = denied_reason(
            lambda: unknown_env.gateway.invoke(
                unknown_waiting,
                changed_operation,
                receipt=unknown_receipt,
                now=unknown_env.now + 2,
            )
        )
        print("same operation replayed:", duplicate.replayed)
        print("new operation:", replay_reason)
        assert duplicate.replayed
        assert replay_reason == "APPROVAL_REPLAY"
        assert unknown_env.effects.count == 1
        """
    ),
    md(
        """
        ## 17. Failure injection — approval and state drift

        Altering the approved proposal fails its digest binding. Changing entitlements or the case
        version after proposal also fails before publication.
        """
    ),
    code(
        """
        binding_env = build_demo_environment()
        binding_waiting = binding_env.agent.start(
            run_id="binding",
            request=demo_request(),
            principal=binding_env.principals["alice"],
            workload=binding_env.workload,
            now=binding_env.now,
        )
        binding_receipt = approve_waiting_run(binding_env, binding_waiting)
        altered_args = dict(binding_waiting.pending_call.arguments)
        altered_args["decision"] = "refer"
        altered_call = replace(binding_waiting.pending_call, arguments=altered_args)
        binding_reason = denied_reason(
            lambda: binding_env.gateway.invoke(
                binding_waiting,
                altered_call,
                receipt=binding_receipt,
                now=binding_env.now + 1,
            )
        )
        print(binding_reason)
        assert binding_reason == "APPROVAL_BINDING_MISMATCH"
        assert binding_env.effects.count == 0
        """
    ),
    code(
        """
        stale_env = build_demo_environment()
        stale_waiting = stale_env.agent.start(
            run_id="stale-entitlements",
            request=demo_request(),
            principal=stale_env.principals["alice"],
            workload=stale_env.workload,
            now=stale_env.now,
        )
        stale_receipt = approve_waiting_run(stale_env, stale_waiting)
        stale_env.entitlements.change(stale_waiting.principal.identity_key)
        stale_done = stale_env.agent.resume_with_approval(
            stale_waiting.run_id,
            stale_receipt,
            now=stale_env.now + 1,
        )
        print(stale_done.status, stale_done.terminal_reason)
        assert stale_done.terminal_reason == "STALE_ENTITLEMENTS"
        assert stale_env.effects.count == 0
        """
    ),
    md(
        """
        ## 18. AgentCore responsibility map

        Managed capabilities can host or replace infrastructure pieces, but responsibility remains
        explicit. Every mapping needs an integration test and an owner.
        """
    ),
    code(
        """
        for row in agentcore_deployment_map():
            print(row)
        """
    ),
    md(
        """
        | Need | Custom/framework path | AgentCore path | Application proof still required |
        |---|---|---|---|
        | agent loop | Python or framework | Runtime or Harness | bounds and terminal state |
        | tool access | API/MCP gateway | Gateway + Policy | per-call authority and no bypass |
        | credentials | IdP/workload platform | Identity | subject/actor/tenant/delegation |
        | memory | application stores | Memory | provenance, retention, deletion, poisoning |
        | traces | OpenTelemetry backend | Observability | redaction and correlation |
        | evaluation | application harness | Evaluations | labels, calibration, release gate |

        AgentCore should be selected from deployment and operating requirements. It is not the
        reason to make a known process autonomous.
        """
    ),
    md(
        """
        ## 19. MCP and framework choices

        MCP standardizes tool/context interoperability; it does not grant business authority.
        LangGraph, OpenAI Agents SDK, Strands, Google ADK, Microsoft Agent Framework, CrewAI, and
        custom runtimes offer different orchestration abstractions. Durable engines such as Step
        Functions or Temporal add long-running recovery semantics. Compare the exact behaviors you
        need: authorization placement, checkpoint atomicity, cancellation, retry ownership,
        concurrency, telemetry, versioning, portability, and operating cost.
        """
    ),
    md(
        """
        ## 20. Multi-agent coordination tax

        Before adding a supervisor or peers, measure the single-agent and workflow baselines. Count
        extra model calls, handoffs, duplicated context/tool work, merge/review steps, privileged
        surfaces, and operator burden. Parallel work can reduce wall-clock latency while increasing
        total work; report both.

        A role label is not isolation. Each specialist needs a bounded context, attenuated
        capability, independent tool authorization, handoff schema, loop limit, and one trusted
        terminal owner.
        """
    ),
    md(
        """
        ## 21. What this lab proves—and does not

        **Executable proof:** least-autonomy baseline, typed action admission, current principal and
        workload policy, approval binding and replay prevention, pre-effect budgets, retry limits,
        cancellation, checkpoint restart/conflict, stable operation replay, unknown-outcome
        reconciliation, and explicit metric denominators.

        **Not proved:** live planner quality, distributed atomicity, provider or MCP compatibility,
        cryptographic tokens, network isolation, sandbox escape resistance, cloud policy coverage,
        regional resilience, production latency/cost, or reviewer effectiveness.
        """
    ),
    md(
        """
        ## 22. Production upgrade

        - Persist tenant-partitioned state with atomic conditional transitions.
        - Authenticate both human and workload; issue attenuated, short-lived tool credentials.
        - Govern tool/MCP admission, schemas, versions, egress, rate limits, and revocation.
        - Use durable timers, waits, cancellation, retry ownership, and recovery.
        - Revalidate resources, policy, evidence, and approval on resume and before effect.
        - Emit redacted OpenTelemetry traces with run/tool/effect/version correlation.
        - Build labelled task and adversarial suites; calibrate semantic judges to human review.
        - Shadow the agent against the workflow before widening authority.
        - Canary by task/tenant/tool and retain kill switches, rollback, and incident runbooks.
        - For AgentCore, test Runtime/Gateway bypass prevention and current feature/region limits.
        """
    ),
    md(
        """
        ## 23. Portfolio exercises

        1. Add a finite router with an abstain route and measure unsafe misrouting.
        2. Add variable evidence needs; prove whether the agent beats a branching workflow.
        3. Simulate a crash after effect commit but before checkpoint save.
        4. Add concurrent resume and atomic approval/effect transitions.
        5. Add an approval-wait expiry and operator recovery path.
        6. Design an MCP server admission, authentication, scope, egress, and revocation process.
        7. Write the workflow-versus-agent ADR with reversal triggers.
        8. Map the architecture to AgentCore and name every application-owned invariant.
        """
    ),
    md(
        """
        ## 24. Completion checklist

        - [x] Workflow and agent use one policy/execution boundary.
        - [x] Model output proposes; application code authorizes and executes.
        - [x] Budgets, cancellation, retries, approval, and termination are deterministic.
        - [x] Restart, stale writer, duplicate, and unknown outcome paths are tested.
        - [x] Malicious retrieved content cannot widen capability.
        - [x] Metrics distinguish success, compliant success, blocking, harm, work, and cost.
        - [x] AgentCore is mapped as infrastructure, not assumed authority.
        - [ ] Your ADR, threat model, recovery plan, and evaluation are review-ready.
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
