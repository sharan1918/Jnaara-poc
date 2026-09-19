# Jnaara — The Contradicting Memory

> **The LLM interprets information. The deterministic engine maintains belief.**

Jnaara is an auditable belief engine that ingests sequential facts about entities, detects contradictions (both direct and inference-based), resolves conflicts using swappable strategies, and maintains persistent belief state with full provenance tracking.

This is not a vector database or an LLM wrapper. It is a **memory system** that tracks what it believes, what evidence supports or contradicts each belief, how beliefs evolved over time, and why a particular resolution was chosen.

---

## Problem Statement

**Problem C: The Contradicting Memory** — Given a stream of facts from multiple sources with varying reliability, build a system that:

1. Extracts structured claims from unstructured text
2. Detects contradictions — both obvious and inference-based
3. Resolves conflicts using pluggable, deterministic strategies
4. Maintains an auditable trail of every belief change

### Independent Benchmark Evaluation (Held-Out Test Partition)

In accordance with rigorous evaluation methodology, Jnaara's conflict detection engine is evaluated against an independent, partition-isolated benchmark dataset (`held_out_test_set.json` with 60 examples across 15 semantic categories) with **zero data leakage**. 

Below are the empirical results comparing the **Deterministic Offline Mock Baseline** against the **Live LLM Provider** (`openai/gpt-oss-120b` via Groq):

| Metric | Offline Heuristic Mock | **Live LLM (`Live LLM (groq)`)** | Change / Impact |
|:---|:---:|:---:|:---|
| **Recall (Sensitivity)** | 29.6% ($8/27$) | **85.2%** ($23/27$) | **+55.6%** (Complex semantic contradictions caught) |
| **Precision** | **80.0%** ($8/10$) | **79.3%** ($23/29$) | Maintained high signal reliability |
| **F1 Score** | 43.2% | **82.1%** | Balanced harmonic performance nearly doubled |
| **Overall Accuracy** | 60.0% ($36/60$) | **80.0%** ($48/60$) | $+20.0\%$ decision accuracy across 15 categories |
| **Specificity** | **92.9%** ($26/28$) | **80.0%** ($24/30$) | True negative rate on non-contradictions |
| **False Negatives (Misses)** | 19 | **4** | Missed contradictions dropped from 19 down to 4 |
| **False Positives (Alarms)** | **2** | 6 | Minor trade-off: heightened sensitivity on edge cases |
| **Abstention Accuracy** | **40.0%** ($2/5$) | 20.0% ($1/5$) | Cautious identification of unverified rumors |

👉 **Full Live Provider Evaluation Report:** [docs/evaluation_live.md](docs/evaluation_live.md)  
👉 **Offline Heuristic Baseline Report:** [docs/evaluation.md](docs/evaluation.md)

---

### End-to-End Sequence Integration Suite

In addition to independent pairwise evaluation, the repository contains **5 sequential narrative sequences** (138 facts across 15 enterprise entities) used for integration sanity testing and verifying deterministic resolution strategy switching:

| Sequence | Difficulty | Scenario Focus | Tested Conflicts | Resolution Strategy Verified |
|---|---|---|:---:|:---:|
| **Sequence 1** | **Easy** | Revenue restatements, CEO succession, hospital closures | 5 | Recency & Corroboration |
| **Sequence 2** | **Medium** | Partner insolvency, EPA emissions violation, unverified exit rumors | 4 | Recency & Corroboration |
| **Sequence 3** | **Hard** | Supply chain inventory mismatch, dual vendor qualification, trial bias | 4 | Recency & Corroboration |
| **Sequence 4** | **Hard** | FinTech asset quality, stablecoin reserve duration mismatch, loan hedging | 3 | Recency & Corroboration |
| **Sequence 5** | **Hard** | Cybersecurity breach denial vs packet captures, five-nines SLAs | 3 | Recency & Corroboration |
| **Integration Suite** | **Sanity** | **All 138 Facts across 15 Companies (286 Extracted Claims)** | **19** | **58/58 Tests Green** |

👉 **Detailed Integration Sequences Analysis:** [docs/ACCURACY_AND_BENCHMARKS.md](docs/ACCURACY_AND_BENCHMARKS.md)

---

## Architecture

