# Development Prompts Log

Here is the chronological log of prompts used during the design, development, testing, and evaluation of Jnaara:

---

### Prompt 1: Initial Architecture & Tech Stack Scaffolding
**Model:** Claude 3.7 Sonnet  
"I want to build the system for Problem C: The Contradicting Memory from the take-home document. Suggest a clean, modular Python architecture using Pydantic v2, SQLite/SQLAlchemy, LangChain for model abstraction, and Typer for the CLI. Keep the architecture focused on deterministic memory rather than complex multi-agent workflows."

---

### Prompt 2: Core Philosophy & Separation of Concerns
**Model:** ChatGPT o1  
"Review this architecture plan. The core requirement is that the LLM interprets information, but the deterministic engine maintains belief. Update the plan so the LLM only does semantic claim extraction and inference detection, while Python handles belief state transitions, conflict resolution, confidence calculation, and provenance. Do not let the LLM write directly to the database."

---

### Prompt 3: Domain Entity Modeling & Immutability
**Model:** Claude 3.7 Sonnet  
"Design the core domain models using Pydantic v2. We need explicit entities for Fact (raw ingested input), Claim (atomic normalized statement), Belief (active synthesized understanding), Conflict (detected contradiction between claims/beliefs), Evidence (support links with confidence weights), and Decision (NEW_BELIEF, UPDATE, CONFLICT, DISCARD_NOISE). Ensure beliefs maintain full provenance history with version incrementing."

---

### Prompt 4: Two-Tier Conflict Detection & Analysis Validator
**Model:** Claude 3.7 Sonnet  
"Update the conflict detection design to use two tiers:
Tier 1 (Deterministic): Detect obvious numeric mismatches and temporal updates in pure Python without LLM calls (e.g. $480M vs $412M revenue).
Tier 2 (Semantic Inference): Call the LLM only when reasoning is required (e.g. cross-entity partner distress or implicit contradictions in Sequence 3).
Also add an Analysis Validator as an explicit firewall between LLM JSON output and domain logic to enforce schema validity and prevent hallucinated state mutations."

---

### Prompt 5: Pluggable Conflict Resolution Strategies
**Model:** Claude 3.7 Sonnet  
"Implement two deterministic conflict resolution strategies implementing a common base class:
1. RecencyWeightedStrategy: Uses source reliability weights and chronological timestamps to favor recent credible updates while rejecting low-reliability blog rumors.
2. CorroborationWeightedStrategy: Evaluates independent source diversity and consensus, grouping sources by independence_group so repeated press releases from the same entity don't artificially amplify consensus.
Make the active strategy configurable at runtime."

---

### Prompt 6: Strategy Divergence & NovaTech Benchmark Scenario
**Model:** Claude 3.7 Sonnet  
"Ensure our conflict resolution strategies demonstrate clear, measurable divergence on realistic enterprise data. Implement the NovaTech customer count scenario such that:
Under RecencyWeightedStrategy, the latest verified executive statement wins (298 customers).
Under CorroborationWeightedStrategy, the multi-source cross-verified consensus wins (340 customers).
Add automated regression tests asserting both distinct winning outcomes."

---

### Prompt 7: LLM Provider Abstraction & Model Decoupling
**Model:** Gemini 3.1 Pro  
"Set up the LLM provider layer using an internal LLMProvider abstract base class with LangChain implementations:
Primary: Groq (openai/gpt-oss-120b) for fast semantic analysis
Secondary: Google Gemini (gemini-3.6-flash) for fallback and second opinion on difficult inference cases
Make all model identifiers, API keys, and temperature settings strictly configurable via .env variables (JNAARA_PRIMARY_MODEL, JNAARA_SECONDARY_MODEL) without hardcoding provider strings in business logic."

---

### Prompt 8: Rate Limiting, Pacing Delays & Exponential Backoff
**Model:** Claude 3.7 Sonnet  
"When streaming sequential facts against Groq and Gemini APIs, we need to avoid 429 rate limit errors. Add a token bucket rate limiter with minimum call intervals (2s for Groq, 4s for Gemini), configurable inter-fact pacing delays, and exponential backoff retry with jitter to guarantee zero dropped fact ingestion runs."

---

### Prompt 9: Offline Test Suite & Deterministic Mock LLM Provider
**Model:** Claude 3.7 Sonnet  
"Create a comprehensive test suite in pytest covering domain models, claim normalization, two-tier conflict detection, strategy switching, and full sequence integration. All tests must run offline using a deterministic MockLLMProvider simulating both standard claim extractions and complex multi-fact inferences so no live API keys or network calls are needed to run pytest."

