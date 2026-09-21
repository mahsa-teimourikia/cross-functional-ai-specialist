"""Rebuild the canonical Course 3 notebook from reviewable cell sources."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
COURSE = ROOT / "curriculum" / "advanced" / "03-enterprise-identity-agent-authorization"
TARGET = COURSE / "enterprise_identity_agent_authorization.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Course 3 Lab — Enterprise Identity and Agent Authorization

- **Scenario:** Northstar delegated underwriting exception
- **Mode:** deterministic and credential-free
- **Expected time:** 3-4 hours plus the authorization ADR

You will move from token-shaped input to trusted user/workload principals, evaluate policy, issue an
attenuated delegation, obtain independent approval, and apply one idempotent effect. Every failure
is observable through a reason code rather than private model reasoning.
"""
    ),
    md(
        """
## 0. Outcomes, safety boundaries, and evidence limits

- The lab performs no JWT cryptography, OAuth redirects, cloud calls, or real side effects.
- `signature_valid` represents the result a real JOSE library or introspection adapter would supply;
  setting it locally is **not** cryptographic proof.
- Identity, tenant, scopes, roles, resources, policy, delegations, and approvals stay outside model
  text and tool arguments.
- The deterministic results prove application invariants, not identity-provider security or cloud
  availability.

The trusted application validates, authorizes, persists, executes, and verifies. A model may only
propose an action.
"""
    ),
    code(
        """
# ruff: noqa: E402
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

course_dir = Path.cwd()
if not (course_dir / "lab.py").exists():
    course_dir = (
        Path.cwd() / "curriculum" / "advanced" / "03-enterprise-identity-agent-authorization"
    )
assert (course_dir / "lab.py").exists(), "Run from the repository or course directory"
sys.path.insert(0, str(course_dir.resolve()))

from lab import (
    Action,
    ActionRequest,
    AuthorizationCase,
    PrincipalKind,
    TrustBoundaryError,
    build_demo_environment,
    evaluate_authorization,
    make_demo_token,
)


def denied_reason(operation) -> str:
    try:
        operation()
    except TrustBoundaryError as error:
        return error.reason_code
    raise AssertionError("The operation was expected to fail closed")
"""
    ),
    md(
        """
## 1. Begin with the anti-pattern

The unsafe baseline accepts identity, role, tenant, and approval as ordinary tool arguments. This
is authorization by self-assertion: the model or caller can fabricate every trusted fact.
"""
    ),
    code(
        """
def unsafe_tool_gateway(arguments: dict[str, object]) -> str:
    if arguments.get("role") == "senior-underwriter" and arguments.get("approved") is True:
        return f"applied:{arguments['tenant']}:{arguments['target']}"
    return "denied"


fabricated = unsafe_tool_gateway(
    {
        "role": "senior-underwriter",
        "approved": True,
        "tenant": "northstar",
        "target": "case-101",
    }
)
print("Unsafe fabricated result:", fabricated)
assert fabricated.startswith("applied")
"""
    ),
    md(
        """
This code is intentionally unsafe and local. Parsing fields proves only shape. The corrected design
derives identity from a verified token adapter, loads tenant/resource state from authoritative
stores, evaluates policy, and treats approval as a bound single-use receipt.
"""
    ),
    md(
        """
## 2. Build the fictional trust environment

The environment contains Alice (underwriter), Bob (senior approver), Mallory (another tenant), a
Northstar agent workload, a narrow subagent, three case resources, a policy engine, delegation and
approval services, a tool gateway, and an atomic teaching store.
"""
    ),
    code(
        """
env = build_demo_environment()
alice = env.principals["alice"]
bob = env.principals["bob"]
mallory = env.principals["mallory"]
agent = env.principals["agent"]
subagent = env.principals["subagent"]

print("Alice identity key:", alice.identity_key)
print("Agent kind/scopes:", agent.kind, sorted(agent.scopes))
print("Resources:", env.resources)
assert alice.kind is PrincipalKind.USER
assert agent.kind is PrincipalKind.WORKLOAD
assert alice.tenant_id == agent.tenant_id == "northstar"
"""
    ),
    md(
        """
## 3. Token boundary: decoded is not verified

The verifier requires an exact trusted issuer/key, allow-listed algorithm, simulated valid
signature evidence, access-token use, API audience, valid time window, subject, and tenant. A real
adapter would use a maintained JOSE library or introspection endpoint; this lab tests the
surrounding decision contract.
"""
    ),
    code(
        """
base_token = make_demo_token(
    "new-underwriter",
    "northstar",
    PrincipalKind.USER,
    now=env.now,
    roles=frozenset({"underwriter"}),
)

token_failures = {
    "wrong audience": replace(base_token, audiences=frozenset({"https://wrong.example"})),
    "ID token at API": replace(base_token, token_use="id"),
    "bad signature": replace(base_token, signature_valid=False),
    "algorithm none": replace(base_token, algorithm="none"),
    "untrusted issuer": replace(base_token, issuer="https://attacker.example"),
}
observed = {
    name: denied_reason(lambda token=token: env.verifier.verify(token, now=env.now))
    for name, token in token_failures.items()
}
print(observed)
assert observed == {
    "wrong audience": "WRONG_AUDIENCE",
    "ID token at API": "WRONG_TOKEN_USE",
    "bad signature": "INVALID_SIGNATURE",
    "algorithm none": "ALGORITHM_REJECTED",
    "untrusted issuer": "UNTRUSTED_ISSUER",
}
"""
    ),
    md(
        """
An email address or `sub` alone is not a federated identity key. OpenID Connect subjects are scoped
to their issuer. Two issuers may legitimately emit the same subject string.
"""
    ),
    code(
        """
lookalike = replace(alice, issuer="https://other-issuer.example")
print(alice.subject, alice.identity_key)
print(lookalike.subject, lookalike.identity_key)
assert alice.subject == lookalike.subject
assert alice.identity_key != lookalike.identity_key
"""
    ),
    md(
        """
## 4. Inspect principal-action-resource policy

The policy combines user roles, resource ownership/classification, tenant equality, and workload
scopes. It defaults to deny. Workload eligibility does not substitute for user authority.
"""
    ),
    code(
        """
matrix = [
    ("alice standard read", alice, Action.READ_CASE, env.resources["case-101"]),
    ("alice own restricted read", alice, Action.READ_CASE, env.resources["case-202"]),
    ("bob approve Alice case", bob, Action.APPROVE_EXCEPTION, env.resources["case-101"]),
    ("alice approve own case", alice, Action.APPROVE_EXCEPTION, env.resources["case-101"]),
    ("alice other tenant", alice, Action.READ_CASE, env.resources["case-901"]),
    ("agent apply scope", agent, Action.APPLY_APPROVED_EXCEPTION, env.resources["case-101"]),
    ("subagent apply", subagent, Action.APPLY_APPROVED_EXCEPTION, env.resources["case-101"]),
]
for name, principal, action, resource in matrix:
    decision = env.policy.evaluate(principal, action, resource)
    print(f"{name:28} {decision.effect.value:5} {decision.reason_code}")

cross_tenant = env.policy.evaluate(alice, Action.READ_CASE, env.resources["case-901"])
narrow_actor = env.policy.evaluate(
    subagent,
    Action.APPLY_APPROVED_EXCEPTION,
    env.resources["case-101"],
)
assert cross_tenant.reason_code == "TENANT_MISMATCH"
assert not narrow_actor.allowed
"""
    ),
    md(
        """
## 5. Evaluate policy with correct safety denominators

The labeled matrix distinguishes unauthorized effects from false denials. “Four attacks blocked”
is not a forbidden-outcome rate unless the labeled forbidden population is defined.
"""
    ),
    code(
        """
cases = [
    AuthorizationCase("owner-read", alice, Action.READ_CASE, env.resources["case-101"], True),
    AuthorizationCase("cross-tenant", alice, Action.READ_CASE, env.resources["case-901"], False),
    AuthorizationCase(
        "senior-approve", bob, Action.APPROVE_EXCEPTION, env.resources["case-101"], True
    ),
    AuthorizationCase(
        "self-approve", alice, Action.APPROVE_EXCEPTION, env.resources["case-101"], False
    ),
    AuthorizationCase("workload-scope", agent, Action.READ_CASE, env.resources["case-101"], True),
    AuthorizationCase(
        "narrow-workload",
        subagent,
        Action.APPLY_APPROVED_EXCEPTION,
        env.resources["case-101"],
        False,
    ),
]
evaluation = evaluate_authorization(env.policy, cases)
print(evaluation)
assert evaluation.total == 6
assert evaluation.accuracy == 1.0
assert evaluation.forbidden_outcomes == 0
assert evaluation.valid_work_blocked == 0
"""
    ),
    md(
        """
## 6. Issue a narrow user-to-workload delegation

Alice delegates only three actions on one case for ten minutes to one verified workload. The service
checks Alice's permission and the workload's eligible scopes for every action/resource pair. The
grant records the policy version and cannot carry approval authority.
"""
    ),
    code(
        """
delegated_actions = frozenset(
    {Action.READ_CASE, Action.PROPOSE_EXCEPTION, Action.APPLY_APPROVED_EXCEPTION}
)
grant = env.delegation_service.issue(
    "grant-001",
    subject=alice,
    actor=agent,
    actions=delegated_actions,
    resource_ids=frozenset({"case-101"}),
    now=env.now,
    expires_at=env.now + 600,
)
print(grant)
assert grant.allowed_actions == delegated_actions
assert grant.resource_ids == frozenset({"case-101"})
assert grant.policy_version == env.policy.version
"""
    ),
    md(
        """
Delegation is an intersection, not an impersonation shortcut. Attempts to delegate approval,
another tenant's resource, or an excessive lifetime fail during issuance.
"""
    ),
    code(
        """
approval_delegation = denied_reason(
    lambda: env.delegation_service.issue(
        "grant-approval",
        subject=alice,
        actor=agent,
        actions=frozenset({Action.APPROVE_EXCEPTION}),
        resource_ids=frozenset({"case-101"}),
        now=env.now,
        expires_at=env.now + 300,
    )
)
cross_tenant_delegation = denied_reason(
    lambda: env.delegation_service.issue(
        "grant-cross-tenant",
        subject=alice,
        actor=agent,
        actions=frozenset({Action.READ_CASE}),
        resource_ids=frozenset({"case-901"}),
        now=env.now,
        expires_at=env.now + 300,
    )
)
print(approval_delegation, cross_tenant_delegation)
assert approval_delegation == "APPROVAL_NOT_DELEGABLE"
assert cross_tenant_delegation == "SUBJECT_PERMISSION_MISSING"
"""
    ),
    md(
        """
## 7. Attenuate once for a subagent

The subagent is eligible only to read. Its child grant reduces actions and lifetime. Adding an
action, resource, time, tenant, or delegation hop would widen authority and is denied.
"""
    ),
    code(
        """
child = env.delegation_service.attenuate(
    "grant-child",
    parent=grant,
    child_actor=subagent,
    actions=frozenset({Action.READ_CASE}),
    resource_ids=frozenset({"case-101"}),
    now=env.now + 1,
    expires_at=env.now + 300,
)
print(child)
assert child.allowed_actions < grant.allowed_actions
assert child.expires_at < grant.expires_at
assert child.parent_grant_id == grant.grant_id

widening = denied_reason(
    lambda: env.delegation_service.attenuate(
        "grant-wide",
        parent=grant,
        child_actor=subagent,
        actions=frozenset({Action.APPROVE_EXCEPTION}),
        resource_ids=frozenset({"case-101"}),
        now=env.now + 1,
        expires_at=env.now + 300,
    )
)
print("Widening attempt:", widening)
assert widening == "DELEGATION_WIDENING"
"""
    ),
    md(
        """
## 8. Tool arguments remain untrusted data

`ActionRequest` has no identity or role field. Extra parameters on a read operation fail schema and
business validation; they cannot override the verified principal or authoritative tenant.
"""
    ),
    code(
        """
injected_request = ActionRequest.create(
    "op-injection",
    Action.READ_CASE,
    "case-101",
    {"role": "senior-underwriter", "tenant": "other-tenant"},
)
injection_reason = denied_reason(
    lambda: env.gateway.execute(
        actor=agent,
        grant=grant,
        request=injected_request,
        now=env.now + 2,
    )
)
print(injection_reason)
assert injection_reason == "INVALID_ACTION_PARAMETERS"
"""
    ),
    md(
        """
## 9. Prepare one exact consequential proposal

The gateway revalidates the actor, subject, grant, target, tenant, parameters, and both policy
decisions. It then hashes the complete operation/delegation context. The digest changes if any
consequential field changes.
"""
    ),
    code(
        """
request = ActionRequest.create(
    "op-apply-001",
    Action.APPLY_APPROVED_EXCEPTION,
    "case-101",
    {"decision": "approve", "limit": "50000"},
)
proposal = env.gateway.prepare_proposal(
    "proposal-001",
    actor=agent,
    grant=grant,
    request=request,
    now=env.now + 3,
)
print(proposal)
assert proposal.subject_identity == alice.identity_key
assert proposal.actor_identity == agent.identity_key
assert len(proposal.request_digest) == 64
"""
    ),
    md(
        """
## 10. Independent approval creates a receipt, not a boolean

Bob must be a current, same-tenant senior user who is not the requester/resource owner. The receipt
binds the exact proposal, policy, parties, delegation, target, and expiry. Alice cannot approve her
own request even though she can propose it.
"""
    ),
    code(
        """
self_approval = denied_reason(
    lambda: env.approval_service.issue(
        "approval-self",
        proposal,
        approver=alice,
        now=env.now + 4,
        expires_at=env.now + 120,
    )
)
assert self_approval == "SEPARATION_OF_DUTIES"

receipt = env.approval_service.issue(
    "approval-001",
    proposal,
    approver=bob,
    now=env.now + 4,
    expires_at=env.now + 120,
)
print(receipt)
assert receipt.approver_identity == bob.identity_key
assert receipt.request_digest == proposal.request_digest
assert receipt.consumed_by_operation is None
"""
    ),
    md(
        """
## 11. Failure injection — alter the approved action

The model changes the approved limit from 50,000 to 90,000 while keeping the approval ID. The new
digest does not match. No effect occurs, and the legitimate receipt is not silently converted into
general authority.
"""
    ),
    code(
        """
altered = ActionRequest.create(
    "op-apply-001",
    Action.APPLY_APPROVED_EXCEPTION,
    "case-101",
    {"decision": "approve", "limit": "90000"},
)
altered_reason = denied_reason(
    lambda: env.gateway.execute(
        actor=agent,
        grant=grant,
        request=altered,
        now=env.now + 5,
        approval_id=receipt.receipt_id,
    )
)
print(altered_reason, "effects:", env.store.effect_count)
assert altered_reason == "APPROVAL_BINDING_MISMATCH"
assert env.store.effect_count == 0
assert receipt.consumed_by_operation is None
"""
    ),
    md(
        """
## 12. Execute atomically and retry idempotently

The teaching store consumes the receipt, records the stable operation, and applies the effect in one
atomic method. The exact retry returns the prior record. A new operation cannot reuse the receipt.
"""
    ),
    code(
        """
first, first_replayed = env.gateway.execute(
    actor=agent,
    grant=grant,
    request=request,
    now=env.now + 6,
    approval_id=receipt.receipt_id,
)
retry, retry_replayed = env.gateway.execute(
    actor=agent,
    grant=grant,
    request=request,
    now=env.now + 7,
    approval_id=receipt.receipt_id,
)
new_operation = replace(request, operation_id="op-apply-002")
replay_reason = denied_reason(
    lambda: env.gateway.execute(
        actor=agent,
        grant=grant,
        request=new_operation,
        now=env.now + 8,
        approval_id=receipt.receipt_id,
    )
)

print(first)
print("exact retry:", retry_replayed, "new operation:", replay_reason)
assert first == retry
assert not first_replayed and retry_replayed
assert replay_reason == "APPROVAL_REPLAY"
assert env.store.effect_count == 1
"""
    ),
    md(
        """
The order matters. The store recognizes the same operation/digest before treating its approval as a
replay. Reusing the operation ID with changed input is a conflict; using the consumed receipt for a
new operation is an approval replay.
"""
    ),
    md(
        """
## 13. Failure injection — policy and entitlement lifecycle

A valid-looking grant can become stale. The gateway rechecks current policy version and
authoritative entitlement state rather than trusting the grant object forever.
"""
    ),
    code(
        """
lifecycle_env = build_demo_environment(now=env.now)
lifecycle_grant = lifecycle_env.delegation_service.issue(
    "grant-lifecycle",
    subject=lifecycle_env.principals["alice"],
    actor=lifecycle_env.principals["agent"],
    actions=frozenset({Action.READ_CASE}),
    resource_ids=frozenset({"case-101"}),
    now=lifecycle_env.now,
    expires_at=lifecycle_env.now + 600,
)
read_request = ActionRequest.create("op-read", Action.READ_CASE, "case-101")

lifecycle_env.policy.version = "policy-next"
stale_policy = denied_reason(
    lambda: lifecycle_env.gateway.execute(
        actor=lifecycle_env.principals["agent"],
        grant=lifecycle_grant,
        request=read_request,
        now=lifecycle_env.now + 1,
    )
)
lifecycle_env.policy.version = lifecycle_grant.policy_version
lifecycle_env.registry.change_entitlements(lifecycle_env.principals["alice"].identity_key)
stale_entitlements = denied_reason(
    lambda: lifecycle_env.gateway.execute(
        actor=lifecycle_env.principals["agent"],
        grant=lifecycle_grant,
        request=read_request,
        now=lifecycle_env.now + 2,
    )
)
print(stale_policy, stale_entitlements)
assert stale_policy == "STALE_POLICY"
assert stale_entitlements == "STALE_ENTITLEMENTS"
"""
    ),
    md(
        """
## 14. Inspect audit evidence

The audit records subject and actor identity keys, tenant, operation, action, target, decision,
reason, policy/delegation and approval IDs. It deliberately excludes bearer tokens, document
content, and hidden reasoning.
"""
    ),
    code(
        """
for event in env.gateway.audit[-8:]:
    print(event)

reason_codes = {event.reason_code for event in env.gateway.audit}
assert "APPROVAL_BINDING_MISMATCH" in reason_codes
assert "EXECUTED" in reason_codes
assert "IDEMPOTENT_REPLAY" in reason_codes
assert "APPROVAL_REPLAY" in reason_codes
assert all(not hasattr(event, "token") for event in env.gateway.audit)
"""
    ),
    md(
        """
## 15. Architecture alternatives

| Option | Strong fit | Primary review question |
|---|---|---|
| embedded policy + ACL | one bounded app | when is externalization justified? |
| Cedar / Verified Permissions | typed app authorization | who owns inputs and rollout? |
| OPA/Rego | cross-stack policy over structured input | can teams govern flexible policy safely? |
| OpenFGA | nested sharing and relationship graphs | what consistency does the product require? |
| cloud IAM | cloud resource/workload authorization | where does app-object authorization live? |

The lab is provider-neutral. Replacing the local policy engine with a managed PDP does not remove
the gateway's responsibility to source trusted inputs, enforce obligations, protect the effect, and
audit the real result.
"""
    ),
    md(
        """
## 16. Production upgrade

- Use maintained OAuth/OIDC/JOSE libraries; pin exact issuer/audience/resource and token profile.
- Prefer managed/federated short-lived workload identity; isolate credentials from model context.
- Define authoritative ownership and freshness for roles, attributes, relationships, resources,
  policy, risk, delegation, and revocation.
- Choose embedded/sidecar/remote PDP from latency, availability, consistency, privacy, and
  ownership.
- Define fail-closed versus explicit degraded modes and policy/cache versioning.
- Make approval consumption and effect atomic, or use outbox/workflow/reconciliation.
- Add access review, emergency deny, key rotation, policy canary/rollback, and incident runbooks.
- Measure forbidden outcomes, valid work blocked, decision latency, cache staleness, approval
  bypass/replay, and effects per successful logical operation.

This local simulator proves none of the provider-specific integration, cryptographic, network,
regional, or operational claims; those require integration, security, load, and recovery evidence.
"""
    ),
    md(
        """
## 17. Portfolio exercises

1. Add future-issued-token and disabled-subject tests; explain the enforcement layer.
2. Add a second tenant whose role names overlap; prove issuer/tenant/resource isolation.
3. Design a policy cache key and show how omitting policy or entitlement version causes stale allow.
4. Compare Cedar, OPA, OpenFGA, and embedded policy for Northstar with a weighted decision record.
5. Draw the production identity sequence from browser to IdP, API, agent workload, PDP, tool, and
   downstream system; mark every audience and credential exchange.
6. Design the database transaction or recovery protocol that atomically consumes approval and
   records an external operation under unknown outcomes.

Defend what evidence would cause you to reverse the architecture choice.
"""
    ),
    md(
        """
## 18. Completion checklist

- [x] Token-shaped input does not become a principal without all validation gates.
- [x] Issuer and subject jointly identify the principal.
- [x] User and workload policy are both required.
- [x] Cross-tenant access and tool-argument role injection fail closed.
- [x] Delegation attenuates action, resource, lifetime, depth, and policy version.
- [x] Approval authority is not delegated to the agent.
- [x] Approval binds the exact proposal and independent approver.
- [x] Receipt consumption, idempotency, and effect are atomic in the teaching store.
- [x] Stale policy and entitlement state invalidate old authority.
- [x] Audit evidence excludes credentials and hidden reasoning.
- [ ] Your authorization matrix, identity sequence, ADR, and operating plan are review-ready.

Complete the Course 3 checkpoint after defending the negative cases and production gaps.
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