```mermaid
flowchart TD
    %% Styling Classes matching pastel boxed reference
    classDef rootBox fill:#ff99f7,stroke:#18181b,stroke-width:3px,color:#18181b,font-weight:bold,rx:8px,ry:8px;
    classDef lavenderBox fill:#ede9fe,stroke:#7c3aed,stroke-width:1.5px,color:#1e1b4b,font-weight:500,rx:8px,ry:8px;
    classDef blueBox fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#1e3a8a,font-weight:500,rx:8px,ry:8px;
    classDef amberBox fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f,font-weight:500,rx:8px,ry:8px;
    classDef greenBox fill:#d1fae5,stroke:#059669,stroke-width:1.5px,color:#064e3b,font-weight:500,rx:8px,ry:8px;
    classDef redBox fill:#fee2e2,stroke:#dc2626,stroke-width:1.5px,color:#7f1d1d,font-weight:500,rx:8px,ry:8px;
    classDef purpleBox fill:#fae8ff,stroke:#a21caf,stroke-width:1.5px,color:#701a75,font-weight:500,rx:8px,ry:8px;
    classDef cyanBox fill:#e0f2fe,stroke:#0284c7,stroke-width:1.5px,color:#0c4a6e,font-weight:500,rx:8px,ry:8px;
    classDef highlightBox fill:#c7d2fe,stroke:#1e1b4b,stroke-width:2.5px,color:#0f172a,font-weight:bold,rx:8px,ry:8px;

    ROOT["[ 1. INCOMING FACT STREAM ]<br/><b>Sequential Enterprise Facts</b><br/><i>(Source, Reliability, Timestamp)</i>"]:::rootBox
    UI["[ 2. INTERFACE &amp; GATEWAY ]<br/>Svelte 5 Dashboard / Typer CLI / FastAPI Backend"]:::lavenderBox
    
    LLM_EXTRACT["[ 3. SEMANTIC EXTRACTION ]<br/><b>LangChain Provider Boundary</b><br/>Groq 120B / Gemini 3.6 / MockLLM"]:::blueBox
    VALIDATOR["[ 4. ANALYSIS VALIDATOR ]<br/><b>Anti-Hallucination Firewall</b><br/>Pydantic Schema &amp; Confidence Guard"]:::amberBox
    
    RETRIEVAL["[ 5. CANDIDATE LOOKUP ]<br/>SQLite Entity &amp; Property State Query"]:::cyanBox
    
    TIER1["[ 6. TIER 1: DETERMINISTIC FAST-PATH ]<br/><b>Pure Python Numeric &amp; Temporal Engine</b><br/>$0 Token Cost / ~1ms (e.g. $480M &ne; $412M)"]:::greenBox
    TIER2["[ 7. TIER 2: SEMANTIC INFERENCE ]<br/><b>LLM Reasoning on Complex Logic</b><br/>Cross-Entity Distress &amp; Hidden Contradictions"]:::blueBox
    
    NEW_B["[ NEW BELIEF ]<br/>First-Time Entity Property Initialized"]:::greenBox
    UPDATE_B["[ TEMPORAL UPDATE ]<br/>Direct Supersession of Prior Version"]:::purpleBox
    CONFLICT_FLOW["[ CONFLICT DETECTED ]<br/>Contradiction Triggered Between Claims"]:::amberBox
    ABSTAIN_B["[ ABSTAIN / UNCERTAIN ]<br/>Speculative / Rumor Held for Review"]:::amberBox
    DISCARD["[ DISCARD NOISE ]<br/>Low Confidence or Irrelevant Claim"]:::redBox
    
    STRATEGY["[ 8. RESOLUTION STRATEGY ]<br/><b>Pluggable Deterministic Engine</b><br/>Recency vs Corroboration"]:::highlightBox
    
    RECENCY["[ RECENCY STRATEGY ]<br/>Reliability &times; Timestamp Decay<br/><i>(Latest Verified Source Wins)</i>"]:::cyanBox
    CORROB["[ CORROBORATION STRATEGY ]<br/>Independent Group Consensus<br/><i>(Multi-Source Agreement Wins)</i>"]:::cyanBox
    
    MANAGER["[ 9. BELIEF MANAGER ]<br/><b>State Transition Engine</b><br/>Applies Decisions, Calculates Confidence &amp; Logs Audit Trail"]:::highlightBox
    MEMORY["[ 10. SYSTEM PERSISTENCE &amp; PROVENANCE ]<br/><b>SQLite Database + Provenance Graph</b><br/>Facts &rarr; Claims &rarr; Decisions &rarr; Conflicts &rarr; Versioned Beliefs"]:::cyanBox

    ROOT --> UI
    UI --> LLM_EXTRACT
    LLM_EXTRACT --> VALIDATOR
    VALIDATOR --> RETRIEVAL
    RETRIEVAL --> TIER1

    TIER1 -->|"Direct Match (New Fact)"| NEW_B
    TIER1 -->|"Temporal Supersession"| UPDATE_B
    TIER1 -->|"Direct Numeric Mismatch"| CONFLICT_FLOW
    TIER1 -->|"Low-Reliability Rumor / Speculation"| ABSTAIN_B
    TIER1 -->|"Low Confidence / Junk"| DISCARD
    TIER1 -->|"Nuanced / Relational Inference Required"| TIER2

    TIER2 -->|"No Conflict Inferred"| NEW_B
    TIER2 -->|"Semantic Contradiction Inferred"| CONFLICT_FLOW
    TIER2 -->|"Dual Disagreement / Epistemic Uncertainty"| ABSTAIN_B
    TIER2 -->|"Ambiguous / Below Threshold"| DISCARD

    CONFLICT_FLOW --> STRATEGY
    STRATEGY --> RECENCY
    STRATEGY --> CORROB
    RECENCY --> MANAGER
    CORROB --> MANAGER
    NEW_B --> MANAGER
    UPDATE_B --> MANAGER
    ABSTAIN_B --> MANAGER
    DISCARD --> MANAGER

    MANAGER --> MEMORY
```

