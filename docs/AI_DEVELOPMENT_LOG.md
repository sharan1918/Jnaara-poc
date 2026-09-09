# AI Development Log — Problem C: The Contradicting Memory

This document tracks the AI-assisted pair programming journey, key decisions, prompt iterations, architecture evolution, and trade-offs made while building the Jnaara belief engine.

---

## 1. Initial Prompting & Problem Scoping
- **Initial Requirement:** The user presented the Problem C takehome challenge ("The Contradicting Memory") involving 84 facts across three difficulty tiers (`sequence_1_easy`, `sequence_2_medium`, `sequence_3_hard`).
- **Initial Challenge:** Ensuring the system handles subtle contradictions (not just simple string or number diffs) while preserving deterministic repeatability and avoiding hallucinated belief modifications.
- **Key Insight:** "The LLM interprets information. The deterministic engine maintains belief." The model should never mutate the persistent state or decide conflict winners autonomously.

---

## 2. Iterations & Refinements

### Iteration 1: LLM Provider Selection & Strategy
- **Prompt:** Evaluate whether to use LiteLLM or LangChain for multi-provider orchestration (Groq primary with GPT-OSS 120B, Google Gemini secondary).
- **Decision:** Do NOT use LiteLLM. Confine LangChain solely at the provider boundary (`src/jnaara/llm/`). The core application depends only on an internal `LLMProvider` ABC.
- **Model Decoupling:** Model names are completely decoupled from code and configured through `JNAARA_PRIMARY_MODEL` and `JNAARA_SECONDARY_MODEL`.

### Iteration 2: Two-Tier Conflict Detection & Analysis Validator
- **Prompt:** How to optimize latency, cost, and accuracy across both obvious numeric updates and complex multi-fact inference?
- **Decision:**
  - Introduce **Tier 1 (Deterministic)** for direct quantitative comparison and temporal updates.
  - Introduce **Tier 2 (LLM Inference)** for qualitative, relational, and multi-fact logical incompatibilities.
  - Introduce **Analysis Validator** as an explicit firewall between LLM structured JSON output and domain business logic.

### Iteration 3: Independence Grouping for Corroboration
- **Prompt:** Prevent echo-chamber effects where five articles repeating the same press release artificially boost corroboration.
- **Decision:** Model `independence_group` on the `Source` entity. Multiple releases from the same corporation share an independence group, ensuring diverse independent reporting outscores internal volume.

### Iteration 4: Pluggable Strategy Pattern & Visible Divergence
- **Prompt:** Demonstrate that changing strategies changes belief outcomes.
- **Implementation:** NovaTech customer count scenario (`298` under Recency vs `340` under Corroboration due to multi-source official confirmation).

---

## 3. Test-Driven Verification & Mocking
- Implemented `MockLLMProvider` capable of simulating both standard extraction and complex inference conflicts across all 84 facts.
- Full test suite includes 23 unit and integration tests covering:
  - Domain models and schema constraints
  - Analysis Validator rules and error catching
  - Tier 1 and Tier 2 conflict detection
  - Recency and Corroboration resolution strategies
  - Idempotent ingestion and provenance audit trail
  - End-to-end multi-fact progression for Sequences 1, 2, and 3
  - Strategy switching outcome differentiation
