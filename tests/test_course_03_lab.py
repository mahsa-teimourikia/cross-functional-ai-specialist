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
        / "03-enterprise-identity-agent-authorization"
        / "lab.py"
    )
    spec = importlib.util.spec_from_file_location("course_03_lab", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lab = _load_course_module()


def issue_grant(env, *, actions=None, resources=None):
    return env.delegation_service.issue(
        "grant-001",
        subject=env.principals["alice"],
        actor=env.principals["agent"],
        actions=actions
        or frozenset(
            {
                lab.Action.READ_CASE,
                lab.Action.PROPOSE_EXCEPTION,
                lab.Action.APPLY_APPROVED_EXCEPTION,
            }
        ),
        resource_ids=resources or frozenset({"case-101"}),
        now=env.now,
        expires_at=env.now + 600,
    )


def approved_action(env, *, operation_id: str = "op-001", limit: str = "50000"):
    grant = issue_grant(env)
    request = lab.ActionRequest.create(
        operation_id,
        lab.Action.APPLY_APPROVED_EXCEPTION,
        "case-101",
        {"decision": "approve", "limit": limit},
    )
    proposal = env.gateway.prepare_proposal(
        "proposal-001",
        actor=env.principals["agent"],
        grant=grant,
        request=request,
        now=env.now,
    )
    receipt = env.approval_service.issue(
        "approval-001",
        proposal,
        approver=env.principals["bob"],
        now=env.now + 1,
        expires_at=env.now + 120,
    )
    return grant, request, receipt


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"audiences": frozenset({"https://wrong.example"})}, "WRONG_AUDIENCE"),
        ({"token_use": "id"}, "WRONG_TOKEN_USE"),
        ({"signature_valid": False}, "INVALID_SIGNATURE"),
        ({"algorithm": "none"}, "ALGORITHM_REJECTED"),
    ],
)
def test_token_boundary_rejects_untrusted_conditions(change, reason: str) -> None:
    env = lab.build_demo_environment()
    token = lab.make_demo_token(
        "new-user",
        "northstar",
        lab.PrincipalKind.USER,
        now=env.now,
        roles=frozenset({"underwriter"}),
    )

    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.verifier.verify(replace(token, **change), now=env.now)
    assert captured.value.reason_code == reason


def test_subject_identity_is_namespaced_by_issuer() -> None:
    env = lab.build_demo_environment()
    alice = env.principals["alice"]
    lookalike = replace(alice, issuer="https://other-issuer.example")

    assert alice.subject == lookalike.subject
    assert alice.identity_key != lookalike.identity_key


def test_expired_token_is_rejected_before_identity_is_trusted() -> None:
    env = lab.build_demo_environment()
    token = lab.make_demo_token(
        "expired-user",
        "northstar",
        lab.PrincipalKind.USER,
        now=env.now,
        roles=frozenset({"underwriter"}),
    )

    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.verifier.verify(replace(token, expires_at=env.now - 31), now=env.now)
    assert captured.value.reason_code == "TOKEN_EXPIRED"


def test_policy_denies_cross_tenant_access() -> None:
    env = lab.build_demo_environment()
    decision = env.policy.evaluate(
        env.principals["alice"], lab.Action.READ_CASE, env.resources["case-901"]
    )

    assert not decision.allowed
    assert decision.reason_code == "TENANT_MISMATCH"


def test_agent_cannot_receive_approval_authority() -> None:
    env = lab.build_demo_environment()

    with pytest.raises(lab.TrustBoundaryError) as captured:
        issue_grant(env, actions=frozenset({lab.Action.APPROVE_EXCEPTION}))
    assert captured.value.reason_code == "APPROVAL_NOT_DELEGABLE"