### Core Architectural Principle

The **LLM** is responsible for semantic understanding:
- Claim extraction and normalization
- Entity/attribute/value interpretation
- Inference-based contradiction detection

The **deterministic Python backend** owns all state:
- Belief state transitions
- Conflict resolution
- Confidence calculation
- Provenance and audit history
- Persistence

The LLM never modifies beliefs or writes to the database directly.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.12+ | Strong backend ecosystem |
| Data validation | Pydantic v2 | Typed Fact, Belief, Conflict, Decision models |
| LLM abstraction | LangChain | Common interface for Groq + Gemini |
| LLM (primary) | Groq (`openai/gpt-oss-120b`) | Fast inference, reasoning-capable |
| LLM (secondary) | Google Gemini (`gemini-3.6-flash`) | Independent provider for fallback/second opinion |
| Conflict resolution | Strategy Pattern | Pluggable, deterministic, auditable |
| Database | SQLite + SQLAlchemy | Persistent beliefs, facts, conflicts, provenance |
| CLI | Typer + Rich | Interactive commands with formatted output |
| Testing | pytest | Unit + integration with mock LLM providers |
| Configuration | pydantic-settings + .env | API keys, model configuration |
| Package management | uv | Fast, modern Python dependency management |

---

## Project Structure

```
jnaara-poc/
├── pyproject.toml
├── .env.example
├── README.md
│
├── data/
│   └── jnaara_memory_facts_dataset.json
│
├── docs/
│   ├── ACCURACY_AND_BENCHMARKS.md # Benchmark accuracy analysis (100% on 3 sequences)
│   ├── EVALUATION_RESULTS.md      # Detailed evaluation runs & metrics
│   ├── architecture.md
│   ├── AI_DEVELOPMENT_LOG.md
│   └── ARCHITECTURE_DECISIONS.md
│
├── src/
│   └── jnaara/
│       ├── config.py
│       ├── models/
│       │   ├── domain.py          # Pydantic v2 domain models
│       │   └── db.py              # SQLAlchemy ORM models
│       ├── db/
│       │   ├── engine.py          # Database setup
│       │   └── repository.py      # CRUD operations
│       ├── ingestion/
│       │   └── ingestor.py        # JSON parsing + fact loading
│       ├── analysis/
│       │   ├── semantic.py        # LLM-powered semantic analyzer
│       │   ├── prompts.py         # Prompt templates
│       │   └── validator.py       # LLM output validation
│       ├── llm/
│       │   ├── provider.py        # LLMProvider ABC
│       │   ├── groq.py            # Groq provider
│       │   ├── gemini.py          # Gemini provider
│       │   └── factory.py         # Provider factory
│       ├── conflict/
│       │   ├── detector.py        # Two-tier conflict detection
│       │   ├── resolver.py        # Conflict resolver orchestrator
│       │   └── strategies/
│       │       ├── base.py        # ResolutionStrategy ABC
│       │       ├── recency.py     # Recency-weighted strategy
│       │       └── corroboration.py  # Corroboration-weighted strategy
│       ├── belief/
│       │   └── manager.py         # Belief lifecycle management
│       └── cli/
│           └── app.py             # Typer CLI
│
└── tests/
    ├── test_models.py
    ├── test_ingestion.py
    ├── test_conflict_detection.py
    ├── test_conflict_resolution.py
    ├── test_belief_manager.py
    └── test_integration.py
```

