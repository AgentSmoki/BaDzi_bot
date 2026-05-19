---
date: 2026-05-19
source_request: "Bogdan — Phase 2.5/3.5/7 decisions"
tasks: ["1.9.x-tech-debt-2", "1.9.x-tech-debt-3", "1.9.x-tech-debt-7"]
verification: "WebSearch + WebFetch on github.com/kuzudb/kuzu — verified 2026-05-19"
---

# Retrieval stack + KuzuDB replacement — research 2026-05-19

Verified findings for three open decisions:
- **Phase 2.5** — embeddings (bge-m3 vs Qwen3 vs e5)
- **Phase 3.5** — LLM concept extraction (Qwen3-3B vs Claude Haiku)
- **#7 upgrade** — what to do given KuzuDB is archived

## A. KuzuDB status — VERIFIED ARCHIVED

[github.com/kuzudb/kuzu](https://github.com/kuzudb/kuzu) — repository **archived and read-only as of October 10, 2025** (Apple acquisition).

- Last release: v0.11.3 (Oct 10, 2025) bundles v0.11.2 + 4 extensions (algo, fts, json, vector).
- v0.11.0 (Jul 13, 2024): **single-file database format** (breaking change — would force docker-compose volume mount refactor).
- v0.9.0 (Apr 2024): async Python API + vector extension + MCP server.
- No further development, no security patches, no new features.

**Implication:** we are running production on a dead project. Migration is inevitable, just a question of urgency.

## B. Embedded graph DB alternatives (2026)

| DB | License | Cypher | Embedded | Vector ext | AI/RAG focus | Best for |
|---|---|---|---|---|---|---|
| **Apache AGE** | Apache 2.0 | OpenCypher | Postgres ext | via pgvector | medium | **You already run managed Postgres on YC** — zero new infra |
| **FalkorDB** | source-available | OpenCypher | Redis-based | native | **high (sparse-matrix optimized for GraphRAG)** | LLM workflows, lowest latency |
| **Memgraph** | commercial | OpenCypher | in-memory | native | high | Lowest-latency real-time, paid |
| **ArcadeDB** | Apache 2.0 | 97.8% Cypher TCK | embeddable | partial | medium | Strict OSI license requirement |
| **HugeGraph** | Apache 2.0 | Gremlin (no Cypher) | distributed | partial | low | Very large scale, Gremlin OK |
| **Neo4j** | GPL + commercial | yes | server-only | yes | high | Already-existing Neo4j team |

**Recommendation for BaDzi_bot:**

Primary: **Apache AGE** on existing YC Managed Postgres.
- 0 new infrastructure (already running PG for users/charts/subscriptions).
- pgvector also drops into same PG → solves Phase 2.5 embeddings naturally.
- OpenCypher syntax → minimal port from our existing Kuzu Cypher.
- Apache 2.0 license, no surprise rug-pulls.

Backup: **FalkorDB** on existing YC Managed Redis.
- Also 0 new infra.
- Sparse-matrix optimization is genuinely faster on GraphRAG workloads.
- License is "source-available" — re-check before commit if it matters.

**Effort to migrate to Apache AGE:** ~6-8 hours
- Rewrite `knowledge/ingest/writer.py` Cypher to Postgres-AGE syntax (mostly identical).
- Rewrite `ai/rag/store.py` to open Postgres connection instead of Kuzu Database (use SQLAlchemy + AGE extension funcs).
- Drop `kuzu_data` volume from docker-compose, kuzu==X.Y.Z from pyproject.
- Update vision.mdc ADR-004.
- Re-ingest via existing pipeline (no .md changes).

## C. Embedding models — Phase 2.5

[bentoml.com/blog](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models) +
[zc277584121.github.io](https://zc277584121.github.io/rag/2026/03/20/embedding-models-benchmark-2026.html)
+ [knowledgesdk.com](https://knowledgesdk.com/blog/embedding-model-comparison-2026):

| Model | Params | Dim | MTEB | RU+ZH | License | Docker overhead |
|---|---:|---:|---:|---|---|---|
| **bge-m3** | 568M | 1024 | 63.0 | native 100+ langs | MIT | ~+500 MB |
| **Qwen3-Embedding-0.6B** | 600M | 1024 | strong | ZH-strong, RU OK | Apache 2.0 | ~+1.2 GB |
| **Qwen3-Embedding-8B** | 8B | 4096 | 70.6 | top-tier | Apache 2.0 | ~+16 GB (too big) |
| **multilingual-e5-large** | 560M | 1024 | 60.0 | OK | MIT | ~+500 MB |

**Recommendation:** **bge-m3**.
- Best multilingual coverage in our weight class.
- Unified dense + sparse + ColBERT in one model — sparse vectors give us BM25-like exact match for free, no need to maintain separate Elasticsearch.
- 500 MB image bump is acceptable.
- Qwen3-Embedding-0.6B better for pure-Chinese workloads; our corpus is 70% Russian, 30% Chinese terminology → bge-m3 wins.

**Trigger to enable:** when keyword+stem retrieval misses important queries. Heuristic: when corpus exceeds 100 docs OR when we collect 30+ real user queries with measured recall < 80%.

## D. LLM concept extraction — Phase 3.5

Models considered for the `extract_concepts(question) → list[str]` pre-retrieval call:

| Model | Provider | Cost/1M tokens | Latency p50 | Russian quality |
|---|---|---:|---:|---|
| **Claude Haiku 4.5** | Anthropic / OpenRouter | $1 in / $5 out | ~400 ms | Excellent |
| **Qwen3-3B** | Alibaba / YC | ~$0.1 in / $0.4 out (YC pricing) | ~600 ms | Good (RU+ZH native) |
| **Qwen3-30B-A3B (current Bazi primary)** | YC | already wired | ~1 s | Excellent |
| **gpt-4o-mini** | OpenAI / OpenRouter | $0.15 in / $0.6 out | ~300 ms | Good |

**Recommendation:** **Qwen3-3B via YC**.
- Same provider as primary Anastasia model → no new API integration.
- 5× cheaper than Haiku, RU+ZH native (matches our domain).
- ~600 ms latency added is acceptable for consultation (already 5-15 s end-to-end).
- Caching keyed on `sha256(question.lower())` in Redis 24h → repeat questions = 0 LLM cost.

**Trigger to enable:** alongside or after bge-m3. Or earlier if we see retrieval missing slang/colloquial phrasings (e.g. "у меня плохо с деньгами" → today's vocab+stem misses → wealth_star slug).

## E. Hybrid stack — final recommendation

```
question
  ↓
extract_concepts(question)              ← Phase 3.5 LLM (cached, Qwen3-3B)
  ↓ list[str]
embed(concepts ⊕ question)              ← Phase 2.5 bge-m3 (sparse + dense)
  ↓ vec1024
graph_query(concepts, vector)           ← Apache AGE OpenCypher
  • related_concepts UNNEST + ANY overlap
  • title CONTAINS (current stem fallback)
  • cosine(node.embedding, query.vector) > 0.7
  • UNION + score merge + top_k
  ↓ list[Node]
format_knowledge_block(nodes)           ← unchanged
  ↓ str
[KNOWLEDGE] in compose_messages         ← unchanged
```

**Phasing:**
1. **Migrate to Apache AGE first** — necessary regardless of B/C decisions, blocks Kuzu archive risk.
2. **Add bge-m3 embeddings (Phase 2.5)** — once AGE is live, embed nodes at ingest, add cosine to retrieve.
3. **Add Qwen3-3B concept extraction (Phase 3.5)** — last, easiest to defer.

## Sources

- [Kuzu GitHub releases](https://github.com/kuzudb/kuzu/releases)
- [ArcadeDB blog — Neo4j alternatives 2026](https://arcadedb.com/blog/neo4j-alternatives-in-2026-a-fair-look-at-the-open-source-options/)
- [FalkorDB vs Neo4j for knowledge graphs](https://www.falkordb.com/blog/best-database-for-knowledge-graphs-falkordb-neo4j/)
- [The Data Quarry — embedded graph DBs](https://thedataquarry.com/blog/embedded-db-2/)
- [BentoML — open-source embedding models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [KnowledgeSDK — embedding model comparison 2026](https://knowledgesdk.com/blog/embedding-model-comparison-2026)
- [Cheney Zhang — 10 models benchmark 2026](https://zc277584121.github.io/rag/2026/03/20/embedding-models-benchmark-2026.html)
- [Medium — Qwen-3 vs BGE-M3 multilingual IR](https://medium.com/@mrAryanKumar/comparative-analysis-of-qwen-3-and-bge-m3-embedding-models-for-multilingual-information-retrieval-72c0e6895413)
