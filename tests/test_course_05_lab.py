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
        / "05-agentic-ai-architecture-agentcore"
        / "lab.py"
    )
    spec = importlib.util.spec_from_file_location("course_05_lab", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lab = _load_course_module()


def _start_agent(env: object, run_id: str = "agent-1") -> object:
    return env.agent.start(
        run_id=run_id,
        request=lab.demo_request(),
        principal=env.principals["alice"],
        workload=env.workload,
        now=env.now,
    )


def _start_workflow(env: object, run_id: str = "workflow-1") -> object:
    return env.workflow.start(
        run_id=run_id,
        request=lab.demo_request(),
        principal=env.principals["alice"],
        workload=env.workload,
        now=env.now,
    )


def test_workflow_is_the_lower_autonomy_baseline() -> None:
    env = lab.build_demo_environment()
    state = _start_workflow(env)

    assert state.status is lab.RunStatus.WAITING_APPROVAL
    assert state.usage.model_calls == 0
    assert state.usage.tool_calls == 3
    assert state.pending_call is not None
    assert state.pending_call.name == "publish_recommendation"


def test_bounded_agent_proposes_actions_but_application_owns_execution() -> None:
    env = lab.build_demo_environment()
    state = _start_agent(env)

    assert state.status is lab.RunStatus.WAITING_APPROVAL
    assert state.usage.model_calls == 4
    assert state.usage.tool_calls == 3
    assert state.case is not None and state.evidence is not None and state.risk is not None
    assert state.published_review is None
    assert env.effects.count == 0


def test_independent_approval_publishes_one_bound_review() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env)
    receipt = lab.approve_waiting_run(env, waiting)

    completed = env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)

    assert completed.status is lab.RunStatus.SUCCEEDED
    assert completed.terminal_reason == "COMPLIANT_SUCCESS"
    assert completed.published_review is not None
    assert completed.published_review.approved_by == env.principals["reviewer"].identity_key
    assert env.effects.count == 1
    assert env.approvals.is_consumed(receipt.receipt_id)


def test_requester_cannot_approve_own_proposal() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env)
    assert waiting.pending_call is not None

    with pytest.raises(lab.AgentBoundaryError) as captured:
        env.approvals.issue(
            receipt_id="self-approval",
            run=waiting,
            approver=env.principals["alice"],
            proposal_digest=lab.canonical_digest(waiting.pending_call.arguments),
            policy_version=env.policy.version,
            now=env.now,
        )

    assert captured.value.reason_code == "SELF_APPROVAL_DENIED"


def test_approval_does_not_authorize_an_altered_proposal() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env)
    receipt = lab.approve_waiting_run(env, waiting)
    assert waiting.pending_call is not None
    changed_arguments = dict(waiting.pending_call.arguments)
    changed_arguments["decision"] = "refer"
    altered = replace(waiting.pending_call, arguments=changed_arguments)

    with pytest.raises(lab.AgentBoundaryError) as captured:
        env.gateway.invoke(waiting, altered, receipt=receipt, now=env.now + 1)

    assert captured.value.reason_code == "APPROVAL_BINDING_MISMATCH"
    assert env.effects.count == 0


def test_approval_replay_cannot_authorize_a_new_operation() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env)
    receipt = lab.approve_waiting_run(env, waiting)
    completed = env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)
    assert completed.status is lab.RunStatus.SUCCEEDED
    assert waiting.pending_call is not None
    new_operation = replace(
        waiting.pending_call,
        logical_operation_id=f"{waiting.run_id}:publish-review-again",
    )

    with pytest.raises(lab.AgentBoundaryError) as captured:
        env.gateway.invoke(waiting, new_operation, receipt=receipt, now=env.now + 2)

    assert captured.value.reason_code == "APPROVAL_REPLAY"
    assert env.effects.count == 1


def test_duplicate_same_operation_reconciles_without_duplicate_effect() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env)
    receipt = lab.approve_waiting_run(env, waiting)
    env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)
    assert waiting.pending_call is not None

    replay = env.gateway.invoke(
        waiting,
        waiting.pending_call,
        receipt=receipt,
        now=env.now + 2,
    )

    assert replay.replayed and replay.reconciled
    assert env.effects.count == 1


def test_cross_tenant_case_fails_before_any_effect() -> None:
    env = lab.build_demo_environment()
    state = env.agent.start(
        run_id="cross-tenant",
        request=lab.demo_request("case-201", 2),
        principal=env.principals["alice"],
        workload=env.workload,
        now=env.now,
    )

    assert state.status is lab.RunStatus.FAILED
    assert state.terminal_reason == "CROSS_TENANT_CASE"
    assert env.effects.count == 0


def test_malicious_retrieved_instruction_cannot_widen_tool_capability() -> None:
    env = lab.build_demo_environment(
        planner=lab.InjectionFollowingPlanner(), malicious_policy=True
    )
    state = _start_agent(env, "injection")

    assert state.status is lab.RunStatus.FAILED
    assert state.terminal_reason == "TOOL_NOT_ALLOWED"
    assert env.effects.count == 0
    assert all(event.tool_name != "export_customer_data" for event in state.trace)


