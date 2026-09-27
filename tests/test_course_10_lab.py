from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load() -> ModuleType:
    path = (
        Path(__file__).parents[1] / "curriculum/advanced/10-ci-cd-infrastructure-ai-devops/lab.py"
    )
    spec = importlib.util.spec_from_file_location("course_10_lab", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lab = _load()


def _decision(
    manifest: Any | None = None,
    evidence: Any | None = None,
    vulnerabilities: Any = (),
    now: int = 1_300,
) -> Any:
    release = manifest or lab.demo_manifest()
    proof = lab.demo_evidence(release) if evidence is None else evidence
    return lab.evaluate_release(
        release, proof, vulnerabilities, lab.demo_pipeline_policy(), now=now
    )


def test_complete_release_manifest_passes() -> None:
    assert _decision().disposition is lab.GateDisposition.PASS


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda item: replace(item, digest="latest"), "mutable-or-invalid-artifact-reference"),
        (lambda item: replace(item, signer="unknown"), "untrusted-artifact-signer"),
        (lambda item: replace(item, builder_id="self-hosted:unknown"), "untrusted-builder"),
        (lambda item: replace(item, provenance_id=""), "missing-provenance"),
        (lambda item: replace(item, source_revision="b" * 40), "artifact-source-revision-mismatch"),
        (lambda item: replace(item, revoked=True), "revoked-artifact"),
    ],
)
def test_artifact_admission_fails_closed(mutation: Any, reason: str) -> None:
    manifest = lab.demo_manifest()
    artifacts = (mutation(manifest.artifacts[0]), *manifest.artifacts[1:])
    changed = replace(manifest, artifacts=artifacts)

    assert reason in _decision(changed).reasons


def test_required_sbom_is_enforced() -> None:
    manifest = lab.demo_manifest()
    changed = replace(
        manifest,
        artifacts=(replace(manifest.artifacts[0], sbom_digest=None), *manifest.artifacts[1:]),
    )

    assert "missing-sbom" in _decision(changed).reasons


def test_duplicate_artifact_identity_is_rejected() -> None:
    manifest = lab.demo_manifest()
    changed = replace(manifest, artifacts=(*manifest.artifacts, manifest.artifacts[0]))

    assert "duplicate-artifact-kind-name" in _decision(changed).reasons


def test_missing_required_artifact_is_rejected() -> None:
    manifest = lab.demo_manifest()
    changed = replace(manifest, artifacts=manifest.artifacts[:-1])

    assert "required-artifact-missing" in _decision(changed).reasons


def test_component_compatibility_is_an_admission_control() -> None:
    manifest = lab.demo_manifest()
    changed = replace(
        manifest,
        compatibility=replace(manifest.compatibility, prompt_schema="underwriting-input/v2"),
    )

    assert "incompatible-component-contract" in _decision(changed).reasons


def test_manifest_digest_covers_attestation_metadata() -> None:
    manifest = lab.demo_manifest()

    changed = replace(
        manifest,
        artifacts=(replace(manifest.artifacts[0], provenance_id="other"), *manifest.artifacts[1:]),
    )

    assert changed.digest != manifest.digest


def test_evidence_is_bound_to_exact_manifest() -> None:
    manifest = lab.demo_manifest()
    evidence = tuple(
        replace(item, manifest_digest=lab.stable_digest("other"))
        for item in lab.demo_evidence(manifest)
    )

    decision = _decision(manifest, evidence)
    assert decision.disposition is lab.GateDisposition.INCONCLUSIVE
    assert "missing-evidence:evaluation" in decision.reasons


def test_failed_gate_fails_release() -> None:
    manifest = lab.demo_manifest()
    evidence = list(lab.demo_evidence(manifest))
    evidence[0] = replace(evidence[0], passed=False)

    assert any(
        reason.startswith("gate-failed:") for reason in _decision(manifest, evidence).reasons
    )


