# Advanced Cross-Functional AI Specialist — Sequential Course Plan

**Audience:** experienced data scientists, ML engineers, AI engineers, and technical leads
**Target:** Staff AI Scientist / AI Architect / cross-functional AI specialist
**Pace:** 24–30 weeks, 6–8 hours per week
**Program thesis:** design, evaluate, secure, operate, and lead an enterprise AI system—not merely
produce a working model call.

## Sequential release model

Courses are developed **one by one**. A course moves from `planned` to `ready` only after its
chapter, reusable implementation, notebook, tests, checkpoint, quiz integration, Hub entry, and
validation evidence all pass. Deployment is a separate verified step. Courses 1–7 are complete
vertical slices; Courses 8–12 define the agreed sequence and scope.

## Program project: Northstar Underwriting AI Platform

The learner progressively turns an internal underwriting assistant into a governed enterprise
capability. The scenario supplies realistic identity, data, latency, audit, reliability, and cost
constraints without requiring access to private systems.

```mermaid
flowchart LR
    B[Business case] --> A[Application boundaries]
    A --> D[Distributed deployment]
    D --> I[Identity and authorization]
    I --> K[Knowledge and RAG]
    K --> G[Agent workflows]
    G --> M[Model gateway]
    M --> O[Observability and SLOs]
    O --> E[Evaluation and experiments]
    E --> S[Security and governance]
    S --> C[Delivery platform]
    C --> T[Technical strategy]
    T --> P[Enterprise operating model]
```

Every course contributes a portfolio artifact under a consistent architecture record. Later
courses may revise earlier decisions; the learner must explain why the evidence changed.

## Sequence at a glance

| # | Course | Weeks | Status | Evidence produced |
|---:|---|---:|---|---|
| 1 | Production AI Development in Python | 3 | **Ready** | Tested service core, review memo, packaging decision |
| 2 | Cloud and Distributed AI Systems | 3 | **Ready** | AWS deployment architecture, load/failure model, ADR |
| 3 | Enterprise Identity and Agent Authorization | 2 | **Ready** | Threat-aware auth design, delegated capability tests |
| 4 | Production RAG and Knowledge Systems | 3 | **Ready** | Secure ingestion/retrieval pipeline and retrieval eval |
| 5 | Agentic AI Architecture and AgentCore | 3 | **Ready** | Bounded workflow/agent comparison and recovery plan |
| 6 | Model Gateways and Inference Economics | 2 | **Ready** | Routing policy, fallback experiment, unit economics |
| 7 | AI Observability and Reliability Engineering | 2 | **Ready** | OpenTelemetry traces, SLOs, runbook, game day |
| 8 | AI Evaluation, Experimentation, and Causal Impact | 3 | Planned | Release gate, human-eval protocol, causal experiment |
| 9 | AI Security, Red Teaming, and Governance | 3 | Planned | Threat model, adversarial suite, governance controls |
| 10 | CI/CD, Infrastructure, and AI DevOps | 2 | Planned | Promotion pipeline, IaC plan, rollback evidence |
| 11 | Solution Architecture and Technical Strategy | 2 | Planned | Options paper, target architecture, migration roadmap |
| 12 | Enterprise AI Operating Model and Leadership | 2 | Planned | Portfolio strategy, standards, executive narrative |

## Course 1 — Production AI Development in Python

**Status:** Ready in repository
**Prerequisites:** fluent Python and prior experience with ML/GenAI prototypes
**Thesis:** a Staff AI specialist can turn an experimental workflow into a typed, testable,
observable application core whose provider and infrastructure adapters can change independently.

### Outcomes and practical increment

The learner separates boundary models, policy, ports, and adapters; explains packaging, build
backends, locking, typing, async I/O, and dependency injection; enforces trusted identity and
authorization before ranking; applies time/result budgets; and distinguishes tests, evaluations,
and monitoring. The lab refactors a notebook-style assistant, injects timeout and forged-citation
failures, and measures state accuracy, citation recall, forbidden outcomes, latency, and a cost
proxy.

**Tools:** `pyproject.toml`, uv, Protocols, Pydantic v2, asyncio, FastAPI concepts, pytest, Ruff,
mypy, deterministic adapters.
**Exit evidence:** passing invariants and notebook; code-review memo; packaging/build ADR; measured
evaluation report with correct denominators.

