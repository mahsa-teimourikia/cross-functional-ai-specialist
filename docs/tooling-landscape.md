# Tooling and State-of-the-Art Review

**Reviewed:** 2026-09-27
**Purpose:** decision guidance for the full program, not a mandatory shopping list.

Tooling changes faster than architecture fundamentals. Verify maintenance, licensing, security,
compatibility, portability, observability, operating cost, and team ownership before adoption.

## Maturity labels

- **Established:** stable standards or broadly production-proven patterns.
- **Current production option:** maintained and suitable when its trade-offs fit.
- **Emerging:** promising for bounded adoption; validate gaps and migration cost.
- **Research/frontier:** useful for experiments; evidence and operating patterns remain incomplete.

## Python project and dependency management

| Option | Maturity | Strengths | Limits / selection rule |
|---|---|---|---|
| `pyproject.toml` + dependency groups | Established standard | Interoperable metadata and internal development groups | A manifest is not a lockfile |
| uv | Current production option | Fast resolver/runner, universal lock, workspaces, Python/tool management | `uv.lock` is tool-specific; plan exits |
| Poetry | Current production option | Integrated workflow and mature ecosystem | Poetry-specific configuration and lock semantics |
| PDM | Current production option | Standards-oriented project manager | Smaller organizational footprint |
| pip + constraints / pip-tools | Established compatibility path | Ubiquitous, simple for existing estates | More files and less integrated workflow |
| `pylock.toml` (PEP 751) | Emerging standard | Tool-neutral reproducible-install format | Ecosystem support is still maturing |

