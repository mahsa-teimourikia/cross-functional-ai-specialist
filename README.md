# Cross-Functional AI Specialist Development Plan

## Goal

This development plan is designed to build the skills required to operate at a **Staff AI Scientist / AI Architect** level in a cross-functional enterprise environment.

The target role combines deep AI expertise with enough software engineering, cloud architecture, security, governance, and platform knowledge to:

* design and review production AI solutions
* make architecture and technology-selection decisions
* compare implementation options and trade-offs
* lead AI developers through implementation
* review development plans and technical proposals
* assist and unblock developers
* collaborate effectively with DevOps, ML engineers, data engineers, architects, product teams, and business stakeholders
* define evaluation, governance, security, responsible AI, and production-readiness requirements

The primary technical environment is:

* Python
* AWS
* Amazon Bedrock
* RAG
* AI agents
* enterprise GenAI applications

The objective is not to become a specialist in every adjacent discipline. The objective is to develop enough depth across disciplines to make sound technical decisions and lead complex AI initiatives end to end.

---

# Target Competency Profile

The desired profile is intentionally T-shaped.

## Deep expertise

* Generative AI
* RAG
* AI agents
* AI evaluation
* AI governance
* Responsible AI
* AI safety
* AI strategy

## Strong working knowledge

* Python software engineering
* distributed systems
* AWS architecture
* AI solution architecture
* enterprise architecture
* authentication and authorization
* AI security
* observability
* CI/CD
* DevOps concepts
* data architecture
* production ML and AI systems

---

# Learning Principles

The program should remain practical and architecture-focused.

Each topic should be learned through realistic enterprise scenarios rather than isolated tutorials.

For every significant technical decision, use the following framework:

```text
Business Requirements
        ↓
Functional Requirements
        ↓
Non-Functional Requirements
        ↓
Constraints
        ↓
Solution Options
        ↓
Trade-off Analysis
        ↓
Architecture Decision
        ↓
Implementation Plan
        ↓
Evaluation & Governance
        ↓
Production Monitoring
```

The central question is not:

> How do I implement this technology?

It is:

> Should we use this technology for this problem, and what are the consequences of that decision?

---

# Roadmap

| Phase | Focus                          | Primary Outcome                                          |
| ----- | ------------------------------ | -------------------------------------------------------- |
| 1     | Production AI Development      | Review and guide production Python AI development        |
| 2     | Cloud & Distributed Systems    | Design scalable AWS AI applications                      |
| 3     | Enterprise Identity & Security | Design authentication, authorization, and agent identity |
| 4     | Production RAG Architecture    | Architect enterprise-grade RAG systems                   |
| 5     | Agentic AI Architecture        | Design reliable and secure agent systems                 |
| 6     | AI Platform & Model Gateway    | Design shared AI infrastructure                          |
| 7     | Observability                  | Operate and troubleshoot distributed AI systems          |
| 8     | AI Evaluation                  | Build comprehensive RAG and agent evaluation strategies  |
| 9     | AI Security & Red Teaming      | Design and validate secure AI products                   |
| 10    | CI/CD & AI DevOps              | Build AI-aware development and deployment pipelines      |
| 11    | Solution Architecture          | Own end-to-end architecture decisions                    |
| 12    | Enterprise AI Architecture     | Define reusable capabilities and cross-project strategy  |

---

# 1. Production AI Development

The goal is to move from notebook-oriented Python toward production-grade AI application development.

## Python engineering

Develop strong working knowledge of:

* project and package structure
* modules and interfaces
* typing
* Pydantic
* dataclasses
* dependency injection
* abstraction and separation of concerns
* design patterns
* async/await
* concurrency
* exception handling
* structured logging
* configuration management
* dependency management
* REST APIs
* FastAPI
* unit testing
* integration testing
* end-to-end testing
* mocking
* pytest
* profiling
* performance debugging

## Architecture skills

Be able to identify problems such as:

