# Cross-Functional AI Specialist — Advanced Program

An executable, project-driven curriculum for experienced data scientists and AI engineers
moving toward Staff AI Scientist, AI Architect, or cross-functional AI technical lead roles.

> **Start here:** open the [Learning Hub](hub/index.html), then complete the ready courses
> in order. The Hub separates material that is ready to learn from courses that are still planned.

[One+i](https://oneplusi.io) · Advanced professional training · Last reviewed 2026-09-20

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
| 03–12 | **Planned** | [Sequential course plan](COURSE_PLAN.md) | Completed one vertical slice at a time |

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
