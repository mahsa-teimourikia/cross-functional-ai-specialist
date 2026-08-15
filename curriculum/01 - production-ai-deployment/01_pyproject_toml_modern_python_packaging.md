# `pyproject.toml` and Modern Python Packaging

**Course:** Production AI Development in Python  
**Context:** Production Python services for RAG, AI agents, APIs, and AWS workloads  
**Last reviewed:** August 2026

## 1. Why packaging matters

A prototype can survive with `pip install ...`. A production AI application needs reproducibility, explicit Python compatibility, dependency ownership, separation of runtime and development tooling, controlled upgrades, CI reproducibility, and immutable builds.

The key principle is:

> Your Python environment should be reproducible from version-controlled project configuration. A developer laptop or notebook is not the source of truth.

A modern project commonly looks like:

```text
underwriting-ai/
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── Dockerfile
├── src/
│   └── underwriting_ai/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       ├── application/
│       ├── domain/
│       ├── ports/
│       └── adapters/
└── tests/
```

## 2. Mental model

`pyproject.toml` is broader than a replacement for `requirements.txt`.

```text
pyproject.toml
      │
      ├── project metadata
      ├── Python compatibility
      ├── direct dependencies
      ├── build configuration
      ├── development dependency groups
      └── tool configuration
      │
      ▼
dependency resolver
      │
      ▼
uv.lock
      │
      ├── exact resolved direct dependencies
      └── exact resolved transitive dependencies
      │
      ▼
reproducible environment
      ├── developer
      ├── CI
      ├── tests
      └── container build
```

The distinction between **declaring acceptable dependencies** and **locking a concrete resolution** is fundamental.

## 3. TOML essentials

```toml
name = "underwriting-ai"
debug = false
timeout = 30

dependencies = [
    "fastapi",
    "pydantic",
]

[project]
name = "underwriting-ai"
version = "0.1.0"

[project.optional-dependencies]
bedrock = ["boto3"]
```

You rarely need advanced TOML syntax. Learn to recognize tables, lists, nested tables, strings, booleans, and numbers.

## 4. The major `pyproject.toml` namespaces

### `[build-system]`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

This tells packaging frontends how the project should be built.

Conceptually:

```text
build frontend
      │
      ▼
build backend
      │
      ▼
wheel / source distribution
```

Common backends include Hatchling, setuptools, Flit, PDM's backend, and Poetry's backend.

Do not confuse a project/dependency manager such as uv with the conceptual role of a build backend.

### `[project]`

Standardized project metadata:

```toml
[project]
name = "underwriting-ai"
version = "0.1.0"
description = "Enterprise underwriting AI assistant"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "pydantic>=2.10",
]
```

### `[dependency-groups]`

Standardized development/internal dependency groups:

```toml
[dependency-groups]
test = ["pytest>=8", "pytest-asyncio"]
lint = ["ruff"]
typecheck = ["mypy"]
```

These are appropriate for testing, linting, documentation, evaluation tooling, and other project-development tasks that should not become package runtime requirements.

### `[tool.*]`

Tool-specific configuration:

```toml
[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.mypy]
python_version = "3.12"
strict = true
```

Prefer standardized metadata when a standard exists; use `[tool.*]` for genuinely tool-specific behavior.

## 5. Distribution name vs import package

You may declare:

```toml
[project]
name = "underwriting-ai"
```

but import:

```python
import underwriting_ai
```

The distribution name and Python import package are related but distinct concepts.

## 6. Declare Python compatibility explicitly

```toml
[project]
requires-python = ">=3.12"
```

or, if your production platform deliberately supports only a bounded range:

```toml
requires-python = ">=3.12,<3.15"
```

Do not add arbitrary upper bounds simply because future versions have not yet been tested. For an enterprise application standardized on one runtime, a tighter organizational policy can be reasonable.

`requires-python` should represent a real compatibility policy.

## 7. Direct vs transitive dependencies

If your code imports FastAPI and Pydantic:

```python
from fastapi import FastAPI
from pydantic import BaseModel
```

they are direct dependencies.

FastAPI itself depends on packages such as Starlette. Those are transitive dependencies.

```text
your application
├── FastAPI
│   └── transitive dependencies
└── Pydantic
```