def test_bounded_planner_treats_malicious_policy_text_as_untrusted_data() -> None:
    env = lab.build_demo_environment(malicious_policy=True)
    waiting = _start_agent(env, "safe-malicious-content")

    assert waiting.status is lab.RunStatus.WAITING_APPROVAL
    assert waiting.pending_call is not None
    assert waiting.pending_call.name == "publish_recommendation"
    assert env.effects.count == 0


def test_tool_schema_rejects_model_supplied_tenant_scope() -> None:
    env = lab.build_demo_environment()
    state = env.agent.start(
        run_id="schema",
        request=lab.demo_request(),
        principal=env.principals["alice"],
        workload=env.workload,
        max_cycles=0,
        now=env.now,
    )
    call = lab.ToolCall(
        "load_case",
        {"case_id": "case-101", "expected_version": 3, "tenant_id": "southstar"},
        "schema:load",
    )

    with pytest.raises(lab.AgentBoundaryError) as captured:
        env.gateway.invoke(state, call, now=env.now)

    assert captured.value.reason_code == "UNKNOWN_TOOL_ARGUMENT"


def test_stale_entitlements_stop_resume_before_effect() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env, "stale-entitlements")
    receipt = lab.approve_waiting_run(env, waiting)
    env.entitlements.change(waiting.principal.identity_key)

    completed = env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)

    assert completed.status is lab.RunStatus.FAILED
    assert completed.terminal_reason == "STALE_ENTITLEMENTS"
    assert env.effects.count == 0


def test_case_change_invalidates_the_approved_proposal() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env, "stale-case")
    receipt = lab.approve_waiting_run(env, waiting)
    current = env.cases.get("case-101")
    env.cases.replace(replace(current, version=current.version + 1))

    completed = env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)

    assert completed.status is lab.RunStatus.FAILED
    assert completed.terminal_reason == "STALE_CASE_VERSION"
    assert env.effects.count == 0
    assert not env.approvals.is_consumed(receipt.receipt_id)


def test_transient_timeout_retries_within_one_owned_budget() -> None:
    env = lab.build_demo_environment()
    env.faults.schedule(
        "retrieve_policy",
        "timeout-success:retrieve-policy",
        (lab.FaultKind.TIMEOUT_BEFORE_EFFECT, lab.FaultKind.TIMEOUT_BEFORE_EFFECT),
    )
    state = _start_agent(env, "timeout-success")

    assert state.status is lab.RunStatus.WAITING_APPROVAL
    assert state.usage.tool_calls == 3
    assert state.usage.tool_attempts == 5
    retrieval = [event for event in state.trace if event.tool_name == "retrieve_policy"]
    assert retrieval[0].attempts == 3


def test_tool_retry_exhaustion_is_an_explicit_terminal_failure() -> None:
    env = lab.build_demo_environment()
    env.faults.schedule(
        "retrieve_policy",
        "timeout-fail:retrieve-policy",
        (
            lab.FaultKind.TIMEOUT_BEFORE_EFFECT,
            lab.FaultKind.TIMEOUT_BEFORE_EFFECT,
            lab.FaultKind.TIMEOUT_BEFORE_EFFECT,
        ),
    )
    state = _start_agent(env, "timeout-fail")

    assert state.status is lab.RunStatus.FAILED
    assert state.terminal_reason == "TOOL_RETRY_EXHAUSTED"
    assert state.usage.tool_calls == 2
    assert state.usage.tool_attempts == 4
    assert env.effects.count == 0


def test_model_budget_exhaustion_stops_before_an_extra_model_call() -> None:
    env = lab.build_demo_environment()
    state = env.agent.start(
        run_id="model-budget",
        request=lab.demo_request(),
        principal=env.principals["alice"],
        workload=env.workload,
        limits=lab.RunLimits(max_model_calls=2),
        now=env.now,
    )

    assert state.status is lab.RunStatus.FAILED
    assert state.terminal_reason == "MODEL_CALL_BUDGET_EXHAUSTED"
    assert state.usage.model_calls == 2
    assert env.effects.count == 0


def test_cost_budget_is_checked_before_a_consequential_effect() -> None:
    env = lab.build_demo_environment()
    waiting = env.agent.start(
        run_id="cost-budget",
        request=lab.demo_request(),
        principal=env.principals["alice"],
        workload=env.workload,
        limits=lab.RunLimits(max_cost_units=19),
        now=env.now,
    )
    assert waiting.status is lab.RunStatus.WAITING_APPROVAL
    receipt = lab.approve_waiting_run(env, waiting)

    completed = env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)

    assert completed.status is lab.RunStatus.FAILED
    assert completed.terminal_reason == "COST_BUDGET_EXHAUSTED"
    assert env.effects.count == 0
    assert not env.approvals.is_consumed(receipt.receipt_id)


