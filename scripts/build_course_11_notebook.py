"""Build the canonical Course 11 notebook from reviewed source cells."""

from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
TARGET = (
    ROOT
    / "curriculum/advanced/11-solution-architecture-technical-strategy"
    / "solution_architecture_strategy.ipynb"
)


def md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


def code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


cells = [
    md("""
    # Course 11 Lab — Solution Architecture and Technical Strategy

    **Capstone:** should Northstar build a centralized RAG and agent platform?

    We turn stakeholder concerns into measurable scenarios, compare credible options with
    version-bound evidence and uncertainty, model economics, record an accountable decision, and
    design a reversible migration.
    """),
    md("""
    ## 1. Scope and decision boundary

    This notebook is deterministic, credential-free and based on synthetic pilot evidence. Its
    recommendation demonstrates a method; it is not a real procurement or cloud recommendation.
    Scores inform judgment. The trusted review process validates evidence and records the decision;
    no model, matrix or vendor claim creates authorization.
    """),
    code("""
    from dataclasses import replace

    from lab import (
        DecisionDisposition,
        DecisionStatus,
        StageStatus,
        assess_migration,
        calculate_tco,
        demo_adr,
        demo_concerns,
        demo_criteria,
        demo_economics,
        demo_evidence,
        demo_migration,
        demo_options,
        demo_quality_scenarios,
        evaluate_option,
        rank_options,
        run_demo_strategy,
        sensitivity_analysis,
        validate_adr,
    )

    TRUSTED = frozenset({"architecture-review-office"})
    NOW = 1_300
    print("Course 11 architecture strategy lab ready")
    """),
    md("## 2. Architecture decision lifecycle"),
    code("""
    lifecycle = [
        "outcomes and stakeholders", "quality scenarios and constraints", "credible options",
        "evidence, economics and risk", "trade-off and sensitivity", "ADR/RFC",
        "transition stages", "runtime feedback and reversal",
    ]
    for index, stage in enumerate(lifecycle, start=1):
        print(index, stage)
    """),
    md("""
    Architecture is not the score or diagram. The evidence chain connects why the system exists to
    how a decision will be tested and changed.
    """),
    md("## 3. Start with stakeholders and decision rights"),
    code("""
    concerns = demo_concerns()
    for item in concerns:
        print(f"{item.stakeholder:10} | {item.outcome:35} | {item.decision_right}")
    """),
    md("""
    Product, platform, security and finance own different decisions. Consultation is not approval;
    review acceptance is not production deployment authority.
    """),
    md("## 4. Make quality attributes testable"),
    code("""
    scenarios = demo_quality_scenarios()
    for item in scenarios:
        print(item.scenario_id, "=>", item.measure, item.direction, item.threshold, item.unit)
    """),
    md("""
    Each scenario names source, stimulus, environment, artifact, response and measure. Generic
    “secure and scalable” requirements cannot drive design or validation.
    """),
    md("## 5. Inspect the credible options"),
    code("""
    options = demo_options()
    for option in options:
        print(
            option.option_id, option.kind, sorted(option.capabilities),
            "exit:", option.exit_strategy,
        )
    """),
    md("""
    Point solutions, a fully custom central platform, and a governed hybrid each include ownership,
    capability scope, provider dependencies and exit—not just product names.
    """),
    md("## 6. Define criteria and preserve hard constraints"),
    code("""
    criteria = demo_criteria()
    for item in criteria:
        print(
            f"{item.criterion_id:28} weight={item.weight:.2f} "
            f"hard={item.hard_threshold} {item.unit}"
        )
    assert abs(sum(item.weight for item in criteria) - 1.0) < 1e-9
    """),
    md("""
    Tenant isolation and compliant success require independent evidence and hard thresholds. Cost
    or speed cannot compensate for a breach.
    """),
    md("## 7. Establish the naive baseline"),
    code("""
    naive = {
        "point-solutions": 9, "central-build": 8, "hybrid-platform": 7,
    }
    print("untraceable executive preference:", max(naive, key=naive.get))
    print("missing: units, constraints, evidence, confidence, cost range, reversal")
    """),
    md("""
    A one-number preference looks decisive but cannot be challenged or reproduced. We replace it
    with exact evidence records and three decision states.
    """),
    md("## 8. Inspect evidence contracts"),
    code("""
    evidence = demo_evidence()
    sample = next(
        item for item in evidence
        if item.option_id == "hybrid-platform" and item.criterion_id == "compliant-success"
    )
    print(sample)
    assert sample.independent and sample.option_version == "v1"
    """),
    md("## 9. Evaluate all options"),
    code("""
    decisions = tuple(
        evaluate_option(option, criteria, evidence, trusted_producers=TRUSTED, now=NOW)
        for option in options
    )
    for item in decisions:
        print(item.option_id, item.disposition, item.utility_score, item.reasons)
    """),
    md("""
    Point solutions fail tenant isolation. The custom central build misses time to value. The hybrid
    meets hard thresholds and is eligible. Disqualification is not a low weighted score.
    """),
    md("## 10. Rank only eligible options"),
    code("""
    ranking = rank_options(decisions)
    print([(item.option_id, item.utility_score, item.confidence) for item in ranking])
    assert [item.option_id for item in ranking] == ["hybrid-platform"]
    """),
    md("## 11. Failure injection: missing evidence"),
    code("""
    missing = tuple(
        item for item in evidence
        if not (item.option_id == "hybrid-platform" and item.criterion_id == "portability")
    )
    hybrid = next(item for item in options if item.option_id == "hybrid-platform")
    unknown = evaluate_option(hybrid, criteria, missing, trusted_producers=TRUSTED, now=NOW)
    print(unknown.disposition, unknown.reasons)
    assert unknown.disposition is DecisionDisposition.INCONCLUSIVE
    """),
    md("""
    Missing evidence is not an observed value of zero. The recommendation pauses until the gap is
    measured or an accountable decision explicitly narrows scope.
    """),
    md("## 12. Failure injection: vendor claim used as independent evidence"),
    code("""
    modified = list(evidence)
    index = next(
        i for i, item in enumerate(modified)
        if item.option_id == "hybrid-platform" and item.criterion_id == "compliant-success"
    )
    modified[index] = replace(modified[index], producer="vendor-sales", independent=False)
    untrusted = evaluate_option(hybrid, criteria, modified, trusted_producers=TRUSTED, now=NOW)
    print(untrusted.disposition, untrusted.reasons)
    assert untrusted.disposition is DecisionDisposition.DISQUALIFIED
    """),
    md("## 13. Failure injection: stale option version"),
    code("""
    wrong_version = tuple(
        replace(item, option_version="v2") if item.option_id == "hybrid-platform" else item
        for item in evidence
    )
    stale_version = evaluate_option(
        hybrid, criteria, wrong_version, trusted_producers=TRUSTED, now=NOW
    )
    print(stale_version.disposition, stale_version.reasons[:3], "…")
    assert stale_version.disposition is DecisionDisposition.INCONCLUSIVE
    """),
    md("## 14. Inspect criterion contributions"),
    code("""
    hybrid_decision = next(item for item in decisions if item.option_id == "hybrid-platform")
    for result in hybrid_decision.results:
        print(
            f"{result.criterion_id:28} normalized={result.normalized_score} "
            f"confidence={result.confidence} contribution={result.weighted_score}"
        )
    """),
    md("""
    Visible contributions reveal where a recommendation depends on low-confidence evidence or a
    controversial weight. The score is not more precise than its assumptions.
    """),
    md("## 15. Run sensitivity analysis"),
    code("""
    sensitivity = sensitivity_analysis(
        options, criteria, evidence, trusted_producers=TRUSTED, now=NOW, shift=0.15
    )
    print(sensitivity)
    assert sensitivity.stable_winner == "hybrid-platform"
    """),
    md("""
    Each criterion receives a relative 15% weight increase. The same winner survives every model;
    this is evidence of local stability, not proof under every future assumption.
    """),
    md("## 16. Model low, expected, and high total economics"),
    code("""
    economics = tuple(calculate_tco(item) for item in demo_economics())
    for item in economics:
        print(
            item.option_id, "low/expected/high=",
            (item.low, item.expected, item.high), "unit=", item.cost_per_unit,
            "risk=", item.expected_risk_loss,
        )
    """),
    md("""
    The model includes migration, annual platform and people, per-unit use, exit and expected risk
    loss. It avoids treating subscription price or existing staff as the total cost.
    """),
    md("## 17. Sensitivity experiment: tenfold volume"),
    code("""
    high_volume = tuple(
        calculate_tco(replace(model, annual_units=model.annual_units * 10))
        for model in demo_economics()
    )
    for item in high_volume:
        print(item.option_id, item.expected, item.cost_per_unit)
    """),
    md("""
    Fixed cost amortizes while variable cost grows. Architecture economics must be evaluated at
    realistic adoption and workload shapes rather than one average request count.
    """),
    md("## 18. Build the architecture decision record"),
    code("""
    adr = demo_adr(evidence)
    print(adr.adr_id, adr.status, adr.selected_option_id)
    print("assumptions:", adr.assumptions)
    print("reversal:", adr.reversal_triggers)
    print("digest:", adr.decision_digest)
    """),
    md("## 19. Validate accountable acceptance"),
    code("""
    known_options = frozenset(item.option_id for item in options)
    known_evidence = frozenset(item.evidence_id for item in evidence)
    reasons = validate_adr(
        adr, known_options=known_options, known_evidence=known_evidence, now=NOW
    )
    print("ADR findings:", reasons)
    assert reasons == () and adr.status is DecisionStatus.ACCEPTED
    """),
    md("## 20. Failure injection: alter the accepted decision"),
    code("""
    altered = replace(adr, decision="Centralize every domain workflow")
    altered_reasons = validate_adr(
        altered, known_options=known_options, known_evidence=known_evidence, now=NOW
    )
    print(altered_reasons)
    assert "decision-digest-mismatch" in altered_reasons
    """),
    md("""
    Acceptance binds an exact record. The owner cannot self-approve, and changing the decision,
    evidence, assumptions or triggers requires a new reviewed version.
    """),
    md("## 21. Design the transition architecture"),
    code("""
    migration = demo_migration()
    for stage in migration:
        print(stage.stage_id, stage.status, "depends on", stage.depends_on)
    assessment = assess_migration(migration)
    print("ready next:", assessment.ready_stages)
    assert assessment.valid and assessment.ready_stages == ("scale",)
    """),
    md("## 22. Failure injection: migration dependency cycle"),
    code("""
    cyclic = (
        replace(migration[0], depends_on=("scale",), status=StageStatus.PLANNED),
        migration[1], migration[2], migration[3],
    )
    cycle_result = assess_migration(cyclic)
    print(cycle_result.reasons)
    assert "migration-cycle" in cycle_result.reasons
    """),
    md("""
    A roadmap is an executable dependency and evidence model, not colored quarters. Each stage has
    an owner, entry/exit evidence, rollback and kill criteria.
    """),
    md("## 23. Compare baseline and evidence-backed practice"),
    code("""
    comparison = {
        "requirements": ("secure and scalable", "quality scenarios with measures"),
        "options": ("preferred vendor", "coherent build/buy/partner/hybrid systems"),
        "evidence": ("claims", "version, unit, source, producer, freshness, confidence"),
        "trade-off": ("one score", "hard gates + uncertainty + sensitivity"),
        "economics": ("price", "TCO range + risk + unit + exit"),
        "decision": ("meeting notes", "ADR with consequences and reversal"),
        "migration": ("target diagram", "staged entry/exit/rollback/kill"),
    }
    for topic, (before, after) in comparison.items():
        print(f"{topic:12} {before:24} -> {after}")
    """),
    md("## 24. Execute the complete strategy path"),
    code("""
    result = run_demo_strategy()
    print("recommended:", result["ranking"][0].option_id)
    print("stable:", result["sensitivity"].stable_winner)
    print("ADR findings:", result["adr_reasons"])
    print("migration valid:", result["migration"].valid)
    assert result["ranking"][0].option_id == "hybrid-platform"
    """),
    md("""
    ## 25. Interpretation and limitations

    The hybrid recommendation follows from this synthetic dataset. A real decision needs provider
    pilots, domain slices, legal/security review, capacity and failure tests, causal adoption/value
    evidence, commercial terms, staffing reality, and verified exit. The method preserves where the
    conclusion came from and what would change it.
    """),
    md("""
    ## 26. Production upgrade path

    | Notebook primitive | Production practice |
    |---|---|
    | dataclass concerns | versioned requirement/scenario registry with owners |
    | synthetic observations | linked pilot, test, SLO, cost and risk evidence |
    | local score | reviewed model with ranges, slices and sensitivity |
    | cost function | finance-reviewed forecast versus actual unit economics |
    | ADR digest | immutable decision repository and supersession workflow |
    | stage tuple | portfolio/dependency tracking with release evidence |
    | local review | cross-functional RFC, dissent, decision and escalation |

    Automate deterministic fitness functions, but retain accountable judgment for goals, trade-offs,
    ethics, legal interpretation, residual risk and organizational consequences.
    """),
    md("""
    ## 27. Exercises

    1. Add an integrated commercial-suite option with vendor and independent evidence separated.
    2. Add sustainability and data-residency criteria without averaging away hard constraints.
    3. Create a regulated-risk slice that fails while the aggregate succeeds.
    4. Find volume, price, staffing or adoption conditions that flip the recommendation.
    5. Design and validate a provider-exit stage before consolidating legacy services.
    """),
    md("""
    ## 28. Summary

    Good architecture makes reasoning inspectable: outcomes, scenarios, constraints, options,
    evidence, uncertainty, costs, decisions, transitions and reversal. The recommendation matters;
    the ability to test and change it matters more.
    """),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
)
nbf.write(notebook, TARGET)
print(f"Wrote {TARGET} with {len(cells)} cells")