## Course 2 — Cloud and Distributed AI Systems

**Status:** Ready in repository · **Prerequisite:** Course 1
**Thesis:** choose deployment, state, and messaging patterns from workload and failure requirements,
not a memorized list of cloud products.

### Depth and practice

- Request/response, asynchronous jobs, event streams, long-running workflows, backpressure, order,
  replay, idempotency, unknown outcomes, cache ownership, consistency, and partitions.
- Lambda, ECS/Fargate, EKS, EC2, SageMaker endpoints, and Bedrock; SQS, SNS, EventBridge, Kinesis,
  and Step Functions; S3, DynamoDB, Aurora/RDS, OpenSearch, and Redis.
- Capacity, tail latency, concurrency, availability, recovery, work amplification, and cost.

The deterministic lab compares synchronous and queued document analysis under duplicate delivery,
out-of-order versions, transient and persistent throttling, an uncertain write, and sustained
overload. It proves stable logical operation identity, payload-digest conflicts, reconciliation,
conditional version writes, bounded retry, and DLQ behavior. Evidence: AWS ADR, failure model, load
experiment, and cost/operability comparison.

## Course 3 — Enterprise Identity and Agent Authorization

**Status:** Ready in repository · **Prerequisite:** Course 2
**Thesis:** identity, delegation, and policy are trusted application capabilities; role text, tool
arguments, and agent names never create authority.

### Depth and practice

- OAuth 2.0/OIDC, issuers, audiences, tokens, scopes, claims, Entra ID service principals, IAM and
  workload identity; RBAC, ABAC, policy decision/enforcement points, tenant/subject isolation.
- User-delegated versus service authority, capability attenuation, credential isolation, and
  single-use approvals bound to principal, action, target, digest, policy version, and expiry.
- Confused deputy, wrong audience, cross-tenant, replay, stale policy, and altered-approval tests.

The lab builds a deterministic token-verification boundary, authoritative identity registry,
default-deny policy decision point, attenuated delegation service, and narrow tool gateway. It
separates user subject from workload actor; binds approvals to the exact proposal; consumes them
atomically with the effect; and measures both forbidden outcomes and valid work blocked. Failure
injection covers wrong audience/token use/signature, cross-tenant access, role injection, scope
widening, self-approval, altered parameters, receipt replay, stale policy, and stale entitlements.
Evidence: identity sequence, authorization matrix, negative tests, and delegated-action ADR.

## Course 4 — Production RAG and Knowledge Systems

**Status:** Ready in repository · **Prerequisites:** Courses 2–3
**Thesis:** a production knowledge system owns provenance, freshness, authorization, retrieval
quality, and lifecycle—not only embeddings and prompts.

### Depth and practice

- Parsing, chunking, metadata, embedding, versioning, deletion, lineage, and poison recovery.
- BM25, dense, hybrid, reranking, query transformation, HyDE, adaptive retrieval, graph and
  multimodal patterns, plus explicit criteria for when each adds value.
- Authorization before ranking, tenant isolation, injection resistance, freshness SLOs, Recall@k,
  MRR, nDCG, and citation correctness/completeness.

The lab builds an idempotent, optimistic-versioned ingestion path; carries source digest, locator,
ACL, classification, lifecycle, and processing versions into each chunk; and compares BM25-like
sparse, deterministic dense, RRF hybrid, and bounded reranking paths. Authorization and current
lifecycle filter candidates before scoring. Failure injection covers stale ingestion plans,
cross-tenant/restricted evidence, supersession, deletion, quarantine, stale entitlements, forged
citations, unsupported claims, and evidence deleted during generation. Evidence: retrieval
evaluation, knowledge data contract, ADR, threat model, and production migration plan.

## Course 5 — Agentic AI Architecture and AgentCore

**Status:** Ready in repository · **Prerequisites:** Courses 2–4
**Thesis:** use the least autonomous architecture that meets the requirement; when autonomy is
justified, bound tools, state, authority, cost, time, retries, and termination in application code.

### Depth and practice

- Deterministic workflow, router, planner-executor, supervisor, and multi-agent trade-offs.
- Typed tools, MCP, state, checkpoints, memory, cancellation, restart, logical operation IDs,
  reconciliation, idempotency, approval, delegation, and coordination tax.
- Bedrock Agents/AgentCore and custom orchestration compared on control, identity, portability,
  observability, durability, operating effort, and cost.