Declare what your project directly depends on. Do not copy every package from `pip freeze` into `[project.dependencies]`.

## 8. Runtime dependencies

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "pydantic>=2.10,<3",
    "httpx>=0.28",
    "boto3>=1.35",
]
```

Runtime examples:

```text
FastAPI      runtime
Pydantic     runtime
Boto3        runtime if the service directly calls AWS
HTTPX        runtime if the service makes HTTP calls

pytest       development/test
Ruff         development/lint
mypy         development/typecheck
```

Do not install development tools in production simply for convenience.

## 9. Version constraints

Examples:

```toml
"fastapi"
"fastapi>=0.115"
"pydantic>=2.10,<3"
"some-library~=2.4"
"some-library==2.4.1"
```

Do not assume version syntax behaves like npm or another ecosystem. Python dependency specifiers have their own standardized semantics.

For applications, a useful model is:

```text
pyproject.toml
acceptable compatibility range
        │
        ▼
resolver
        │
        ▼
lockfile
exact tested resolution
```

## 10. Why not exact-pin everything in `[project]`?

This works:

```toml
dependencies = [
    "fastapi==0.116.1",
    "pydantic==2.11.7",
]
```

but combines compatibility policy with environment reproducibility.

A more flexible application pattern is:

```toml
dependencies = [
    "fastapi>=0.115,<1",
    "pydantic>=2.10,<3",
]
```

with exact resolution captured in the lockfile.

For reusable libraries, excessive exact pinning is especially problematic because it constrains consuming applications.

## 11. Application vs reusable library

A reusable internal library should generally advertise the broadest dependency range it genuinely supports:

```toml
pydantic = ">=2.8,<3"
```

A deployable application needs a concrete tested environment:

```text
pyproject.toml + lockfile
```

Do not apply library dependency strategy blindly to applications or vice versa.

## 12. Lockfiles

With uv:

```text
uv.lock
```

records the resolved graph.

```text
pyproject.toml
 fastapi>=0.115
 pydantic>=2.10
        │
        ▼
      resolver
        │
        ▼
      uv.lock
 exact direct + transitive resolution
```

For deployable applications such as RAG APIs, agent services, batch pipelines, and internal APIs, normally commit `uv.lock`.

## 13. Locking vs syncing

```bash
uv lock
```

resolves dependencies and updates the lockfile.

```bash
uv sync
```

installs the required resolved environment.

Mental model:

```text
pyproject.toml → uv lock → uv.lock → uv sync → .venv
```

uv also automatically locks/syncs for many project commands.

## 14. `uv run`

Prefer commands tied to the managed project environment:

```bash
uv run pytest
uv run ruff check .
uv run mypy src
uv run python -m underwriting_ai.main
```

This is often cleaner than relying on manually activated environments.

## 15. CI and `--locked`

CI should not silently produce a new dependency resolution.

```bash
uv sync --locked
```

should fail if the committed lockfile is stale relative to project metadata.

Desired workflow:

```text
developer changes dependency
        │
        ▼
update lockfile
        │
        ▼
commit pyproject.toml + uv.lock
        │
        ▼
CI verifies locked environment
```

## 16. Development dependency groups

Bad:

```toml
[project]
dependencies = [
    "fastapi",
    "boto3",
    "pytest",
    "ruff",
    "mypy",
]
```

Better:

```toml
[project]
dependencies = [
    "fastapi",
    "boto3",
]

[dependency-groups]
test = [
    "pytest>=8",
    "pytest-asyncio",
]
lint = ["ruff"]
typecheck = ["mypy"]
```

For a small service, one `dev` group can be sufficient:

```toml
[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio",
    "ruff",
    "mypy",
]
```

For larger projects, multiple groups allow targeted CI environments.

## 17. Nested dependency groups

```toml
[dependency-groups]
lint = ["ruff"]
test = ["pytest>=8", "pytest-asyncio"]
typecheck = ["mypy"]