def test_stale_gate_is_inconclusive() -> None:
    decision = _decision(now=5_001)

    assert decision.disposition is lab.GateDisposition.INCONCLUSIVE
    assert any(reason.startswith("stale-evidence:") for reason in decision.reasons)


def test_duplicate_gate_evidence_is_rejected() -> None:
    manifest = lab.demo_manifest()
    evidence = lab.demo_evidence(manifest)

    assert "duplicate-gate-evidence" in _decision(manifest, (*evidence, evidence[0])).reasons


def test_untrusted_evidence_producer_is_rejected() -> None:
    manifest = lab.demo_manifest()
    evidence = list(lab.demo_evidence(manifest))
    evidence[0] = replace(evidence[0], producer="model:self-attested")

    assert any(
        reason.startswith("untrusted-evidence-producer:")
        for reason in _decision(manifest, evidence).reasons
    )


def test_exploitable_critical_vulnerability_blocks_release() -> None:
    manifest = lab.demo_manifest()
    finding = lab.Vulnerability(
        "CVE-demo", manifest.artifacts[1].digest, lab.Severity.CRITICAL, True, "10.0.1"
    )

    assert (
        "exploitable-critical-vulnerability"
        in _decision(manifest, vulnerabilities=(finding,)).reasons
    )


def test_current_explicit_waiver_can_bound_a_known_finding() -> None:
    manifest = lab.demo_manifest()
    finding = lab.Vulnerability(
        "CVE-demo",
        manifest.artifacts[1].digest,
        lab.Severity.CRITICAL,
        True,
        "10.0.1",
        "waiver-1",
        1_400,
    )

    assert _decision(manifest, vulnerabilities=(finding,)).disposition is lab.GateDisposition.PASS


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("issuer", "https://evil.invalid", "oidc-issuer-mismatch"),
        ("audience", "wrong", "oidc-audience-mismatch"),
        ("repository", "attacker/repo", "oidc-repository-mismatch"),
        ("environment", "staging", "oidc-environment-mismatch"),
        ("workflow_ref", "unreviewed.yml@main", "oidc-workflow-mismatch"),
        ("ref", "refs/heads/feature", "oidc-ref-mismatch"),
    ],
)
def test_oidc_claims_are_fully_bound(field: str, value: str, reason: str) -> None:
    claims = replace(lab.demo_oidc_claims(), **{field: value})

    with pytest.raises(PermissionError, match=reason):
        lab.exchange_oidc_for_capability(
            claims, lab.demo_trust_policy(), manifest_digest=lab.demo_manifest().digest, now=1_300
        )


def test_oidc_subject_must_match_environment_boundary() -> None:
    claims = replace(
        lab.demo_oidc_claims(), subject="repo:northstar/underwriting-ai:ref:refs/heads/main"
    )

    with pytest.raises(PermissionError, match="oidc-subject-mismatch"):
        lab.exchange_oidc_for_capability(
            claims, lab.demo_trust_policy(), manifest_digest=lab.demo_manifest().digest, now=1_300
        )


def test_expired_oidc_token_is_rejected() -> None:
    with pytest.raises(PermissionError, match="oidc-expired"):
        lab.exchange_oidc_for_capability(
            lab.demo_oidc_claims(),
            lab.demo_trust_policy(),
            manifest_digest=lab.demo_manifest().digest,
            now=1_900,
        )


def test_oidc_exchange_issues_release_bound_capability() -> None:
    manifest = lab.demo_manifest()
    capability = lab.exchange_oidc_for_capability(
        lab.demo_oidc_claims(), lab.demo_trust_policy(), manifest_digest=manifest.digest, now=1_300
    )

    assert capability.manifest_digest == manifest.digest
    assert capability.actions == frozenset({"infrastructure:apply", "service:deploy"})