* tightly coupled retrieval and generation logic
* duplicated infrastructure code
* poor abstraction boundaries
* untestable agent workflows
* global configuration
* hidden dependencies
* inadequate error handling
* poor observability

The target skill is being able to review code and explain how its architecture should evolve.

---

# 2. Cloud Architecture & Distributed Systems

Focus on architecture patterns rather than memorizing AWS services.

## Core AWS capabilities

### Compute

Understand when to use:

* AWS Lambda
* ECS
* Fargate
* EKS
* EC2
* SageMaker endpoints
* Amazon Bedrock managed inference

Compare them across:

* latency
* workload duration
* scalability
* operational complexity
* cost
* portability
* state management

### Storage

Understand the architectural role of:

* Amazon S3
* DynamoDB
* Aurora / RDS
* OpenSearch
* vector databases
* ElastiCache / Redis

Develop a strong understanding of:

* relational storage
* key-value storage
* object storage
* search indexes
* vector search
* caching

### Messaging and event-driven architecture

Study:

* SQS
* SNS
* EventBridge
* Kinesis
* Step Functions

Understand the distinction between:

```text
SQS
Work queue / asynchronous processing

SNS
Publish-subscribe notifications

EventBridge
Event routing and application integration

Kinesis
High-throughput event streaming

Step Functions
Workflow orchestration
```

## Example AI streaming architecture

```text
Call / Event Stream
        ↓
     Kinesis
        ↓
Processing Service
        ↓
Transcription
        ↓
AI Processing
        ↓
Insights
        ↓
Downstream Applications
```

---

# 3. Enterprise Identity, Authentication & Authorization

Identity should be treated as a core architecture capability.

## Fundamentals

Understand:

* authentication
* authorization
* federation
* SSO
* OAuth 2.0
* OpenID Connect
* JWT
* access tokens
* refresh tokens
* scopes
* claims
* RBAC
* ABAC

Develop a strong conceptual understanding of:

> Authentication answers "Who are you?"

> Authorization answers "What are you allowed to do?"

---

# 4. Microsoft Entra ID

Learn how enterprise identity integrates with AI applications.

Topics include:

* Entra tenants
* users
* groups
* enterprise applications
* application registrations
* service principals
* client IDs
* client secrets
* certificates
* OAuth flows
* OIDC
* redirect URIs
* scopes
* application roles
* delegated permissions
* application permissions

## Example

```text
Corporate User
      ↓
Microsoft Entra ID
      ↓
SSO / OIDC
      ↓
AWS-hosted AI Application
      ↓
Application Authorization
      ↓
AI Service
```

The hosting cloud and the identity provider do not need to be the same platform.

---

# 5. Agent Identity

Agentic systems introduce new identity and authorization problems.

A system should never simply assume:

> The agent can access this system.

Instead ask:

> Under whose identity is the action performed?

Possible models include:

* agent identity
* workload identity
* service identity
* user-delegated identity

## Topics

* workload identity
* service accounts
* delegated authorization
* OAuth delegation
* temporary credentials
* least privilege
* identity propagation
* tool permissions
* credential isolation
* agent authorization
* audit trails
* user-to-agent delegation

## Example

```text
User
 ↓
AI Agent
 ↓
Tool
 ↓
Enterprise System
```

The architecture must determine whether the enterprise-system action executes as:

```text
User Identity
```

or

```text
Agent / Service Identity
```

This decision has major security and governance implications.

---

# 6. Production RAG Architecture

The objective is to move beyond basic RAG implementation toward enterprise RAG architecture.

## Ingestion architecture

Study:

```text
Enterprise Sources
        ↓
Ingestion
        ↓
Parsing
        ↓
Validation
        ↓
Chunking
        ↓
Metadata
        ↓
Embedding
        ↓
Indexing
        ↓
Vector / Search Store
```

Understand:

* incremental indexing
* document versioning
* re-indexing
* deletion
* failed ingestion recovery
* document lineage
* metadata strategy
* access-control propagation
* tenant isolation
* freshness