dev = [
    { include-group = "lint" },
    { include-group = "test" },
    { include-group = "typecheck" },
]
```

This gives:

```text
dev
├── lint
├── test
└── typecheck
```

## 18. Dependency groups vs extras

This distinction is essential.

An **extra** is an optional capability offered to consumers of a distributable project:

```toml
[project.optional-dependencies]
aws = ["boto3"]
azure = ["azure-identity"]
```

A consumer might install:

```bash
pip install "company-ai-runtime[aws]"
```

A **dependency group** is for project-development/internal environment needs:

```toml
[dependency-groups]
test = ["pytest"]
lint = ["ruff"]
```

Decision rule:

> If a consumer needs to request the feature, consider an extra. If developers/CI need it for testing, linting, docs, or tooling, use a dependency group.

Do not make Bedrock optional in a service that cannot function without Bedrock.

## 19. Environment markers

Dependencies may be conditional:

```toml
dependencies = [
    'some-package>=2; python_version >= "3.13"',
]
```

Use markers only for genuine environment-specific requirements. Avoid unnecessary dependency complexity.

## 20. `src/` layout

Recommended starting point:

```text
underwriting-ai/
├── pyproject.toml
├── uv.lock
├── src/
│   └── underwriting_ai/
│       ├── __init__.py
│       └── main.py
└── tests/
```

A flat layout can also work, but `src/` helps prevent accidental imports directly from the repository root and encourages tests to exercise the installed package correctly.

Avoid hacks such as:

```python
import sys
sys.path.append("../src")
```

If this is necessary throughout the application, fix the project/package setup.

## 21. Wheel vs source distribution

A wheel is a built distribution:

```text
underwriting_ai-0.1.0-py3-none-any.whl
```

A source distribution (sdist) is typically:

```text
underwriting_ai-0.1.0.tar.gz
```

Conceptually:

```text
source → build → wheel → install
```

Wheels are generally faster and more predictable to install because they are already built.

## 22. Does an internal service need PyPI?

Usually not.

A service may flow through:

```text
Git repository
      ↓
CI
      ↓
Docker image
      ↓
ECR
      ↓
ECS / EKS
```

Correct packaging is still valuable for imports, tests, dependency management, and reproducibility.

Reusable internal libraries may instead be published to an approved private package index. Never publish proprietary code to public PyPI unless explicitly intended and approved.

## 23. Build backend choices

### Setuptools

Mature and widely used:

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"
```

### Hatchling

Modern and focused:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

For this learning track:

```text
project/dependency management → uv
project metadata              → pyproject.toml
locking                       → uv.lock
build backend                 → Hatchling
lint/format                   → Ruff
type checking                 → mypy
testing                       → pytest
```

This is a reference stack, not an enterprise mandate. Organizational standards may be more important than personal tool preference.

## 24. Complete starter configuration

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "underwriting-ai"
version = "0.1.0"
description = "Enterprise underwriting RAG and agent service"
readme = "README.md"
requires-python = ">=3.12,<3.15"

dependencies = [
    "boto3>=1.35",
    "fastapi>=0.115",
    "httpx>=0.28",
    "pydantic>=2.10,<3",
    "pydantic-settings>=2.7",
]

[dependency-groups]
lint = ["ruff"]

test = [
    "pytest>=8",
    "pytest-asyncio",
    "pytest-cov",
]

typecheck = ["mypy"]

dev = [
    { include-group = "lint" },
    { include-group = "test" },
    { include-group = "typecheck" },
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.mypy]
python_version = "3.12"
strict = true
```

Do not copy version numbers blindly. Validate current versions and compatibility during dependency maintenance.

## 25. Creating the project with uv

```bash
uv init --package underwriting-ai
cd underwriting-ai

uv add fastapi pydantic pydantic-settings httpx boto3

uv add --group test pytest pytest-asyncio pytest-cov
uv add --group lint ruff
uv add --group typecheck mypy

uv tree
uv run pytest
uv run ruff check .
uv run mypy src
```

Prefer dependency-management commands where practical so declarations and lock state stay coordinated.

## 26. Inspect dependency trees

```bash
uv tree
```

A tree might conceptually show:

```text
underwriting-ai
├── boto3
│   ├── botocore
│   └── s3transfer
├── fastapi
│   ├── pydantic
│   └── starlette
└── httpx
    └── httpcore
```

This matters for vulnerability remediation, conflicts, unexpected upgrades, image size, and architecture reviews.

If a vulnerability scanner reports a package you did not declare, first determine which direct dependency brought it in. Do not automatically promote it to a direct dependency.

## 27. `requirements.txt` is not obsolete

Do not learn "`requirements.txt` is old and wrong." Requirements files remain valid and useful, particularly in pip-oriented workflows.

A common alternative is:

```text
requirements.in
      ↓
