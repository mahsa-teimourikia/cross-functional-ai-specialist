"""Rebuild the canonical Course 4 notebook from reviewable cell sources."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).parents[1]
COURSE = ROOT / "curriculum" / "advanced" / "04-production-rag-knowledge-systems"
TARGET = COURSE / "production_rag_knowledge_systems.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Course 4 Lab — Production RAG and Knowledge Systems

- **Scenario:** Northstar's governed underwriting policy corpus
- **Mode:** deterministic, local, and credential-free
- **Expected time:** 4-5 hours plus the knowledge-system ADR

You will trace a policy from source manifest to validated answer, compare sparse/dense/hybrid
retrieval, inject lifecycle and provenance failures, and evaluate relevance and forbidden outcomes
with explicit denominators.
"""
    ),
    md(
        """
## 0. Outcomes, boundaries, and evidence limits

The lab proves application invariants. It performs no PDF parsing, live embedding/model call,
approximate-nearest-neighbour benchmark, cloud query, or production authorization.

- The eight-dimensional semantic fixture makes synonym behaviour inspectable; it is not a model.
- Toy relevance results do not predict production quality.
- Retrieved text is untrusted data and cannot become identity, policy, or instructions.
- The trusted application admits sources, preserves provenance, authorizes before scoring, manages
  lifecycle, and validates claims/citations after generation.
"""
    ),
    code(
        """
# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

course_dir = Path.cwd()
if not (course_dir / "lab.py").exists():
    course_dir = Path.cwd() / "curriculum" / "advanced" / "04-production-rag-knowledge-systems"
assert (course_dir / "lab.py").exists(), "Run from the repository or course directory"
sys.path.insert(0, str(course_dir.resolve()))

from lab import (
    AnswerDraft,
    ChunkState,
    GeneratedClaim,
    GroundedKnowledgeService,
    KnowledgeBoundaryError,
    RetrievalMode,
    RetrievalRequest,
    build_demo_environment,
    cosine_similarity,
    demo_evaluation_cases,
    deterministic_embedding,
    evaluate_retrieval,
)


def denied_reason(operation) -> str:
    try:
        operation()
    except KnowledgeBoundaryError as error:
        return error.reason_code
    raise AssertionError("The operation was expected to fail closed")
"""
    ),
    md(
        """
## 1. Architecture walkthrough

```text
authorized source → manifest → parse/chunk → provenance + ACL → embed/index
                                                             ↓
trusted principal + query → authorize current chunks → sparse/dense → fuse/rerank
                                                             ↓
                                      proposed claims → citation revalidation → answer/refusal
```

The write lifecycle and read lifecycle meet at the current chunk manifest. The model-facing path
never decides tenant, permissions, source authority, deletion, or whether a citation is valid.
"""
    ),
    md(
        """
## 2. Build the deterministic Northstar corpus

The fixture includes two versions of a debt policy, a flood policy, restricted executive guidance,
another tenant's policy, a poisoned upload, and a deleted policy. Alice is a regular underwriter;
Bob has senior/restricted access; Mallory belongs to Southstar.
"""
    ),
    code(
        """
env = build_demo_environment()
alice = env.principals["alice"]
bob = env.principals["bob"]
mallory = env.principals["mallory"]

print("corpus version:", env.index.corpus_version)
for name, principal in env.principals.items():
    print(name, principal.tenant_id, sorted(principal.groups), principal.clearance.name)

assert alice.tenant_id == "northstar"
assert mallory.tenant_id == "southstar"
"""
    ),
    md(
        """
## 3. Inspect ingestion manifests

A manifest binds logical operation, source digest, versions of parsing/chunking/embedding, chunk
IDs, lifecycle state, and corpus publication version. A digest establishes equality to an input;
it does not establish truth or authority.
"""
    ),
    code(
        """
for operation_id, manifest in env.manifests.items():
    print(
        operation_id,
        manifest.document_id,
        f"v{manifest.document_version}",
        manifest.state.value,
        manifest.source_digest[:10],
        manifest.chunk_ids,
    )

assert env.manifests["ingest-debt-v2"].document_version == 2
assert env.manifests["ingest-poison"].state is ChunkState.QUARANTINED
"""
    ),
    md(
        """
## 4. Inspect lifecycle state

The admitted debt v2 supersedes v1. The poisoned upload is quarantined rather than promoted. The
retired policy is tombstoned. None of these non-active chunks may enter candidate scoring.
"""
    ),
    code(
        """
for document_id in ("debt-policy", "uploaded-note", "retired-policy"):
    states = env.index.inspect_states("northstar", document_id)
    print(document_id, [state.value for state in states])

assert ChunkState.SUPERSEDED in env.index.inspect_states("northstar", "debt-policy")
assert env.index.inspect_states("northstar", "uploaded-note") == (ChunkState.QUARANTINED,)
assert env.index.inspect_states("northstar", "retired-policy") == (ChunkState.DELETED,)
"""
    ),
    md(
        """
## 5. Prove idempotent ingestion replay

Retrying the exact logical ingestion operation returns the same manifest without changing corpus
version. Reusing an operation ID for different input would be a conflict.
"""
    ),
    code(
        """
original = env.manifests["ingest-flood"]
flood_document = next(
    chunk for chunk in env.index.chunks_for_policy() if chunk.document_id == "flood-policy"
)

# Rebuild the same source object from the indexed evidence for this deterministic replay.
from lab import Fact, SourceDocument, SourceSection

same_source = SourceDocument(
    document_id=flood_document.document_id,
    tenant_id=flood_document.tenant_id,
    version=flood_document.document_version,
    title=flood_document.title,
    source_uri=flood_document.source_uri,
    producer=flood_document.producer,
    updated_at=flood_document.updated_at,
    effective_from=flood_document.effective_from,
    effective_to=flood_document.effective_to,
    allowed_groups=flood_document.allowed_groups,
    classification=flood_document.classification,
    sections=(
        SourceSection(
            flood_document.locator,
            flood_document.text,
            tuple(Fact(fact.fact_id, fact.text) for fact in flood_document.facts),
        ),
    ),
    authoritative=flood_document.authoritative,
)
before = env.index.corpus_version
replay = env.index.ingest(
    same_source,
    operation_id="ingest-flood",
    expected_current_version=None,
    parser_version="parser-1",
    chunker_version="section-1",
    embedding_model_version="semantic-fixture-1",
    now=env.now + 1,
)
print("replayed:", replay.replayed, "corpus:", before, env.index.corpus_version)
assert replay.replayed and replay.manifest == original
assert env.index.corpus_version == before
"""
    ),
    md(
        """
## 6. Expose the unsafe global-ranking baseline

This intentionally unsafe function scores every active chunk before tenant/ACL policy. Another
tenant's semantically close document can enter the ranked candidates. Never copy this baseline into
an application.
"""
    ),
    code(
        """
def unsafe_global_dense(query: str, top_k: int = 5) -> list[tuple[str, float]]:
    query_vector = deterministic_embedding(query)
    scored = [
        (chunk.document_id, cosine_similarity(query_vector, chunk.embedding))
        for chunk in env.index.chunks_for_policy()
        if chunk.state is ChunkState.ACTIVE
    ]
    return sorted(scored, key=lambda item: (-item[1], item[0]))[:top_k]


unsafe = unsafe_global_dense("liability burden needing an experienced assessor")
print(unsafe)
assert any(document_id == "southstar-debt" for document_id, _ in unsafe)
"""
    ),
    md(
        """
The problem is not merely what the UI displays. Restricted content can influence fusion,
reranking, generation, caches, traces, timing, and model context before a late filter removes it.
The secure retriever authorizes current chunks first.
"""
    ),
    md(
        """
## 7. Sparse retrieval: exact identifiers

The BM25-like branch uses term frequency, inverse document frequency, and length normalization over
the already-authorized candidate corpus. It should find `UW-17`; the semantic fixture intentionally
has no representation for that identifier.
"""
    ),
    code(
        """
sparse_exact = env.retriever.retrieve(
    alice,
    RetrievalRequest("UW-17", RetrievalMode.SPARSE, top_k=3, as_of=env.now),
)
dense_exact = env.retriever.retrieve(
    alice,
    RetrievalRequest("UW-17", RetrievalMode.DENSE, top_k=3, as_of=env.now),
)
print("sparse:", [(hit.document_id, round(hit.sparse_score, 3)) for hit in sparse_exact.hits])
print("dense:", dense_exact.hits)
assert sparse_exact.hits[0].document_id == "debt-policy"
assert dense_exact.hits == ()
"""
    ),
    md(
        """
## 8. Dense retrieval: semantic paraphrases

The paraphrase shares no exact content words with Northstar's debt policy, but the teaching vector
maps liability/debt and assessor/underwriter to common concepts. Sparse search should miss; dense
search should retrieve the authorized Northstar document—not Southstar's closer-looking text.
"""
    ),
    code(
        """
semantic_query = "liability burden needing an experienced assessor"
sparse_semantic = env.retriever.retrieve(
    alice,
    RetrievalRequest(semantic_query, RetrievalMode.SPARSE, top_k=3, as_of=env.now),
)
dense_semantic = env.retriever.retrieve(
    alice,
    RetrievalRequest(semantic_query, RetrievalMode.DENSE, top_k=3, as_of=env.now),
)
print("sparse:", sparse_semantic.hits)
print("dense:", [(hit.document_id, round(hit.dense_score, 3)) for hit in dense_semantic.hits])
assert sparse_semantic.hits == ()
assert dense_semantic.hits[0].document_id == "debt-policy"
assert all(hit.document_id != "southstar-debt" for hit in dense_semantic.hits)
"""
    ),
    md(
        """
## 9. Hybrid retrieval with reciprocal rank fusion

RRF combines rank positions instead of pretending sparse and dense scores share a calibrated
scale. On this fixture, hybrid covers the exact and semantic query classes. That is a measured
local result, not a universal claim.
"""
    ),
    code(
        """
for query in ("UW-17", semantic_query, "inundation zone certification"):
    result = env.retriever.retrieve(
        alice,
        RetrievalRequest(query, RetrievalMode.HYBRID, top_k=3, as_of=env.now),
    )
    print()
    print(query)
    for hit in result.hits:
        print(
            hit.document_id,
            "sparse=", round(hit.sparse_score, 3),
            "dense=", round(hit.dense_score, 3),
            "rrf=", round(hit.fusion_score, 5),
        )
    assert result.hits
"""
    ),
    md(
        """
## 10. Add a bounded deterministic reranker

The teaching reranker considers only the hybrid candidate pool, then adds exact query coverage and
a small provenance signal. Production rerankers may be cross-encoders or late-interaction models;
they still cannot recover absent candidates or see unauthorized text.
"""
    ),
    code(
        """
hybrid = env.retriever.retrieve(
    bob,
    RetrievalRequest(
        "executive officer waiver approvals",
        RetrievalMode.HYBRID,
        top_k=3,
        as_of=env.now,
    ),
)
reranked = env.retriever.retrieve(
    bob,
    RetrievalRequest(
        "executive officer waiver approvals",
        RetrievalMode.HYBRID_RERANK,
        top_k=3,
        as_of=env.now,
    ),
)
print("hybrid:", [(hit.document_id, round(hit.final_score, 4)) for hit in hybrid.hits])
print("reranked:", [(hit.document_id, round(hit.final_score, 4)) for hit in reranked.hits])
assert reranked.hits[0].document_id == "executive-waiver"
"""
    ),
    md(
        """
## 11. Inspect the retrieval trace

The trace exposes mode, policy/corpus versions, aggregate candidate counts, result count, and a
reason code. It does not expose rejected document IDs or private model reasoning.
"""
    ),
    code(
        """
trace = reranked.trace
print(trace)
assert trace.policy_version == env.policy.version
assert trace.corpus_version == env.index.corpus_version
assert trace.authorized_current_candidates < trace.total_index_chunks
assert trace.reason_code == "AUTHORIZED_RESULTS"
"""
    ),
    md(
        """
## 12. Authorization changes candidate generation

Alice cannot retrieve restricted executive guidance. Bob can. Both requests use identical query
text, proving that role words in a prompt do not establish access.
"""
    ),
    code(
        """
restricted_request = RetrievalRequest(
    "executive officer waiver approvals",
    RetrievalMode.HYBRID,
    top_k=5,
    as_of=env.now,
)
regular = env.retriever.retrieve(alice, restricted_request)
senior = env.retriever.retrieve(bob, restricted_request)
print("regular:", [hit.document_id for hit in regular.hits])
print("senior:", [hit.document_id for hit in senior.hits])
assert "executive-waiver" not in {hit.document_id for hit in regular.hits}
assert "executive-waiver" in {hit.document_id for hit in senior.hits}
"""
    ),
    md(
        """
## 13. Cross-tenant, deleted, superseded, and poisoned evidence stay out

Even a query naming the forbidden material cannot make it rank. The result set must be empty or
contain only evidence authorized for the trusted principal.
"""
    ),
    code(
        """
attack_query = "southstar retired legacy system prompt executive waiver"
attack_result = env.retriever.retrieve(
    alice,
    RetrievalRequest(attack_query, RetrievalMode.HYBRID, top_k=20, as_of=env.now),
)
returned = {hit.document_id for hit in attack_result.hits}
for forbidden in ("southstar-debt", "retired-policy", "uploaded-note", "executive-waiver"):
    assert forbidden not in returned
assert all(
    hit.document_version == 2
    for hit in attack_result.hits
    if hit.document_id == "debt-policy"
)
print("safe returned documents:", sorted(returned))
"""
    ),
    md(
        """
## 14. Entitlement changes invalidate old principal state

A long-lived principal object cannot preserve removed access. The policy registry rejects its stale
entitlement version before candidate selection.
"""
    ),
    code(
        """
lifecycle_env = build_demo_environment(now=env.now)
lifecycle_alice = lifecycle_env.principals["alice"]
lifecycle_env.policy.change_entitlements(lifecycle_alice.identity_key)
reason = denied_reason(
    lambda: lifecycle_env.retriever.retrieve(
        lifecycle_alice,
        RetrievalRequest("debt", RetrievalMode.SPARSE, as_of=lifecycle_env.now),
    )
)
print(reason)
assert reason == "STALE_ENTITLEMENTS"
"""
    ),
    md(
        """
## 15. Evaluate retrieval with explicit denominators

The labelled suite contains four relevant documents across exact, semantic, flood, and restricted
query cases. Recall uses the relevant-document population. MRR and nDCG are averaged across queries.
Forbidden outcomes count actual forbidden documents returned—not blocked attempts.
"""
    ),
    code(
        """
cases = demo_evaluation_cases(env)
reports = {
    mode.value: evaluate_retrieval(env.retriever, cases, mode=mode)
    for mode in (
        RetrievalMode.SPARSE,
        RetrievalMode.DENSE,
        RetrievalMode.HYBRID,
        RetrievalMode.HYBRID_RERANK,
    )
}
for name, report in reports.items():
    print(name, report)

hybrid_report = reports[RetrievalMode.HYBRID.value]
assert hybrid_report.relevant_documents == 4
assert hybrid_report.recall_at_k == 1.0
assert hybrid_report.forbidden_outcomes == 0
assert hybrid_report.valid_queries_with_no_hits == 0
"""
    ),
    md(
        """
The sparse and dense branches fail different slices; hybrid closes both gaps in this constructed
set. Before adopting that result, expand the evaluation with real query distributions, no-answer
cases, graded judgments, parser types, languages, temporal questions, filters, and tenant skew.
"""
    ),
    md(
        """
## 16. Generate one provenance-bound answer

The deterministic generator proposes a fact from retrieved evidence. The service verifies the
citation belongs to this request, rechecks current policy/lifecycle/digest, and confirms the cited
fact supports the exact claim.
"""
    ),
    code(
        """
answer = env.service.answer(
    alice,
    RetrievalRequest("UW-17", RetrievalMode.HYBRID, top_k=3, as_of=env.now),
)
print(answer)
assert answer.state == "grounded"
assert set(answer.citation_ids) <= set(answer.retrieved_ids)
assert answer.claims[0].fact_id == "debt-form"
"""
    ),
    md(
        """
## 17. Failure injection — forged citation

Typed output is not trusted output. This generator emits a well-shaped citation that was never
retrieved. The application rejects it.
"""
    ),
    code(
        """
class ForgedGenerator:
    def generate(self, query, hits):
        del query, hits
        return AnswerDraft(
            (GeneratedClaim("invented", "Invented policy.", ("not-retrieved",)),)
        )


forged_service = GroundedKnowledgeService(
    env.index, env.policy, env.retriever, ForgedGenerator()
)
forged_reason = denied_reason(
    lambda: forged_service.answer(
        alice,
        RetrievalRequest("UW-17", RetrievalMode.HYBRID, 3, env.now),
    )
)
print(forged_reason)
assert forged_reason == "FORGED_CITATION"
"""
    ),
    md(
        """
## 18. Failure injection — unsupported claim

A real retrieved chunk is not automatic support for any nearby sentence. This generator cites a
retrieved chunk but invents a fact ID and text. Claim-level support validation fails.
"""
    ),
    code(
        """
class UnsupportedGenerator:
    def generate(self, query, hits):
        del query
        return AnswerDraft(
            (GeneratedClaim("invented", "Invented policy.", (hits[0].chunk_id,)),)
        )


unsupported_service = GroundedKnowledgeService(
    env.index, env.policy, env.retriever, UnsupportedGenerator()
)
unsupported_reason = denied_reason(
    lambda: unsupported_service.answer(
        alice,
        RetrievalRequest("UW-17", RetrievalMode.HYBRID, 3, env.now),
    )
)
print(unsupported_reason)
assert unsupported_reason == "UNSUPPORTED_CLAIM"
"""
    ),
    md(
        """
## 19. Failure injection — evidence deleted during generation

Retrieval is only a time-of-check. The custom generator tombstones the retrieved document before
returning its otherwise valid claim. Citation-time revalidation closes the lifecycle race.
"""
    ),
    code(
        """
race_env = build_demo_environment(now=env.now)


class DeleteDuringGeneration:
    def generate(self, query, hits):
        del query
        hit = hits[0]
        race_env.index.delete(
            tenant_id="northstar",
            document_id=hit.document_id,
            expected_current_version=hit.document_version,
            operation_id="delete-during-generation",
            now=race_env.now + 1,
        )
        fact = hit.facts[0]
        return AnswerDraft(
            (GeneratedClaim(fact.fact_id, fact.text, (hit.chunk_id,)),)
        )


race_service = GroundedKnowledgeService(
    race_env.index,
    race_env.policy,
    race_env.retriever,
    DeleteDuringGeneration(),
)
race_reason = denied_reason(
    lambda: race_service.answer(
        race_env.principals["alice"],
        RetrievalRequest("UW-17", RetrievalMode.HYBRID, 3, race_env.now),
    )
)
print(race_reason)
assert race_reason == "CHUNK_DELETED"
"""
    ),
    md(
        """
## 20. Failure injection — stale ingestion plan

The live debt policy is version 2. An ingestion plan created against version 1 cannot publish a new
version, even if its proposed source object is otherwise well formed.
"""
    ),
    code(
        """
from lab import make_document

stale_source = make_document(
    "debt-policy",
    "northstar",
    3,
    "Debt service policy",
    (SourceSection("section:threshold", "Proposed threshold is 0.40."),),
    now=env.now + 10,
)
version_reason = denied_reason(
    lambda: env.index.ingest(
        stale_source,
        operation_id="stale-ingestion-plan",
        expected_current_version=1,
        parser_version="parser-1",
        chunker_version="section-1",
        embedding_model_version="semantic-fixture-1",
        now=env.now + 10,
    )
)
print(version_reason)
assert version_reason == "VERSION_CONFLICT"
"""
    ),
    md(
        """
## 21. What the local lab proves—and does not

**Proved by executable behavior:** operation replay/conflict, monotonic publication, quarantine,
supersession/deletion exclusion, authorization-before-scoring, retrieval-mode differences,
request-bound citations, claim support, and lifecycle revalidation.

**Not proved:** parser accuracy, cryptographic connector identity, production embedding relevance,
ANN recall/latency, distributed atomicity, cloud ACL propagation, model faithfulness, privacy,
regional resilience, throughput, cost, or real user outcomes.
"""
    ),
    md(
        """
## 22. Technology decision frame

| Option | Start here when | Prove before adoption |
|---|---|---|
| PostgreSQL + pgvector | relational truth, bounded vectors | filtered ANN recall, headroom |
| OpenSearch / Elasticsearch | lexical/filter/hybrid depth | cluster ownership, consistency |
| vector-first service | vector scale or managed features | isolation, lexical fit, portability |
| managed cloud search | integrated delivery | preview limits, ACL sync, rollback |

Frameworks can assemble the pipeline but do not own the knowledge contract. Record the decision,
reversal trigger, source of truth, filter semantics, consistency, SLOs, cost, and migration path.
"""
    ),
    md(
        """
## 23. Conditional state-of-the-art upgrades

- Query rewriting/expansion: evaluate intent drift and cost.
- HyDE: evaluate zero-shot semantic queries and invented terminology.
- Late interaction: evaluate quality versus multi-vector storage/latency.
- Parent-child or RAPTOR: evaluate cross-section questions and derived-summary lineage.
- GraphRAG: evaluate global/relational questions and extraction/deletion quality.
- ColPali-style multimodal retrieval: evaluate tables, figures, layout, cost, and citation UX.

Adopt an upgrade only when a labelled slice improves enough to justify its new failure modes and
operating burden.
"""
    ),
    md(
        """
## 24. Production upgrade

- Preserve immutable originals, source manifests, page/section coordinates, and parser errors.
- Use authenticated least-privilege connectors and validate type, size, malware, metadata, and ACL.
- Publish immutable versioned indexes via alias/manifest switch with rollback.
- Propagate permission changes and deletes under explicit SLOs; reconcile source and projections.
- Treat embeddings as sensitive derived data with source-equivalent encryption and retention.
- Benchmark exact versus ANN retrieval under representative filters and tenant skew.
- Shadow-evaluate embedding/chunking/ranking upgrades before dual-read canary promotion.
- Trace safe IDs, policy/corpus/model versions, cutoffs, latency, costs, and reason codes.
- Calibrate automated answer/citation judges against blinded human labels.
- Measure ingest freshness, forbidden outcomes, stale/deleted exposure, valid work blocked, answer
  success, p95/p99 latency, and cost per successful compliant answer.
"""
    ),
    md(
        """
## 25. Portfolio exercises

1. Add future-effective and expired sources; prove temporal filtering and citation revalidation.
2. Add a corrected version after quarantine and define whether version gaps are valid.
3. Implement weighted score fusion; compare against RRF on the same labelled set.
4. Add graded relevance and show how nDCG differs from first-hit MRR.
5. Add parent-child evidence without counting overlapping chunks as independent corroboration.
6. Design the safe retrieval-cache key and invalidation events.
7. Benchmark exact versus ANN search under ACL filters on a realistic synthetic corpus.
8. Write the knowledge-system ADR and the dual-index migration/rollback plan.
"""
    ),
    md(
        """
## 26. Completion checklist

- [x] Source, processing, access, lifecycle, and citation provenance are explicit.
- [x] Ingestion replay and stale publication fail deterministically.
- [x] Authorization/current-state filtering precedes all scoring.
- [x] Sparse, dense, hybrid, and reranked modes have inspectable behaviour.
- [x] Cross-tenant, restricted, superseded, deleted, and poisoned evidence do not leak.
- [x] Retrieval metrics name their relevant and forbidden populations.
- [x] Forged and unsupported citations fail closed.
- [x] Citation evidence is revalidated after generation.
- [ ] Your data contract, evaluation, ADR, threat model, and migration plan are review-ready.

Complete the Course 4 checkpoint after explaining the production gaps and architecture reversal
triggers.
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