## Retrieval

Study:

* semantic search
* lexical search
* hybrid retrieval
* reranking
* metadata filtering
* query transformation
* query expansion
* query routing
* multi-stage retrieval
* caching
* adaptive retrieval

Evaluate each approach across:

* quality
* latency
* complexity
* cost

## Secure RAG

Understand identity-aware retrieval.

```text
User Identity
      ↓
Authorization
      ↓
Query
      ↓
Permission-Aware Retrieval
      ↓
Only Authorized Documents
      ↓
Generation
```

---

# 7. Agentic AI Architecture

Move beyond tool calling toward production agent-system design.

## Architecture patterns

Understand the difference between deterministic workflows and autonomous agents.

### Workflow

```text
A → B → C → D
```

### Agent loop

```text
Goal
 ↓
Reason
 ↓
Select Tool
 ↓
Execute
 ↓
Observe
 ↓
Reason
 ↺
```

### Multi-agent system

```text
          Supervisor
              │
      ┌───────┼───────┐
      ↓       ↓       ↓
   Agent A Agent B Agent C
```

## Topics

* orchestration
* agent loops
* planning
* tool design
* tool schemas
* memory
* state
* checkpoints
* retries
* idempotency
* failure recovery
* human approval
* agent permissions
* distributed workflows
* agent-to-agent communication
* long-running agents
* MCP
* agent observability
* agent evaluation

A core competency should be knowing:

> When should this remain a deterministic workflow instead of becoming an agent?

---

# 8. Amazon Bedrock AgentCore

Use AgentCore as both a technology topic and a vehicle for studying production agent infrastructure.

Study capabilities around:

* agent runtime
* identity
* tool connectivity
* gateway capabilities
* memory
* observability
* governance
* security

Architecture discussions should compare managed AgentCore capabilities with custom implementation.

Key question:

> Which capabilities should we build ourselves, and which should be delegated to managed infrastructure?

---

# 9. Model Gateway & LiteLLM

Understand the model-gateway architecture pattern.

Without a gateway:

```text
App A → Bedrock
App B → Azure OpenAI
App C → OpenAI
App D → Bedrock
App E → Other Provider
```

Potential problems:

* duplicated authentication
* inconsistent retry logic
* fragmented logging
* inconsistent governance
* difficult cost tracking
* provider coupling

With a model gateway:

```text
AI Applications
       ↓
   Model Gateway
      LiteLLM
       ↓
 ┌─────┼─────────┐
 ↓     ↓         ↓
Bedrock Azure  Other Models
```

## Topics

* model abstraction
* model routing
* fallback
* retries
* rate limiting
* quotas
* token budgets
* model access policies
* cost management
* observability
* governance
* provider portability

Also evaluate when a gateway introduces unnecessary complexity.

---

# 10. Observability & OpenTelemetry

Observability should be treated as a first-class AI architecture capability.

## Traditional observability

Understand:

* logs
* metrics
* traces

## OpenTelemetry

Study:

```text
Trace
 ↓
Span
 ↓
Context
 ↓
Propagation
 ↓
Attributes
 ↓
Exporter
 ↓
Collector
 ↓
Observability Backend
```

Understand distributed tracing across services.

Example:

```text
User Request
    ↓
API
    ↓
Agent
    ↓
Retrieval       300 ms
    ↓
LLM            1.6 sec
    ↓
Tool           450 ms
    ↓
LLM            1.1 sec
    ↓
Response
```

## AI-specific telemetry

Capture where appropriate:

* model
* prompt version
* tokens
* latency
* cost
* retrieval calls
* retrieval results
* tool execution
* agent steps
* errors
* safety events
* guardrail events
* evaluation results

Study integration with:

* OpenTelemetry
* AWS CloudWatch
* tracing backends
* AI observability platforms

---

# 11. RAG Evaluation

RAG should be evaluated as a system rather than only evaluating the final response.