@pytest.mark.parametrize(
    "attributes,reason",
    [
        ({"public": True}, "public-resource"),
        ({"encrypted": False}, "unencrypted-resource"),
        ({"iam_actions": "*"}, "wildcard-iam"),
        ({"ingress_cidr": "0.0.0.0/0"}, "open-ingress"),
        ({"contains_secret": True}, "secret-in-plan-or-state"),
    ],
)
def test_iac_review_detects_dangerous_attributes(
    attributes: dict[str, object], reason: str
) -> None:
    plan = lab.demo_plan()
    changed = replace(
        plan, changes=(lab.PlanChange("bad", "service", lab.ChangeAction.UPDATE, attributes),)
    )

    assert reason in lab.review_infrastructure_plan(changed, reviewer="r", now=1_300).findings


def test_destructive_production_plan_requires_redesign() -> None:
    plan = lab.demo_plan()
    changed = replace(plan, changes=(replace(plan.changes[0], action=lab.ChangeAction.DELETE),))

    assert (
        "destructive-production-change"
        in lab.review_infrastructure_plan(changed, reviewer="r", now=1_300).findings
    )


def test_database_requires_backup_and_deletion_protection() -> None:
    plan = lab.demo_plan()
    change = lab.PlanChange("db", "database", lab.ChangeAction.UPDATE, {"encrypted": True})
    review = lab.review_infrastructure_plan(
        replace(plan, changes=(change,)), reviewer="r", now=1_300
    )

    assert {"missing-backup", "missing-deletion-protection"} <= set(review.findings)


def _apply_inputs() -> tuple[Any, Any, Any]:
    manifest = lab.demo_manifest()
    plan = lab.demo_plan(manifest)
    review = lab.review_infrastructure_plan(plan, reviewer="platform", now=1_300)
    capability = lab.exchange_oidc_for_capability(
        lab.demo_oidc_claims(), lab.demo_trust_policy(), manifest_digest=manifest.digest, now=1_300
    )
    return plan, review, capability


def test_apply_is_bound_to_exact_reviewed_plan() -> None:
    plan, review, capability = _apply_inputs()
    changed = replace(plan, configuration_digest=lab.stable_digest("changed"))

    with pytest.raises(PermissionError, match="reviewed-plan-digest-mismatch"):
        lab.InfrastructureApplier(current_state_version=41).apply(
            changed, review, capability, operation_id="op-1", now=1_350
        )


def test_apply_rejects_state_drift() -> None:
    plan, review, capability = _apply_inputs()

    with pytest.raises(RuntimeError, match="state-changed-replan-required"):
        lab.InfrastructureApplier(current_state_version=42).apply(
            plan, review, capability, operation_id="op-1", now=1_350
        )


def test_apply_is_idempotent_for_same_logical_operation() -> None:
    plan, review, capability = _apply_inputs()
    applier = lab.InfrastructureApplier(current_state_version=41)

    first = applier.apply(plan, review, capability, operation_id="op-1", now=1_350)
    second = applier.apply(plan, review, capability, operation_id="op-1", now=1_360)

    assert first == second
    assert applier.current_state_version == 42


def test_apply_rejects_operation_id_reuse_for_changed_plan() -> None:
    plan, review, capability = _apply_inputs()
    applier = lab.InfrastructureApplier(current_state_version=41)
    applier.apply(plan, review, capability, operation_id="op-1", now=1_350)

    with pytest.raises(ValueError, match="operation-id-conflict"):
        applier.apply(
            replace(plan, plan_id="other"), review, capability, operation_id="op-1", now=1_360
        )


def test_healthy_canary_passes() -> None:
    baseline, candidate = lab.demo_canary()
    decision = lab.assess_canary(baseline, candidate, lab.RolloutPolicy(200, 0.01, 1.2, 1.2, 0.02))

    assert decision.disposition is lab.GateDisposition.PASS


def test_low_volume_canary_is_inconclusive_not_success() -> None:
    baseline, candidate = lab.demo_canary()
    decision = lab.assess_canary(
        baseline, replace(candidate, requests=20), lab.RolloutPolicy(200, 0.01, 1.2, 1.2, 0.02)
    )

    assert decision.disposition is lab.GateDisposition.INCONCLUSIVE


