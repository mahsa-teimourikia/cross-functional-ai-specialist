# Course 1 — Production AI Development in Python

**Track:** Cross-Functional AI Specialist / Staff AI Scientist  
**Focus:** Move from Data Science Python and notebooks to production-quality AI services that you can design, review, and help developers implement.  
**Primary scenario:** Enterprise Underwriting Guideline Assistant  
**Recommended pace:** 3–4 weeks, ~6–8 hours/week  
**Last reviewed:** August 2026

---

## 1. Why this course matters

A Staff AI Scientist does not need to become the strongest backend engineer on the team, but should be able to:

- recognize whether an AI codebase is structured for production or only for experimentation;
- define clean boundaries between retrieval, orchestration, model access, APIs, configuration, and infrastructure;
- review implementation plans and PRs at an architectural level;
- reason about synchronous vs asynchronous execution;
- guide developers on testing strategies and failure handling;
- identify coupling that will make future RAG, agent, observability, identity, or model-gateway changes expensive;
- understand how Python application design maps to containers and cloud deployment;
- troubleshoot enough of the application layer to unblock AI developers;
- make implementation decisions based on maintainability, reliability, cost, and team ownership—not only whether a prototype works.

This course deliberately stops before deep AWS architecture, Terraform, AgentCore, enterprise identity, OpenTelemetry, CI/CD, and AI security. It creates the **application architecture foundation** those later courses will extend.

---

# 2. Learning outcomes

By the end of this course, you should be able to independently explain and review an application structured approximately like this:

```text
                   Client
                     |
                  FastAPI
                     |
              Request Validation
                     |
               Application Service
              /        |          \
             /         |           \
       Retriever    LLM Client    Policy
        Protocol     Protocol     / Rules
          |             |
      Adapter(s)    Bedrock Adapter
          |
   Search / Vector Store

Cross-cutting:
Configuration | Logging | Errors | Tests | Type Checking
```

You should be able to answer:

1. Why shouldn't FastAPI route handlers contain the complete RAG workflow?
2. Why define interfaces around the retriever and model client?
3. When should Python code use `async`?
4. What is dependency injection solving?
5. What belongs in Pydantic models vs domain objects?
6. What should be unit tested vs integration tested?
7. How do we make Bedrock replaceable without rewriting business logic?
8. How should configuration and secrets enter the application?
9. What failures should be retried, surfaced, translated, or fail closed?
10. How does this code become a containerized service later?

---

# 3. Current Python production stack to know

This is not a claim that every project must use every tool. These are useful current technologies and standards to understand well enough to make an informed choice.

| Concern | Technologies / standards | Target depth |
|---|---|---|
| Python runtime | Python 3.12–3.14 concepts | Strong |
| Project metadata | `pyproject.toml` | Strong |
| Project/dependency management | `uv` | Working implementation depth |
| Formatting/linting | Ruff | Working implementation depth |
| Static typing | Python typing + Protocols; mypy or equivalent | Strong |
| Data validation | Pydantic v2 | Strong |
| API layer | FastAPI | Strong |
| HTTP client | HTTPX | Working knowledge |
| Concurrency | `asyncio`, `TaskGroup`, timeouts | Strong conceptual depth |
| Testing | pytest, fixtures, monkeypatch/mock | Strong |
| AWS model access | Bedrock Runtime APIs / Boto3 | Working implementation depth |
| Containers | Docker | Working knowledge in this course; deeper later |
| Application logging | standard Python logging / structured records | Strong fundamentals |

---

# 4. Reading path

## Week 1 — Modern Python project structure and typing

### 4.1 `pyproject.toml` and modern packaging

**Read first**