```text
Question
   ↓
Retrieval
   ↓
Context
   ↓
Generation
   ↓
Answer
```

## Retrieval metrics

Understand:

* Recall@K
* Precision@K
* Hit Rate
* MRR
* NDCG
* context relevance

## Generation evaluation

Evaluate:

* groundedness
* faithfulness
* answer relevance
* completeness
* citation correctness
* citation completeness
* factual consistency

## System evaluation

Include:

* task success
* latency
* cost
* reliability
* user satisfaction
* failure rate

Build reusable evaluation datasets and regression tests.

---

# 12. Agent Evaluation

Agent evaluation requires evaluating both results and behavior.

A correct final answer does not necessarily mean the agent performed correctly.

## Evaluate

* task success
* trajectory
* tool selection
* tool arguments
* number of steps
* unnecessary actions
* recovery from failures
* policy compliance
* latency
* token usage
* cost
* user outcome

Compare:

* deterministic evaluators
* rule-based evaluators
* LLM-as-judge
* human evaluation

Agent evaluation should become part of both development and production monitoring.

---

# 13. AI Security & Red Teaming

AI security testing should be systematic and repeatable.

## Threats

Study:

* direct prompt injection
* indirect prompt injection
* jailbreaks
* system-prompt leakage
* sensitive-data leakage
* data exfiltration
* RAG poisoning
* malicious documents
* tool abuse
* insecure tool parameters
* excessive agency
* privilege escalation
* memory poisoning
* identity abuse
* agent impersonation
* denial-of-wallet attacks
* resource exhaustion

## Security testing architecture

```text
AI Security Test Suite
        ↓
 ┌────────────────────┐
 │ Prompt Injection   │
 │ Jailbreaks         │
 │ Data Leakage       │
 │ RAG Attacks        │
 │ Tool Abuse         │
 │ Agent Attacks      │
 │ Identity Attacks   │
 └────────────────────┘
        ↓
Security Evaluation
        ↓
Release Gate
```

Red teaming should evolve from manual experimentation into automated regression testing.

---

# 14. GitHub Actions & CI/CD

Develop working knowledge of modern software-delivery pipelines.

## CI

Example:

```text
Developer
    ↓
Pull Request
    ↓
GitHub Actions
    ↓
Lint
    ↓
Unit Tests
    ↓
Security Scan
    ↓
Integration Tests
    ↓
RAG / Agent Evaluation
    ↓
AI Security Tests
```

## CD

```text
Build
 ↓
Docker Image
 ↓
Container Registry
 ↓
Development
 ↓
Integration / Evaluation
 ↓
Staging
 ↓
Approval
 ↓
Production
```

Study:

* GitHub Actions
* reusable workflows
* secrets
* environment variables
* artifact management
* Docker builds
* deployment automation
* environment promotion
* approvals
* rollback

## Deployment strategies

Understand:

* rolling deployment
* blue-green deployment
* canary deployment
* feature flags

AI systems require additional consideration because system behavior can change without application-code changes.

Changes may include:

```text
Model
Prompt
Knowledge Base
Embedding Model
Retriever
Reranker
Guardrail
Agent Instructions
Tools
```

Therefore:

> Evaluation must be part of the AI CI/CD lifecycle.

---

# 15. AI Governance as Architecture

Governance should not be treated as a separate approval activity.

Governance requirements should directly influence architecture.

## Examples

### Auditability requirement

```text
Requirement
AI actions must be auditable.

Architecture consequence
Structured and immutable action logs.
```

### Human oversight

```text
Requirement
High-impact actions require human approval.

Architecture consequence
Human-in-the-loop checkpoints.
```

### Knowledge access

```text
Requirement
Users can only access permitted documents.

Architecture consequence
Identity-aware retrieval.
```

### AI quality

```text
Requirement
Models must meet defined quality thresholds.

Architecture consequence
Evaluation gates in CI/CD.
```

### Safety