---

### Prompt 10: FastAPI Backend & REST Service Layer
**Model:** Gemini 3.1 Pro  
"Build a FastAPI backend exposing clean REST endpoints:
POST /api/ingest: Ingest individual or batched facts and return structured decision traces.
GET /api/beliefs: Query active beliefs with entity/property filtering and provenance trail.
GET /api/conflicts: Retrieve unresolved and resolved conflict history.
POST /api/strategy: Dynamically toggle between Recency and Corroboration resolution strategies.
Include automatic OpenAPI/Swagger documentation."

---

### Prompt 11: Web UI Dashboard & State Management
**Model:** Claude 3.7 Sonnet  
"Build a clean, high-performance web dashboard using Svelte and Vite to visualize the belief engine in action. The UI should display:
1. Sequence selector (Easy, Medium, Hard, FinTech, Cybersecurity).
2. Incoming stream of facts with color-coded source reliability badges.
3. Active Belief Matrix organized by entity with confidence meters.
4. Conflict resolution log showing competing claims and resolution rationale."

---

### Prompt 12: Interactive Step-by-Step Player & Playback Controls
**Model:** Claude 3.7 Sonnet  
"The web UI needs intuitive controls for evaluating sequential fact processing. Implement:
1. Play / Pause / Step Next / Step Back / Reset playback controls with adjustable interval speeds (0.5s to 3s).
2. Live Fact Card detailing extracted claims, detection tier (Tier 1 vs Tier 2), and engine decision.
3. Interactive strategy toggle that dynamically re-computes beliefs and highlights divergent states."

---

### Prompt 13: Belief Provenance Graph & Version Timeline
**Model:** Claude 3.7 Sonnet  
"Add a belief provenance inspector to the UI. For any active belief, users should be able to click and view:
The full chronological history of prior values (superseded versions).
Supporting evidence facts with source weights, timestamps, and extracted quotes.
Conflicting claims that were evaluated and rejected, along with the mathematical score comparison."

---

### Prompt 14: Synthetic Dataset Expansion & Stress Testing (Sequences 4 & 5)
**Model:** Claude 3.7 Sonnet  
"As encouraged in the assignment document, add 2 new hard contradiction sequences (27 facts each) to stress-test the belief engine:
Sequence 4 (FinTech / Liquidity): Stablecoin 100% liquid reserve claim vs bank call report showing 62% in illiquid commercial real estate loans, instant settlement claims vs frozen merchant receivables, and loan default CDS hedging.
Sequence 5 (Cybersecurity / Cloud SLA): Zero-day breach denial vs forensic packet captures proving kernel driver bypass, five-nines uptime SLA vs $28M penalty credits, and in-region data residency vs global model training.
Run the full evaluation across all 5 sequences and update the accuracy benchmarks."

---

### Prompt 15: Quantitative Benchmark Evaluation & Metrics Engine
**Model:** Gemini 3.1 Pro  
"Implement an automated evaluation engine in src/jnaara/evaluation/ that computes:
Conflict Detection Precision, Recall, and F1 score against ground truth annotations.
Resolution Accuracy under both Recency and Corroboration strategies.
Tier 1 vs Tier 2 latency and token cost breakdown.
Generate formatted Markdown reports summarizing benchmark results across all 5 sequences."

---

### Prompt 16: CLI Interface & Interactive Terminal Tooling
**Model:** Claude 3.7 Sonnet  
"Develop a polished command-line interface using Typer and Rich. Support commands for:
jnaara ingest: Stream facts with live progress bars and colored decision tables.
jnaara query: Inspect active beliefs with confidence scores.
jnaara eval: Run automated benchmarks and output terminal summary cards.
jnaara serve: Launch the API and web UI concurrently."

---

### Prompt 17: Architecture Decision Records & Production Documentation
**Model:** Claude 3.7 Sonnet  
"Document all technical decisions in docs/:
@ARCHITECTURE_DECISIONS.md Record decisions on SQLite persistence, two-tier conflict detection, LangChain boundary encapsulation, and pluggable strategies.
@ACCURACY_AND_BENCHMARKS.md Comprehensive evaluation results, confusion matrices, and failure mode analysis.
@README.md Clear setup instructions, quickstart commands, and architectural diagram."