- [Python Packaging User Guide](https://packaging.python.org/en/latest/)
- [Packaging Python Projects](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [uv: Working on projects](https://docs.astral.sh/uv/guides/projects/)
- [uv: Project structure and files](https://docs.astral.sh/uv/concepts/projects/layout/)

### Understand

- why application dependencies belong in version-controlled project metadata;
- project vs environment;
- dependency locking and reproducibility;
- `src/` layouts;
- runtime dependencies vs development dependencies;
- why "it works in my notebook environment" is not a deployment strategy.

### Hands-on target

Be comfortable with:

```bash
uv init
uv add fastapi pydantic httpx boto3
uv add --dev pytest ruff mypy
uv lock
uv sync
uv run pytest
```

---

## 4.2 Ruff

**Read**

- [Ruff documentation](https://docs.astral.sh/ruff/)
- [Ruff linter](https://docs.astral.sh/ruff/linter/)
- [Ruff formatter](https://docs.astral.sh/ruff/formatter/)

### Understand

Linting and formatting solve different problems.

You should be able to explain why teams automate both rather than relying on developers to manually enforce style.

---

## 4.3 Python typing and contracts

**Read**

- [Python `typing` documentation](https://docs.python.org/3/library/typing.html)
- [mypy documentation](https://mypy.readthedocs.io/en/stable/)
- [Protocols and structural subtyping](https://mypy.readthedocs.io/en/stable/protocols.html)

### Prioritize

- `str | None`
- collection types
- `TypedDict`
- `Literal`
- `Protocol`
- generics at a conceptual level
- return types
- narrowing
- avoiding unnecessary `Any`

### Architectural concept: ports and adapters

Instead of tightly coupling business logic to Bedrock or a vector DB:

```python
class Retriever(Protocol):
    async def retrieve(self, query: str, k: int) -> list[Document]:
        ...
```

Application logic depends on the **contract**, while infrastructure implements the contract.

Later you can swap:

```text
InMemoryRetriever
        |
        +---- OpenSearchRetriever
        |
        +---- BedrockKnowledgeBaseRetriever
        |
        +---- AnotherRetriever
```

without rewriting the core service.

This is a critical architecture habit for RAG and agent systems.

---

# 5. Week 2 — Validation, APIs, dependency injection and async

## 5.1 Pydantic v2

**Read**

- [Pydantic documentation](https://docs.pydantic.dev/latest/)
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### Understand

Use Pydantic primarily at **system boundaries**:

```text
Untrusted input
      |
   Validation
      |
Typed application data
```

Examples:

- HTTP request
- environment configuration
- tool arguments
- external API payloads

Do not automatically turn every internal domain class into a Pydantic model.

---

## 5.2 FastAPI

**Read**

- [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/)
- [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)

### Understand

FastAPI routes should generally coordinate the HTTP boundary, not own the business workflow.

Avoid:

```text
POST /ask
   |
   +-- embed query
   +-- query OpenSearch
   +-- construct prompt
   +-- invoke Bedrock
   +-- parse citations
   +-- apply policy
   +-- log everything
```

Prefer:

```text
POST /ask
   |
   v
Application Service
   |
   +-- Retriever
   +-- Generator
   +-- Policy
```

The route translates HTTP <-> application contracts.

---

## 5.3 Dependency injection

FastAPI supports dependency injection, but understand the concept independently of FastAPI.

Dependency injection lets a component receive dependencies instead of constructing them internally.

Avoid:

```python
class RAGService:
    def __init__(self):
        self.bedrock = boto3.client("bedrock-runtime")
        self.search = SomeVectorDatabase(...)
```

Prefer:

```python
class RAGService:
    def __init__(self, retriever: Retriever, generator: Generator):
        self.retriever = retriever
        self.generator = generator
```

Why?

- testability;
- replaceable infrastructure;
- clearer ownership;
- easier local development;
- easier migration;
- fewer hidden dependencies.

---

## 5.4 Async I/O and structured concurrency

**Read**

- [Python `asyncio`](https://docs.python.org/3/library/asyncio.html)
- [Coroutines, Tasks and TaskGroup](https://docs.python.org/3/library/asyncio-task.html)

### Know the decision rule

`async` is primarily useful when the application spends time **waiting on I/O**:

- model APIs;
- databases;
- vector stores;
- HTTP services;
- object storage.

It does not automatically speed up CPU-heavy Python work.

### Understand

- coroutine;
- task;
- event loop;
- `await`;
- timeout;
- cancellation;
- `TaskGroup`;
- bounded concurrency.

For new structured concurrent code, understand why `TaskGroup` can provide stronger failure semantics than ad-hoc background tasks.

---

# 6. Week 3 — Testing, reliability and model adapters

## 6.1 pytest

**Read**

- [pytest documentation](https://docs.pytest.org/en/stable/)
- [pytest how-to guides](https://docs.pytest.org/en/stable/how-to/index.html)

### Master

- test discovery;
- plain assertions;
- fixtures;
- parametrization;
- monkeypatching;
- temporary resources;
- testing exceptions.

---

## 6.2 Testing pyramid for an AI application

Do not make every test call an LLM.

### Unit tests

Fast, deterministic tests for:

- prompt construction;
- citation rules;
- access rules;
- orchestration decisions;
- parsing;
- validation;
- retry classification.

### Component/integration tests

Test:

- retriever adapter against a development search index;
- Bedrock adapter against an enabled model;
- database integration;
- authentication provider.

### End-to-end tests

Test a deployed flow with a controlled evaluation set.

### AI evaluation

RAG quality and agent behavior evaluation are **not replacements for software tests**.

We will study evaluation deeply in a later course.

---

## 6.3 Amazon Bedrock as an adapter

**Read**

- [Amazon Bedrock — Inference using Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Amazon Bedrock APIs](https://docs.aws.amazon.com/bedrock/latest/userguide/apis.html)
- [Amazon Bedrock model inference parameters](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters.html)

AWS documents the Converse API as a consistent interface for Bedrock models that support messages. Also be aware that Bedrock's API surface continues to evolve; select an API deliberately based on the capabilities and portability you need.

### Architectural objective

Your application service should not know Boto3 request syntax.

Prefer:

```text
RAG Service
    |
Generator Protocol
    |
Bedrock Generator Adapter
    |
AWS SDK
```

This gives you a future path to LiteLLM/model gateways without rewriting the domain/application layer.

---

# 7. Week 4 — Container readiness and architecture review

## 7.1 Docker fundamentals

**Read**

- [Docker build best practices](https://docs.docker.com/build/building/best-practices/)

### Understand

- image vs container;
- build context;
- Dockerfile;
- layers;
- build cache;
- `.dockerignore`;
- immutable/reproducible builds;
- ephemeral/stateless containers;
- running as a non-root user;
- dependency pinning;
- keeping runtime images minimal.

Deployment architecture comes in later courses. Here, the goal is to make the Python application **container-ready**.

---

# 8. Architecture patterns to master

## 8.1 Layer responsibilities

A useful starting structure is:

```text
src/
└── underwriting_ai/
    ├── api/
    │   ├── routes.py
    │   └── schemas.py
    │
    ├── application/
    │   └── rag_service.py
    │
    ├── domain/
    │   └── models.py
    │
    ├── ports/
    │   ├── retriever.py
    │   └── generator.py
    │
    ├── adapters/
    │   ├── bedrock.py
    │   └── search.py
    │
    ├── config.py
    └── main.py
```

This is not mandatory. The architectural idea matters more than the exact folders:

> Separate business/application behavior from technology-specific adapters.

---

## 8.2 Configuration

Follow the principle:

```text
Code != Environment Configuration != Secrets
```

Examples:

**Code**

```text
retrieval algorithm
citation policy
application workflow
```

**Configuration**

```text
model ID
AWS region
retrieval k
timeout
```

**Secrets**

```text
API credentials
database passwords
private tokens
```

Secrets should not be embedded in source code.

Later courses will cover AWS Secrets Manager, IAM, Entra identity and workload/agent identity.

---

## 8.3 Error taxonomy

Do not catch `Exception` everywhere and return "Something went wrong."

Create meaningful categories:

```text
ApplicationError
    |
    +-- RetrievalError
    |
    +-- ModelError
    |
    +-- ValidationError
    |
    +-- AuthorizationError
    |
    +-- DependencyTimeout
```

Think about whether each failure is:

- retryable;
- non-retryable;
- safe to expose;
- safe to log;
- a user error;
- an infrastructure error;
- a security event.

---

# 9. Production AI code-review checklist

When reviewing a RAG/agent implementation, ask:

## Architecture

- Are application decisions separated from infrastructure integrations?
- Does business logic depend directly on SDK-specific objects?
- Can the LLM provider be replaced?
- Can the retriever be replaced?
- Are components independently testable?
- Are responsibilities clear?

## Python

- Are public interfaces typed?
- Is `Any` overused?
- Are async functions used for actual I/O?
- Are resources and clients reused appropriately?
- Is error handling explicit?

## API

- Are external inputs validated?
- Are internal exceptions translated safely?
- Is the API contract independent of provider-specific response structures?
- Are timeouts defined?

## Reliability

- What happens when retrieval fails?
- What happens when model inference times out?
- Is retry behavior safe?
- Can retries duplicate side effects?
- Is there a fallback behavior?

## Testing

- Can core orchestration be tested without calling AWS?
- Are boundary conditions tested?
- Are integrations separately tested?
- Are test fixtures representative?

## Operations readiness

- Is configuration externalized?
- Are secrets absent from source?
- Are logs useful?
- Does the service expose enough information for future tracing and metrics?

---

# 10. Practical lab

Run the companion notebook:

**`course_01_production_ai_development.ipynb`**

Scenario:

> Build the application layer for an Underwriting Guideline Assistant that answers underwriter questions using retrieved policy guidance, requires citations, can run locally, and can optionally call Amazon Bedrock.

The notebook intentionally starts with an implementation that looks like typical Data Science prototype code, then refactors it.

You will implement:

1. domain models;
2. Pydantic boundary schemas;
3. Retriever and Generator `Protocol`s;
4. deterministic local adapters;
5. async retrieval;
6. orchestration service;
7. grounding/citation policy;
8. explicit error types;
9. structured application logging;
10. FastAPI boundary;
11. deterministic tests;
12. optional Bedrock generator adapter;
13. architecture review exercises.

---

# 11. Required exercises

Do not just run the notebook.

After completing it, implement these changes yourself.

## Exercise 1 — Failure handling

Make one retriever fail.

Decide whether:

- the complete request should fail;
- the service should return partial results;
- retry should happen.

Document the reasoning.

---

## Exercise 2 — Add a second model implementation

Create another `Generator` implementation.

The RAG service itself should require **zero changes**.

If the service must change, revisit your abstraction boundary.

---

## Exercise 3 — Access-aware retrieval

Add a `user_groups` field to the request.

Documents have `allowed_groups`.

Filter unauthorized documents before they can become LLM context.

Think carefully:

> Should authorization be enforced only in the application service, or closer to the data/search layer?

We will revisit this during the identity and secure-RAG modules.

---

## Exercise 4 — Latency budget

Assume:

```text
Total SLA:        5.0 s
API overhead:     0.1 s
Retrieval:        0.8 s
Reranking:        0.5 s
Generation:       3.0 s
Safety checks:    0.3 s
```

Determine:

- remaining budget;
- timeout values;
- where parallelism is possible;
- which components require fallbacks.

---

## Exercise 5 — Architecture review

A developer proposes:

```python
@app.post("/ask")
def ask(question):
    client = boto3.client("bedrock-runtime")
    docs = opensearch.search(question)
    prompt = build_prompt(question, docs)
    response = client.invoke_model(...)
    return response
```

Write a Staff-level review.

Do **not** merely say "use clean code."

Explain:

- coupling;
- testability;
- error boundaries;
- provider dependence;
- configuration;
- operational concerns;
- proposed architecture.

---

# 12. Exit assessment

You are ready for Course 2 when you can confidently answer these without notes:

1. What should live in an API layer vs application service vs adapter?
2. Why are Protocols/interfaces useful in AI systems?
3. When is dependency injection useful?
4. When should a FastAPI route be `async`?
5. Why can blocking SDK/library calls undermine an async application?
6. Why shouldn't most unit tests call Bedrock?
7. What does Pydantic validate, and where should validation happen?
8. What is the architectural difference between a model adapter and application orchestration?
9. What should happen when the model times out?
10. How would you migrate from direct Bedrock access to LiteLLM later?
11. What parts of this application should remain unchanged when deployment moves from local execution to ECS?
12. What would you challenge in a developer's design before approving implementation?

---

# 13. Follow-on courses

This foundation feeds directly into:

1. **AWS & Distributed AI Systems**
2. **Enterprise Identity, SSO & Agent Identity**
3. **Production RAG Architecture**
4. **Agentic AI & Amazon Bedrock AgentCore**
5. **Model Gateways & LiteLLM**
6. **OpenTelemetry & AI Observability**
7. **RAG and Agent Evaluation**
8. **AI Red Teaming & Security Testing**
9. **GitHub Actions, CI/CD & Terraform**
10. **Solution Architecture**
11. **Enterprise AI Architecture**

---

# 14. Reference set

Use primary documentation as the source of truth because these technologies change quickly.

- Python: https://docs.python.org/3/
- Python Packaging Authority: https://packaging.python.org/
- uv: https://docs.astral.sh/uv/
- Ruff: https://docs.astral.sh/ruff/
- Pydantic: https://docs.pydantic.dev/latest/
- FastAPI: https://fastapi.tiangolo.com/
- pytest: https://docs.pytest.org/en/stable/
- mypy: https://mypy.readthedocs.io/en/stable/
- Docker: https://docs.docker.com/
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/latest/userguide/
- Boto3: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
