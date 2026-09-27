# Cross-Functional AI Specialist — Advanced Program

An executable, project-driven curriculum for experienced data scientists and AI engineers
moving toward Staff AI Scientist, AI Architect, or cross-functional AI technical lead roles.

> **Start here:** open the [Learning Hub](hub/index.html), then complete the ready courses
> in order. The Hub separates material that is ready to learn from courses that are still planned.

[One+i](https://oneplusi.io) · Advanced professional training · Last reviewed 2026-09-27

## What this program develops

The learner should finish able to turn an ambiguous AI opportunity into a secure, observable,
evaluated, economically defensible production system—and lead the decisions across product,
engineering, platform, security, legal, and operations.

This is intentionally not another catalogue of ML algorithms. Its thesis is:

```text
prototype skill
      ↓
production AI engineering
      ↓
system and solution architecture
      ↓
evaluation, reliability, security, and governance
      ↓
technical strategy and organizational influence
```

## Current release

| Course | Status | Primary artifact | Practical proof |
|---|---|---|---|
| 01 — Production AI Development in Python | **Ready in repository** | [Course chapter](curriculum/advanced/01-production-ai-development/README.md) | [Notebook](curriculum/advanced/01-production-ai-development/production_ai_development.ipynb) · [Lab](curriculum/advanced/01-production-ai-development/lab.py) |
| 02 — Cloud and Distributed AI Systems | **Ready in repository** | [Course chapter](curriculum/advanced/02-cloud-distributed-ai-systems/README.md) | [Notebook](curriculum/advanced/02-cloud-distributed-ai-systems/cloud_distributed_ai_systems.ipynb) · [Lab](curriculum/advanced/02-cloud-distributed-ai-systems/lab.py) |
| 03 — Enterprise Identity and Agent Authorization | **Ready in repository** | [Course chapter](curriculum/advanced/03-enterprise-identity-agent-authorization/README.md) | [Notebook](curriculum/advanced/03-enterprise-identity-agent-authorization/enterprise_identity_agent_authorization.ipynb) · [Lab](curriculum/advanced/03-enterprise-identity-agent-authorization/lab.py) |
| 04 — Production RAG and Knowledge Systems | **Ready in repository** | [Course chapter](curriculum/advanced/04-production-rag-knowledge-systems/README.md) | [Notebook](curriculum/advanced/04-production-rag-knowledge-systems/production_rag_knowledge_systems.ipynb) · [Lab](curriculum/advanced/04-production-rag-knowledge-systems/lab.py) |
| 05 — Agentic AI Architecture and AgentCore | **Ready in repository** | [Course chapter](curriculum/advanced/05-agentic-ai-architecture-agentcore/README.md) | [Notebook](curriculum/advanced/05-agentic-ai-architecture-agentcore/agentic_ai_architecture_agentcore.ipynb) · [Lab](curriculum/advanced/05-agentic-ai-architecture-agentcore/lab.py) |
| 06 — Model Gateways and Inference Economics | **Ready in repository** | [Course chapter](curriculum/advanced/06-model-gateways-inference-economics/README.md) | [Notebook](curriculum/advanced/06-model-gateways-inference-economics/model_gateways_inference_economics.ipynb) · [Lab](curriculum/advanced/06-model-gateways-inference-economics/lab.py) |
| 07 — AI Observability and Reliability Engineering | **Ready in repository** | [Course chapter](curriculum/advanced/07-ai-observability-reliability/README.md) | [Notebook](curriculum/advanced/07-ai-observability-reliability/ai_observability_reliability.ipynb) · [Lab](curriculum/advanced/07-ai-observability-reliability/lab.py) |
| 08 — AI Evaluation, Experimentation, and Causal Impact | **Ready in repository** | [Course chapter](curriculum/advanced/08-ai-evaluation-causal-impact/README.md) | [Notebook](curriculum/advanced/08-ai-evaluation-causal-impact/ai_evaluation_causal_impact.ipynb) · [Lab](curriculum/advanced/08-ai-evaluation-causal-impact/lab.py) |
| 09–12 | **Planned** | [Sequential course plan](COURSE_PLAN.md) | Completed one vertical slice at a time |

“Planned” is deliberate: a title in a roadmap is not presented as completed training.

## How the learning product works

Each ready course contains:

- a technical chapter that teaches mechanics, architecture choices, failure modes, production
  concerns, and the state of the art;
- one credential-free notebook that moves from baseline to implementation, experiments,
  evaluation, failure injection, mitigation, and production upgrade;
- a reusable `lab.py` with typed contracts and deterministic behavior;
- invariant tests, a focused checkpoint, and questions in the full quiz;
- an evidence-producing portfolio deliverable rather than a completion certificate.

The twelve courses build one evolving **Enterprise Underwriting AI Platform**. Each increment
leaves behind an architecture decision, tested implementation, evaluation result, or operating
artifact that can be defended in a Staff-level interview or design review.

## Run the ready courses

Prerequisites: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked
uv run pytest
uv run python scripts/validate_repo.py
uv run jupyter execute \
  curriculum/advanced/01-production-ai-development/production_ai_development.ipynb \
  --inplace
uv run jupyter execute \
  curriculum/advanced/02-cloud-distributed-ai-systems/cloud_distributed_ai_systems.ipynb \
  --inplace
uv run jupyter execute \
  curriculum/advanced/03-enterprise-identity-agent-authorization/enterprise_identity_agent_authorization.ipynb \
  --inplace
uv run jupyter execute \
  curriculum/advanced/04-production-rag-knowledge-systems/production_rag_knowledge_systems.ipynb \
  --inplace
uv run jupyter execute \
  curriculum/advanced/05-agentic-ai-architecture-agentcore/agentic_ai_architecture_agentcore.ipynb \
  --inplace
uv run jupyter execute \
  curriculum/advanced/06-model-gateways-inference-economics/model_gateways_inference_economics.ipynb \
  --inplace
uv run jupyter execute \
  curriculum/advanced/07-ai-observability-reliability/ai_observability_reliability.ipynb \
  --inplace
uv run jupyter execute \
  curriculum/advanced/08-ai-evaluation-causal-impact/ai_evaluation_causal_impact.ipynb \
  --inplace
```

The notebook and lab use deterministic local adapters. No cloud account, API key, or paid model
is required. Optional provider integrations are architecture exercises, not hidden prerequisites.

To use the Hub locally, serve the repository and open `http://localhost:8000/hub/`:

```bash
uv run python -m http.server 8000
```

## Program navigation

- [Course sequence, prerequisites, capstones, and exit evidence](COURSE_PLAN.md)
- [Current tooling and state-of-the-art review](docs/tooling-landscape.md)
- [Course 1 checkpoint](curriculum/advanced/01-production-ai-development/checkpoint.json)
- [Course 2 checkpoint](curriculum/advanced/02-cloud-distributed-ai-systems/checkpoint.json)
- [Course 3 checkpoint](curriculum/advanced/03-enterprise-identity-agent-authorization/checkpoint.json)
- [Course 4 checkpoint](curriculum/advanced/04-production-rag-knowledge-systems/checkpoint.json)
- [Course 5 checkpoint](curriculum/advanced/05-agentic-ai-architecture-agentcore/checkpoint.json)
- [Course 6 checkpoint](curriculum/advanced/06-model-gateways-inference-economics/checkpoint.json)
- [Course 7 checkpoint](curriculum/advanced/07-ai-observability-reliability/checkpoint.json)
- [Course 8 checkpoint](curriculum/advanced/08-ai-evaluation-causal-impact/checkpoint.json)
- [Full knowledge check](quiz/index.html)
- [Contribution and course quality standard](CONTRIBUTING.md)

## Validation contract

A course is marked ready only when its prose, implementation, tests, notebook, checkpoint, Hub
metadata, and quiz agree. CI checks Python quality, deterministic tests, notebook execution,
JSON validity, and local links. Live cloud adapters, deployment, and external service tests are
clearly labelled when not run. GitHub Pages deployment has not been performed or verified.

## Program boundaries

This curriculum teaches technical decision-making and safe reference patterns. It does not grant
production authorization, replace organizational security review, or claim that a mock model
measures live-model quality. The trusted application—not a model response—validates identity,
permissions, evidence, approvals, and side effects.