def test_cancellation_stops_before_model_or_tool_work() -> None:
    env = lab.build_demo_environment()
    env.cancellations.cancel("cancelled")
    state = _start_agent(env, "cancelled")

    assert state.status is lab.RunStatus.CANCELLED
    assert state.terminal_reason == "RUN_CANCELLED"
    assert state.usage == lab.RunUsage()
    assert env.effects.count == 0


def test_checkpoint_can_resume_on_a_fresh_runtime_instance() -> None:
    env = lab.build_demo_environment()
    partial = env.agent.start(
        run_id="restart",
        request=lab.demo_request(),
        principal=env.principals["alice"],
        workload=env.workload,
        max_cycles=2,
        now=env.now,
    )
    assert partial.status is lab.RunStatus.RUNNING
    assert partial.case is not None and partial.evidence is not None

    restarted = lab.AgentRuntime(
        gateway=env.gateway,
        checkpoints=env.checkpoints,
        planner=lab.BoundedPlanner(),
        cancellations=env.cancellations,
    )
    waiting = restarted.continue_run("restart", now=env.now)
    receipt = lab.approve_waiting_run(env, waiting)
    completed = restarted.resume_with_approval("restart", receipt, now=env.now + 1)

    assert waiting.status is lab.RunStatus.WAITING_APPROVAL
    assert completed.status is lab.RunStatus.SUCCEEDED
    assert completed.usage.model_calls == 4
    assert env.effects.count == 1


def test_checkpoint_optimistic_revision_rejects_stale_writer() -> None:
    env = lab.build_demo_environment()
    partial = env.agent.start(
        run_id="checkpoint-conflict",
        request=lab.demo_request(),
        principal=env.principals["alice"],
        workload=env.workload,
        max_cycles=1,
        now=env.now,
    )
    current = env.checkpoints.load(partial.run_id)
    env.checkpoints.save(current, expected_revision=current.revision)

    with pytest.raises(lab.AgentBoundaryError) as captured:
        env.checkpoints.save(current, expected_revision=current.revision)

    assert captured.value.reason_code == "CHECKPOINT_CONFLICT"


def test_unknown_write_outcome_is_reconciled_without_duplicate_effect() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env, "unknown-outcome")
    receipt = lab.approve_waiting_run(env, waiting)
    env.faults.schedule(
        "publish_recommendation",
        "unknown-outcome:publish-review",
        (lab.FaultKind.UNKNOWN_AFTER_EFFECT,),
    )

    completed = env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)

    assert completed.status is lab.RunStatus.SUCCEEDED
    assert env.effects.count == 1
    assert env.approvals.is_consumed(receipt.receipt_id)
    assert completed.trace[-1].reason_code == "TOOL_RECONCILED"


def test_expired_approval_fails_closed() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env, "expired")
    receipt = lab.approve_waiting_run(env, waiting)

    completed = env.agent.resume_with_approval(
        waiting.run_id, receipt, now=receipt.expires_at + 1
    )

    assert completed.status is lab.RunStatus.FAILED
    assert completed.terminal_reason == "APPROVAL_EXPIRED"
    assert env.effects.count == 0


def test_policy_version_change_invalidates_approval() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env, "policy-change")
    receipt = lab.approve_waiting_run(env, waiting)
    env.policy.version += 1

    completed = env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)

    assert completed.status is lab.RunStatus.FAILED
    assert completed.terminal_reason == "APPROVAL_BINDING_MISMATCH"
    assert env.effects.count == 0


def test_evidence_change_after_proposal_fails_publication() -> None:
    env = lab.build_demo_environment()
    waiting = _start_agent(env, "evidence-change")
    receipt = lab.approve_waiting_run(env, waiting)
    current = env.policies.get("exception-policy")
    changed_text = current.text + " Changed after proposal."
    env.policies.replace(
        replace(
            current,
            version=current.version + 1,
            text=changed_text,
            digest=lab.evidence_digest(
                changed_text,
                current.tenant_id,
                current.version + 1,
            ),
        )
    )

    completed = env.agent.resume_with_approval(waiting.run_id, receipt, now=env.now + 1)

    assert completed.status is lab.RunStatus.FAILED
    assert completed.terminal_reason == "STALE_EVIDENCE"
    assert env.effects.count == 0
    assert not env.approvals.is_consumed(receipt.receipt_id)


def test_architecture_evaluation_uses_outcome_and_cost_denominators() -> None:
    cases = (("case-101", 3), ("case-102", 1))
    workflow = lab.evaluate_architecture(lab.Architecture.WORKFLOW, cases)
    agent = lab.evaluate_architecture(lab.Architecture.BOUNDED_AGENT, cases)

    assert workflow.cases == agent.cases == 2
    assert workflow.successful_compliant_tasks == agent.successful_compliant_tasks == 2
    assert workflow.task_success_rate == agent.task_success_rate == 1.0
    assert workflow.forbidden_outcomes == agent.forbidden_outcomes == 0
    assert workflow.model_calls == 0
    assert agent.model_calls == 8
    assert workflow.cost_per_successful_compliant_task < agent.cost_per_successful_compliant_task
    assert lab.recommend_architecture(workflow, agent) is lab.Architecture.WORKFLOW