def test_child_delegation_can_only_attenuate_parent_authority() -> None:
    env = lab.build_demo_environment()
    parent = issue_grant(env)
    child = env.delegation_service.attenuate(
        "grant-child",
        parent=parent,
        child_actor=env.principals["subagent"],
        actions=frozenset({lab.Action.READ_CASE}),
        resource_ids=frozenset({"case-101"}),
        now=env.now + 1,
        expires_at=env.now + 300,
    )

    assert child.allowed_actions < parent.allowed_actions
    assert child.depth == 1
    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.delegation_service.attenuate(
            "grant-too-wide",
            parent=parent,
            child_actor=env.principals["subagent"],
            actions=frozenset({lab.Action.APPROVE_EXCEPTION}),
            resource_ids=frozenset({"case-101"}),
            now=env.now + 1,
            expires_at=env.now + 300,
        )
    assert captured.value.reason_code == "DELEGATION_WIDENING"


def test_model_controlled_parameters_cannot_claim_identity_or_scope() -> None:
    env = lab.build_demo_environment()
    grant = issue_grant(env, actions=frozenset({lab.Action.READ_CASE}))
    request = lab.ActionRequest.create(
        "op-role-injection",
        lab.Action.READ_CASE,
        "case-101",
        {"role": "senior-underwriter", "tenant": "northstar"},
    )

    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.gateway.execute(
            actor=env.principals["agent"], grant=grant, request=request, now=env.now
        )
    assert captured.value.reason_code == "INVALID_ACTION_PARAMETERS"


def test_consequential_action_requires_bound_independent_approval() -> None:
    env = lab.build_demo_environment()
    grant = issue_grant(env)
    request = lab.ActionRequest.create(
        "op-no-approval",
        lab.Action.APPLY_APPROVED_EXCEPTION,
        "case-101",
        {"decision": "approve", "limit": "50000"},
    )

    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.gateway.execute(
            actor=env.principals["agent"], grant=grant, request=request, now=env.now
        )
    assert captured.value.reason_code == "APPROVAL_REQUIRED"
    assert env.store.effect_count == 0


def test_requester_cannot_approve_own_proposal() -> None:
    env = lab.build_demo_environment()
    grant = issue_grant(env)
    request = lab.ActionRequest.create(
        "op-self-approval",
        lab.Action.APPLY_APPROVED_EXCEPTION,
        "case-101",
        {"decision": "approve", "limit": "50000"},
    )
    proposal = env.gateway.prepare_proposal(
        "proposal-self",
        actor=env.principals["agent"],
        grant=grant,
        request=request,
        now=env.now,
    )

    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.approval_service.issue(
            "approval-self",
            proposal,
            approver=env.principals["alice"],
            now=env.now + 1,
            expires_at=env.now + 120,
        )
    assert captured.value.reason_code == "SEPARATION_OF_DUTIES"


def test_altered_action_invalidates_approval_binding() -> None:
    env = lab.build_demo_environment()
    grant, _, receipt = approved_action(env)
    altered = lab.ActionRequest.create(
        "op-001",
        lab.Action.APPLY_APPROVED_EXCEPTION,
        "case-101",
        {"decision": "approve", "limit": "90000"},
    )

    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.gateway.execute(
            actor=env.principals["agent"],
            grant=grant,
            request=altered,
            now=env.now + 2,
            approval_id=receipt.receipt_id,
        )
    assert captured.value.reason_code == "APPROVAL_BINDING_MISMATCH"
    assert env.store.effect_count == 0


def test_approval_is_single_use_but_same_operation_retry_is_idempotent() -> None:
    env = lab.build_demo_environment()
    grant, request, receipt = approved_action(env)
    first, first_replayed = env.gateway.execute(
        actor=env.principals["agent"],
        grant=grant,
        request=request,
        now=env.now + 2,
        approval_id=receipt.receipt_id,
    )
    retry, retry_replayed = env.gateway.execute(
        actor=env.principals["agent"],
        grant=grant,
        request=request,
        now=env.now + 3,
        approval_id=receipt.receipt_id,
    )

    assert first == retry
    assert not first_replayed and retry_replayed
    assert env.store.effect_count == 1

    new_operation = replace(request, operation_id="op-002")
    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.gateway.execute(
            actor=env.principals["agent"],
            grant=grant,
            request=new_operation,
            now=env.now + 4,
            approval_id=receipt.receipt_id,
        )
    assert captured.value.reason_code == "APPROVAL_REPLAY"