```text
Requirement
High-risk AI behaviors must be tested before release.

Architecture consequence
Automated red-team and safety test suites.
```

---

# 16. Solution Architecture

Solution architecture is one of the central development areas.

Every proposed AI solution should consider both functional and non-functional requirements.

## Functional requirements

What must the system do?

## Non-functional requirements

Develop strong fluency in:

* latency
* throughput
* scalability
* availability
* reliability
* durability
* resilience
* disaster recovery
* maintainability
* interoperability
* observability
* security
* privacy
* compliance
* cost

## Architecture-decision process

Use:

```text
Requirements
   ↓
Constraints
   ↓
Architecture Options
   ↓
Trade-off Analysis
   ↓
Decision
   ↓
ADR
```

Practice decisions such as:

* Lambda vs ECS vs EKS
* SQS vs EventBridge vs Kinesis
* OpenSearch vs pgvector vs managed knowledge bases
* Bedrock Agents vs AgentCore vs LangGraph vs custom orchestration
* RAG vs fine-tuning
* Step Functions vs agent orchestration
* managed vs self-hosted infrastructure
* direct model access vs LiteLLM gateway

---

# 17. Technology Selection

Technology selection should be systematic rather than preference-driven.

Use a decision framework such as:

| Dimension       | Questions                                                |
| --------------- | -------------------------------------------------------- |
| Requirements    | Does it satisfy the business and technical requirements? |
| Capability      | Does it provide the required features?                   |
| Scalability     | Can it support expected growth?                          |
| Reliability     | What are its failure characteristics?                    |
| Security        | Does it provide appropriate enterprise controls?         |
| Governance      | Can access and behavior be controlled and audited?       |
| Integration     | Does it fit the existing architecture?                   |
| Operations      | Who will operate it?                                     |
| Skills          | Can the team maintain it?                                |
| Cost            | What are development and operating costs?                |
| Time to Market  | How quickly can the solution be delivered?               |
| Lock-in         | How difficult is migration?                              |
| Maintainability | How complex will ongoing support become?                 |

---

# 18. Enterprise AI Architecture

Solution architecture focuses on one application.

Enterprise architecture asks which capabilities should exist once for the organization.

For example, if five teams build RAG applications independently, they may each build:

* ingestion
* model access
* security
* retrieval
* evaluation
* guardrails
* monitoring
* authentication

The architectural question becomes:

> Which of these should become shared platform capabilities?

## Example enterprise AI platform

```text
                   Enterprise AI Platform

┌────────────────────────────────────────────────┐
│ Identity │ Model Gateway │ Secrets │ Policies │
├────────────────────────────────────────────────┤
│ RAG Platform │ Agent Runtime │ Tool Gateway   │
├────────────────────────────────────────────────┤
│ Evaluation │ Observability │ Security Testing │
├────────────────────────────────────────────────┤
│ Governance │ Audit │ Cost Management          │
├────────────────────────────────────────────────┤
│      AWS Data / Compute / AI Foundation        │
└────────────────────────────────────────────────┘
       ↑               ↑               ↑
   Product A        Product B       Product C
```

Study:

* platform vs product responsibilities
* shared services
* service boundaries
* reference architectures
* architectural standards
* paved roads
* reusable components
* centralization vs decentralization
* platform governance
* cost allocation
* enterprise integration

---

# 19. Cross-Functional Technical Leadership

A Staff-level AI specialist must communicate at different technical altitudes.

## AI developers

Discuss:

* implementation
* APIs
* abstractions
* testing
* agent logic
* RAG pipelines

## DevOps engineers

Discuss:

* deployment
* containers
* scalability
* IAM
* networking
* CI/CD
* monitoring
* terraform/IaaC

## ML engineers

Discuss:

* inference
* model lifecycle
* evaluation
* experimentation
* deployment

## Data engineers

Discuss:

* ingestion
* pipelines
* lineage
* schemas
* streaming
* data quality

## Architects

Discuss:

