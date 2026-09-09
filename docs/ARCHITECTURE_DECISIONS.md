# Architecture Decision Records (ADR) — Problem C: The Contradicting Memory

## ADR-001: Strict Separation of LLM Interpretation and Deterministic Engine
- **Status:** Accepted
- **Context:** The system must handle contradictions across 84 sequential corporate facts without hallucinations, nondeterministic drift, or silent database mutations.
- **Decision:** The LLM is restricted strictly to semantic extraction, claim normalization, and inference contradiction reasoning. The LLM never writes to the database, never alters belief states directly, and never applies conflict resolution strategies. All state transitions and resolution algorithms are 100% deterministic Python backend code.

## ADR-002: Two-Tier Conflict Detection Architecture
- **Status:** Accepted
- **Context:** Many contradictions are clear quantitative deltas (e.g. $480M -> $412M) or chronological state updates (CEO stepping down -> successor appointed), whereas others require deep multi-fact inference.
- **Decision:** Implement a two-tier detection pipeline:
  - **Tier 1 (Deterministic):** Direct attribute matching, normalized quantitative value comparison, and temporal supersession checks. Tier 1 resolves clear cases with zero LLM inference latency or cost.
  - **Tier 2 (LLM Inference):** Invoked only when Tier 1 cannot decide, or for relational, cross-entity, or qualitative claims. Uses GPT-OSS 120B (with optional Gemini second opinion).

## ADR-003: LLM Provider Abstraction & Model Name Decoupling
- **Status:** Accepted
- **Context:** Hardcoding model names or provider-specific APIs couples the core business logic to external vendors.
- **Decision:** Confine LangChain and provider integrations behind an abstract `LLMProvider` interface in `src/jnaara/llm/`. No core engine module imports LangChain or provider SDKs. Model names (`primary_model`, `secondary_model`) are dynamically configured via environment variables (`JNAARA_PRIMARY_MODEL`, `JNAARA_SECONDARY_MODEL`) with zero hardcoded model names in the core architecture.

## ADR-004: Primary (Groq GPT-OSS 120B) and Secondary (Gemini) Policy
- **Status:** Accepted
- **Context:** Balancing fast inference, high-capacity reasoning, cost efficiency, and resilience.
- **Decision:** Groq GPT-OSS 120B serves as the primary provider for both extraction (low/medium reasoning effort) and Tier 2 inference (high reasoning effort). Google Gemini serves as:
  1. Automatic fallback upon primary rate limits, timeouts, or API failures.
  2. Optional independent second opinion for high-ambiguity multi-entity inferences. Disagreements are preserved as `DualAnalysis` and resolved deterministically.

## ADR-005: Analysis Validator Gate
- **Status:** Accepted
- **Context:** LLM structured JSON output may be syntactically valid JSON yet fail business-level integrity (e.g., mismatched fact IDs, out-of-bounds confidence, missing normalized values).
- **Decision:** Implement `AnalysisValidator` between the LLM output and the conflict engine. Every LLM response is validated for schema compliance, fact references, confidence bounds, and normalization completeness before reaching business logic.

## ADR-006: First-Class Decision Model for Full Auditability
- **Status:** Accepted
- **Context:** In enterprise intelligence, stakeholders require an auditable trail explaining *why* the system believed, discarded, updated, or flagged a contradiction for every incoming claim.
- **Decision:** Introduce a first-class `Decision` entity with actions `NEW_BELIEF`, `UPDATE`, `CONFLICT`, `DISCARD_NOISE`. Every claim results in a persisted `Decision` record linked to its source fact and claim.

## ADR-007: Strategy Pattern for Conflict Resolution
- **Status:** Accepted
- **Context:** The system must allow users to toggle between different resolution philosophies (e.g., recency-biased vs consensus/corroboration-biased) and observe visibly different outcomes.
- **Decision:** Implement the Strategy Pattern via `ResolutionStrategy(ABC)` with two pluggable, deterministic implementations:
  - `RecencyWeightedStrategy`: Balances chronological recency with source reliability.
  - `CorroborationWeightedStrategy`: Groups supporting sources by `independence_group` to reward diverse confirmation over echo chambers.

## ADR-008: Source Independence Modeling
- **Status:** Accepted
- **Context:** Five press releases from the same corporation repeating the same claim do not constitute five independent corroborations.
- **Decision:** The `Source` domain model tracks `independence_group`. Corporate internal releases from the same company share an independence group, preventing circular confirmation from overwhelming genuine independent evidence.

## ADR-009: Relational Persistence with SQLite & SQLAlchemy 2.0
- **Status:** Accepted
- **Context:** The system requires local, zero-setup, atomic persistence with referential integrity and version history tracking.
- **Decision:** Use SQLite with SQLAlchemy 2.0 ORM across 8 relational tables: `facts`, `sources`, `claims`, `beliefs`, `belief_history`, `decisions`, `conflicts`, and `resolutions`. Prior versions are preserved in `belief_history` rather than overwritten.

## ADR-010: Idempotent Fact Ingestion
- **Status:** Accepted
- **Context:** Re-running pipelines or re-ingesting datasets must not create duplicate beliefs, conflicts, or skew confidence metrics.
- **Decision:** Enforce idempotency at the ingestion boundary: `FactIngestor` checks `repository.fact_exists(fact.id)` and safely skips duplicate fact IDs.