dependency compiler
      ↓
requirements.txt
```

Compare:

| Approach | Intent | Resolved environment |
|---|---|---|
| uv project | `pyproject.toml` | `uv.lock` |
| pip-tools style | `requirements.in` | compiled `requirements.txt` |
| basic pip | `requirements.txt` | workflow-dependent |

For new projects in this course, prefer `pyproject.toml + uv.lock`, while recognizing legitimate alternatives.

## 28. Constraints

A constraints file can influence resolution without claiming the package is a direct application dependency:

```text
# constraints.txt
some-transitive-package<5
```

This can be useful for temporary transitive incompatibilities.

## 29. Git dependencies

You may encounter:

```toml
dependencies = [
    "company-ai-lib @ git+https://github.com/company/company-ai-lib.git@v1.2.0",
]
```

Be cautious about authentication, reproducibility, supply-chain controls, network availability, and build performance.

Avoid mutable production dependencies such as:

```text
@main
```

Prefer approved immutable releases, tags/commits, or package artifacts.

## 30. Local/editable dependencies

uv can separate the standardized dependency declaration from a development source:

```toml
[project]
dependencies = ["company-ai-runtime"]

[tool.uv.sources]
company-ai-runtime = { path = "../ai-runtime", editable = true }
```

Editable installations are useful for development, not as a production deployment model.

## 31. CLI entry points

```python
# src/underwriting_ai/cli.py

def main() -> None:
    print("Starting underwriting assistant")
```

```toml
[project.scripts]
underwriting-ai = "underwriting_ai.cli:main"
```

Then:

```bash
underwriting-ai
```

can invoke the entry point after installation.

## 32. Keep application configuration separate

These are runtime configuration:

```text
AWS_REGION
BEDROCK_MODEL_ID
OPENSEARCH_ENDPOINT
LOG_LEVEL
```

They are not dependency metadata.

Keep boundaries clear:

```text
pyproject.toml
→ project/dependency/build/tool configuration

runtime configuration
→ deployed application behavior

Secrets Manager / workload identity
→ sensitive values and credentials
```

Never put credentials in `pyproject.toml`.

## 33. `.python-version`, `.venv`, and source control

`.python-version` can express a preferred local interpreter:

```text
3.12
```

This differs from project compatibility:

```toml
requires-python = ">=3.12"
```

Do not commit `.venv`.

Typical `.gitignore` entries:

```gitignore
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
```

Commit enough configuration to recreate the environment rather than committing the environment itself.

## 34. Docker relationship

Conceptually:

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
```

before copying frequently changing source can allow dependency-layer caching.

The exact production uv/Docker pattern should follow current uv documentation and organizational container standards.

Production images normally should not include pytest, mypy, Ruff, Jupyter, or evaluation tooling unless the runtime actually needs them.

## 35. Dependency security and supply chain

Dependencies create supply-chain risk:

- vulnerable packages;
- compromised releases;
- typosquatting;
- malicious updates;
- abandoned projects;
- excessive transitive graphs.

AI frameworks can create particularly large dependency surfaces.

Before adding a major dependency, ask:

1. What capability does it provide?
2. Can an existing approved dependency solve the problem?
3. Is it actively maintained?
4. What transitive dependencies does it introduce?
5. What licenses and vulnerabilities are involved?
6. Does it require native/system dependencies?
7. How deeply will our code depend on its abstractions?
8. Who owns upgrades?
9. How difficult would replacement be?

Package selection is an architecture decision.

## 36. AI-framework decision example

A developer proposes LangChain.

Do not answer based on personal preference.

Ask which capabilities are required:

```text
orchestration?
integrations?
retrieval?
agents?
observability?
```

Then compare framework value against dependency footprint, API stability, team expertise, testability, provider abstraction, security, observability, and migration cost.

## 37. Separate AI evaluation dependencies

If RAG evaluation requires heavy libraries not used by the serving application:

```toml
[dependency-groups]
eval = [
    "ragas",
    "pandas",
]
```

Conceptually:

```text
production API → runtime dependencies

evaluation job → runtime + evaluation dependencies
```

