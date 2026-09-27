"""Deterministic Course 10 lab: CI/CD, infrastructure, and AI DevOps.

The module simulates release admission, workload identity, infrastructure review, progressive
delivery, rollback, and recovery. It never contacts GitHub, AWS, a registry, or Terraform.
Mock digests and claims teach contracts; production systems must cryptographically verify them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256


def stable_digest(value: str) -> str:
    return f"sha256:{sha256(value.encode()).hexdigest()}"


class ArtifactKind(StrEnum):
    APPLICATION = "application"
    CONTAINER = "container"
    MODEL = "model"
    PROMPT = "prompt"
    POLICY = "policy"
    DATASET = "dataset"
    EVALUATION = "evaluation"
    INFRASTRUCTURE = "infrastructure"


class Environment(StrEnum):
    STAGING = "staging"
    PRODUCTION = "production"


class GateDisposition(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class ChangeAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"
    NOOP = "noop"


class Strategy(StrEnum):
    SHADOW = "shadow"
    CANARY = "canary"
    BLUE_GREEN = "blue-green"


class ReleaseState(StrEnum):
    CANDIDATE = "candidate"
    ADMITTED = "admitted"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled-back"
    FAILED = "failed"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Artifact:
    kind: ArtifactKind
    name: str
    version: str
    digest: str
    signer: str
    builder_id: str
    provenance_id: str
    sbom_digest: str | None
    source_revision: str
    revoked: bool = False


@dataclass(frozen=True)
class CompatibilityContract:
    model_api: str
    prompt_schema: str
    policy_api: str
    data_schema: str
    evaluator_api: str


@dataclass(frozen=True)
class ReleaseManifest:
    release_id: str
    repository: str
    commit_sha: str
    workflow_ref: str
    run_id: str
    policy_version: str
    artifacts: tuple[Artifact, ...]
    compatibility: CompatibilityContract
    created_at: int

    @property
    def digest(self) -> str:
        artifact_rows = sorted(
            "|".join(
                [
                    item.kind,
                    item.name,
                    item.version,
                    item.digest,
                    item.signer,
                    item.builder_id,
                    item.provenance_id,
                    item.sbom_digest or "",
                    item.source_revision,
                    str(item.revoked),
                ]
            )
            for item in self.artifacts
        )
        compatibility = (
            f"{self.compatibility.model_api}|{self.compatibility.prompt_schema}|"
            f"{self.compatibility.policy_api}|{self.compatibility.data_schema}|"
            f"{self.compatibility.evaluator_api}"
        )
        return stable_digest(
            "|".join(
                [
                    self.release_id,
                    self.repository,
                    self.commit_sha,
                    self.workflow_ref,
                    self.run_id,
                    self.policy_version,
                    str(self.created_at),
                    compatibility,
                    *artifact_rows,
                ]
            )
        )


@dataclass(frozen=True)
class Vulnerability:
    vulnerability_id: str
    artifact_digest: str
    severity: Severity
    exploitable: bool
    fixed_version: str | None
    waiver_id: str | None = None
    waiver_expires_at: int | None = None


@dataclass(frozen=True)
class GateEvidence:
    evidence_id: str
    gate: str
    manifest_digest: str
    commit_sha: str
    policy_version: str
    producer: str
    passed: bool
    observed_value: float | None
    threshold: float | None
    created_at: int
    expires_at: int


@dataclass(frozen=True)
class PipelinePolicy:
    version: str
    required_artifact_kinds: frozenset[ArtifactKind]
    required_gates: frozenset[str]
    trusted_signers: frozenset[str]
    trusted_builders: frozenset[str]
    trusted_evidence_producers: Mapping[str, frozenset[str]]
    max_evidence_age_seconds: int
    require_sbom_for: frozenset[ArtifactKind]


@dataclass(frozen=True)
class GateDecision:
    disposition: GateDisposition
    reasons: tuple[str, ...]
    manifest_digest: str
    evidence_ids: tuple[str, ...]


def _duplicate_values(values: Sequence[str]) -> set[str]:
    return {item for item in values if values.count(item) > 1}


def evaluate_release(
    manifest: ReleaseManifest,
    evidence: Sequence[GateEvidence],
    vulnerabilities: Sequence[Vulnerability],
    policy: PipelinePolicy,
    *,
    now: int,
) -> GateDecision:
    """Admit only exact, immutable, compatible, evidenced release manifests."""

    failures: set[str] = set()
    unknowns: set[str] = set()
    kinds = {artifact.kind for artifact in manifest.artifacts}
    if not manifest.release_id or not manifest.commit_sha or not manifest.run_id:
        failures.add("incomplete-release-identity")
    if not manifest.artifacts:
        failures.add("empty-artifact-set")
    if policy.required_artifact_kinds - kinds:
        failures.add("required-artifact-missing")
    artifact_keys = [f"{item.kind}:{item.name}" for item in manifest.artifacts]
    if _duplicate_values(artifact_keys):
        failures.add("duplicate-artifact-kind-name")

    for artifact in manifest.artifacts:
        if not artifact.digest.startswith("sha256:") or len(artifact.digest) != 71:
            failures.add("mutable-or-invalid-artifact-reference")
        if artifact.signer not in policy.trusted_signers:
            failures.add("untrusted-artifact-signer")
        if artifact.builder_id not in policy.trusted_builders:
            failures.add("untrusted-builder")
        if not artifact.provenance_id:
            failures.add("missing-provenance")
        if artifact.kind in policy.require_sbom_for and not artifact.sbom_digest:
            failures.add("missing-sbom")
        if artifact.source_revision != manifest.commit_sha:
            failures.add("artifact-source-revision-mismatch")
        if artifact.revoked:
            failures.add("revoked-artifact")

    contract = manifest.compatibility
    if not (
        contract.model_api == "model-api/v2"
        and contract.prompt_schema == "underwriting-input/v3"
        and contract.policy_api == "policy/v4"
        and contract.data_schema == "case/v5"
        and contract.evaluator_api == "release-eval/v2"
    ):
        failures.add("incompatible-component-contract")

    matching_evidence: dict[str, GateEvidence] = {}
    for evidence_item in evidence:
        if (
            evidence_item.manifest_digest != manifest.digest
            or evidence_item.commit_sha != manifest.commit_sha
        ):
            continue
        if evidence_item.policy_version != manifest.policy_version:
            continue
        if evidence_item.gate in matching_evidence:
            failures.add("duplicate-gate-evidence")
            continue
        matching_evidence[evidence_item.gate] = evidence_item

    for gate in policy.required_gates:
        gate_evidence = matching_evidence.get(gate)
        if gate_evidence is None:
            unknowns.add(f"missing-evidence:{gate}")
            continue
        if gate_evidence.producer not in policy.trusted_evidence_producers.get(
            gate, frozenset()
        ):
            failures.add(f"untrusted-evidence-producer:{gate}")
        if (
            gate_evidence.expires_at < now
            or now - gate_evidence.created_at > policy.max_evidence_age_seconds
        ):
            unknowns.add(f"stale-evidence:{gate}")
        if not gate_evidence.passed:
            failures.add(f"gate-failed:{gate}")
        if gate_evidence.threshold is not None and gate_evidence.observed_value is None:
            unknowns.add(f"missing-observation:{gate}")

    artifact_digests = {item.digest for item in manifest.artifacts}
    for finding in vulnerabilities:
        if finding.artifact_digest not in artifact_digests:
            continue
        waiver_current = (
            finding.waiver_id is not None
            and finding.waiver_expires_at is not None
            and finding.waiver_expires_at >= now
        )
        if finding.severity is Severity.CRITICAL and finding.exploitable and not waiver_current:
            failures.add("exploitable-critical-vulnerability")
        if finding.severity is Severity.HIGH and finding.exploitable and not finding.fixed_version:
            failures.add("unresolved-high-vulnerability")

    evidence_ids = tuple(sorted(item.evidence_id for item in matching_evidence.values()))
    if failures:
        return GateDecision(
            GateDisposition.FAIL, tuple(sorted(failures | unknowns)), manifest.digest, evidence_ids
        )
    if unknowns:
        return GateDecision(
            GateDisposition.INCONCLUSIVE, tuple(sorted(unknowns)), manifest.digest, evidence_ids
        )
    return GateDecision(GateDisposition.PASS, (), manifest.digest, evidence_ids)


@dataclass(frozen=True)
class OIDCClaims:
    issuer: str
    audience: str
    subject: str
    repository: str
    environment: str
    workflow_ref: str
    ref: str
    run_id: str
    issued_at: int
    expires_at: int
    token_id: str


@dataclass(frozen=True)
class WorkloadTrustPolicy:
    issuer: str
    audience: str
    repository: str
    environment: Environment
    workflow_ref: str
    ref: str
    allowed_actions: frozenset[str]
    max_token_lifetime_seconds: int = 600


@dataclass(frozen=True)
class DeploymentCapability:
    capability_id: str
    run_id: str
    repository: str
    environment: Environment
    actions: frozenset[str]
    manifest_digest: str
    expires_at: int


def exchange_oidc_for_capability(
    claims: OIDCClaims,
    trust: WorkloadTrustPolicy,
    *,
    manifest_digest: str,
    now: int,
) -> DeploymentCapability:
    """Validate identity claims before issuing a narrow, release-bound capability."""

    expected_subject = f"repo:{trust.repository}:environment:{trust.environment.value}"
    checks = {
        "oidc-issuer-mismatch": claims.issuer == trust.issuer,
        "oidc-audience-mismatch": claims.audience == trust.audience,
        "oidc-subject-mismatch": claims.subject == expected_subject,
        "oidc-repository-mismatch": claims.repository == trust.repository,
        "oidc-environment-mismatch": claims.environment == trust.environment.value,
        "oidc-workflow-mismatch": claims.workflow_ref == trust.workflow_ref,
        "oidc-ref-mismatch": claims.ref == trust.ref,
        "oidc-expired": claims.issued_at <= now < claims.expires_at,
        "oidc-lifetime-too-long": (
            claims.expires_at - claims.issued_at <= trust.max_token_lifetime_seconds
        ),
    }
    rejected = sorted(reason for reason, passed in checks.items() if not passed)
    if rejected:
        raise PermissionError(",".join(rejected))
    if not manifest_digest.startswith("sha256:"):
        raise ValueError("capability requires immutable manifest digest")
    return DeploymentCapability(
        capability_id=stable_digest(f"{claims.token_id}|{manifest_digest}"),
        run_id=claims.run_id,
        repository=claims.repository,
        environment=trust.environment,
        actions=trust.allowed_actions,
        manifest_digest=manifest_digest,
        expires_at=min(claims.expires_at, now + 600),
    )


@dataclass(frozen=True)
class PlanChange:
    address: str
    resource_type: str
    action: ChangeAction
    attributes: Mapping[str, object]


@dataclass(frozen=True)
class InfrastructurePlan:
    plan_id: str
    manifest_digest: str
    environment: Environment
    state_version: int
    configuration_digest: str
    provider_lock_digest: str
    changes: tuple[PlanChange, ...]
    created_at: int

    @property
    def digest(self) -> str:
        rows = sorted(
            f"{item.address}|{item.resource_type}|{item.action}|"
            f"{sorted((key, str(value)) for key, value in item.attributes.items())}"
            for item in self.changes
        )
        return stable_digest(
            "|".join(
                [
                    self.plan_id,
                    self.manifest_digest,
                    self.environment,
                    str(self.state_version),
                    self.configuration_digest,
                    self.provider_lock_digest,
                    *rows,
                ]
            )
        )


@dataclass(frozen=True)
class PlanReview:
    plan_digest: str
    disposition: GateDisposition
    findings: tuple[str, ...]
    reviewer: str
    reviewed_at: int
    expires_at: int


def review_infrastructure_plan(plan: InfrastructurePlan, *, reviewer: str, now: int) -> PlanReview:
    findings: set[str] = set()
    if not plan.changes:
        findings.add("empty-plan")
    for change in plan.changes:
        attrs = change.attributes
        if change.action in {ChangeAction.DELETE, ChangeAction.REPLACE}:
            if plan.environment is Environment.PRODUCTION:
                findings.add("destructive-production-change")
        if attrs.get("public") is True:
            findings.add("public-resource")
        if attrs.get("encrypted") is False:
            findings.add("unencrypted-resource")
        if attrs.get("iam_actions") == "*" or attrs.get("iam_resources") == "*":
            findings.add("wildcard-iam")
        if attrs.get("ingress_cidr") == "0.0.0.0/0":
            findings.add("open-ingress")
        if attrs.get("contains_secret") is True:
            findings.add("secret-in-plan-or-state")
        if change.resource_type in {"database", "artifact_registry"}:
            if attrs.get("deletion_protection") is not True:
                findings.add("missing-deletion-protection")
            if attrs.get("backup_enabled") is not True:
                findings.add("missing-backup")
    disposition = GateDisposition.FAIL if findings else GateDisposition.PASS
    return PlanReview(plan.digest, disposition, tuple(sorted(findings)), reviewer, now, now + 3_600)


@dataclass(frozen=True)
class ApplyReceipt:
    operation_id: str
    plan_digest: str
    manifest_digest: str
    state_before: int
    state_after: int
    applied_by_capability: str
    applied_at: int


class InfrastructureApplier:
    """Apply the exact reviewed plan once; reconcile repeated logical operations."""

    def __init__(self, *, current_state_version: int) -> None:
        self.current_state_version = current_state_version
        self._receipts: dict[str, ApplyReceipt] = {}

    def apply(
        self,
        plan: InfrastructurePlan,
        review: PlanReview,
        capability: DeploymentCapability,
        *,
        operation_id: str,
        now: int,
    ) -> ApplyReceipt:
        existing = self._receipts.get(operation_id)
        if existing is not None:
            if existing.plan_digest != plan.digest:
                raise ValueError("operation-id-conflict")
            return existing
        if review.disposition is not GateDisposition.PASS:
            raise PermissionError("plan-review-did-not-pass")
        if review.plan_digest != plan.digest:
            raise PermissionError("reviewed-plan-digest-mismatch")
        if review.expires_at < now:
            raise PermissionError("stale-plan-review")
        if capability.expires_at < now or "infrastructure:apply" not in capability.actions:
            raise PermissionError("capability-invalid-or-insufficient")
        if capability.manifest_digest != plan.manifest_digest:
            raise PermissionError("capability-manifest-mismatch")
        if plan.state_version != self.current_state_version:
            raise RuntimeError("state-changed-replan-required")
        receipt = ApplyReceipt(
            operation_id,
            plan.digest,
            plan.manifest_digest,
            self.current_state_version,
            self.current_state_version + 1,
            capability.capability_id,
            now,
        )
        self.current_state_version += 1
        self._receipts[operation_id] = receipt
        return receipt


@dataclass(frozen=True)
class CanaryObservation:
    manifest_digest: str
    requests: int
    compliant_successes: int
    forbidden_outcomes: int
    error_rate: float
    p95_latency_ms: float
    cost_per_success: float


@dataclass(frozen=True)
class RolloutPolicy:
    min_requests: int
    max_error_rate_delta: float
    max_latency_ratio: float
    max_cost_ratio: float
    max_compliant_success_drop: float


@dataclass(frozen=True)
class RolloutDecision:
    disposition: GateDisposition
    reasons: tuple[str, ...]
    candidate_manifest_digest: str
    strategy: Strategy


def assess_canary(
    baseline: CanaryObservation,
    candidate: CanaryObservation,
    policy: RolloutPolicy,
    *,
    strategy: Strategy = Strategy.CANARY,
) -> RolloutDecision:
    failures: set[str] = set()
    if candidate.requests < policy.min_requests:
        return RolloutDecision(
            GateDisposition.INCONCLUSIVE,
            ("insufficient-canary-volume",),
            candidate.manifest_digest,
            strategy,
        )
    if (
        baseline.requests <= 0
        or baseline.compliant_successes <= 0
        or baseline.p95_latency_ms <= 0
        or baseline.cost_per_success <= 0
    ):
        return RolloutDecision(
            GateDisposition.INCONCLUSIVE,
            ("invalid-baseline-population",),
            candidate.manifest_digest,
            strategy,
        )
    baseline_success = baseline.compliant_successes / baseline.requests
    candidate_success = candidate.compliant_successes / candidate.requests
    if candidate.forbidden_outcomes > 0:
        failures.add("forbidden-outcome-observed")
    if candidate.error_rate - baseline.error_rate > policy.max_error_rate_delta:
        failures.add("error-rate-regression")
    if candidate.p95_latency_ms / baseline.p95_latency_ms > policy.max_latency_ratio:
        failures.add("latency-regression")
    if candidate.cost_per_success / baseline.cost_per_success > policy.max_cost_ratio:
        failures.add("cost-regression")
    if baseline_success - candidate_success > policy.max_compliant_success_drop:
        failures.add("compliant-success-regression")
    return RolloutDecision(
        GateDisposition.FAIL if failures else GateDisposition.PASS,
        tuple(sorted(failures)),
        candidate.manifest_digest,
        strategy,
    )


@dataclass(frozen=True)
class DeploymentRecord:
    release_id: str
    manifest_digest: str
    environment: Environment
    state: ReleaseState
    strategy: Strategy
    deployed_at: int
    gate_evidence_ids: tuple[str, ...]
    previous_manifest_digest: str | None
    verified: bool


@dataclass(frozen=True)
class RollbackReceipt:
    failed_manifest_digest: str
    restored_manifest_digest: str
    reason: str
    verified: bool
    initiated_at: int
    completed_at: int


def rollback_to_known_good(
    failed: DeploymentRecord,
    known_good: DeploymentRecord,
    *,
    reason: str,
    now: int,
) -> RollbackReceipt:
    if failed.environment is not known_good.environment:
        raise PermissionError("rollback-environment-mismatch")
    if failed.manifest_digest == known_good.manifest_digest:
        raise ValueError("rollback-target-is-failed-release")
    if known_good.state is not ReleaseState.DEPLOYED or not known_good.verified:
        raise PermissionError("rollback-target-not-known-good")
    if not known_good.gate_evidence_ids:
        raise PermissionError("rollback-target-missing-evidence")
    return RollbackReceipt(
        failed.manifest_digest,
        known_good.manifest_digest,
        reason,
        True,
        now,
        now + 45,
    )


@dataclass(frozen=True)
class RecoveryPlan:
    plan_id: str
    release_manifest_digest: str
    backup_digest: str
    backup_created_at: int
    maximum_backup_age_seconds: int
    rto_seconds: int
    rpo_seconds: int
    restore_steps_version: str


@dataclass(frozen=True)
class RecoveryObservation:
    plan_id: str
    restored_manifest_digest: str
    backup_digest: str
    recovery_time_seconds: int
    data_loss_seconds: int
    integrity_verified: bool
    authorization_revalidated: bool
    completed_at: int


@dataclass(frozen=True)
class RecoveryDecision:
    disposition: GateDisposition
    reasons: tuple[str, ...]


def evaluate_recovery(
    plan: RecoveryPlan, observation: RecoveryObservation, *, now: int
) -> RecoveryDecision:
    failures: set[str] = set()
    if observation.plan_id != plan.plan_id:
        failures.add("recovery-plan-mismatch")
    if observation.restored_manifest_digest != plan.release_manifest_digest:
        failures.add("restored-release-mismatch")
    if observation.backup_digest != plan.backup_digest:
        failures.add("backup-digest-mismatch")
    if now - plan.backup_created_at > plan.maximum_backup_age_seconds:
        failures.add("backup-too-old")
    if observation.recovery_time_seconds > plan.rto_seconds:
        failures.add("rto-missed")
    if observation.data_loss_seconds > plan.rpo_seconds:
        failures.add("rpo-missed")
    if not observation.integrity_verified:
        failures.add("restore-integrity-unverified")
    if not observation.authorization_revalidated:
        failures.add("authorization-not-revalidated")
    return RecoveryDecision(
        GateDisposition.FAIL if failures else GateDisposition.PASS, tuple(sorted(failures))
    )


def demo_artifacts() -> tuple[Artifact, ...]:
    source = "a" * 40
    specs = (
        (ArtifactKind.APPLICATION, "underwriting-api", "10.0.0", True),
        (ArtifactKind.CONTAINER, "underwriting-image", "10.0.0", True),
        (ArtifactKind.MODEL, "risk-model", "2026-09", True),
        (ArtifactKind.PROMPT, "case-analysis", "10.0.0", False),
        (ArtifactKind.POLICY, "release-policy", "4.0.0", False),
        (ArtifactKind.DATASET, "release-suite", "2026-09", False),
        (ArtifactKind.EVALUATION, "release-report", "10.0.0", False),
        (ArtifactKind.INFRASTRUCTURE, "aws-stack", "10.0.0", True),
    )
    return tuple(
        Artifact(
            kind,
            name,
            version,
            stable_digest(f"{kind}:{name}:{version}"),
            "sigstore:github-actions",
            "https://github.com/actions/runner-images/ubuntu",
            f"provenance:{name}:{version}",
            stable_digest(f"sbom:{name}:{version}") if with_sbom else None,
            source,
        )
        for kind, name, version, with_sbom in specs
    )


def demo_manifest() -> ReleaseManifest:
    return ReleaseManifest(
        release_id="release-10.0.0",
        repository="northstar/underwriting-ai",
        commit_sha="a" * 40,
        workflow_ref="northstar/platform/.github/workflows/deploy.yml@refs/heads/main",
        run_id="run-1001",
        policy_version="release-policy/v4",
        artifacts=demo_artifacts(),
        compatibility=CompatibilityContract(
            "model-api/v2",
            "underwriting-input/v3",
            "policy/v4",
            "case/v5",
            "release-eval/v2",
        ),
        created_at=1_000,
    )


def demo_pipeline_policy() -> PipelinePolicy:
    gates = frozenset(
        {
            "unit-tests",
            "type-check",
            "notebook-execution",
            "evaluation",
            "security",
            "provenance",
            "iac-review",
            "recovery-drill",
        }
    )
    return PipelinePolicy(
        version="release-policy/v4",
        required_artifact_kinds=frozenset(ArtifactKind),
        required_gates=gates,
        trusted_signers=frozenset({"sigstore:github-actions"}),
        trusted_builders=frozenset({"https://github.com/actions/runner-images/ubuntu"}),
        trusted_evidence_producers={gate: frozenset({f"ci:{gate}"}) for gate in gates},
        max_evidence_age_seconds=3_600,
        require_sbom_for=frozenset(
            {
                ArtifactKind.APPLICATION,
                ArtifactKind.CONTAINER,
                ArtifactKind.MODEL,
                ArtifactKind.INFRASTRUCTURE,
            }
        ),
    )


def demo_evidence(manifest: ReleaseManifest | None = None) -> tuple[GateEvidence, ...]:
    release = manifest or demo_manifest()
    return tuple(
        GateEvidence(
            f"evidence:{gate}:1001",
            gate,
            release.digest,
            release.commit_sha,
            release.policy_version,
            f"ci:{gate}",
            True,
            1.0,
            0.95,
            1_100,
            4_000,
        )
        for gate in sorted(demo_pipeline_policy().required_gates)
    )


def demo_oidc_claims() -> OIDCClaims:
    return OIDCClaims(
        issuer="https://token.actions.githubusercontent.com",
        audience="sts.amazonaws.com",
        subject="repo:northstar/underwriting-ai:environment:production",
        repository="northstar/underwriting-ai",
        environment="production",
        workflow_ref="northstar/platform/.github/workflows/deploy.yml@refs/heads/main",
        ref="refs/heads/main",
        run_id="run-1001",
        issued_at=1_200,
        expires_at=1_800,
        token_id="jti-1001",
    )


def demo_trust_policy() -> WorkloadTrustPolicy:
    return WorkloadTrustPolicy(
        "https://token.actions.githubusercontent.com",
        "sts.amazonaws.com",
        "northstar/underwriting-ai",
        Environment.PRODUCTION,
        "northstar/platform/.github/workflows/deploy.yml@refs/heads/main",
        "refs/heads/main",
        frozenset({"infrastructure:apply", "service:deploy"}),
    )


def demo_plan(manifest: ReleaseManifest | None = None) -> InfrastructurePlan:
    release = manifest or demo_manifest()
    return InfrastructurePlan(
        "tfplan-1001",
        release.digest,
        Environment.PRODUCTION,
        41,
        stable_digest("terraform-configuration-v10"),
        stable_digest("provider-lock-v10"),
        (
            PlanChange(
                "module.service.aws_ecs_service.api",
                "service",
                ChangeAction.UPDATE,
                {"public": False, "encrypted": True, "ingress_cidr": "10.0.0.0/8"},
            ),
            PlanChange(
                "module.data.aws_db_instance.case_store",
                "database",
                ChangeAction.UPDATE,
                {
                    "public": False,
                    "encrypted": True,
                    "deletion_protection": True,
                    "backup_enabled": True,
                },
            ),
        ),
        1_250,
    )


def demo_canary(
    manifest: ReleaseManifest | None = None,
) -> tuple[CanaryObservation, CanaryObservation]:
    release = manifest or demo_manifest()
    baseline = CanaryObservation(stable_digest("known-good"), 2_000, 1_930, 0, 0.02, 850.0, 0.08)
    candidate = CanaryObservation(release.digest, 500, 480, 0, 0.022, 880.0, 0.082)
    return baseline, candidate


def run_demo_release() -> Mapping[str, object]:
    manifest = demo_manifest()
    gate = evaluate_release(
        manifest, demo_evidence(manifest), (), demo_pipeline_policy(), now=1_300
    )
    capability = exchange_oidc_for_capability(
        demo_oidc_claims(), demo_trust_policy(), manifest_digest=manifest.digest, now=1_300
    )
    plan = demo_plan(manifest)
    review = review_infrastructure_plan(plan, reviewer="platform-reviewer", now=1_300)
    apply = InfrastructureApplier(current_state_version=41).apply(
        plan, review, capability, operation_id="apply-1001", now=1_350
    )
    baseline, candidate = demo_canary(manifest)
    rollout = assess_canary(
        baseline,
        candidate,
        RolloutPolicy(200, 0.01, 1.2, 1.2, 0.02),
    )
    return {
        "manifest": manifest,
        "gate": gate,
        "capability": capability,
        "plan_review": review,
        "apply_receipt": apply,
        "rollout": rollout,
    }


if __name__ == "__main__":
    result = run_demo_release()
    print({key: getattr(value, "disposition", "created") for key, value in result.items()})
