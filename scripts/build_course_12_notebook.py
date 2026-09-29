"""Build the canonical Course 12 notebook from reviewed source cells."""

from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
TARGET = (
    ROOT
    / "curriculum/advanced/12-enterprise-ai-operating-model-leadership"
    / "enterprise_ai_operating_model.ipynb"
)


def md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


def code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


cells = [
    md("""
    # Course 12 Lab — Enterprise AI Operating Model and Leadership

    **Capstone:** turn Northstar's 70 GenAI proofs of concept into a small, governed,
    evidence-backed production portfolio and a defensible 12-month operating-model roadmap.
    """),
    md("""
    ## 1. Scope, safety, and authority

    This notebook is deterministic, credential-free, and synthetic. It teaches decision mechanics;
    it is not a real investment recommendation or compliance assessment. Scores and models propose.
    Trusted evidence processes and accountable authorities validate, allocate, accept risk,
    authorize production, and verify outcomes.
    """),
    code("""
    from dataclasses import replace

    from lab import (
        DelegationContract,
        DissentRecord,
        DissentStatus,
        ExceptionRequest,
        MaturityLevel,
        PortfolioDisposition,
        RiskTier,
        assess_candidate,
        assess_maturity,
        assess_roadmap,
        control_profile,
        demo_candidates,
        demo_decision_rights,
        demo_evidence,
        demo_investments,
        demo_maturity_evidence,
        demo_roadmap,
        demo_services,
        evaluate_investment,
        issue_exception,
        portfolio_metrics,
        run_demo_operating_model,
        select_portfolio,
        validate_decision_rights,
        validate_delegation,
        validate_dissent,
        validate_exception,
        validate_service_catalog,
    )

    TRUSTED = frozenset({"portfolio-evidence-office"})
    NOW = 1_300
    print("Course 12 operating-model lab ready")
    """),
    md("## 2. The operating model is a decision system"),
    code("""
    loops = [
        "strategy and risk appetite", "intake and inventory", "portfolio allocation",
        "product and platform delivery", "assurance and authorization",
        "outcome, economics and learning feedback",
    ]
    for index, item in enumerate(loops, start=1):
        print(index, item)
    """),
    md("""
    Team boxes are insufficient. The system needs records, authority, service interfaces,
    constraints, feedback, and a path to stop or change work.
    """),
    md("## 3. Load the complete 70-PoC portfolio"),
    code("""
    candidates = demo_candidates()
    evidence = demo_evidence(candidates)
    print("candidates:", len(candidates), "evidence records:", len(evidence))
    assert len(candidates) == 70 and len(evidence) == 210
    """),
    md("## 4. Inspect the intake contract"),
    code("""
    for item in candidates[:5]:
        print(
            item.candidate_id, item.domain, item.risk_tier,
            f"value=${item.expected_annual_value:,.0f}",
            f"cost=${item.annual_cost:,.0f}", "owner=", item.owner,
        )
    """),
    md("""
    Every record has an exact version, owner, outcome, risk, data state, resources and dependencies.
    Evidence is stored separately so a claim cannot validate itself.
    """),
    md("## 5. Establish a naive baseline"),
    code("""
    naive = sorted(candidates, key=lambda item: item.sunk_cost, reverse=True)[:8]
    print("naive sunk-cost continuation:", [item.candidate_id for item in naive])
    print("failure: prior spend is not prospective value, evidence, safety, capacity or authority")
    """),
    md("## 6. Inspect hard gates before scoring"),
    code("""
    prohibited = next(item for item in candidates if item.risk_tier is RiskTier.PROHIBITED)
    prohibited_result = assess_candidate(
        prohibited, evidence, trusted_producers=TRUSTED, now=NOW
    )
    print(prohibited.candidate_id, prohibited_result)
    assert prohibited_result.disposition is PortfolioDisposition.STOP
    """),
    md("""
    A high expected value cannot compensate for prohibited use, missing ownership, or unapproved
    sensitive data. No weighted score is calculated after a hard failure.
    """),
    md("## 7. Assess every candidate"),
    code("""
    assessments = tuple(
        assess_candidate(item, evidence, trusted_producers=TRUSTED, now=NOW)
        for item in candidates
    )
    counts = {
        state.value: sum(item.disposition is state for item in assessments)
        for state in PortfolioDisposition
    }
    print(counts)
    """),
    md("## 8. Inspect the score evidence chain"),
    code("""
    first = candidates[0]
    first_proof = [item for item in evidence if item.candidate_id == first.candidate_id]
    print(first)
    for item in first_proof:
        print(item.metric, item.value, item.unit, item.producer, item.expires_at)
    print(next(item for item in assessments if item.candidate_id == first.candidate_id))
    """),
    md("## 9. Failure injection: missing evidence"),
    code("""
    missing = tuple(
        item for item in evidence
        if not (item.candidate_id == first.candidate_id and item.metric == "feasibility")
    )
    missing_result = assess_candidate(first, missing, trusted_producers=TRUSTED, now=NOW)
    print(missing_result)
    assert missing_result.disposition is PortfolioDisposition.REFER
    """),
    md("""
    Missing evidence is not zero and not a pass. `refer` sends the question to an evidence owner or
    a bounded experiment without pretending the candidate failed its outcome.
    """),
    md("## 10. Failure injection: stale and untrusted evidence"),
    code("""
    changed = list(evidence)
    index = next(
        i for i, item in enumerate(changed)
        if item.candidate_id == first.candidate_id and item.metric == "annual-value"
    )
    changed[index] = replace(changed[index], producer="sponsor-slide", expires_at=1_200)
    untrusted = assess_candidate(first, changed, trusted_producers=TRUSTED, now=NOW)
    print(untrusted.reasons)
    assert untrusted.disposition is PortfolioDisposition.REFER
    """),
    md("## 11. Create a bounded experiment"),
    code("""
    candidate = replace(first, feasibility=0.50)
    experiment_proof = demo_evidence((candidate,))
    experiment = assess_candidate(candidate, experiment_proof, trusted_producers=TRUSTED, now=NOW)
    print(experiment)
    assert experiment.disposition is PortfolioDisposition.EXPERIMENT
    """),
    md("""
    An experiment buys information under a smaller spend and capacity envelope. It does not receive
    production authorization and creates no obligation to continue.
    """),
    md("## 12. Select under enterprise constraints"),
    code("""
    selection = select_portfolio(
        candidates, assessments, budget=2_500_000, capacity=45, max_high_risk=2
    )
    print("funded:", selection.funded)
    print("experiments:", selection.experiments)
    print("held:", len(selection.held), "stopped:", len(selection.stopped))
    print("spend:", selection.annual_cost, "capacity:", selection.team_capacity)
    assert selection.annual_cost <= 2_500_000 and selection.team_capacity <= 45
    """),
    md("## 13. Inspect dependency and duplication reasons"),
    code("""
    interesting = {
        key: value for key, value in selection.reasons.items()
        if value in {"dependency-not-funded", "duplicate-capability", "high-risk-cap-reached"}
    }
    print(interesting)
    """),
    md("""
    Portfolio value is not the sum of isolated rankings. Shared capabilities, dependencies,
    concentration, scarce teams, and learning options alter the best set.
    """),
    md("## 14. Prove sunk cost does not affect selection"),
    code("""
    changed_candidates = tuple(
        replace(item, sunk_cost=item.sunk_cost + 5_000_000) for item in candidates
    )
    changed_selection = select_portfolio(
        changed_candidates, assessments, budget=2_500_000, capacity=45, max_high_risk=2
    )
    print("same funded set:", changed_selection.funded == selection.funded)
    assert changed_selection.funded == selection.funded
    """),
    md("## 15. Map risk to a production path"),
    code("""
    for tier in RiskTier:
        profile = control_profile(tier)
        print(tier, profile.mode, sorted(profile.required_controls), profile.independent_review)
    """),
    md("""
    Risk changes the control path. It never removes the need for ownership or outcome evidence, and
    a prohibited path cannot become self-service through an exception.
    """),
    md("## 16. Issue a narrow exception"),
    code("""
    request = ExceptionRequest(
        "request-1", "service-owner", first.candidate_id, first.version,
        "telemetry-policy", "regional-dashboard", "migration window",
        ("daily manual review", "restricted access"),
    )
    receipt = issue_exception(
        request, approver="control-owner",
        authorized_approvers=frozenset({"control-owner"}),
        policy_version="policy-v7", now=NOW, ttl=90,
    )
    print(receipt)
    validate_exception(request, receipt, current_policy_version="policy-v7", now=1_350)
    """),
    md("## 17. Failure injection: altered exception subject"),
    code("""
    altered = replace(request, candidate_version="v2")
    try:
        validate_exception(altered, receipt, current_policy_version="policy-v7", now=1_350)
    except ValueError as error:
        print("rejected:", error)
    else:
        raise AssertionError("altered exception was accepted")
    """),
    md("## 18. Validate decision rights"),
    code("""
    rights = demo_decision_rights()
    validate_decision_rights(rights)
    for item in rights:
        print(
            item.kind, "A=", item.accountable, "R=", item.responsible,
            "escalate=", item.escalation_owner,
        )
    """),
    md("""
    The matrix covers product outcome, platform standard, risk acceptance, production release,
    provider contract and policy exception exactly once. Organizational labels document agreement;
    runtime identity and policy still enforce technical authorization.
    """),
    md("## 19. Failure injection: accountability becomes informed-only"),
    code("""
    broken_rights = list(rights)
    broken_rights[0] = replace(broken_rights[0], informed=(broken_rights[0].accountable,))
    try:
        validate_decision_rights(broken_rights)
    except ValueError as error:
        print("rejected:", error)
    """),
    md("## 20. Validate the AI service catalogue"),
    code("""
    services = demo_services()
    validate_service_catalog(services)
    for service in services:
        print(service.service_id, service.outcome, service.service_level, service.exit_path)
    """),
    md("## 21. Failure injection: paved road without exit"),
    code("""
    broken_service = replace(services[0], exit_path="")
    try:
        validate_service_catalog((broken_service,))
    except ValueError as error:
        print("rejected:", error)
    """),
    md("""
    A portal entry is not a service. Consumers need eligibility, onboarding, SLO, support, quota,
    lifecycle, unit cost, deprecation and a governed escape path.
    """),
    md("## 22. Assess nine capability dimensions"),
    code("""
    maturity = assess_maturity(
        demo_maturity_evidence(),
        trusted_producers=frozenset({"assurance-office"}), now=NOW,
    )
    for dimension, level in maturity.levels.items():
        print(f"{dimension:12} {level}")
    print("overall floor:", maturity.overall)
    assert maturity.overall is MaturityLevel.PROVISIONAL
    """),
    md("## 23. Failure injection: missing maturity proof"),
    code("""
    incomplete_maturity = assess_maturity(
        demo_maturity_evidence()[:-1],
        trusted_producers=frozenset({"assurance-office"}), now=NOW,
    )
    print(incomplete_maturity.overall, incomplete_maturity.gaps)
    assert incomplete_maturity.overall is None
    """),
    md("""
    Maturity is an evidenced capability claim, not a workshop mood. The floor exposes a weak people
    system that an average would conceal.
    """),
    md("## 24. Validate the 12-month roadmap"),
    code("""
    roadmap = demo_roadmap()
    roadmap_result = assess_roadmap(
        roadmap,
        quarterly_budget={1: 200_000, 2: 250_000, 3: 350_000, 4: 250_000},
        quarterly_capacity={1: 3, 2: 4, 3: 6, 4: 4},
    )
    print("valid:", roadmap_result.valid)
    print("quarterly cost:", roadmap_result.quarterly_cost)
    assert roadmap_result.valid
    """),
    md("## 25. Trace roadmap outcomes and kill criteria"),
    code("""
    for item in roadmap:
        print(
            f"Q{item.quarter}", item.initiative_id, item.outcome_metric,
            f"{item.baseline} -> {item.target}", "kill:", item.kill_criteria,
        )
    """),
    md("## 26. Failure injection: dependency in the same quarter"),
    code("""
    broken_roadmap = list(roadmap)
    broken_roadmap[1] = replace(broken_roadmap[1], quarter=1)
    broken_result = assess_roadmap(
        broken_roadmap,
        quarterly_budget={1: 1_000_000, 2: 1_000_000, 3: 1_000_000, 4: 1_000_000},
        quarterly_capacity={1: 20, 2: 20, 3: 20, 4: 20},
    )
    print(broken_result.reasons)
    assert not broken_result.valid
    """),
    md("## 27. Compare low, base, and high investment cases"),
    code("""
    investment_results = tuple(
        evaluate_investment(item, discount_rate=0.08) for item in demo_investments()
    )
    for item in investment_results:
        print(item)
    assert investment_results[0].npv < investment_results[1].npv < investment_results[2].npv
    """),
    md("""
    Benefits are discounted by adoption as well as time. The scenarios expose sensitivity; they do
    not promise that modelled productivity becomes cash or that correlation is causal impact.
    """),
    md("## 28. Preserve evidence-backed dissent"),
    code("""
    dissent = DissentRecord(
        "portfolio-2027", "proposal-digest", "security-lead", ("threat-model-12",),
        "portfolio-chair", "stage with additional monitoring",
        DissentStatus.ACCEPTED_RISK, ("supplier concentration",),
    )
    validate_dissent(dissent)
    print(dissent)
    """),
    md("## 29. Failure injection: resolved status hides risk"),
    code("""
    try:
        validate_dissent(replace(dissent, status=DissentStatus.RESOLVED))
    except ValueError as error:
        print("rejected:", error)
    """),
    md("## 30. Define bounded delegation and mentoring"),
    code("""
    delegation = DelegationContract(
        "draft and defend the evaluation service standard", "staff-engineer",
        "may propose and revise; control owner approves",
        ("principal architect", "policy repository", "consumer interviews"),
        7, "hard constraint or unresolved owner conflict",
        "review-ready standard, conformance test and migration note",
        "lead a cross-functional evidence review",
    )
    validate_delegation(delegation)
    print(delegation)
    """),
    md("""
    Delegation names the objective, authority boundary, resources, check-ins, escalation, completion
    and learning. It grows decision capacity without silently transferring production authority.
    """),
    md("## 31. Evaluate portfolio metrics with explicit denominators"),
    code("""
    metrics = portfolio_metrics(candidates, selection)
    print(metrics)
    assert metrics.total == 70
    assert metrics.funded_rate == round(len(selection.funded) / 70, 4)
    """),
    md("## 32. Compare baseline and governed system"),
    code("""
    comparison = {
        "naive": {"hard_gates": False, "evidence_state": False, "constraints": 1, "audit": False},
        "governed": {"hard_gates": True, "evidence_state": True, "constraints": 5, "audit": True},
    }
    for name, attributes in comparison.items():
        print(name, attributes)
    """),
    md("## 33. Run the complete operating-model demonstration"),
    code("""
    result = run_demo_operating_model()
    print("candidate count:", result["candidate_count"])
    print("maturity floor:", result["maturity"].overall)
    print("roadmap valid:", result["roadmap"].valid)
    print("investment cases:", [item.name for item in result["investments"]])
    """),
    md("## 34. Production authorization boundary"),
    code("""
    boundary = {
        "model_or_score": "propose, cluster, summarize, challenge",
        "evidence_process": "validate identity, version, unit, freshness and independence",
        "accountable_authority": "allocate, accept risk, contract, authorize, sunset",
        "control_system": "enforce, execute, observe, reconcile and record",
    }
    for actor, responsibility in boundary.items():
        print(actor, "->", responsibility)
    """),
    md("""
    No notebook output is an approval. A production implementation needs authenticated identities,
    current policy, durable state, atomic approvals, protected evidence, retries, audit and appeal.
    """),
    md("## 35. Production upgrade checklist"),
    code("""
    upgrades = [
        "versioned authorized portfolio registry", "signed evidence provenance",
        "policy enforcement and atomic exception use", "finance and capacity integration",
        "live service SLO and support telemetry", "quarterly outcome and sunset review",
        "least-privilege access, retention and audit", "metric definitions and anti-gaming review",
    ]
    for item in upgrades:
        print("[ ]", item)
    """),
    md("## 36. Executive narrative exercise"),
    code("""
    narrative = {
        "problem": "70 PoCs exceed ownership, evidence and delivery capacity",
        "decision": (
            f"fund {len(selection.funded)}, experiment {len(selection.experiments)}, "
            f"stop {len(selection.stopped)}"
        ),
        "investment": "approve staged low/base/high envelope, not one guaranteed ROI",
        "risk": "hard gates, tiered controls and independently owned exceptions",
        "milestones": "decision rights -> portfolio gate -> paved road -> scale review",
        "ask": "fund evidence and shared capability before broad production expansion",
    }
    for key, value in narrative.items():
        print(f"{key:12}: {value}")
    """),
    md("""
    ## 37. Exercises

    1. Add a domain-concentration constraint while preserving deterministic reason codes.
    2. Design a bounded experiment for one referred high-value candidate.
    3. Add opportunity cost and forecast error to the investment scenarios.
    4. Write a non-waivable control and an identity-backed enforcement design.
    5. Define a platform experience metric that cannot be satisfied by forced adoption.
    6. Rehearse a five-minute oral defense and answer an evidence-backed dissent.
    """),
    md("""
    ## 38. Summary

    You converted a demo backlog into an operating system for enterprise AI decisions. The system
    gates non-compensatory risk, qualifies evidence, separates learning from scaling, selects under
    real constraints, defines service and authority boundaries, preserves dissent, funds a
    dependency-aware roadmap, and keeps uncertainty visible. That is Staff-level leverage.
    """),
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
