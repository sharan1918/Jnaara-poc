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

The system is tested against **3 sequences of increasing difficulty** (84 facts total):

| Sequence | Difficulty | What It Tests |
|---|---|---|
| Sequence 1 | Easy | Clear contradictions — revenue restatements, CEO changes, count updates |
| Sequence 2 | Medium | Partial updates, conflicting sources, cross-entity inference |
| Sequence 3 | Hard | Nuanced logical incompatibilities requiring multi-fact reasoning |

---

## Architecture

```
Raw Fact (JSON)
   ↓
Fact Ingestor                       ← Parse, validate (Pydantic), persist
   ↓
LLM Semantic Analysis               ← GPT-OSS 120B via Groq (primary)
   ↓                                   Gemini on failure or second opinion
Structured FactAnalysis
   ↓
Analysis Validator                  ← Validates LLM output before business logic
   ↓
Candidate Belief Retrieval          ← SQLite query by entity
   ↓
Tier 1: Deterministic Detection     ← Direct conflicts, temporal updates
   │
   ├── Can decide → Decision
   │
   └── Cannot decide
            ↓
     Tier 2: LLM Inference          ← Semantic/cross-entity reasoning
            ↓
         Decision
            ↓
Conflict Resolution Strategy        ← Deterministic, never calls LLM
   ├── RecencyWeightedStrategy
   └── CorroborationWeightedStrategy
            ↓
Belief Manager                      ← Applies decision to state
            ↓
SQLite (Beliefs, Decisions, Conflicts, Provenance)
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
| LLM (primary) | Groq (GPT-OSS 120B) | Fast inference, reasoning-capable |
| LLM (secondary) | Google Gemini | Independent provider for fallback/second opinion |
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

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Groq API key
- Google Gemini API key

### Installation

```bash
# Clone the repository
git clone https://github.com/sharan1918/Jnaara-poc.git
cd Jnaara-poc

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys and model preferences
```

### Configuration

```env
JNAARA_GROQ_API_KEY=gsk_...
JNAARA_GOOGLE_API_KEY=AIza...
JNAARA_PRIMARY_LLM=groq
JNAARA_PRIMARY_MODEL=<your-groq-model>
JNAARA_SECONDARY_LLM=gemini
JNAARA_SECONDARY_MODEL=<your-gemini-model>
JNAARA_DB_PATH=data/jnaara.db
JNAARA_DEFAULT_STRATEGY=recency
```

---

## Usage

### Ingest Facts

```bash
# Ingest a specific sequence
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

### Decision Model

Every incoming claim produces a first-class `Decision` record:

```
NEW_BELIEF      — No prior belief exists
UPDATE          — Temporal supersession of existing belief
CONFLICT        — Contradiction detected, resolution required
DISCARD_NOISE   — Irrelevant or low-confidence claim
```

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
- [ ] Pydantic v2 domain models
- [ ] SQLite database layer
- [ ] LLM provider abstraction (Groq + Gemini)
- [ ] Semantic claim extraction
- [ ] Analysis validation
- [ ] Two-tier conflict detection
- [ ] Resolution strategies (Recency + Corroboration)
- [ ] Belief manager orchestration
- [ ] Provenance and audit trail
- [ ] CLI
- [ ] Unit and integration tests
- [ ] Sequence 1–3 validation

### Stretch

- [ ] FastAPI REST API
- [ ] Counterfactual queries
- [ ] Real-time streaming

---

## License

This project is part of a take-home assignment for Jnaara.
