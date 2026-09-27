"""Build the canonical Course 8 notebook from reviewed source cells."""

from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
TARGET = (
    ROOT
    / "curriculum"
    / "advanced"
    / "08-ai-evaluation-causal-impact"
    / "ai_evaluation_causal_impact.ipynb"
)


def md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


def code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


cells = [
    md(
        """
        # Course 8 Lab — AI Evaluation, Experimentation, and Causal Impact

        **Decision question:** should Northstar progress its candidate underwriting assistant to a
        bounded monitored rollout, and does randomized access improve task productivity without
        harming reviewed decision quality?

        We will construct the evidence, inject failures, evaluate uncertainty, and preserve
        accountable decision ownership. A good aggregate score is never sufficient by itself.
        """
    ),
    md(
        """
        ## 1. Success and safety contract

        A healthy candidate must clear frozen offline cases, required slices, evidence support,
        latency, cost, judge-calibration, and order-bias gates. Restricted-data leakage or an
        unauthorized tool is a hard failure. The product experiment must reach its fixed horizon,
        improve task time, preserve decision accuracy, and produce no prohibited outcome.

        All cases are synthetic. No API key, model call, production record, or cloud account is
        required. The notebook demonstrates analysis contracts; it does not authorize deployment.
        """
    ),
    code(
        """
        from dataclasses import replace

        from lab import (
            CausalDesign,
            DatasetPartition,
            EvaluationHarness,
            PanelPoint,
            ReleaseDisposition,
            ReleasePolicy,
            adjudicated_human_labels,
            adopter_only_time_saved,
            analyze_experiment,
            bootstrap_paired_delta,
            build_decision_memo,
            build_demo_experiment,
            build_demo_manifest,
            calibrate_judge,
            decide_release,
            default_metric_contracts,
            demo_experiment_plan,
            demo_human_labels,
            demo_judge_assessments,
            demo_system_outputs,
            difference_in_differences,
            evaluation_decision_map,
            holm_bonferroni,
            naive_peeking_false_positive,
            pairwise_order_flip_rate,
            pretrend_difference,
            required_sample_size_per_arm,
            run_demo_release,
        )

        print("Course 8 deterministic evidence lab ready")
        """
    ),
    md(
        """
        ## 2. Inspect the decision map

        Each layer has one job. In particular, a judge provides a measurement and the application
        owner makes a release decision; evaluator code never gains deployment authorization.
        """
    ),
    code(
        """
        for layer, contract in evaluation_decision_map().items():
            print(f"{layer:12} {contract}")
        """
    ),
    md(
        """
        ## 3. Make the metric contracts reviewable

        Inspect the numerator and denominator before any result. Notice that unit economics uses
        successful compliant tasks—not all attempts—as its denominator.
        """
    ),
    code(
        """
        for metric in default_metric_contracts():
            print(metric.name)
            print(" population:", metric.population)
            print(" numerator:", metric.numerator)
            print(" denominator:", metric.denominator)
            print(" slices:", metric.required_slices, "owner:", metric.owner)
        """
    ),
    md(
        """
        ## 4. Prove dataset partitioning

        Development cases support iteration, calibration cases tune measurement, and the release
        partition remains frozen. Stable digests catch exact cross-partition leakage; production
        also needs semantic near-duplicate and benchmark-contamination review.
        """
    ),
    code(
        """
        manifest = build_demo_manifest()
        for partition in DatasetPartition:
            cases = manifest.partition(partition)
            print(partition.value, len(cases), sorted({case.slice_name for case in cases}))
        assert len(manifest.cases) == 32
        """
    ),
    md(
        """
        ## 5. Failure injection: leakage

        Reusing a development prompt in the release set invalidates the evidence boundary. The
        manifest rejects it before a score can be computed.
        """
    ),
    code(
        """
        leaked_case = replace(manifest.cases[-1], prompt=manifest.cases[0].prompt)
        leaked_manifest = replace(manifest, cases=(*manifest.cases[:-1], leaked_case))
        try:
            leaked_manifest.validate()
        except ValueError as error:
            print("blocked:", error)
        """
    ),
    md(
        """
        ## 6. Evaluate the paired baseline and candidate

        Both systems run on identical ordered release cases. The harness enforces complete output
        coverage, case binding, allowed tools, evidence recall, terminal state, and forbidden
        outcomes before aggregating overall and required-slice reports.
        """
    ),
    code(
        """
        release_cases = manifest.partition(DatasetPartition.RELEASE)
        harness = EvaluationHarness(manifest)
        baseline = harness.evaluate(
            system_id="baseline-v8",
            partition=DatasetPartition.RELEASE,
            outputs=demo_system_outputs(release_cases, candidate=False),
        )
        candidate = harness.evaluate(
            system_id="candidate-v9",
            partition=DatasetPartition.RELEASE,
            outputs=demo_system_outputs(release_cases, candidate=True),
        )
        print("system       compliant  evidence  p95-ms  cost/success")
        for report in (baseline, candidate):
            print(
                report.system_id,
                f"{report.compliant_success_rate:.3f}",
                f"{report.evidence_recall:.3f}",
                report.p95_latency_ms,
                f"{report.cost_per_successful_compliant_task:.3f}",
            )
        """
    ),
    md(
        """
        ## 7. Pair before estimating uncertainty

        Candidate-minus-baseline outcomes are resampled as pairs. A positive point estimate is not
        enough: non-inferiority depends on the lower interval bound and a predeclared margin.
        """
    ),
    code(
        """
        paired = bootstrap_paired_delta(
            [float(case.successful_compliant) for case in baseline.cases],
            [float(case.successful_compliant) for case in candidate.cases],
        )
        print(paired)
        assert paired.lower >= -0.05
        """
    ),
    md(
        """
        ## 8. Establish human ground truth

        Each case has three independent blinded annotations under one rubric version. The lab
        refuses a tie instead of silently inventing a label.
        """
    ),
    code(
        """
        human_truth, annotations = demo_human_labels()
        adjudicated = adjudicated_human_labels(
            annotations, rubric_version="underwriting-rubric-v4"
        )
        assert adjudicated == human_truth
        print("adjudicated cases:", len(adjudicated))
        """
    ),
    md(
        """
        ## 9. Calibrate the judge, then inspect disagreement

        Overall accuracy is accompanied by precision, recall, false-positive rate, kappa, a Wilson
        interval, and case-level disagreements. The judge is valid only for the measured task and
        version envelope.
        """
    ),
    code(
        """
        judge = calibrate_judge(human_truth, demo_judge_assessments())
        print(judge)
        assert judge.accuracy >= 0.85
        print("disagreements requiring review:", judge.disagreements)
        """
    ),
    md(
        """
        ## 10. Failure injection: judge drift and order bias

        A changed evaluator can fall below the calibration floor. Pairwise reversal estimates how
        often presentation order changes the preference.
        """
    ),
    code(
        """
        biased_judge = calibrate_judge(human_truth, demo_judge_assessments(biased=True))
        flip_rate = pairwise_order_flip_rate(
            {"a": "left", "b": "right", "c": "left", "d": "tie"},
            {"a": "right", "b": "right", "c": "right", "d": "tie"},
        )
        print("biased accuracy:", biased_judge.accuracy, "order flip rate:", flip_rate)
        """
    ),
    md(
        """
        ## 11. Apply the three-way release gate

        Hard privacy or tool violations fail. Weak statistical, slice, judge, latency, or cost
        evidence is inconclusive. Only clearing every gate passes.
        """
    ),
    code(
        """
        policy = ReleasePolicy(4, 0.85, 0.05, 0.85, 1.20, 1.10, 0.85, 0.10)
        offline = decide_release(
            baseline,
            candidate,
            policy=policy,
            judge=judge,
            order_flip_rate=0.0,
            leakage_detected=False,
        )
        print(offline)
        assert offline.disposition is ReleaseDisposition.PASS
        """
    ),
    md(
        """
        ## 12. Failure injection: forbidden outcome

        One restricted-data leak is not averaged into a high success rate. It fails the release
        even if every other case improves.
        """
    ),
    code(
        """
        unsafe = harness.evaluate(
            system_id="unsafe-candidate",
            partition=DatasetPartition.RELEASE,
            outputs=demo_system_outputs(
                release_cases, candidate=True, inject_forbidden=True
            ),
        )
        unsafe_decision = decide_release(
            baseline,
            unsafe,
            policy=policy,
            judge=judge,
            order_flip_rate=0.0,
            leakage_detected=False,
        )
        print(unsafe_decision.disposition, unsafe_decision.reasons)
        assert unsafe_decision.disposition is ReleaseDisposition.FAIL
        """
    ),
    md(
        """
        ## 13. Multiplicity and optional-stopping traps

        Holm-Bonferroni keeps a confirmatory family honest. The peeking helper deliberately shows
        the invalid rule: repeatedly stop when an ordinary fixed-horizon p-value happens to cross
        0.05.
        """
    ),
    code(
        """
        print(holm_bonferroni({"primary": 0.01, "novice": 0.03, "expert": 0.04}))
        print("naive peeking claims a win:", naive_peeking_false_positive([0.4, 0.18, 0.049]))
        print(
            "illustrative fixed sample per arm:",
            required_sample_size_per_arm(
                standard_deviation=10, minimum_detectable_effect=4
            ),
        )
        """
    ),
    md(
        """
        ## 14. Analyze the randomized product experiment

        The estimand is intention to treat: all assigned underwriters remain in their arm.
        Productivity is the primary outcome; decision accuracy is a non-inferiority guardrail.
        """
    ),
    code(
        """
        units = build_demo_experiment()
        plan = demo_experiment_plan()
        experiment = analyze_experiment(units, plan)
        print("decision:", experiment.decision, experiment.reasons)
        print("ITT minutes saved:", experiment.time_saved_itt)
        print("accuracy delta:", experiment.accuracy_delta)
        print("adoption:", experiment.adoption_rate)
        assert experiment.decision is ReleaseDisposition.PASS
        """
    ),
    md(
        """
        ## 15. CUPED improves precision, not truth

        Pre-task duration predicts post-task duration and is measured before assignment effects.
        The adjusted interval is narrower while the raw ITT remains visible.
        """
    ),
    code(
        """
        raw_width = experiment.time_saved_itt.upper - experiment.time_saved_itt.lower
        adjusted_width = experiment.time_saved_cuped.upper - experiment.time_saved_cuped.lower
        print("raw width:", raw_width, "CUPED width:", adjusted_width)
        assert adjusted_width < raw_width
        """
    ),
    md(
        """
        ## 16. Adoption is not the causal estimand

        Treatment adopters are a post-assignment selected subgroup. Compare the adopter-only number
        with ITT, but do not describe the former as a randomized effect.
        """
    ),
    code(
        """
        adopter_estimate = adopter_only_time_saved(units)
        print("ITT:", experiment.time_saved_itt.difference)
        print("selected adopters only:", adopter_estimate)
        assert adopter_estimate != experiment.time_saved_itt.difference
        """
    ),
    md(
        """
        ## 17. Inspect heterogeneity without data dredging

        Novices and experts have different effects in the fixture. These slices were defined before
        analysis; sparse exploratory segments would require replication and multiplicity control.
        """
    ),
    code(
        """
        for expertise, minutes in experiment.heterogeneous_time_saved.items():
            print(expertise, f"{minutes:.2f} minutes saved")
        """
    ),
    md(
        """
        ## 18. Failure injection: an incomplete experiment

        Stopping after six units per arm cannot satisfy a pre-registered forty-per-arm horizon,
        even if the early point estimate looks attractive.
        """
    ),
    code(
        """
        early = analyze_experiment(
            build_demo_experiment(sample_per_arm=6),
            demo_experiment_plan(sample_per_arm=40),
        )
        print(early.decision, early.reasons)
        assert "fixed-horizon-not-reached" in early.reasons
        """
    ),
    md(
        """
        ## 19. Difference-in-differences and pretrends

        When randomization is unavailable, DiD subtracts the control trend from the treated trend.
        Its identification rests on parallel untreated trends and other design assumptions, not on
        the subtraction formula alone.
        """
    ),
    code(
        """
        panel = [
            PanelPoint("c", False, 0, 10),
            PanelPoint("c", False, 1, 11),
            PanelPoint("c", False, 2, 12),
            PanelPoint("t", True, 0, 14),
            PanelPoint("t", True, 1, 15),
            PanelPoint("t", True, 2, 11),
        ]
        print("pretrend difference:", pretrend_difference(panel, treatment_period=2))
        print("DiD effect:", difference_in_differences(panel, treatment_period=2))
        assert pretrend_difference(panel, treatment_period=2) == 0
        """
    ),
    md(
        """
        ## 20. Failure injection: invalid causal adjustment

        Experience is a pre-treatment confounder in this declared graph. Adoption is a mediator and
        reviewed-only inclusion is a collider. Adding every convenient column can bias the result.
        """
    ),
    code(
        """
        design = CausalDesign(
            treatment="assistant access",
            outcome="decision quality",
            confounders=frozenset({"experience"}),
            mediators=frozenset({"adoption"}),
            colliders=frozenset({"reviewed"}),
        )
        design.validate_adjustment_set(frozenset({"experience"}))
        for invalid in (
            frozenset({"experience", "adoption"}),
            frozenset({"experience", "reviewed"}),
            frozenset(),
        ):
            try:
                design.validate_adjustment_set(invalid)
            except ValueError as error:
                print("blocked:", error)
        """
    ),
    md(
        """
        ## 21. Produce the decision memo

        The memo joins offline and causal evidence, retains limitations, and names accountable
        owners. It recommends only a bounded monitored rollout—not universal production safety.
        """
    ),
    code(
        """
        memo = build_decision_memo(offline, experiment)
        print("recommendation:", memo.recommendation)
        print("evidence:")
        for item in memo.evidence:
            print(" -", item)
        print("limitations:")
        for item in memo.limitations:
            print(" -", item)
        print("owners:", ", ".join(memo.owners))
        """
    ),
    md(
        """
        ## 22. End-to-end regression proof

        The packaged demonstration reproduces the same passing release and experiment decisions.
        This protects the teaching path from silent fixture drift.
        """
    ),
    code(
        """
        demo_release, demo_experiment, demo_memo = run_demo_release()
        assert demo_release.disposition is ReleaseDisposition.PASS
        assert demo_experiment.decision is ReleaseDisposition.PASS
        assert demo_memo.recommendation == "progress to a bounded monitored rollout"
        print("end-to-end evidence chain passed")
        """
    ),
    md(
        """
        ## 23. Production upgrade plan

        Replace fixtures with versioned application-owned datasets and output records; bind every
        case to prompt, model, policy, retrieval, and evaluator versions; run deterministic checks
        before semantic evaluation; calibrate judges against blinded domain reviewers; store paired
        outputs and uncertainty; and make CI emit a signed evidence manifest without deploying.

        For the experiment, use the product's trusted eligibility and assignment service, immutable
        exposure events, complete outcome joins, authorization-safe instrumentation, sample-ratio
        and missingness diagnostics, cluster-aware analysis where users interact, and a reviewed
        analysis plan. Roll out gradually with Course 7 monitoring and a tested rollback path.
        """
    ),
    md(
        """
        ## 24. Evidence checklist

        - metric registry with populations, denominators, thresholds, uncertainty, and owners;
        - dataset card with roles, provenance, slices, leakage review, and refresh triggers;
        - human protocol and adjudicated labels;
        - judge calibration, disagreement, order-bias, and drift report;
        - paired offline release result with hard failures and three-way status;
        - pre-registered experiment and power calculation;
        - ITT, guardrail, CUPED, SRM, adoption, and heterogeneity results;
        - causal graph and identification assumptions for any observational estimate; and
        - decision memo with limitations, decision rights, bounded rollout, monitoring, and
          rollback.
        """
    ),
    md(
        """
        ## 25. Reflection

        1. Which result would change if abstentions entered the denominator differently?
        2. Which slice is both high risk and underpowered in your real system?
        3. What judge error is costliest, and does overall accuracy reveal it?
        4. Which treatment spillover would require cluster randomization?
        5. What pre-treatment covariate could safely reduce variance?
        6. Which unmeasured confounder makes an observational claim least credible?
        7. What evidence would reverse the rollout decision?
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