def test_same_operation_id_with_altered_request_is_rejected() -> None:
    env = lab.build_demo_environment()
    grant, request, receipt = approved_action(env)
    env.gateway.execute(
        actor=env.principals["agent"],
        grant=grant,
        request=request,
        now=env.now + 2,
        approval_id=receipt.receipt_id,
    )
    altered = replace(
        request,
        parameters=(("decision", "approve"), ("limit", "60000")),
    )

    with pytest.raises(lab.TrustBoundaryError) as captured:
        env.gateway.execute(
            actor=env.principals["agent"],
            grant=grant,
            request=altered,
            now=env.now + 3,
            approval_id=receipt.receipt_id,
        )
    assert captured.value.reason_code == "OPERATION_CONFLICT"
    assert env.store.effect_count == 1


def test_policy_change_and_entitlement_change_invalidate_old_authority() -> None:
    env = lab.build_demo_environment()
    grant = issue_grant(env, actions=frozenset({lab.Action.READ_CASE}))
    request = lab.ActionRequest.create("op-read", lab.Action.READ_CASE, "case-101")
    env.policy.version = "policy-2026-09-21"

    with pytest.raises(lab.TrustBoundaryError) as stale_policy:
        env.gateway.execute(
            actor=env.principals["agent"], grant=grant, request=request, now=env.now + 1
        )
    assert stale_policy.value.reason_code == "STALE_POLICY"

    env.policy.version = grant.policy_version
    env.registry.change_entitlements(env.principals["alice"].identity_key)
    with pytest.raises(lab.TrustBoundaryError) as stale_identity:
        env.gateway.execute(
            actor=env.principals["agent"], grant=grant, request=request, now=env.now + 2
        )
    assert stale_identity.value.reason_code == "STALE_ENTITLEMENTS"


def test_disabled_workload_and_expired_delegation_are_denied_at_execution() -> None:
    env = lab.build_demo_environment()
    grant = issue_grant(env, actions=frozenset({lab.Action.READ_CASE}))
    request = lab.ActionRequest.create("op-read", lab.Action.READ_CASE, "case-101")
    env.registry.disable(env.principals["agent"].identity_key)

    with pytest.raises(lab.TrustBoundaryError) as inactive:
        env.gateway.execute(
            actor=env.principals["agent"],
            grant=grant,
            request=request,
            now=env.now + 1,
        )
    assert inactive.value.reason_code == "PRINCIPAL_INACTIVE"

    fresh = lab.build_demo_environment()
    expiring_grant = issue_grant(fresh, actions=frozenset({lab.Action.READ_CASE}))
    with pytest.raises(lab.TrustBoundaryError) as expired:
        fresh.gateway.execute(
            actor=fresh.principals["agent"],
            grant=expiring_grant,
            request=request,
            now=expiring_grant.expires_at,
        )
    assert expired.value.reason_code == "DELEGATION_EXPIRED"


def test_authorization_evaluation_keeps_safety_denominators_separate() -> None:
    env = lab.build_demo_environment()
    cases = [
        lab.AuthorizationCase(
            "owner-read",
            env.principals["alice"],
            lab.Action.READ_CASE,
            env.resources["case-101"],
            True,
        ),
        lab.AuthorizationCase(
            "cross-tenant",
            env.principals["alice"],
            lab.Action.READ_CASE,
            env.resources["case-901"],
            False,
        ),
        lab.AuthorizationCase(
            "independent-approval",
            env.principals["bob"],
            lab.Action.APPROVE_EXCEPTION,
            env.resources["case-101"],
            True,
        ),
    ]

    report = lab.evaluate_authorization(env.policy, cases)

    assert report.total == 3
    assert report.accuracy == 1.0
    assert report.forbidden_outcomes == 0
    assert report.valid_work_blocked == 0