Course 1 uses uv for a coherent experience while teaching the standards underneath it. Sources:
[PyPA `pyproject.toml`](https://packaging.python.org/en/latest/specifications/pyproject-toml/),
[dependency groups](https://packaging.python.org/en/latest/specifications/dependency-groups/),
[`pylock.toml`](https://packaging.python.org/en/latest/specifications/pylock-toml/), and
[uv locking/syncing](https://docs.astral.sh/uv/concepts/projects/sync/).

## Build backends

| Need | Starting options | Decision concern |
|---|---|---|
| Conventional pure Python | uv_build, Hatchling, Flit Core | standards, file selection, hooks, familiarity |
| Existing/custom Python build | setuptools | broad compatibility versus legacy complexity |
| CMake/C/C++/Fortran | scikit-build-core | compiler matrix, ABI and wheel production |
| Meson/multi-language | meson-python | existing build system and expertise |
| Rust/PyO3 | Maturin | Rust toolchain and platform wheel coverage |

See the [build-backend deep dive](../curriculum/advanced/01-production-ai-development/references/build-backends.md)
and [PyPA build-system specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/#declaring-build-system-dependencies-the-build-system-table).

## Linting, formatting, and typing

Ruff is a strong consolidated formatter/linter choice. Mypy and Pyright are mature type-checking
choices with different inference, editor, and configuration trade-offs. Astral's `ty` is a notable
fast-moving option; evaluate compatibility before migration and avoid tool-specific typing features
when portability matters. A type checker proves consistency with declared types—not authorization,
grounding, freshness, or business correctness.

Sources: [Python typing](https://docs.python.org/3/library/typing.html),
[typing specification](https://typing.python.org/en/latest/spec/),
[mypy protocols](https://mypy.readthedocs.io/en/stable/protocols.html),
[Ruff](https://docs.astral.sh/ruff/), and [ty](https://docs.astral.sh/ty/).

## Validation and API boundaries

Pydantic v2 is a strong option for typed external boundaries and JSON Schema; dataclasses are often
cleaner for trusted domain state. Pydantic may coerce values by default, so make strictness explicit
for sensitive fields. FastAPI is a productive typed adapter, but routes should not own retrieval,
model, or policy workflows. Litestar, Django Ninja, Flask, and Django remain credible depending on
estate, feature set, and ownership.

Sources: [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/),
[strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/), and
[FastAPI concurrency](https://fastapi.tiangolo.com/async/).

## Concurrency and durable workflows

`asyncio.TaskGroup` and `asyncio.timeout()` provide structured concurrency for in-process I/O, but
cancellation must propagate. Use a durable workflow engine when work must survive process loss,
wait for long periods, reconcile uncertain outcomes, or coordinate external effects. Step Functions,
Temporal, queues, and application state machines solve different problems. LangGraph is useful when
an explicit agent state graph adds value; it is not a required wrapper for every model call.

Sources: [Python task groups](https://docs.python.org/3/library/asyncio-task.html),
[AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html), and
[Temporal](https://docs.temporal.io/).

## Cloud compute, messaging, and state

Choose the interaction pattern before the service. Synchronous APIs fit bounded work inside a user
deadline; SQS-style queues fit independently processed bursty work; EventBridge/SNS fit routed or
fan-out notifications; Kinesis-style logs fit partitioned replay; Step Functions/Temporal fit
durable multi-step state. At-least-once delivery requires application idempotency, conditional
writes, bounded retry, and owned dead-letter recovery.

On AWS, Lambda is a strong event-driven option, ECS/Fargate adds container/runtime control without
node ownership, EKS earns its overhead when Kubernetes capability is an organizational requirement,
and EC2/AWS Batch fit specialized or batch compute. Bedrock and SageMaker AI overlap at some AI
workload boundaries but differ in model access, customization, hosting control, and operating
model. Select state from access patterns and consistency needs: S3 for objects/manifests, DynamoDB
for key-value/conditional state, Aurora/RDS for relational transactions, OpenSearch for search
projections, and Redis for bounded ephemeral state. A cache or search index should not silently
become the source of truth.

Sources: [AWS compute decision guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/choosing-aws-compute-service.html),
[AWS messaging decision guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/sns-or-sqs-or-eventbridge.html),
[AWS application integration guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/application-integration-on-aws-how-to-choose.html),
and [Course 2's distributed-systems chapter](../curriculum/advanced/02-cloud-distributed-ai-systems/README.md).

## Identity, delegation, and policy engines

OAuth 2.0 and OpenID Connect establish interoperable authorization and authentication protocols;
they do not make every parsed JWT trustworthy. Resource servers must pin trusted issuers, verify
signatures and allowed algorithms, require the intended token use and audience, validate time, and
apply application authorization. Use issuer plus subject as the federated identity key. OAuth's
current security best practice discourages implicit and resource-owner-password flows, requires
exact redirect matching, and recommends sender-constrained tokens where bearer replay risk warrants
the added lifecycle cost. Token exchange can represent delegation, but issuance policy still has to
prevent scope, resource, audience, tenant, or actor widening.

| Option | Maturity | Strong fit | Selection concern |
|---|---|---|---|
| Embedded application policy | Established pattern | One bounded service and close transactional data | Duplication, review, and rollout as the estate grows |
| Cedar / Amazon Verified Permissions | Current production option | Typed principal-action-resource authorization | Entity ownership, schema evolution, latency, and outage mode |
| OPA/Rego | Current production option | General policy over structured data across stacks | Flexible policy/data require disciplined governance |
| OpenFGA | Current production option | Relationship-based and nested sharing decisions | Tuple lifecycle, consistency, and model complexity |
| Cloud IAM / Entra workload identity | Established platform capability | Workload-to-platform and service access | Does not replace application-object authorization |
| SPIFFE/SPIRE | Current production option | Federated workload identity across heterogeneous runtime estates | Trust-domain and control-plane operations |
| AuthZEN Authorization API | Emerging interoperability standard | PDP/PEP protocol portability | Profile coverage and vendor maturity |
| Agent-specific identity profiles | Emerging / pre-standard | Research and bounded pilots | Do not treat drafts as settled security architecture |

Choose the authorization model from the domain: RBAC for stable job functions, ABAC for contextual
attributes, relationship-based authorization for sharing graphs, and attenuated capabilities for
narrow delegation. Most real systems combine them. Keep policy administration, information,
decision, and enforcement responsibilities explicit; default deny; enforce at the component that
controls the real effect; version policy and entitlements; and define cache freshness, emergency
deny, fail-closed/degraded behavior, review, rollback, and audit ownership.

For AI tools, authenticate both the human subject and executing workload actor, then intersect their
authority. Keep credentials outside model context. Treat tool arguments, prompt roles, agent names,
and retrieved text as untrusted requests—not identity. Consequential approvals should bind the
canonical principal, actor, action, resource, parameters or digest, policy version, expiry, and
logical operation; separation of duties and atomic single-use consumption prevent self-approval,
alteration, replay, and duplicate effects.

Primary sources: [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0-errata2.html),
[OAuth 2.0 Security Best Current Practice](https://www.rfc-editor.org/rfc/rfc9700.html),
[JWT access-token profile](https://www.rfc-editor.org/rfc/rfc9068.html),
[JWT best current practice](https://www.rfc-editor.org/rfc/rfc8725.html),
[DPoP](https://www.rfc-editor.org/rfc/rfc9449.html),
[OAuth token exchange](https://www.rfc-editor.org/rfc/rfc8693.html),
[NIST ABAC](https://csrc.nist.gov/pubs/sp/800/162/upd2/final),
[NIST zero trust](https://csrc.nist.gov/pubs/sp/800/207/final),
[Cedar authorization](https://docs.cedarpolicy.com/auth/authorization.html),
[OPA](https://www.openpolicyagent.org/docs), [OpenFGA](https://openfga.dev/docs/concepts),
[SPIFFE](https://spiffe.io/docs/latest/spiffe-specs/), and
[AuthZEN Authorization API](https://openid.net/specs/authorization-api-1_0.html).

## Testing and evaluation

Use pytest for deterministic invariants and Hypothesis where generated cases explore meaningful
boundaries. Separate integration tests from live-model evaluation. AI release evidence should mix
deterministic checks, labelled sets, calibrated judges, blinded human review, production outcomes,
and slices. Evaluation frameworks accelerate execution; metric contracts and release thresholds
remain application responsibilities.

Sources: [pytest practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html),
[Hypothesis](https://hypothesis.readthedocs.io/en/latest/),
[OpenAI Evals](https://github.com/openai/evals), and
[Ragas metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/).

## Model access and gateways

Direct SDKs minimize moving parts. A gateway earns its cost when multiple applications need shared
identity, quotas, policy, routing, telemetry, fallback, or spend controls. Bedrock Converse provides
a common message interface across supported Bedrock models; LiteLLM provides a normalized proxy;
OpenAI-compatible interfaces aid portability but cannot erase capability, safety, streaming, and
schema differences. Evaluate every route with observed workload, failure, privacy, latency, and
cost evidence.

### Gateway responsibilities

A production gateway separates a versioned control plane from the request data plane. The control
plane admits tenants, principals, credentials, providers, deployments, regions, capabilities,
prompts, schemas, routes, quotas, budgets, cache policy, and price metadata. The data plane derives
scope from authenticated state, reserves capacity, chooses only eligible models, translates the
request, enforces deadlines, normalizes usage/errors, validates output, settles actual cost, and
records the application-owned result.

Do not accept provider, tenant, region, budget, or safety-policy overrides from prompt content.
Structured output proves shape within the supported schema subset; application code still proves
resource binding, authorization, freshness, safety, and task quality.

### Routing patterns

| Pattern | Strong fit | Main cost/risk |
|---|---|---|
| direct provider adapter | one bounded workload/provider | duplication if shared controls later emerge |
| static/rule route | task, region, capability, or risk is explicit | rule sprawl and unmeasured assumptions |
| load balance | equivalent deployment replicas | does not select for task quality |
| learned/semantic route | heterogeneous models and sufficient labels | router calibration, drift, added latency and cost |
| small-to-large cascade | cheap path can be accepted by a calibrated gate | probe cost and serial latency on escalations |
| reliability fallback | retryable capacity/dependency failure | correlated failure and semantic change |
| delayed hedge | strict tail-latency objective with spare capacity | duplicate calls, quota and cost amplification |

Authentication, authorization, invalid request, residency, data policy, and safety refusal should
not become generic provider-shopping loops. Assign retry ownership across clients, gateway, SDK,
and provider. Count every started retry, fallback, cascade probe, and losing hedge in usage and
cost.

### Economics and caching

Track uncached input, cached input/cache write, output, reasoning or other provider usage, fixed
charges, network, gateway operation, and failed/late calls using effective-dated price metadata.
The primary unit metric is often total cost divided by successful compliant tasks—not requests or
HTTP 200 responses. Report quality, p95/p99 latency, availability, provider work, and cost by task,
tenant, model, route, and risk slice.

Provider prompt/KV caches reuse prefix computation but still generate output. Application response
caches reuse validated results and require tenant/subject scope, prompt/schema/policy/router/model
generations, source freshness, region, classification, TTL, invalidation, deletion, and cache-hit
privacy. A high hit rate on stale or cross-tenant output is not an optimization.

Concurrent spend and token enforcement requires atomic worst-case reservation before a call and
settlement to actual authoritative usage. A check against completed spend alone can allow many
in-flight requests to overshoot. Decide how distributed counter/database state behaves when stale
or unavailable and whether hard limits fail closed.

### Current implementation options

| Option | Current fit | Selection concerns |
|---|---|---|
| direct OpenAI/Anthropic/Google provider API | fastest native feature access, bounded integration | native lifecycle, retention, errors, schemas, caching, migration |
| Amazon Bedrock APIs | AWS-governed access to supported models and API shapes | model/feature/region support, IAM, quota, cross-Region/data boundaries |
| Bedrock intelligent prompt routing | managed selection among documented compatible model sets | workload quality evidence, routing criteria, version and region constraints |
| Microsoft Foundry model router | managed per-request selection with routing modes/model subsets | record underlying model; evaluate workload and version changes |
| LiteLLM gateway/router | OpenAI-shaped multi-provider proxy, keys, limits, budgets, routing | Redis/database semantics, admin plane, release parity, retry ownership |
| cloud API management / commercial AI gateway | organizational identity, networking, policy and analytics | data path, key custody, latency, pricing, export, bypass prevention |
| Kubernetes Gateway API Inference Extension | self-hosted inference pools and endpoint selection | model-server signals, EPP operation, API maturity, cluster ownership |
| Envoy AI Gateway | Envoy/Gateway API translation and provider/backend routing | feature maturity, policy integration, data-plane operations |

LiteLLM's current documentation distinguishes retries within a model group from fallbacks to
another group and documents distributed budget/rate-limit dependencies. Treat those implementation
details as architecture, not configuration trivia. Managed routers from Bedrock or Foundry reduce
selection implementation but do not own application eligibility, semantic validation, metric
denominators, release thresholds, or business outcomes.

### State of the art

Established practice is a provider adapter, immutable prompt/model/policy versions, typed error
classification, hard deadlines and limits, strongest/cheapest baselines, and workload evaluation.
Current production direction adds centralized gateways, managed routing, task-aware cascades,
prompt-cache diagnostics, regional capacity routing, and open inference-gateway integrations.

[FrugalGPT](https://arxiv.org/abs/2305.05176) demonstrated learned cascades;
[RouteLLM](https://arxiv.org/abs/2406.18665) learned strong-versus-weak selection from preference
data; and [BEST-Route](https://proceedings.mlr.press/v267/ding25d.html) explores adaptive test-time
routing. These are research results in particular model pools and datasets, not promised savings.
Emerging work considers joint quality/output-length/latency/cost prediction, online bandits,
trajectory-aware agent routing, and uncertainty-aware escalation. Open problems include selective
feedback, router-induced label bias, distribution and model-pool drift, correlated provider
failure, semantic non-portability, and caching versus privacy/freshness.

Primary and official sources:
[OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching),
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data),
[Bedrock inference APIs](https://docs.aws.amazon.com/bedrock/latest/userguide/apis.html),
[Bedrock intelligent prompt routing](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-routing.html),
[Bedrock prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html),
[LiteLLM router](https://docs.litellm.ai/docs/routing),
[LiteLLM request lifecycle](https://docs.litellm.ai/docs/proxy/architecture),
[LiteLLM budgets and rate limits](https://docs.litellm.ai/docs/proxy/users),
[Microsoft Foundry model router](https://learn.microsoft.com/azure/foundry/openai/concepts/model-router),
[Kubernetes Gateway API Inference Extension](https://gateway-api-inference-extension.sigs.k8s.io/),
[Envoy AI Gateway](https://aigateway.envoyproxy.io/), and
[The Tail at Scale](https://research.google/pubs/the-tail-at-scale/).

## Retrieval and knowledge systems

A production RAG system is a governed knowledge lifecycle, not an embedding API plus a prompt.
Preserve immutable originals and manifests; carry tenant, ACL/classification, source/version/locator,
digest, lifecycle, parser/chunker/embedding versions, and lineage into every chunk; authorize
current evidence before every candidate/reranking stage; and revalidate cited evidence after
generation. Treat embeddings as sensitive derived data and retrieved content as untrusted data.

Hybrid lexical+dense retrieval with rank fusion and optional reranking is an established baseline
when exact identifiers and semantic paraphrases both matter. Keep BM25 as a measured baseline:
[BEIR](https://arxiv.org/abs/2104.08663) found it robust in zero-shot evaluation, while reranking
and late interaction improved average quality at greater computation. Compare approximate vector
search with exact search under representative tenant/ACL filters; metadata filtering can consume
ANN candidate budgets and reduce recall.

| Option | Maturity | Strong fit | Primary selection concern |
|---|---|---|---|
| PostgreSQL full text + pgvector | Current production option | relational truth and bounded/medium vector workloads | filtered ANN recall, index operations, scale headroom |
| OpenSearch / Elasticsearch | Established search platforms | lexical, filters, hybrid pipelines, search operations | cluster skill, consistency, resource cost |
| Qdrant / Milvus / Weaviate / Pinecone | Current vector-first options | specialized vector scale and managed features | tenant model, lexical depth, metadata filtering, exit cost |
| Azure AI Search and managed cloud search | Current production option | integrated cloud ingestion, identity, semantic features | preview boundaries, region, coupling, reindex semantics |
| Vespa | Established specialist option | large-scale programmable retrieval and ranking | operating and ranking expertise |
| model-provider file search | Bounded managed option | fastest integration for a contained product | lifecycle control, observability, portability, policy fit |

For parsing, Apache Tika is a broad content/metadata extraction layer; Docling and Unstructured add
layout/element-aware document processing. Select with downstream field/table accuracy, reading
order, locator preservation, failure visibility, latency, cost, and deployment constraints—not a
single attractive PDF example.

Conditional upgrades require a labelled query slice and an operating-cost case: query expansion and
HyDE for vocabulary mismatch; ColBERT-style late interaction for token-level matching; parent-child
or RAPTOR for long cross-section questions; GraphRAG for measured global/relational questions; and
ColPali-style multimodal retrieval for layout/table/image evidence. Each adds derived data,
lineage, deletion, evaluation, latency, and cost obligations.

Measure retrieval with Recall@k, MRR, nDCG, exact-versus-ANN recall, and access/freshness outcomes;
measure generation separately with answer correctness, claim support, citation completeness and
correctness, refusal quality, user outcomes, latency, and cost per successful compliant answer.
Ragas and RAGChecker accelerate diagnostics, but automated judges must be calibrated against human
labels and drift slices.

Primary and official sources: [RAG](https://arxiv.org/abs/2005.11401),
[Dense Passage Retrieval](https://arxiv.org/abs/2004.04906),
[BEIR](https://arxiv.org/abs/2104.08663), [ColBERTv2](https://arxiv.org/abs/2112.01488),
[HyDE](https://arxiv.org/abs/2212.10496), [RAPTOR](https://arxiv.org/abs/2401.18059),
[GraphRAG](https://arxiv.org/abs/2404.16130), [ColPali](https://arxiv.org/abs/2407.01449),
[pgvector](https://github.com/pgvector/pgvector),
[OpenSearch hybrid search](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index/),
[Azure document access](https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview),
and [OWASP RAG security](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html).

## Agents and tools

Begin with a deterministic workflow. Add routing, planning, or multiple agents only when measured
task variability justifies coordination and capability cost. MCP standardizes how applications
expose/consume context and tools, but descriptions, resources, arguments, results, elicitation, and
task state remain untrusted. Schema validity is not business authorization. Authenticate the user
and workload, derive tenant/resource scope from trusted state, keep credentials at the gateway,
authorize every call, reserve budget before execution, validate results, and reconcile unknown
effects with one stable logical operation ID.

### Control-flow options

| Option | Maturity | Strong fit | Primary selection concern |
|---|---|---|---|
| plain Python/state machine | Established pattern | small bounded workflow with owned runtime | durability and platform work |
| LangGraph | Current production option | explicit state graphs, checkpoints, interrupts | store/concurrency/replay semantics |
| OpenAI Agents SDK | Current production option | lightweight tools, handoffs, guardrails, tracing | hosted boundaries and provider fit |
| Strands Agents | Current production option | AWS-oriented agents, graphs, workflows, swarms | runtime and AWS-default decisions |
| Google ADK | Current production option | deterministic and dynamic multi-agent workflows | ecosystem/deployment maturity |
| Microsoft Agent Framework | Current evolving option | functional/graph workflows and orchestrations | migration and version maturity |
| CrewAI | Current production option | crews plus explicit flow orchestration | prove durability and coordination value |
| custom event-driven runtime | Specialist option | distributed actor/message architecture | highest engineering and operating cost |

Use a durable workflow engine such as AWS Step Functions, Temporal, Durable Task, Dapr, or Restate
when runs must survive process loss, wait for approval, own timers, or coordinate external effects.
Agent frameworks and workflow engines can be composed: put model decisions inside bounded durable
nodes/activities. Do not execute provider calls inside replayed deterministic workflow logic.

### MCP

The final MCP 2026-07-28 release uses a stateless protocol core and an extensions framework,
including Tasks for long-running operations. Stateless HTTP transport simplifies load balancing;
it does not make the underlying business task stateless, authorized, or exactly once. Validate OAuth
issuer/audience/client/scope, isolate server credentials, authorize every task poll/cancel/result,
scope cache entries, constrain egress, and propagate only safe trace context.

Protocol adoption is moving quickly. Pin a supported revision, test negotiation and downgrade,
review SDK release notes, and treat new extensions according to maturity. Internal registries need
admission, ownership, versioning, trust metadata, review, revocation, and incident response.

### Amazon Bedrock AgentCore

As reviewed in September 2026, AgentCore documents independently usable managed capabilities:
Harness, Runtime, Memory, Gateway, Identity, Browser, Code Interpreter, Observability, Payments,
Evaluations, Optimization, Policy, and Registry. Runtime supports custom frameworks and models;
Gateway can front APIs, Lambda functions, MCP servers, and runtime targets; Policy can enforce
deterministic rules around gateway calls; and telemetry integrates with OpenTelemetry-compatible
signals.

Do not confuse AgentCore with Agents for Amazon Bedrock. Bedrock Agents is a managed orchestration
service configured around a foundation model, instructions, action groups, knowledge bases,
guardrails, and optional agent collaborators. AgentCore is modular infrastructure for custom or
framework-built agents. Use Bedrock Agents when its managed loop fits; use AgentCore or a custom
runtime when the application must own loop, graph, checkpoint, replay, or framework behavior. They
can be combined, but neither product removes the need to prove application authorization,
idempotency, approval freshness, budgets, cancellation, and recovery.

| AgentCore capability | Use it for | Still prove in the application |
|---|---|---|
| Harness / Runtime | managed loop or deployment/isolation | budgets, state, termination, framework semantics |
| Gateway / Policy | governed tool surface and deterministic policy | every route covered; direct runtime bypass denied |
| Identity | inbound/outbound authentication and credentials | user/workload/tenant binding and delegation |
| Memory | short/long-term memory infrastructure | provenance, authorization, correction, retention, deletion |
| Browser / Code Interpreter | managed isolated tools | filesystem/network/data policy and output validation |
| Observability | traces, logs, metrics, operational inspection | redaction, sampling, retention, correlation, SLO ownership |
| Evaluations / Optimization | trace/session scoring and experiments | labels, judge calibration, thresholds, rollback decisions |
| Registry | tool, MCP, skill, and agent discovery/governance | admission authority, ownership, signatures, revocation |

AgentCore Runtime security guidance distinguishes IAM SigV4 service authentication from JWT
end-user authentication. The raw user-ID path does not itself verify an IdP identity; production
systems should derive it from authenticated context. Separate user-delegated and autonomous
credentials, scope runtime roles and network egress, run containers without root, and use current
metadata-service protections. If Gateway/Policy is the enforcement point, use resource/workload and
network restrictions so callers cannot invoke the Runtime directly and bypass it.

Compare AgentCore with custom orchestration on region/feature availability, quotas, network and
data boundaries, checkpoint semantics, tool policy coverage, observability export, framework/model
portability, operating ownership, cost, incident recovery, and exit plan. Managed runtime does not
prove business authorization, effect idempotency, usefulness, or compliance.

### Evaluation and coordination tax

Evaluate labelled task and adversarial cases with required/forbidden tools, argument/resource
bindings, evidence, terminal states, approval, and budgets. Measure task success, compliant success,
forbidden outcomes, valid work blocked, trajectory/tool accuracy, retry amplification, restart and
cancellation recovery, latency, and cost per successful compliant task. Calibrate model judges to
human labels; use code evaluators for deterministic invariants.

Multi-agent designs must beat workflow and single-agent baselines after counting extra calls,
handoffs, duplicated context/tool work, merge/review work, capability exposure, and operations.
Parallelism may reduce wall-clock latency while increasing total work; report both.

Primary and official sources: [ReAct](https://arxiv.org/abs/2210.03629),
[AgentBench](https://arxiv.org/abs/2308.03688), [SWE-bench](https://arxiv.org/abs/2310.06770),
[MCP 2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28/),
[MCP Tasks](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks),
[LangGraph durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution),
[OpenAI Agents orchestration](https://openai.github.io/openai-agents-python/multi_agent/),
[Google ADK workflows](https://google.github.io/adk-docs/workflows/),
[Microsoft Agent Framework workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/),
[Strands patterns](https://strandsagents.com/docs/user-guide/sdk/multi-agent/multi-agent-patterns/),
[Agents for Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-build-modify.html),
[AgentCore overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html),
[AgentCore Runtime security](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html),
and [AgentCore release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html).

## Observability

OpenTelemetry is the vendor-neutral base for traces, metrics, logs, context propagation, and OTLP.
As reviewed on 27 September 2026, Python traces and metrics are stable while logs remain in
development. GenAI semantic conventions moved from the core repository to the dedicated
`semantic-conventions-genai` repository; its generative-client spans remain development-stage and
the new repository still marks the schema URL as TODO. Pin versions, keep a stable internal
contract, test the mapping, and migrate dashboards and alerts deliberately.

Record stable logical request/run/attempt/provider request IDs; route, prompt, policy, evaluator,
schema, model, deployment, and telemetry-contract versions; bounded reason/error classes; budgets,
usage, duration, cost, fallback/retry/degradation, application validation, and terminal state. Do
not record secrets or private reasoning. Default prompt/input/output capture off: the current GenAI
span guidance also defaults to no instruction, input, or output recording.

### Signal and sampling contract

Use traces for causal reconstruction, metrics for population objectives, events for named state
changes, and logs for correlated diagnostics. Create authoritative counters and histograms before
trace sampling. Tail sampling can retain errors, slow traces, fallback, and degradation, but it
buffers state and must receive all spans for a trace at one decision point. OpenTelemetry's scaled
gateway guidance uses trace-ID routing and warns about topology changes and decision consistency.

Keep metric dimensions bounded: request, trace, user, case, prompt text, output, and raw error
strings do not belong in labels. Treat pseudonymization, tenant query isolation, region, redaction,
retention, deletion, Collector queues/export loss, and backend access as architecture—not dashboard
configuration.

### Reliability objective and control plane

Define eligible user events and successful compliant outcomes before choosing a target. Keep policy
blocks, degraded outcomes, and transport success distinct. Track compliant-success ratio, latency
threshold ratio and tails, fallback and attempts per logical request, saturation, cost per
successful compliant task, and version/model mix. Use multiwindow burn alerts for actionable error-
budget risk, with explicit low-traffic handling, ownership, and runbooks.

Retries need one owner and a deadline. Circuit breakers count relevant dependency failures, not
authorization, safety, or malformed-input denials. Bulkheads isolate workload capacity. Degradation
must have a typed user-visible contract and cannot silently count as full success. A game day needs
a hypothesis, fault scope, abort conditions, expected detector/containment, cleanup, owners, and
retest. Application evidence and accountable owners—not model text—establish recovery and closure.

### Current implementation options

| Option | Current fit | Selection concerns |
|---|---|---|
| OpenTelemetry SDK + Collector | portable instrumentation, processing, multi-backend OTLP | per-language maturity, component pins, redaction, trace affinity, loss, Collector operations |
| Prometheus/Grafana + tracing/log backend | mature SLI, alert, dashboard, and infrastructure operations | exemplars, cardinality, storage, multi-tenancy, AI-specific semantics |
| cloud-native APM | existing cloud identity, service operations, and managed storage | AI coverage, export, cross-account/region access, data defaults, price |
| Amazon Bedrock AgentCore Observability | AgentCore workloads and CloudWatch-native agent views | custom outcome spans, non-AgentCore correlation, content policy, export, SLO ownership |
| Langfuse | AI tracing, prompt/evaluation workflows, hosted or self-hosted | current OTLP path, region, RBAC, lifecycle, SDK/server compatibility, operations |
| MLflow Tracing | MLflow-centered AI trace and evaluation workflows | convention translation, backend operations, tenant access, sampling, retention |
| Phoenix/OpenInference | open-source AI tracing, evaluation, framework instrumentation | OpenInference/OTel mapping, authentication, scale, lifecycle, owner |
| LangSmith | LangChain/LangGraph-heavy tracing and evaluation | platform coupling, non-LangChain paths, region/retention, export, cost |
| commercial APM/AI observability | enterprise on-call and existing service telemetry | GenAI schema/content defaults, evaluation depth, portability, cardinality cost |

Run a production-shaped pilot. Score correlation completeness, telemetry loss and overhead,
redaction timing, tenant isolation, SLO arithmetic, query performance, incident workflow,
convention/version support, export/exit, operating burden, and total cost. A trace viewer does not
own application outcome validation, reliability objectives, resilience, or incident closure.

Primary and official sources: [W3C Trace Context](https://www.w3.org/TR/trace-context/),
[OpenTelemetry Python status](https://opentelemetry.io/docs/languages/python/),
[OpenTelemetry specification](https://opentelemetry.io/docs/specs/otel/overview/),
[Collector agent-to-gateway deployment](https://opentelemetry.io/docs/collector/deploy/other/agent-to-gateway/),
[GenAI conventions repository](https://github.com/open-telemetry/semantic-conventions-genai),
[GenAI span conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md),
[Google SRE alerting on SLOs](https://sre.google/workbook/alerting-on-slos/),
[AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html),
[MLflow Tracing](https://mlflow.org/docs/latest/genai/tracing/),
[Langfuse tracing](https://langfuse.com/docs/observability/get-started),
[Phoenix tracing](https://docs.arize.com/phoenix/tracing/), and
[LangSmith observability](https://docs.langchain.com/langsmith/observability).

## Security and governance

Use several lenses: OWASP for application risks, MITRE ATLAS for adversary tactics, NIST AI RMF for
risk outcomes, and ISO/IEC 42001 for organizational management-system requirements. None replaces
domain threat modelling, identity controls, secure SDLC, privacy review, or measured control
effectiveness. Guardrails are defense in depth; prompts are not security boundaries.

Sources: [OWASP LLM Top 10](https://genai.owasp.org/llm-top-10/),
[MITRE ATLAS](https://atlas.mitre.org/), [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework),
and [ISO/IEC 42001](https://www.iso.org/standard/81230.html).

## Selection scorecard

For every material decision, record the requirement/non-goal; maturity; functional fit; identity,
authorization, and data handling; failure/retry/restart/rollback behavior; evaluation and telemetry;
portability and exit cost; team ownership/on-call burden; total cost per successful compliant task;
and pilot evidence, review date, and reversal trigger.

The state of the art is not the newest tool. It is the best evidenced architecture for the actual
quality, latency, reliability, security, governance, cost, and organizational constraints.