The lab implements one exception-review task as a workflow and bounded agent over the same trusted
tool gateway, then measures task/compliant success, tool attempts, latency, and cost. It proves
typed action admission, current principal/workload authorization, pre-effect budgets, exact
single-use approval, stable logical operation replay, unknown-outcome reconciliation, optimistic
checkpoint restart, and application-owned termination. Failure injection covers malicious
retrieved instructions, cross-tenant scope, schema widening, transient timeout/retry exhaustion,
model/cost budgets, cancellation, stale entitlements and case state, concurrent checkpoint writes,
approval alteration/replay/expiry, duplicate delivery, and a lost response after commit. Evidence:
measured architecture decision, threat model, recovery plan, and agent evaluation.

## Course 6 — Model Gateways and Inference Economics

**Status:** Ready in repository · **Prerequisite:** Course 5
**Thesis:** model access is a policy and economics layer balancing quality, latency, availability,
safety, privacy, and cost—not one provider SDK call.

### Depth and practice

- Provider-normalized contracts, structured outputs, streaming, caching, quotas, rate limits,
  routing, small/large cascades, fallback, and hedged requests.
- Retry classification, non-determinism, prompt/version registry, residency, and capability gaps.
- Direct APIs, Bedrock, LiteLLM, and managed gateways; token/cache/egress/retry/operating cost and
  cost per successful compliant task.

The lab uses deterministic fictional provider simulators to compare economy and premium direct
baselines, a calibrated small-to-large cascade, reliability fallback, and delayed hedging through
one provider-normalized boundary. It proves authenticated eligibility, residency/classification and
capability admission, prompt/schema/model versions, pre-call token and spend reservation, bounded
retry classification, safety non-bypass, output/resource binding, tenant-safe response caching,
deadline accounting, and correct economics denominators. Failure injection covers throttling,
authentication and safety errors, invalid and wrong-case output, cross-region fallback, quota and
budget exhaustion, router drift, late responses, cache scope, and hedge amplification. Evidence:
routing policy, gateway ADR, quality/latency/cost frontier, and sensitivity analysis.

## Course 7 — AI Observability and Reliability Engineering

**Status:** Ready in repository · **Prerequisites:** Courses 2 and 6
**Thesis:** operate AI systems with correlated telemetry and user-facing objectives without logging
secrets, unnecessary content, or private reasoning.

### Depth and practice

- Logs, metrics, traces, context propagation, sampling, OpenTelemetry and collector boundaries.
- Request/run/tool/evidence/policy/prompt/model IDs; versions, reason codes, budgets, cost, latency,
  errors and terminal state; redaction and retention.
- SLIs/SLOs, error budgets, circuit breakers, bulkheads, graceful degradation, game days and
  incident review; maturity of GenAI semantic conventions.

The lab defines a privacy-safe versioned telemetry contract; reconstructs tenant-scoped parent/child
traces; keeps authoritative low-cardinality metrics independent of trace sampling; compares head
and policy-based tail sampling; calculates compliant-success, latency, error-budget, fallback, and
unit-economics signals; detects silent fallback through route/model/cost shifts; and exercises a
closed/open/half-open circuit breaker, bulkhead isolation, typed degradation, and evidence-backed
incident lifecycle. Failure injection covers raw content, secrets and high-cardinality fields,
rare errors lost by head sampling, sustained versus low-volume burn, provider impairment, batch
overload, and invalid incident closure. Evidence: telemetry contract, Collector data flow,
dashboard/alert specification, SLO, runbook, resilience ADR, game-day record, incident report, and
tool-selection memo.

## Course 8 — AI Evaluation, Experimentation, and Causal Impact

**Status:** Planned · **Prerequisites:** Courses 4–7
**Thesis:** release decisions need representative cases, trustworthy measurements, uncertainty,
and causal product evidence—not one aggregate judge score.

### Depth and practice

- Labelled sets, slices, deterministic assertions, semantic metrics, pairwise/rubric review, judge
  calibration, position/order bias, leakage, variance, and blinded human evaluation.
- RAG component and end-to-end measures, tool/trajectory evaluation, confidence intervals,
  thresholds, sequential tests, power, variance reduction, and multiple comparisons.
- A/B tests, DAGs, confounding, heterogeneous effects, propensity methods and difference-in-
  differences; adoption versus task quality, time saved, and business outcomes.

