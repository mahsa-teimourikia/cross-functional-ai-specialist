"""Build the canonical Course 10 notebook from reviewed source cells."""

from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "curriculum/advanced/10-ci-cd-infrastructure-ai-devops/ai_devops.ipynb"


def md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


def code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


cells = [
    md(
        """
        # Course 10 Lab — CI/CD, Infrastructure, and AI DevOps

        **Thesis:** promote one immutable, compatible AI release through exact evidence gates,
        short-lived deployment identity, reviewed infrastructure change, progressive delivery,
        verified rollback, and rehearsed recovery.

        Northstar is replacing a tag-based deployment with an evidence-preserving release system.
        """
    ),
    md(
        """
        ## 1. Scope, success, and safety

        Everything here is deterministic and offline. Mock digests and OIDC claims are teaching
        fixtures, not cryptographic validation. No cloud, registry, Terraform, model, credential,
        production data, or external side effect is used.

        Success requires an exact multi-artifact manifest; fresh trusted evidence; short-lived
        authorization; an unchanged reviewed plan; a statistically sufficient healthy canary; a
        verified rollback target; and recovery within RTO/RPO with integrity and auth revalidated.
        """
    ),
    code(
        """
        from dataclasses import replace

        from lab import (
            ArtifactKind,
            ChangeAction,
            DeploymentRecord,
            Environment,
            GateDisposition,
            InfrastructureApplier,
            PlanChange,
            RecoveryObservation,
            RecoveryPlan,
            ReleaseState,
            RolloutPolicy,
            Severity,
            Strategy,
            Vulnerability,
            assess_canary,
            demo_canary,
            demo_evidence,
            demo_manifest,
            demo_oidc_claims,
            demo_pipeline_policy,
            demo_plan,
            demo_trust_policy,
            evaluate_recovery,
            evaluate_release,
            exchange_oidc_for_capability,
            review_infrastructure_plan,
            rollback_to_known_good,
            run_demo_release,
            stable_digest,
        )

        print("Course 10 deterministic release lab ready")
        """
    ),
    md(
        """
        ## 2. Architecture and decision rights

        Builders produce artifacts and provenance. Evaluators produce scoped observations. The
        trusted controller verifies identity, compatibility, evidence, policy, authority and state
        before execution. The candidate never approves or deploys itself.

        ```text
        source -> build -> immutable artifacts -> manifest -> evidence admission
                                                       -> OIDC deploy capability
                                                       -> reviewed IaC -> canary
                                                       -> promote or known-good rollback
        ```
        """
    ),
    md("## 3. Inspect the complete release graph"),
    code(
        """
        manifest = demo_manifest()
        print("release:", manifest.release_id)
        print("manifest digest:", manifest.digest)
        for artifact in manifest.artifacts:
            print(f"{artifact.kind:16} {artifact.name:22} {artifact.digest[:20]}…")
        assert set(ArtifactKind) == {item.kind for item in manifest.artifacts}
        """
    ),
    md(
        """
        The digest covers the exact artifact set and compatibility contract. A tag or commit alone
        cannot tell us which model, prompt, policy, dataset, evaluator and infrastructure shipped.
        """
    ),
    md("## 4. Baseline anti-pattern: one green boolean"),
    code(
        """
        baseline_release = {"image": "northstar:latest", "tests_green": True}
        baseline_problems = [
            "mutable image", "missing model/prompt/policy identity", "no producer or expiry",
            "no provenance/SBOM", "no compatibility", "no rollback target",
        ]
        print(baseline_release)
        print("unproved claims:", len(baseline_problems), baseline_problems)
        """
    ),
    md("## 5. Admit the healthy release"),
    code(
        """
        policy = demo_pipeline_policy()
        evidence = demo_evidence(manifest)
        admitted = evaluate_release(manifest, evidence, (), policy, now=1_300)
        print(admitted)
        assert admitted.disposition is GateDisposition.PASS
        """
    ),
    md(
        """
        Each evidence item is bound to manifest, commit, policy, producer, creation and expiry. A
        pass means the required current evidence exists; it does not mean the system is risk-free.
        """
    ),
    md("## 6. Failure injection: break the quality gate"),
    code(
        """
        failed_evidence = list(evidence)
        evaluation_index = next(
            i for i, item in enumerate(failed_evidence) if item.gate == "evaluation"
        )
        failed_evidence[evaluation_index] = replace(failed_evidence[evaluation_index], passed=False)
        failed_quality = evaluate_release(manifest, failed_evidence, (), policy, now=1_300)
        print(failed_quality.disposition, failed_quality.reasons)
        assert "gate-failed:evaluation" in failed_quality.reasons
        """
    ),
    md("## 7. Missing and stale evidence are inconclusive"),
    code(
        """
        missing = evaluate_release(manifest, evidence[:-1], (), policy, now=1_300)
        stale = evaluate_release(manifest, evidence, (), policy, now=5_001)
        print("missing:", missing.disposition, missing.reasons)
        print("stale:", stale.disposition, stale.reasons)
        assert missing.disposition is GateDisposition.INCONCLUSIVE
        assert stale.disposition is GateDisposition.INCONCLUSIVE
        """
    ),
    md(
        """
        This distinction matters operationally: a measured threshold breach is failure; a broken
        evaluator cannot establish either safety or regression and must not silently promote.
        """
    ),
    md("## 8. Failure injection: vulnerable dependency"),
    code(
        """
        critical = Vulnerability(
            "CVE-DEMO-0001", manifest.artifacts[1].digest, Severity.CRITICAL, True, "10.0.1"
        )
        vulnerable = evaluate_release(manifest, evidence, (critical,), policy, now=1_300)
        print(vulnerable.disposition, vulnerable.reasons)
        assert "exploitable-critical-vulnerability" in vulnerable.reasons
        """
    ),
    md("## 9. Compatibility is a gate"),
    code(
        """
        old_prompt = replace(
            manifest,
            compatibility=replace(manifest.compatibility, prompt_schema="underwriting-input/v2"),
        )
        compatibility = evaluate_release(
            old_prompt, demo_evidence(old_prompt), (), policy, now=1_300
        )
        print(compatibility.reasons)
        assert "incompatible-component-contract" in compatibility.reasons
        """
    ),
    md(
        """
        An independently valid component can still be invalid in this release. Model, prompt,
        policy, data and evaluator contracts must agree before exposure.
        """
    ),
    md("## 10. Exchange OIDC identity for narrow deployment authority"),
    code(
        """
        claims = demo_oidc_claims()
        trust = demo_trust_policy()
        capability = exchange_oidc_for_capability(
            claims, trust, manifest_digest=manifest.digest, now=1_300
        )
        print(capability)
        assert capability.manifest_digest == manifest.digest
        assert "infrastructure:apply" in capability.actions
        """
    ),
    md(
        """
        The trust policy verifies issuer, audience, repository, environment subject, central
        workflow, branch and time. The capability is short-lived and bound to this manifest.
        """
    ),
    md("## 11. Failure injection: forged branch and stale token"),
    code(
        """
        for changed_claims, label, now in [
            (replace(claims, ref="refs/heads/feature"), "wrong ref", 1_300),
            (claims, "expired", 1_900),
        ]:
            try:
                exchange_oidc_for_capability(
                    changed_claims, trust, manifest_digest=manifest.digest, now=now
                )
            except PermissionError as error:
                print(label, "blocked:", error)
            else:
                raise AssertionError("invalid workload identity was accepted")
        """
    ),
    md("## 12. Review the AWS-targeted infrastructure plan"),
    code(
        """
        plan = demo_plan(manifest)
        review = review_infrastructure_plan(plan, reviewer="platform-reviewer", now=1_300)
        print("plan:", plan.digest)
        print("review:", review)
        assert review.disposition is GateDisposition.PASS
        """
    ),
    md("## 13. Failure injection: unsafe IaC"),
    code(
        """
        unsafe_change = PlanChange(
            "module.api.aws_security_group.public", "service", ChangeAction.REPLACE,
            {"public": True, "encrypted": False, "ingress_cidr": "0.0.0.0/0",
             "iam_actions": "*", "contains_secret": True},
        )
        unsafe_plan = replace(plan, changes=(unsafe_change,))
        unsafe_review = review_infrastructure_plan(unsafe_plan, reviewer="platform", now=1_300)
        print(unsafe_review.disposition, unsafe_review.findings)
        assert unsafe_review.disposition is GateDisposition.FAIL
        """
    ),
    md(
        """
        The deterministic review is intentionally small. Production combines semantic review,
        policy-as-code, provider controls, plan inspection and accountable human judgment.
        """
    ),
    md("## 14. Apply exactly the reviewed plan once"),
    code(
        """
        applier = InfrastructureApplier(current_state_version=41)
        receipt = applier.apply(
            plan, review, capability, operation_id="apply-1001", now=1_350
        )
        replay = applier.apply(
            plan, review, capability, operation_id="apply-1001", now=1_360
        )
        print(receipt)
        assert receipt == replay and applier.current_state_version == 42
        """
    ),
    md("## 15. Drift demands a new plan"),
    code(
        """
        drifted = InfrastructureApplier(current_state_version=42)
        try:
            drifted.apply(plan, review, capability, operation_id="apply-1002", now=1_350)
        except RuntimeError as error:
            print("blocked:", error)
        else:
            raise AssertionError("stale plan was applied")
        """
    ),
    md(
        """
        State version is a simplified optimistic concurrency control. Real automation also binds
        configuration, provider locks, account/region, variables and protected saved plan bytes.
        """
    ),
    md("## 16. Establish the canary baseline"),
    code(
        """
        baseline, candidate = demo_canary(manifest)
        rollout_policy = RolloutPolicy(200, 0.01, 1.2, 1.2, 0.02)
        healthy = assess_canary(baseline, candidate, rollout_policy)
        print(healthy)
        assert healthy.disposition is GateDisposition.PASS
        """
    ),
    md("## 17. Failure injection: failed canary"),
    code(
        """
        bad_candidate = replace(
            candidate, forbidden_outcomes=1, error_rate=0.08,
            p95_latency_ms=1_400.0, cost_per_success=0.18,
        )
        failed_canary = assess_canary(baseline, bad_candidate, rollout_policy)
        print(failed_canary.disposition, failed_canary.reasons)
        assert failed_canary.disposition is GateDisposition.FAIL
        assert "forbidden-outcome-observed" in failed_canary.reasons
        """
    ),
    md("## 18. Low volume is not a pass"),
    code(
        """
        underpowered = assess_canary(baseline, replace(candidate, requests=20), rollout_policy)
        print(underpowered)
        assert underpowered.disposition is GateDisposition.INCONCLUSIVE
        """
    ),
    md(
        """
        The canary evaluates compliant success, forbidden outcomes, errors, latency and cost. A
        production gate also needs representative slices, telemetry completeness and time windows.
        """
    ),
    md("## 19. Roll back the entire release identity"),
    code(
        """
        failed_deploy = DeploymentRecord(
            manifest.release_id, manifest.digest, Environment.PRODUCTION, ReleaseState.DEPLOYED,
            Strategy.CANARY, 1_400, admitted.evidence_ids, stable_digest("known-good"), False,
        )
        known_good = DeploymentRecord(
            "release-9.3.2", stable_digest("known-good"), Environment.PRODUCTION,
            ReleaseState.DEPLOYED, Strategy.CANARY, 900, ("evidence:release-9.3.2",), None, True,
        )
        rollback = rollback_to_known_good(
            failed_deploy, known_good, reason="canary policy breached", now=1_410
        )
        print(rollback)
        assert rollback.verified
        """
    ),
    md(
        """
        Rollback selects a verified manifest, not `previous` or an image alone. Data migrations may
        require roll-forward or restore, so their reversibility must be decided before deployment.
        """
    ),
    md("## 20. Prove disaster recovery"),
    code(
        """
        recovery_plan = RecoveryPlan(
            "dr-10", known_good.manifest_digest, stable_digest("backup-77"), 1_000,
            1_000, 600, 300, "restore/v2",
        )
        recovery_observation = RecoveryObservation(
            "dr-10", known_good.manifest_digest, recovery_plan.backup_digest,
            420, 120, True, True, 1_500,
        )
        recovery = evaluate_recovery(recovery_plan, recovery_observation, now=1_500)
        print(recovery)
        assert recovery.disposition is GateDisposition.PASS
        """
    ),
    md("## 21. Recovery failure analysis"),
    code(
        """
        failed_recovery = evaluate_recovery(
            recovery_plan,
            replace(
                recovery_observation, recovery_time_seconds=800,
                data_loss_seconds=400, integrity_verified=False,
                authorization_revalidated=False,
            ),
            now=1_500,
        )
        print(failed_recovery.disposition, failed_recovery.reasons)
        assert failed_recovery.disposition is GateDisposition.FAIL
        """
    ),
    md("## 22. Compare the baseline and governed architecture"),
    code(
        """
        comparison = {
            "artifact identity": ("tag", "full manifest digest"),
            "evidence": ("green boolean", "producer/version/scope/time-bound records"),
            "cloud identity": ("stored key", "OIDC short session"),
            "IaC": ("re-plan on apply", "exact reviewed plan + state version"),
            "rollout": ("all at once", "sufficient multi-metric canary"),
            "recovery": ("restart", "known-good rollback + tested RTO/RPO/integrity/authz"),
        }
        for concern, (baseline_value, governed_value) in comparison.items():
            print(f"{concern:18} {baseline_value:24} -> {governed_value}")
        """
    ),
    md("## 23. Execute the healthy end-to-end path"),
    code(
        """
        result = run_demo_release()
        for name, value in result.items():
            print(name, getattr(value, "disposition", "created"))
        assert result["gate"].disposition is GateDisposition.PASS
        assert result["rollout"].disposition is GateDisposition.PASS
        """
    ),
    md(
        """
        ## 24. Evaluation interpretation

        The notebook proves deterministic invariants on synthetic fixtures. It does not estimate a
        live model's quality, a scanner's recall, a cloud provider's reliability, or true recovery
        time. Production evidence needs representative datasets, real attestations, cloud policy
        tests, state/backend failure drills, canary slices, telemetry-loss accounting and review.
        """
    ),
    md(
        """
        ## 25. Production upgrade path

        | Local primitive | Production implementation |
        |---|---|
        | mock digest/signature | registry digest + Sigstore/GitHub attestation verification |
        | tuple manifest | signed canonical release manifest and immutable evidence store |
        | claim dataclass | verified JWT signature/JWKS + cloud trust conditions |
        | plan mapping | protected Terraform/OpenTofu saved plan, state and provider locks |
        | deterministic metrics | observability-backed sliced canary analysis with loss detection |
        | in-memory receipt | atomic durable release/deployment ledger and reconciliation |
        | recovery fixture | isolated restore environment and scheduled audited game day |

        Keep build and deploy trust zones separate. Pin workflow dependencies, scope tokens, protect
        environments, encrypt state/evidence, expire waivers, and verify every external effect.
        """
    ),
    md(
        """
        ## 26. Exercises

        1. Add a telemetry-schema artifact and reject incompatible dashboard contracts.
        2. Add a single-use production approval bound to manifest and plan digest.
        3. Reconcile a lost apply response without duplicating the operation.
        4. Add risk-slice canary thresholds that catch an aggregate pass hiding a high-risk failure.
        5. Design a two-region recovery drill including identity, keys, registry and state backend.
        """
    ),
    md(
        """
        ## 27. Summary

        A production AI release is a verified compatibility graph. Build once, identify everything,
        bind evidence to the exact manifest, authorize with short-lived workload identity, apply
        only reviewed state changes, expose progressively, and verify rollback and recovery.
        """
    ),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
)
TARGET.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, TARGET)
print(f"Wrote {TARGET} with {len(cells)} cells")
