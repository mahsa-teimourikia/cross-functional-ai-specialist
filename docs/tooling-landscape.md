# Tooling and State-of-the-Art Review

**Reviewed:** 2026-09-21
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
schema differences. Evaluate fallbacks with observed failure and quality data.

Sources: [Bedrock Converse](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html),
[LiteLLM proxy](https://docs.litellm.ai/docs/simple_proxy), and
[OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses).

## Retrieval and knowledge systems

Hybrid sparse+dense retrieval plus reranking is an established strong baseline when exact terms and
semantic similarity both matter. Query transformation, HyDE, graph retrieval, late interaction,
and multimodal retrieval are conditional upgrades. Authorize before ranking, preserve provenance
and version, and evaluate freshness/deletion as well as Recall@k.

Primary references: [BM25](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf),
[Dense Passage Retrieval](https://arxiv.org/abs/2004.04906),
[ColBERT](https://arxiv.org/abs/2004.12832),
[HyDE](https://arxiv.org/abs/2212.10496), and [BEIR](https://arxiv.org/abs/2104.08663).

## Agents and tools

Begin with a deterministic workflow. Add routing, planning, or multiple agents only when measured
task variability justifies coordination and capability cost. MCP standardizes how applications
expose/consume context and tools, but descriptions and results remain untrusted. Compare managed
and custom orchestration on restart, identity, tool authorization, observability, versioning,
lock-in, evaluation, and operating effort—not demo speed.

Sources: [MCP specification](https://modelcontextprotocol.io/specification/),
[Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html),
and [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/).

## Observability

OpenTelemetry is the vendor-neutral base for traces, metrics, and logs. Check current component
maturity; Python traces and metrics are stable while logs have historically evolved. Emerging GenAI
semantic conventions improve portability but do not decide what should be recorded. Capture IDs,
versions, validated arguments/digests, policy decisions, evidence, budgets, latency, cost, errors,
and terminal state. Avoid secrets, unnecessary content, and private reasoning.

Sources: [OpenTelemetry Python status](https://opentelemetry.io/docs/languages/python/),
[instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/), and
[GenAI conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).

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