def test_invalid_baseline_denominators_are_inconclusive() -> None:
    baseline, candidate = lab.demo_canary()
    decision = lab.assess_canary(
        replace(baseline, p95_latency_ms=0.0),
        candidate,
        lab.RolloutPolicy(200, 0.01, 1.2, 1.2, 0.02),
    )

    assert decision.disposition is lab.GateDisposition.INCONCLUSIVE
    assert decision.reasons == ("invalid-baseline-population",)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("forbidden_outcomes", 1, "forbidden-outcome-observed"),
        ("error_rate", 0.20, "error-rate-regression"),
        ("p95_latency_ms", 1_500.0, "latency-regression"),
        ("cost_per_success", 0.20, "cost-regression"),
        ("compliant_successes", 400, "compliant-success-regression"),
    ],
)
def test_failed_canary_stops_promotion(field: str, value: object, reason: str) -> None:
    baseline, candidate = lab.demo_canary()
    changed = replace(candidate, **{field: value})

    decision = lab.assess_canary(baseline, changed, lab.RolloutPolicy(200, 0.01, 1.2, 1.2, 0.02))
    assert reason in decision.reasons


def _deployment(digest: str, *, verified: bool = True) -> Any:
    return lab.DeploymentRecord(
        "r",
        digest,
        lab.Environment.PRODUCTION,
        lab.ReleaseState.DEPLOYED,
        lab.Strategy.CANARY,
        1_000,
        ("e1",),
        None,
        verified,
    )


def test_rollback_restores_verified_known_good_release() -> None:
    receipt = lab.rollback_to_known_good(
        _deployment(lab.stable_digest("failed")),
        _deployment(lab.stable_digest("good")),
        reason="canary failed",
        now=1_400,
    )

    assert receipt.verified and receipt.restored_manifest_digest == lab.stable_digest("good")


def test_rollback_rejects_unverified_target() -> None:
    with pytest.raises(PermissionError, match="rollback-target-not-known-good"):
        lab.rollback_to_known_good(
            _deployment(lab.stable_digest("failed")),
            _deployment(lab.stable_digest("good"), verified=False),
            reason="bad",
            now=1_400,
        )


def _recovery() -> tuple[Any, Any]:
    plan = lab.RecoveryPlan(
        "dr-1",
        lab.stable_digest("good"),
        lab.stable_digest("backup"),
        1_000,
        1_000,
        600,
        300,
        "restore/v2",
    )
    observation = lab.RecoveryObservation(
        "dr-1", plan.release_manifest_digest, plan.backup_digest, 420, 120, True, True, 1_500
    )
    return plan, observation


def test_recovery_drill_proves_rto_rpo_and_integrity() -> None:
    plan, observation = _recovery()

    assert (
        lab.evaluate_recovery(plan, observation, now=1_500).disposition is lab.GateDisposition.PASS
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("recovery_time_seconds", 700, "rto-missed"),
        ("data_loss_seconds", 400, "rpo-missed"),
        ("integrity_verified", False, "restore-integrity-unverified"),
        ("authorization_revalidated", False, "authorization-not-revalidated"),
    ],
)
def test_recovery_drill_reports_failed_objective(field: str, value: object, reason: str) -> None:
    plan, observation = _recovery()

    assert (
        reason
        in lab.evaluate_recovery(plan, replace(observation, **{field: value}), now=1_500).reasons
    )


def test_end_to_end_demo_produces_passed_evidence_chain() -> None:
    result = lab.run_demo_release()

    assert result["gate"].disposition is lab.GateDisposition.PASS
    assert result["plan_review"].disposition is lab.GateDisposition.PASS
    assert result["rollout"].disposition is lab.GateDisposition.PASS
    assert result["apply_receipt"].state_after == 42