Likewise, red-team/security tooling may belong in its own CI group rather than the production image.

## 38. Optional provider adapters for reusable libraries

A reusable internal library might use:

```toml
[project]
name = "company-ai-runtime"
dependencies = [
    "pydantic>=2.10,<3",
]

[project.optional-dependencies]
aws = ["boto3"]
azure = ["azure-identity"]
opensearch = ["opensearch-py"]
```

This can align package dependencies with an adapter architecture.

A single deployable service that always uses AWS probably should not make its required AWS SDK artificially optional.

## 39. Common anti-patterns

### Ad-hoc dependency management

```text
run → ModuleNotFoundError → pip install → repeat
```

Instead:

```text
identify requirement
→ declare dependency
→ update resolution
→ run tests
```

### `pip freeze` as project architecture

`pip freeze` captures what is installed, not why it is installed. It mixes direct, transitive, runtime, and development packages.

### Giant runtime dependency list

Do not add frameworks and SDKs "because we may need them later." Every runtime dependency should correspond to a real capability.

### Mutable CI environment

Avoid separately declaring dependencies in CI:

```yaml
- run: pip install fastapi boto3 pytest
```

while `pyproject.toml` declares something different.

Prefer CI consuming project metadata and the committed lock.

### Resolving latest versions during production deployment

Prefer:

```text
reviewed lock
→ CI
→ immutable build artifact
→ deployment
```

### Manual lockfile editing

Treat `uv.lock` as generated resolver output.

### Assuming a lockfile provides security

A reproducible vulnerable package is still vulnerable.

### Notebook environment as production truth

Always test a clean environment.

## 40. Fresh-environment test

A critical reproducibility test is:

```text
clean machine/environment
       ↓
clone repository
       ↓
uv sync --locked
       ↓
uv run pytest
       ↓
application works
```

If this fails, the project is not reproducible.

## 41. Mature AI repository example

```text
underwriting-ai/
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── Dockerfile
├── src/
│   └── underwriting_ai/
│       ├── main.py
│       ├── api/
│       ├── application/
│       ├── domain/
│       ├── ports/
│       ├── adapters/
│       ├── config/
│       └── observability/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── evals/
│   ├── datasets/
│   └── evaluators/
├── terraform/
└── .github/
    └── workflows/
```

## 42. Monorepos and shared libraries

You may eventually see:

```text
enterprise-ai/
├── services/
│   ├── underwriting/
│   ├── claims/
│   └── assistant/
└── libraries/
    ├── ai-runtime/
    └── evaluation/
```

Questions become:

- Does each service have its own `pyproject.toml`?
- Are libraries independently versioned?
- What are release boundaries?
- Should a workspace be used?
- How are cross-package changes tested?

Do not adopt a monorepo/workspace simply because tooling supports it. Repository design should follow ownership and release boundaries.

## 43. Shared-library extraction is an architecture decision

If three services duplicate Bedrock wrappers, retry policies, telemetry, and response normalization, you might consider an internal library.

Before extracting one, ask:

- Is the behavior genuinely common?
- Who owns it?
- Will teams need independent releases?
- How are breaking changes managed?
- Would a platform/network service be a better abstraction?

Packaging enables reuse; it does not prove reuse is architecturally correct.

## 44. Semantic versioning

You will commonly see:

```text
2.4.1
```

often interpreted as:

```text
MAJOR.MINOR.PATCH
```

But do not assume every package strictly follows Semantic Versioning. Check the project's release/versioning policy.

Python packaging version syntax and Semantic Versioning are related concepts, not identical standards.

## 45. Dynamic metadata

You may encounter:

```toml
dynamic = ["version"]
```

This means a build backend/tool supplies the value dynamically, perhaps from source control.

Use dynamic metadata only when it solves a concrete release-management need. Static configuration is easier to reason about.

## 46. Package data and prompts

Packages may contain non-Python resources such as schemas or prompt templates. Build configuration determines what enters the artifact.

For AI applications, ask whether a prompt should be packaged with code.

Advantages:

- versioned with code;
- reproducible;
- easy rollback.

Trade-offs:

- prompt changes may require a new application artifact;
- prompt lifecycle may need independent governance;
- experimentation can become slower.

Packaging choices should follow configuration and governance requirements.