The lab builds a release gate, calibrates an automated judge against human labels, and designs the
experiment: “Does the assistant improve productivity without harming decision quality?” Evidence:
metric contracts, evaluation strategy, analysis plan, and decision memo.

## Course 9 — AI Security, Red Teaming, and Governance

**Status:** Planned · **Prerequisites:** Courses 3–8
**Thesis:** combine deterministic preventive controls, adversarial evidence, monitoring, and
governance records across the whole system lifecycle.

### Depth and practice

- Prompt/context injection, exfiltration, excessive agency, tool poisoning, supply chain, denial of
  service, secure RAG, MCP trust, egress, sandboxing, secrets, isolation, and least privilege.
- Threat models, abuse cases, red-team coverage and regression; blocked attempts versus forbidden
  outcomes versus valid work blocked.
- NIST AI RMF, ISO/IEC 42001 concepts, OWASP, MITRE ATLAS, AI inventory, risk tier, system cards,
  approvals, auditability, continuous controls and residual-risk ownership.

The lab attacks the platform using labelled adversarial cases. Evidence: threat model, control
matrix, red-team report, governance-as-code proposal, and explicit residual-risk acceptance.

## Course 10 — CI/CD, Infrastructure, and AI DevOps

**Status:** Planned · **Prerequisites:** Courses 2 and 7–9
**Thesis:** promote immutable application, infrastructure, prompt, model, policy, and evaluation
artifacts through evidence-based gates with provenance and rollback.

### Depth and practice

- GitHub Actions, environments, OIDC federation, least-privilege runners and supply-chain controls.
- Containers, SBOMs, signatures, vulnerability/dependency checks; Terraform modules, state, plans,
  drift, and review; shadow, canary, blue-green and rollback.
- Compatibility/versioning across data, model, prompt and policy; migration and recovery rehearsal.

The lab builds a local-first pipeline and AWS-targeted plan, then breaks a quality gate, introduces
a vulnerable dependency, and simulates a failed canary. Evidence: pipeline policy, IaC review,
release record, rollback proof, and disaster-recovery rehearsal.

## Course 11 — Solution Architecture and Technical Strategy

**Status:** Planned · **Prerequisites:** Courses 1–10
**Thesis:** turn requirements and constraints into options, evidence, decisions, migration paths,
and operating consequences that stakeholders can challenge.

### Depth and practice

- Capabilities, functional/non-functional requirements, quality-attribute scenarios, C4-style
  views, data/control/trust boundaries, ADRs, RFCs, and architecture reviews.
- Build/buy/partner, portability, lock-in, total cost, risk, ownership, reversibility, and kill
  criteria; current, transition, and target states.
- Communication with product, engineering, platform, security, legal, finance, and executives.

Capstone question: “Should Northstar build a centralized RAG and agent platform?” Evidence: options
paper, target architecture, cost/risk model, ADR set, migration roadmap, and executive review.

## Course 12 — Enterprise AI Operating Model and Leadership

**Status:** Planned · **Prerequisite:** Course 11
**Thesis:** Staff impact improves how the organization chooses, builds, governs, and learns from AI
work—not how much one person implements.

### Depth and practice

- Platform/team interaction, paved roads, federated governance, decision rights, intake, portfolio
  prioritization, risk-based controls, reusable capabilities, and exception paths.
- Design reviews, standards, mentoring, delegation, disagreement and escalation; outcome, platform
  health, developer experience, capability maturity and technical-debt measures.
- Executive narratives, roadmap funding, sunset criteria, and organizational change.

Final scenario: triage 70 GenAI proofs of concept and define how a small, evidence-backed portfolio
moves to production. Evidence: standards, service catalogue, decision rights, maturity assessment,
12-month roadmap, investment case, and oral architecture defense.

## Cross-course interview practice

Beginning after Course 3, complete one weekly prompt rotating through:

- **technical depth:** explain a failure from mechanics, not slogans;
- **system design:** meet explicit quality, latency, reliability, security, and cost targets;
- **strategy:** recommend among credible options and define reversal triggers;
- **leadership:** navigate disagreement while preserving evidence, ownership, and decision clarity.

## Program completion standard

Completion requires the portfolio to show that the learner can explain, implement, evaluate,
debug, secure, productionize, and lead the system. Passing quizzes without the practical evidence
does not satisfy the outcome.