---

## Setup & Installation

### Prerequisites

- **Python 3.12+** and [**uv**](https://docs.astral.sh/uv/) package manager
- **Node.js 18+** and **npm** (for the web frontend)
- *Optional:* Groq / Google Gemini API keys for live LLM inference (the system includes deterministic mock providers for offline development and test execution)

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/sharan1918/Jnaara-poc.git
cd Jnaara-poc

# Install Python backend dependencies
uv sync

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys and model preferences (optional for mock mode)
```

#### Running the Backend API Server

Start the FastAPI REST backend server:

```bash
# From the project root:
uv run uvicorn jnaara.api.main:app --reload --port 8000
```

- **Backend API URL:** `http://localhost:8000`
- **Interactive OpenAPI / Swagger Docs:** `http://localhost:8000/docs`
- **Health Check Endpoint:** `http://localhost:8000/health`

---

### 2. Frontend (Web UI) Setup

The web dashboard is an interactive visual interface with real-time sequence ingestion, step-by-step belief timeline player, provenance graph visualization, and strategy switching.

```bash
# Navigate to the web frontend directory
cd web

# Install Node.js frontend dependencies
npm install

# Start the Vite development server
npm run dev
```

- **Web Dashboard URL:** `http://localhost:5173` (or the port displayed in your terminal)
- **Production Build:** `npm run build`

---

### 3. Configuration (.env)

```env
JNAARA_GROQ_API_KEY=gsk_...
JNAARA_GOOGLE_API_KEY=AIza...
JNAARA_PRIMARY_LLM=groq
JNAARA_PRIMARY_MODEL=openai/gpt-oss-120b
JNAARA_SECONDARY_LLM=gemini
JNAARA_SECONDARY_MODEL=gemini-3.6-flash
JNAARA_DB_PATH=data/jnaara.db
JNAARA_DEFAULT_STRATEGY=recency
```

---

## CLI Usage

You can also interact with the belief engine directly via the Typer CLI:

### Ingest Facts

```bash
# Ingest a specific sequence (e.g. sequence 1, 2, 3, 4, or 5)
jnaara ingest data/jnaara_memory_facts_dataset.json --sequence sequence_1_easy

# Ingest all sequences
jnaara ingest data/jnaara_memory_facts_dataset.json --sequence all
```

### Query Beliefs

```bash
# View all active beliefs
jnaara beliefs

# Filter by entity
jnaara beliefs --entity "NovaTech Inc."
```

### View Conflicts

```bash
# View all detected conflicts and their resolutions
jnaara conflicts

# Filter by entity
jnaara conflicts --entity "NovaTech Inc."
```

### Provenance

```bash
# Trace the full history of a belief
jnaara provenance <belief-id>
```

### Strategy Switching

The system supports pluggable conflict resolution strategies. Switching strategies changes how the system resolves contradictions, producing different belief states from the same data:

```bash
# Run with recency-weighted strategy
jnaara strategy recency
jnaara ingest data/jnaara_memory_facts_dataset.json --sequence sequence_1_easy
jnaara beliefs --entity "NovaTech Inc."

# Reset and run with corroboration-weighted strategy
jnaara reset
jnaara strategy corroboration
jnaara ingest data/jnaara_memory_facts_dataset.json --sequence sequence_1_easy
jnaara beliefs --entity "NovaTech Inc."
```

**Example: NovaTech enterprise customer count**

Multiple sources report different customer counts with varying reliability:

| Fact | Source | Reliability | Value |
|---|---|---|---|
| E4/E10 | Official filings | High | 340 |
| E12 | Anonymous blog | Low | ~200 |
| E22 | Press release | High | 312 |
| E26 | New CEO statement | High | 298 |

- **Recency strategy** → Believes 298 (E26 is the most recent high-reliability source)
- **Corroboration strategy** → May differ based on independent source diversity

### Independent Evaluation Runner

Run independent evaluation benchmarks against partition-isolated dataset splits (dev, val, test) with full metric and confusion matrix computation:

```bash
# Run held-out test split (60 examples across 15 semantic categories)
jnaara eval --split test

# Run development or validation splits
jnaara eval --split dev
jnaara eval --split val

# Export evaluation metrics to Markdown or JSON
jnaara eval --split test --output docs/evaluation.md --json-output output/evaluation_test.json
```

### Other Commands

```bash
jnaara summary    # Stats dashboard: facts, beliefs, conflicts, resolutions
jnaara strategy   # Show currently active strategy
jnaara reset      # Reset database and start fresh
```

---

## Key Design Decisions

### Two-Tier Conflict Detection

- **Tier 1 (Deterministic)**: Handles obvious cases without LLM calls — same entity, same attribute, different quantitative values. No need to ask an LLM whether `$480M ≠ $412M`.
- **Tier 2 (LLM Inference)**: For nuanced cases requiring semantic reasoning — cross-entity relationships, multi-fact logical incompatibilities, Sequence 3 challenges.

### Decision Model with Epistemic Abstention

Every incoming claim produces a first-class `Decision` record:

```
NEW_BELIEF      — No prior belief exists; initializes first-time entity state
UPDATE          — Temporal supersession of existing belief
CONFLICT        — Contradiction detected, pluggable resolution strategy invoked
ABSTAIN         — High epistemic uncertainty or unverified speculation held without mutating belief state
DISCARD_NOISE   — Irrelevant or unparseable claim
```

### Independent Evaluation & Transparent Metrics

Rather than evaluating the system on author-constructed integration sequences with self-graded 100% claims, Jnaara implements an independent, partition-isolated evaluation framework:
- **Separated Partitions**: Dev (20 examples), Val (15 examples), and Held-Out Test (60 examples) with automated leakage detection.
- **Statistical Metrics**: Full reporting of TP, TN, FP, FN, Precision, Recall, Specificity, F1, Accuracy, and Confusion Matrix.
- **Visible Failure Analysis**: Automatic categorization of false negatives and false positives across 10 diagnosed failure modes (e.g. subtle semantic inference, negation handling, temporal scope shifts).
- **Deterministic Offline Reproducibility**: Evaluator runs out-of-the-box in mock mode without API keys or token expenditure, guaranteeing reproducible numbers across environments.

### Provenance Chain

Every belief is fully traceable:

```
Fact → Claim → Decision → Conflict → Resolution → Belief Version
```

### Analysis Validation

LLM output is validated before reaching business logic. A valid JSON response from an LLM is not automatically a valid business input.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run integration tests only
pytest tests/test_integration.py -v
```

All tests use `MockLLMProvider` — no live LLM calls required for the test suite.

---

## Development Roadmap

### Core (Priority)

- [x] Project structure and configuration
- [x] Pydantic v2 domain models
- [x] SQLite database layer
- [x] LLM provider abstraction (Groq + Gemini with rate limiting & backoff retry)
- [x] Semantic claim extraction
- [x] Analysis validation
- [x] Two-tier conflict detection
- [x] Resolution strategies (Recency + Corroboration)
- [x] Belief manager orchestration
- [x] Provenance and audit trail
- [x] Typer CLI (`ingest`, `beliefs`, `conflicts`, `provenance`, `strategy`, `summary`)
- [x] 58 Unit, integration, abstention, and evaluation metrics tests with 100% pass rate
- [x] Independent held-out evaluation runner with statistical metrics & failure diagnostics (`jnaara eval`)
- [x] Epistemic uncertainty detection and `ABSTAIN` action handling
- [x] Partition-isolated evaluation datasets (dev, val, test) covering 15 semantic categories with zero leakage

### Stretch & Production Additions

- [x] FastAPI REST API with security rate limiter and CORS
- [x] Interactive Svelte Web Dashboard with provenance trees & strategy switcher
- [x] JSON evaluation report generation to `output/` and Markdown to `docs/evaluation.md`
- [x] LLM Rate Limiting, Inter-Fact Pacing & Exponential Backoff Retry

---

## License

This project is part of a take-home assignment for Jnaara.