## 47. Dependency policy for an enterprise AI service

A practical baseline:

1. Every runtime dependency maps to a documented capability.
2. Development tooling belongs in dependency groups.
3. Direct dependencies are declared in `pyproject.toml`.
4. Deployable applications commit the lockfile.
5. CI verifies lock consistency.
6. Production builds consume the locked graph.
7. Upgrades happen through reviewed PRs.
8. Software tests run before merge.
9. AI evaluations run for changes that can affect AI behavior.
10. Vulnerability/security scanning runs in CI.
11. Secrets never enter project metadata.
12. Major frameworks require architectural justification.

## 48. Practical bootstrap exercise

```bash
uv init --package underwriting-ai
cd underwriting-ai

uv add fastapi pydantic pydantic-settings httpx boto3

uv add --group test pytest pytest-asyncio pytest-cov
uv add --group lint ruff
uv add --group typecheck mypy

uv tree
uv run pytest
uv run ruff check .
uv run mypy src
uv lock --check
uv sync
```

Create:

```text
underwriting-ai/
├── pyproject.toml
├── README.md
├── src/
│   └── underwriting_ai/
│       ├── __init__.py
│       └── main.py
└── tests/
    └── test_main.py
```

`main.py`:

```python
def greeting(name: str) -> str:
    return f"Hello {name}"
```

`test_main.py`:

```python
from underwriting_ai.main import greeting


def test_greeting() -> None:
    assert greeting("Underwriter") == "Hello Underwriter"
```

Then delete `.venv/` and reproduce:

```bash
uv sync --locked
uv run pytest
```

## 49. Dependency-classification exercise

Classify:

```text
FastAPI
Pydantic
Boto3
pytest
Ruff
mypy
RAG evaluation framework
OpenSearch client
Jupyter
security scanner
```

One possible answer:

```text
Runtime:
- FastAPI
- Pydantic
- Boto3
- OpenSearch client

Test:
- pytest

Lint:
- Ruff

Typecheck:
- mypy

Evaluation:
- RAG evaluation framework

Security:
- security scanner

Experimentation:
- Jupyter
```

Then challenge the answer based on architecture. If evaluation runs in a separate production evaluation service, its dependencies become runtime dependencies of *that service*.

## 50. Review exercise

Review:

```toml
[project]
name = "ai"
version = "1"
dependencies = [
    "boto3",
    "fastapi",
    "pytest",
    "ruff",
    "mypy",
    "langchain",
    "langgraph",
    "openai",
    "azure-identity",
    "pandas",
    "numpy",
    "jupyter",
]
```

Ask:

1. Is the name meaningful?
2. Which Python versions are supported?
3. Which dependencies are runtime?
4. Which are development-only?
5. Why are AWS and other provider SDKs both required?
6. Why are multiple AI frameworks required?
7. Does the service need pandas/NumPy?
8. Why is Jupyter a runtime dependency?
9. What is the build backend?
10. What is the locking strategy?
11. Which dependencies are actually imported?
12. What capability justifies each major dependency?

A Staff-level review asks **why**, not merely how to reorganize TOML.

## 51. Architecture scenario: LiteLLM migration

Today:

```text
Application → Boto3 → Bedrock
```

so:

```toml
dependencies = ["boto3"]
```

Later:

```text
Application → HTTP → LiteLLM Gateway → Bedrock/Azure/other
```

Now the application may no longer need `boto3`.

This illustrates:

> Dependency boundaries reflect architecture boundaries.

## 52. Packaging → CI/CD → Terraform

Keep layers separate:

```text
pyproject.toml + uv.lock
        ↓
Python dependencies/environment
        ↓
container build
        ↓
immutable image
        ↓
Terraform-provisioned infrastructure
        ↓
ECS / EKS / Lambda
```

Terraform does not manage Python dependencies. Python packaging does not provision AWS infrastructure.

Clear ownership boundaries prevent configuration chaos.

## 53. Packaging and AI-specific CI

A dependency upgrade can alter AI behavior even when software tests pass.

For example:

```text
LLM SDK
retrieval library
agent framework
tokenizer
```

Therefore a mature AI dependency PR can trigger:

```text
dependency change
      ├── lint/type checks
      ├── unit/integration tests
      ├── vulnerability checks
      ├── RAG/agent evaluation
      └── security/red-team regression
```

