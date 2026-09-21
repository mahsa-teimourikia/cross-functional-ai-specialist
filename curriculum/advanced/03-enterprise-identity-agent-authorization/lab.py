"""Deterministic identity and authorization lab for Course 3.

This module does not implement cryptography or an identity provider. It models the
application controls that remain after a trusted adapter verifies a token: issuer and
audience checks, principal construction, policy decisions, capability attenuation,
approval binding, atomic consumption, idempotent execution, and safe audit evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class PrincipalKind(StrEnum):
    USER = "user"
    WORKLOAD = "workload"


class Action(StrEnum):
    READ_CASE = "read_case"
    PROPOSE_EXCEPTION = "propose_exception"
    APPLY_APPROVED_EXCEPTION = "apply_approved_exception"
    APPROVE_EXCEPTION = "approve_exception"


class DecisionEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class ExecutionStatus(StrEnum):
    COMPLETED = "completed"
    APPLIED = "applied"


class TrustBoundaryError(Exception):
    """An authentication, authorization, delegation, or approval invariant failed."""

    def __init__(self, message: str, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class UnverifiedToken:
    """Decoded token-shaped input; no field is trusted until verification succeeds."""

    issuer: str
    subject: str
    audiences: frozenset[str]
    tenant_id: str
    token_use: str
    principal_kind: PrincipalKind
    scopes: frozenset[str]
    roles: frozenset[str]
    issued_at: int
    not_before: int
    expires_at: int
    algorithm: str
    key_id: str
    signature_valid: bool
    entitlement_version: int = 1


@dataclass(frozen=True, slots=True)
class Principal:
    issuer: str
    subject: str
    tenant_id: str
    kind: PrincipalKind
    scopes: frozenset[str]
    roles: frozenset[str]
    token_id: str
    token_expires_at: int
    entitlement_version: int

    @property
    def identity_key(self) -> str:
        """Subjects are unique within an issuer, not globally."""

        return f"{self.issuer}|{self.subject}"


class DeterministicTokenVerifier:
    """Models verification decisions; it deliberately does not perform JWT cryptography."""

    def __init__(
        self,
        trusted_keys: Mapping[str, frozenset[str]],
        *,
        expected_audience: str,
        allowed_algorithms: frozenset[str] = frozenset({"RS256", "ES256"}),
        clock_skew_seconds: int = 30,
    ) -> None:
        self._trusted_keys = dict(trusted_keys)
        self.expected_audience = expected_audience
        self.allowed_algorithms = allowed_algorithms
        self.clock_skew_seconds = clock_skew_seconds

    def verify(self, token: UnverifiedToken, *, now: int) -> Principal:
        issuer_keys = self._trusted_keys.get(token.issuer)
        if issuer_keys is None:
            raise TrustBoundaryError("issuer is not trusted", "UNTRUSTED_ISSUER")
        if token.algorithm not in self.allowed_algorithms:
            raise TrustBoundaryError("signing algorithm is not allowed", "ALGORITHM_REJECTED")
        if token.key_id not in issuer_keys or not token.signature_valid:
            raise TrustBoundaryError("token signature could not be verified", "INVALID_SIGNATURE")
        if token.token_use != "access":
            raise TrustBoundaryError("an access token is required", "WRONG_TOKEN_USE")
        if self.expected_audience not in token.audiences:
            raise TrustBoundaryError("token is not intended for this API", "WRONG_AUDIENCE")
        if now + self.clock_skew_seconds < token.not_before:
            raise TrustBoundaryError("token is not active yet", "TOKEN_NOT_ACTIVE")
        if now - self.clock_skew_seconds >= token.expires_at:
            raise TrustBoundaryError("token has expired", "TOKEN_EXPIRED")
        if token.issued_at > now + self.clock_skew_seconds:
            raise TrustBoundaryError("token issue time is in the future", "INVALID_ISSUED_AT")
        if not token.subject or not token.tenant_id:
            raise TrustBoundaryError("subject and tenant are required", "MISSING_IDENTITY")

        token_id_material = "\x1f".join(
            (token.issuer, token.subject, str(token.issued_at), token.key_id)
        )
        return Principal(
            issuer=token.issuer,
            subject=token.subject,
            tenant_id=token.tenant_id,
            kind=token.principal_kind,
            scopes=token.scopes,
            roles=token.roles,
            token_id=hashlib.sha256(token_id_material.encode()).hexdigest()[:16],
            token_expires_at=token.expires_at,
            entitlement_version=token.entitlement_version,
        )


@dataclass(slots=True)
class IdentityState:
    tenant_id: str
    kind: PrincipalKind
    entitlement_version: int
    active: bool = True


class IdentityRegistry:
    """Small authoritative directory used to detect disabled or stale principals."""

    def __init__(self) -> None:
        self._states: dict[str, IdentityState] = {}

    def register(self, principal: Principal) -> None:
        self._states[principal.identity_key] = IdentityState(
            tenant_id=principal.tenant_id,
            kind=principal.kind,
            entitlement_version=principal.entitlement_version,
        )

    def disable(self, identity_key: str) -> None:
        self._states[identity_key].active = False

    def change_entitlements(self, identity_key: str) -> None:
        self._states[identity_key].entitlement_version += 1

    def require_current(self, principal: Principal, *, now: int) -> None:
        state = self._states.get(principal.identity_key)
        if state is None or not state.active:
            raise TrustBoundaryError("principal is disabled or unknown", "PRINCIPAL_INACTIVE")
        if state.tenant_id != principal.tenant_id or state.kind is not principal.kind:
            raise TrustBoundaryError("principal binding changed", "PRINCIPAL_BINDING_CHANGED")
        if state.entitlement_version != principal.entitlement_version:
            raise TrustBoundaryError("principal entitlements changed", "STALE_ENTITLEMENTS")
        if now >= principal.token_expires_at:
            raise TrustBoundaryError("principal token expired", "TOKEN_EXPIRED")


@dataclass(frozen=True, slots=True)
class CaseResource:
    case_id: str
    tenant_id: str
    owner_identity_key: str
    classification: str
    version: int = 1


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    effect: DecisionEffect
    reason_code: str
    policy_version: str
    obligations: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.effect is DecisionEffect.ALLOW


class PolicyEngine:
    """Provider-neutral PDP using trusted principal, action, resource, and context data."""

    def __init__(self, version: str = "policy-2026-09-20") -> None:
        self.version = version

    def evaluate(
        self,
        principal: Principal,
        action: Action,
        resource: CaseResource,
    ) -> PolicyDecision:
        if principal.tenant_id != resource.tenant_id:
            return self._deny("TENANT_MISMATCH")

        if principal.kind is PrincipalKind.WORKLOAD:
            if action.value not in principal.scopes:
                return self._deny("WORKLOAD_SCOPE_MISSING")
            return self._allow("WORKLOAD_SCOPE_ALLOWED")

        roles = principal.roles
        is_owner = principal.identity_key == resource.owner_identity_key
        is_underwriter = bool(roles & {"underwriter", "senior-underwriter"})
        is_senior = "senior-underwriter" in roles

        if action is Action.READ_CASE:
            if resource.classification == "restricted" and not (is_owner or is_senior):
                return self._deny("RESTRICTED_CASE")
            if is_owner or is_underwriter:
                return self._allow("CASE_READ_ALLOWED")
        elif action is Action.PROPOSE_EXCEPTION and is_underwriter:
            return self._allow("PROPOSAL_ALLOWED")
        elif action is Action.APPLY_APPROVED_EXCEPTION and is_underwriter:
            return self._allow("APPLY_ALLOWED_WITH_APPROVAL", ("VALID_APPROVAL",))
        elif action is Action.APPROVE_EXCEPTION and is_senior and not is_owner:
            return self._allow("INDEPENDENT_APPROVER_ALLOWED")

        return self._deny("NO_MATCHING_PERMISSION")

    def _allow(
        self, reason_code: str, obligations: tuple[str, ...] = ()
    ) -> PolicyDecision:
        return PolicyDecision(DecisionEffect.ALLOW, reason_code, self.version, obligations)

    def _deny(self, reason_code: str) -> PolicyDecision:
        return PolicyDecision(DecisionEffect.DENY, reason_code, self.version)


@dataclass(frozen=True, slots=True)
class DelegationGrant:
    grant_id: str
    subject: Principal
    actor: Principal
    tenant_id: str
    allowed_actions: frozenset[Action]
    resource_ids: frozenset[str]
    issued_at: int
    expires_at: int
    policy_version: str
    depth: int = 0
    parent_grant_id: str | None = None


class DelegationService:
    """Issues and attenuates application capabilities; it never widens authority."""

    def __init__(
        self,
        registry: IdentityRegistry,
        policy: PolicyEngine,
        resources: Mapping[str, CaseResource],
        *,
        max_ttl_seconds: int = 900,
        max_depth: int = 1,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.resources = dict(resources)
        self.max_ttl_seconds = max_ttl_seconds
        self.max_depth = max_depth

    def issue(
        self,
        grant_id: str,
        *,
        subject: Principal,
        actor: Principal,
        actions: frozenset[Action],
        resource_ids: frozenset[str],
        now: int,
        expires_at: int,
    ) -> DelegationGrant:
        self.registry.require_current(subject, now=now)
        self.registry.require_current(actor, now=now)
        if subject.kind is not PrincipalKind.USER or actor.kind is not PrincipalKind.WORKLOAD:
            raise TrustBoundaryError(
                "delegation requires a user subject and workload actor",
                "BAD_DELEGATION_PARTIES",
            )
        if subject.tenant_id != actor.tenant_id:
            raise TrustBoundaryError(
                "delegation cannot cross tenants", "DELEGATION_TENANT_MISMATCH"
            )
        if not actions or not resource_ids:
            raise TrustBoundaryError("delegation must be narrow and non-empty", "EMPTY_DELEGATION")
        if Action.APPROVE_EXCEPTION in actions:
            raise TrustBoundaryError(
                "approval authority cannot be delegated to the agent",
                "APPROVAL_NOT_DELEGABLE",
            )
        max_expiry = min(
            subject.token_expires_at,
            actor.token_expires_at,
            now + self.max_ttl_seconds,
        )
        if expires_at <= now or expires_at > max_expiry:
            raise TrustBoundaryError("delegation lifetime is invalid", "DELEGATION_TTL_INVALID")

        self._verify_scope(subject, actor, actions, resource_ids)
        return DelegationGrant(
            grant_id=grant_id,
            subject=subject,
            actor=actor,
            tenant_id=subject.tenant_id,
            allowed_actions=actions,
            resource_ids=resource_ids,
            issued_at=now,
            expires_at=expires_at,
            policy_version=self.policy.version,
        )

    def attenuate(
        self,
        grant_id: str,
        *,
        parent: DelegationGrant,
        child_actor: Principal,
        actions: frozenset[Action],
        resource_ids: frozenset[str],
        now: int,
        expires_at: int,
    ) -> DelegationGrant:
        if now >= parent.expires_at or parent.policy_version != self.policy.version:
            raise TrustBoundaryError("parent delegation is stale", "STALE_PARENT_DELEGATION")
        if parent.depth >= self.max_depth:
            raise TrustBoundaryError(
                "delegation depth budget exhausted", "DELEGATION_DEPTH_EXHAUSTED"
            )
        if not actions <= parent.allowed_actions or not resource_ids <= parent.resource_ids:
            raise TrustBoundaryError(
                "child delegation would widen authority", "DELEGATION_WIDENING"
            )
        if expires_at > parent.expires_at:
            raise TrustBoundaryError(
                "child delegation outlives its parent", "DELEGATION_TTL_WIDENING"
            )
        self.registry.require_current(child_actor, now=now)
        if child_actor.kind is not PrincipalKind.WORKLOAD:
            raise TrustBoundaryError("child actor must be a workload", "BAD_DELEGATION_ACTOR")
        if child_actor.tenant_id != parent.tenant_id:
            raise TrustBoundaryError(
                "child actor belongs to another tenant", "DELEGATION_TENANT_MISMATCH"
            )

        self._verify_scope(parent.subject, child_actor, actions, resource_ids)
        return DelegationGrant(
            grant_id=grant_id,
            subject=parent.subject,
            actor=child_actor,
            tenant_id=parent.tenant_id,
            allowed_actions=actions,
            resource_ids=resource_ids,
            issued_at=now,
            expires_at=expires_at,
            policy_version=self.policy.version,
            depth=parent.depth + 1,
            parent_grant_id=parent.grant_id,
        )

    def _verify_scope(
        self,
        subject: Principal,
        actor: Principal,
        actions: frozenset[Action],
        resource_ids: frozenset[str],
    ) -> None:
        for resource_id in resource_ids:
            resource = self.resources.get(resource_id)
            if resource is None:
                raise TrustBoundaryError("delegated resource does not exist", "UNKNOWN_RESOURCE")
            for action in actions:
                subject_decision = self.policy.evaluate(subject, action, resource)
                actor_decision = self.policy.evaluate(actor, action, resource)
                if not subject_decision.allowed:
                    raise TrustBoundaryError(
                        "subject cannot delegate an unavailable permission",
                        "SUBJECT_PERMISSION_MISSING",
                    )
                if not actor_decision.allowed:
                    raise TrustBoundaryError(
                        "workload is not eligible for the delegated action",
                        "ACTOR_PERMISSION_MISSING",
                    )


@dataclass(frozen=True, slots=True)
class ActionRequest:
    operation_id: str
    action: Action
    target_id: str
    parameters: tuple[tuple[str, str], ...] = ()

    @classmethod
    def create(
        cls,
        operation_id: str,
        action: Action,
        target_id: str,
        parameters: Mapping[str, str] | None = None,
    ) -> ActionRequest:
        if not operation_id or not target_id:
            raise ValueError("operation_id and target_id are required")
        return cls(operation_id, action, target_id, tuple(sorted((parameters or {}).items())))


def proposal_digest(request: ActionRequest, grant: DelegationGrant) -> str:
    material = {
        "action": request.action.value,
        "actor": grant.actor.identity_key,
        "delegation": grant.grant_id,
        "operation": request.operation_id,
        "parameters": dict(request.parameters),
        "policy_version": grant.policy_version,
        "subject": grant.subject.identity_key,
        "target": request.target_id,
        "tenant": grant.tenant_id,
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ActionProposal:
    proposal_id: str
    operation_id: str
    tenant_id: str
    subject_identity: str
    actor_identity: str
    delegation_id: str
    action: Action
    target_id: str
    request_digest: str
    policy_version: str
    delegation_expires_at: int


@dataclass(slots=True)
class ApprovalReceipt:
    receipt_id: str
    proposal_id: str
    tenant_id: str
    subject_identity: str
    actor_identity: str
    delegation_id: str
    action: Action
    target_id: str
    request_digest: str
    policy_version: str
    approver_identity: str
    issued_at: int
    expires_at: int
    consumed_by_operation: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    operation_id: str
    request_digest: str
    action: Action
    target_id: str
    status: ExecutionStatus
    approval_id: str | None
    result: str


class TransactionalActionStore:
    """Atomic teaching store for approval consumption, idempotency, and the effect."""

    def __init__(self) -> None:
        self.receipts: dict[str, ApprovalReceipt] = {}
        self.operations: dict[str, ExecutionRecord] = {}
        self.effect_count = 0

    def add_receipt(self, receipt: ApprovalReceipt) -> None:
        if receipt.receipt_id in self.receipts:
            raise TrustBoundaryError("approval ID already exists", "DUPLICATE_APPROVAL_ID")
        self.receipts[receipt.receipt_id] = receipt

    def commit(
        self,
        request: ActionRequest,
        grant: DelegationGrant,
        *,
        now: int,
        policy_version: str,
        approval_id: str | None,
        approval_required: bool,
    ) -> tuple[ExecutionRecord, bool]:
        digest = proposal_digest(request, grant)
        existing = self.operations.get(request.operation_id)
        if existing is not None:
            if existing.request_digest != digest:
                raise TrustBoundaryError(
                    "operation ID was reused for altered input", "OPERATION_CONFLICT"
                )
            return existing, True

        receipt: ApprovalReceipt | None = None
        if approval_required:
            if approval_id is None:
                raise TrustBoundaryError("a bound approval is required", "APPROVAL_REQUIRED")
            receipt = self.receipts.get(approval_id)
            if receipt is None:
                raise TrustBoundaryError("approval receipt does not exist", "APPROVAL_NOT_FOUND")
            if receipt.consumed_by_operation is not None:
                raise TrustBoundaryError("approval receipt was already consumed", "APPROVAL_REPLAY")
            if now >= receipt.expires_at:
                raise TrustBoundaryError("approval receipt expired", "APPROVAL_EXPIRED")
            expected = (
                grant.tenant_id,
                grant.subject.identity_key,
                grant.actor.identity_key,
                grant.grant_id,
                request.action,
                request.target_id,
                digest,
                policy_version,
            )
            actual = (
                receipt.tenant_id,
                receipt.subject_identity,
                receipt.actor_identity,
                receipt.delegation_id,
                receipt.action,
                receipt.target_id,
                receipt.request_digest,
                receipt.policy_version,
            )
            if actual != expected:
                raise TrustBoundaryError(
                    "approval is not bound to this exact action", "APPROVAL_BINDING_MISMATCH"
                )

        status = (
            ExecutionStatus.APPLIED
            if request.action is Action.APPLY_APPROVED_EXCEPTION
            else ExecutionStatus.COMPLETED
        )
        record = ExecutionRecord(
            operation_id=request.operation_id,
            request_digest=digest,
            action=request.action,
            target_id=request.target_id,
            status=status,
            approval_id=approval_id,
            result=f"{request.action.value}:{request.target_id}:{status.value}",
        )
        if receipt is not None:
            receipt.consumed_by_operation = request.operation_id
        self.operations[request.operation_id] = record
        if status is ExecutionStatus.APPLIED:
            self.effect_count += 1
        return record, False


class ApprovalService:
    def __init__(
        self,
        registry: IdentityRegistry,
        policy: PolicyEngine,
        resources: Mapping[str, CaseResource],
        store: TransactionalActionStore,
        *,
        max_ttl_seconds: int = 300,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.resources = dict(resources)
        self.store = store
        self.max_ttl_seconds = max_ttl_seconds

    def issue(
        self,
        receipt_id: str,
        proposal: ActionProposal,
        *,
        approver: Principal,
        now: int,
        expires_at: int,
    ) -> ApprovalReceipt:
        self.registry.require_current(approver, now=now)
        resource = self.resources.get(proposal.target_id)
        if resource is None:
            raise TrustBoundaryError("approval target does not exist", "UNKNOWN_RESOURCE")
        if proposal.policy_version != self.policy.version:
            raise TrustBoundaryError("proposal used a stale policy", "STALE_POLICY")
        if approver.identity_key == proposal.subject_identity:
            raise TrustBoundaryError(
                "requester cannot approve their own action", "SEPARATION_OF_DUTIES"
            )
        decision = self.policy.evaluate(approver, Action.APPROVE_EXCEPTION, resource)
        if not decision.allowed:
            raise TrustBoundaryError("approver is not authorized", decision.reason_code)
        max_expiry = min(
            now + self.max_ttl_seconds,
            approver.token_expires_at,
            proposal.delegation_expires_at,
        )
        if expires_at <= now or expires_at > max_expiry:
            raise TrustBoundaryError("approval lifetime is invalid", "APPROVAL_TTL_INVALID")

        receipt = ApprovalReceipt(
            receipt_id=receipt_id,
            proposal_id=proposal.proposal_id,
            tenant_id=proposal.tenant_id,
            subject_identity=proposal.subject_identity,
            actor_identity=proposal.actor_identity,
            delegation_id=proposal.delegation_id,
            action=proposal.action,
            target_id=proposal.target_id,
            request_digest=proposal.request_digest,
            policy_version=proposal.policy_version,
            approver_identity=approver.identity_key,
            issued_at=now,
            expires_at=expires_at,
        )
        self.store.add_receipt(receipt)
        return receipt


@dataclass(frozen=True, slots=True)
class AuditEvent:
    operation_id: str
    subject_identity: str
    actor_identity: str
    tenant_id: str
    action: str
    target_id: str
    decision: str
    reason_code: str
    policy_version: str
    delegation_id: str
    approval_id: str | None = None


class ToolGateway:
    """Policy enforcement point. Model text and tool arguments never establish authority."""

    def __init__(
        self,
        registry: IdentityRegistry,
        policy: PolicyEngine,
        resources: Mapping[str, CaseResource],
        store: TransactionalActionStore,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.resources = dict(resources)
        self.store = store
        self.audit: list[AuditEvent] = []

    def prepare_proposal(
        self,
        proposal_id: str,
        *,
        actor: Principal,
        grant: DelegationGrant,
        request: ActionRequest,
        now: int,
    ) -> ActionProposal:
        try:
            self._authorize(actor, grant, request, now=now)
            proposal = ActionProposal(
                proposal_id=proposal_id,
                operation_id=request.operation_id,
                tenant_id=grant.tenant_id,
                subject_identity=grant.subject.identity_key,
                actor_identity=grant.actor.identity_key,
                delegation_id=grant.grant_id,
                action=request.action,
                target_id=request.target_id,
                request_digest=proposal_digest(request, grant),
                policy_version=self.policy.version,
                delegation_expires_at=grant.expires_at,
            )
            self._record(request, grant, "allow", "PROPOSAL_PREPARED", None)
            return proposal
        except TrustBoundaryError as error:
            self._record(request, grant, "deny", error.reason_code, None)
            raise

    def execute(
        self,
        *,
        actor: Principal,
        grant: DelegationGrant,
        request: ActionRequest,
        now: int,
        approval_id: str | None = None,
    ) -> tuple[ExecutionRecord, bool]:
        try:
            subject_decision = self._authorize(actor, grant, request, now=now)
            record, replayed = self.store.commit(
                request,
                grant,
                now=now,
                policy_version=self.policy.version,
                approval_id=approval_id,
                approval_required="VALID_APPROVAL" in subject_decision.obligations,
            )
            reason = "IDEMPOTENT_REPLAY" if replayed else "EXECUTED"
            self._record(request, grant, "allow", reason, approval_id)
            return record, replayed
        except TrustBoundaryError as error:
            self._record(request, grant, "deny", error.reason_code, approval_id)
            raise

    def _authorize(
        self,
        actor: Principal,
        grant: DelegationGrant,
        request: ActionRequest,
        *,
        now: int,
    ) -> PolicyDecision:
        self.registry.require_current(actor, now=now)
        self.registry.require_current(grant.subject, now=now)
        if actor.identity_key != grant.actor.identity_key:
            raise TrustBoundaryError("caller does not own the delegation", "ACTOR_MISMATCH")
        if now >= grant.expires_at:
            raise TrustBoundaryError("delegation expired", "DELEGATION_EXPIRED")
        if grant.policy_version != self.policy.version:
            raise TrustBoundaryError("delegation used a stale policy", "STALE_POLICY")
        if request.action not in grant.allowed_actions:
            raise TrustBoundaryError("action is outside delegated scope", "ACTION_NOT_DELEGATED")
        if request.target_id not in grant.resource_ids:
            raise TrustBoundaryError("target is outside delegated scope", "TARGET_NOT_DELEGATED")
        resource = self.resources.get(request.target_id)
        if resource is None:
            raise TrustBoundaryError("target does not exist", "UNKNOWN_RESOURCE")
        if resource.tenant_id != grant.tenant_id:
            raise TrustBoundaryError("resource belongs to another tenant", "TENANT_MISMATCH")
        self._validate_parameters(request)

        subject_decision = self.policy.evaluate(grant.subject, request.action, resource)
        if not subject_decision.allowed:
            raise TrustBoundaryError(
                "subject is no longer authorized", subject_decision.reason_code
            )
        actor_decision = self.policy.evaluate(actor, request.action, resource)
        if not actor_decision.allowed:
            raise TrustBoundaryError("workload is not authorized", actor_decision.reason_code)
        return subject_decision

    @staticmethod
    def _validate_parameters(request: ActionRequest) -> None:
        parameters = dict(request.parameters)
        if request.action is Action.APPLY_APPROVED_EXCEPTION:
            if set(parameters) != {"decision", "limit"} or parameters["decision"] != "approve":
                raise TrustBoundaryError(
                    "action parameters are invalid", "INVALID_ACTION_PARAMETERS"
                )
            try:
                limit = int(parameters["limit"])
            except ValueError as error:
                raise TrustBoundaryError(
                    "approved limit must be numeric", "INVALID_ACTION_PARAMETERS"
                ) from error
            if not 1 <= limit <= 100_000:
                raise TrustBoundaryError(
                    "approved limit is outside the application bound",
                    "INVALID_ACTION_PARAMETERS",
                )
        elif parameters:
            raise TrustBoundaryError(
                "this action does not accept parameters", "INVALID_ACTION_PARAMETERS"
            )

    def _record(
        self,
        request: ActionRequest,
        grant: DelegationGrant,
        decision: str,
        reason_code: str,
        approval_id: str | None,
    ) -> None:
        self.audit.append(
            AuditEvent(
                operation_id=request.operation_id,
                subject_identity=grant.subject.identity_key,
                actor_identity=grant.actor.identity_key,
                tenant_id=grant.tenant_id,
                action=request.action.value,
                target_id=request.target_id,
                decision=decision,
                reason_code=reason_code,
                policy_version=self.policy.version,
                delegation_id=grant.grant_id,
                approval_id=approval_id,
            )
        )


@dataclass(frozen=True, slots=True)
class AuthorizationCase:
    name: str
    principal: Principal
    action: Action
    resource: CaseResource
    expected_allowed: bool


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    total: int
    correct: int
    allowed: int
    denied: int
    forbidden_outcomes: int
    valid_work_blocked: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def evaluate_authorization(
    policy: PolicyEngine, cases: Sequence[AuthorizationCase]
) -> EvaluationReport:
    correct = 0
    allowed = 0
    forbidden = 0
    blocked = 0
    for case in cases:
        actual = policy.evaluate(case.principal, case.action, case.resource).allowed
        correct += int(actual == case.expected_allowed)
        allowed += int(actual)
        forbidden += int(actual and not case.expected_allowed)
        blocked += int(not actual and case.expected_allowed)
    return EvaluationReport(
        total=len(cases),
        correct=correct,
        allowed=allowed,
        denied=len(cases) - allowed,
        forbidden_outcomes=forbidden,
        valid_work_blocked=blocked,
    )


@dataclass(slots=True)
class DemoEnvironment:
    now: int
    verifier: DeterministicTokenVerifier
    registry: IdentityRegistry
    policy: PolicyEngine
    resources: dict[str, CaseResource]
    principals: dict[str, Principal]
    delegation_service: DelegationService
    approval_service: ApprovalService
    gateway: ToolGateway
    store: TransactionalActionStore


def make_demo_token(
    subject: str,
    tenant_id: str,
    kind: PrincipalKind,
    *,
    now: int,
    scopes: frozenset[str] = frozenset(),
    roles: frozenset[str] = frozenset(),
) -> UnverifiedToken:
    return UnverifiedToken(
        issuer="https://identity.northstar.example",
        subject=subject,
        audiences=frozenset({"https://api.northstar.example"}),
        tenant_id=tenant_id,
        token_use="access",
        principal_kind=kind,
        scopes=scopes,
        roles=roles,
        issued_at=now - 10,
        not_before=now - 10,
        expires_at=now + 1_800,
        algorithm="RS256",
        key_id="key-2026-09",
        signature_valid=True,
    )


def build_demo_environment(now: int = 1_000_000) -> DemoEnvironment:
    """Create the notebook's fictional multi-principal Northstar environment."""

    verifier = DeterministicTokenVerifier(
        {"https://identity.northstar.example": frozenset({"key-2026-09"})},
        expected_audience="https://api.northstar.example",
    )
    tokens = {
        "alice": make_demo_token(
            "alice", "northstar", PrincipalKind.USER, now=now, roles=frozenset({"underwriter"})
        ),
        "bob": make_demo_token(
            "bob",
            "northstar",
            PrincipalKind.USER,
            now=now,
            roles=frozenset({"senior-underwriter"}),
        ),
        "mallory": make_demo_token(
            "mallory", "other-tenant", PrincipalKind.USER, now=now, roles=frozenset({"underwriter"})
        ),
        "agent": make_demo_token(
            "northstar-agent",
            "northstar",
            PrincipalKind.WORKLOAD,
            now=now,
            scopes=frozenset(
                {
                    Action.READ_CASE.value,
                    Action.PROPOSE_EXCEPTION.value,
                    Action.APPLY_APPROVED_EXCEPTION.value,
                }
            ),
        ),
        "subagent": make_demo_token(
            "northstar-subagent",
            "northstar",
            PrincipalKind.WORKLOAD,
            now=now,
            scopes=frozenset({Action.READ_CASE.value}),
        ),
    }
    principals = {name: verifier.verify(token, now=now) for name, token in tokens.items()}
    registry = IdentityRegistry()
    for principal in principals.values():
        registry.register(principal)

    resources = {
        "case-101": CaseResource(
            "case-101", "northstar", principals["alice"].identity_key, "standard"
        ),
        "case-202": CaseResource(
            "case-202", "northstar", principals["alice"].identity_key, "restricted"
        ),
        "case-901": CaseResource(
            "case-901", "other-tenant", principals["mallory"].identity_key, "standard"
        ),
    }
    policy = PolicyEngine()
    store = TransactionalActionStore()
    delegation_service = DelegationService(registry, policy, resources)
    gateway = ToolGateway(registry, policy, resources, store)
    approval_service = ApprovalService(registry, policy, resources, store)
    return DemoEnvironment(
        now=now,
        verifier=verifier,
        registry=registry,
        policy=policy,
        resources=resources,
        principals=principals,
        delegation_service=delegation_service,
        approval_service=approval_service,
        gateway=gateway,
        store=store,
    )