* system boundaries
* NFRs
* trade-offs
* integration
* architectural standards

## Governance and security teams

Discuss:

* risks
* controls
* auditability
* identity
* safety
* approval requirements

## Product owners

Discuss:

* requirements
* prioritization
* feasibility
* technical dependencies

## Business stakeholders

Discuss:

* business value
* cost
* risk
* adoption
* ROI
* delivery strategy

A core Staff-level skill is the ability to move between these perspectives without losing the overall technical direction.

---

# Practical Learning Project

The roadmap will use one continuous enterprise scenario:

## Enterprise Underwriting AI Platform

### Stage 1 — Document Q&A

Build a simple RAG assistant.

### Stage 2 — Production RAG

Introduce:

* APIs
* testing
* scalable deployment
* observability
* authentication
* permission-aware retrieval
* evaluation

### Stage 3 — Enterprise Assistant

Add:

* conversational workflows
* business APIs
* user context
* guardrails
* human oversight

### Stage 4 — Tool-Using Agent

Add:

* tools
* AgentCore
* identity
* state
* memory
* workflow controls

### Stage 5 — Multi-Agent Workflow

Add:

* specialized agents
* orchestration
* agent-to-agent interactions
* failure recovery
* agent evaluation

### Stage 6 — Shared Enterprise AI Platform

Extract reusable capabilities:

* model gateway
* RAG services
* agent runtime
* identity
* evaluation
* observability
* security testing
* governance
* CI/CD

---

# Target Architecture

By the end of the learning program, the goal is to be comfortable reviewing and reasoning about an architecture such as:

```text
                         ENTERPRISE USERS
                                │
                         Entra ID / SSO
                                │
                        Authentication
                                │
                         API / Gateway
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
             RAG Services                Agent Services
                 │                             │
                 │                      AgentCore Runtime
                 │                             │
                 │                       Agent Identity
                 │                             │
                 └──────────────┬──────────────┘
                                │
                          Model Gateway
                             LiteLLM
                                │
                  ┌─────────────┼─────────────┐
                  ↓             ↓             ↓
               Bedrock      Other LLMs    Embeddings
                                │
                         Enterprise Tools
                                │
                         Business Systems


                         DATA & KNOWLEDGE
                                │
                       Enterprise Sources
                                │
                       Ingestion Pipelines
                                │
                  Kinesis / EventBridge / SQS
                                │
                     Search / Vector Stores


                      CROSS-CUTTING CAPABILITIES

      Identity        Entra ID / IAM / Agent Identity
      Security        Guardrails / Red Teaming / IAM
      Observability   OpenTelemetry / CloudWatch
      Evaluation      RAG / Agent / Safety Evaluation
      Governance      Audit / Policies / Approvals
      Delivery        GitHub Actions / CI/CD
```

The goal is not to apply this entire architecture to every project.

A key architecture competency is being able to identify:

> Which components are actually required for this solution?

and equally importantly:

> Which components would introduce unnecessary complexity?

---

# Definition of Success

By the end of this development path, the target capability is to independently:

* translate business requirements into AI system requirements
* identify functional and non-functional requirements
* propose multiple architecture options
* evaluate technical trade-offs
* select appropriate AWS services
* design RAG and agent architectures
* design enterprise authentication and authorization
* reason about human and agent identity
* review Python AI implementations
* review development plans
* assess technology choices
* guide developers during implementation
* troubleshoot and unblock teamss
* design observability strategies
* define RAG and agent evaluation frameworks
* define AI security-testing strategies
* integrate governance into architecture
* design AI-aware CI/CD pipelines
* collaborate effectively across engineering and architecture disciplines
* communicate technical decisions to business stakeholders
* identify reusable enterprise AI platform capabilities
* defend architecture decisions based on requirements rather than preference

The ultimate objective is to move from:

> **Building AI solutions**

to:

> **Defining how AI solutions should be designed, governed, implemented, evaluated, operated, and scaled across the organization.**