This is why production AI CI/CD goes beyond conventional software CI.

## 54. Best-practice checklist

### Do

- use `pyproject.toml`;
- declare supported Python versions;
- separate runtime and development dependencies;
- use dependency groups for development tooling;
- use extras for genuine consumer-facing optional features;
- commit a lockfile for deployable applications;
- verify the lockfile in CI;
- prefer clean/reproducible environments;
- understand `src/` layout;
- inspect dependency trees;
- review dependency changes;
- scan dependencies;
- upgrade deliberately;
- build immutable artifacts.

### Avoid

- ad-hoc `pip install` as project management;
- notebook environments as dependency truth;
- blindly copying `pip freeze`;
- putting every tool into runtime dependencies;
- manually editing lockfiles;
- committing `.venv`;
- storing secrets in project files;
- mutable Git branches as production dependencies;
- major frameworks without architecture review;
- CI redefining dependencies independently;
- fresh resolution during production deployment;
- assuming lockfile = security;
- confusing extras with dependency groups;
- confusing package managers with build backends;
- `sys.path` hacks for broken packaging.

## 55. Staff-level dependency review checklist

When a PR adds a dependency, ask:

### Capability
- What requirement does it satisfy?
- Is the dependency necessary now?

### Architecture
- Which component owns it?
- Does it cross an intended abstraction boundary?
- Does it duplicate an existing capability?

### Dependency graph
- What transitive packages appear?
- Are there version conflicts?

### Security
- Is it actively maintained?
- Are licenses acceptable?
- Are known vulnerabilities present?
- Is its source/provenance acceptable?

### Operations
- Does it add native binaries or OS requirements?
- What does it do to container size/startup?
- Does it affect deployment/runtime support?

### Ownership
- Who upgrades it?
- What tests/evaluations validate upgrades?
- What is the replacement/migration cost?

## 56. Exit assessment

Answer without the guide:

1. Why is `pip install fastapi boto3` insufficient as project dependency management?
2. What is the difference between `[project].dependencies` and `[dependency-groups]`?
3. What is the difference between an optional extra and a development dependency group?
4. Why can `pydantic>=2.10,<3` coexist with one exact version in a lockfile?
5. Should `uv.lock` be committed for a production RAG API? Why?
6. Why should you not copy `pip freeze` directly into `[project.dependencies]`?
7. Why can a `src/` layout reveal packaging errors?
8. What is the conceptual difference between Hatchling and uv?
9. If a vulnerability is in a transitive dependency, what should you inspect first?
10. If the service talks only to a remote LiteLLM gateway, why might `boto3` no longer belong in the service?
11. What should CI do when `pyproject.toml` changed but the lockfile did not?
12. Why should AI evaluation run after some dependency upgrades even when unit tests pass?

## 57. Primary references

Use current primary documentation as the source of truth because packaging tooling evolves.

- Python Packaging User Guide: https://packaging.python.org/
- Writing `pyproject.toml`: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- `pyproject.toml` specification: https://packaging.python.org/en/latest/specifications/pyproject-toml/
- Dependency specifiers: https://packaging.python.org/en/latest/specifications/dependency-specifiers/
- Dependency Groups: https://packaging.python.org/en/latest/specifications/dependency-groups/
- Packaging flow: https://packaging.python.org/en/latest/flow/
- `pylock.toml` specification: https://packaging.python.org/en/latest/specifications/pylock-toml/
- uv documentation: https://docs.astral.sh/uv/
- uv dependency management: https://docs.astral.sh/uv/concepts/projects/dependencies/
- uv locking and syncing: https://docs.astral.sh/uv/concepts/projects/sync/
- uv pip-to-project migration: https://docs.astral.sh/uv/guides/migration/pip-to-project/
- Hatch: https://hatch.pypa.io/
- Ruff: https://docs.astral.sh/ruff/
- pytest: https://docs.pytest.org/
- mypy: https://mypy.readthedocs.io/

## 58. Next topic

**4.2 — Ruff, formatting, linting, and automated code-quality gates**

The next chapter should distinguish and operationalize:

```text
formatting
vs
linting
vs
type checking
vs
testing
vs
security scanning
```

and then connect them to the GitHub Actions pipeline used later in the roadmap.
