Raw Fact (JSON)
   ↓
Fact Ingestor                       ← Parse, validate (Pydantic), persist raw fact
   ↓
LLM Semantic Analysis               ← GPT-OSS 120B via Groq (primary)
   ↓                                   Gemini only on Groq failure or
Structured FactAnalysis                 optional second opinion
   ↓
┌──────────────────────┐
│  Analysis Validator  │            ← Validates LLM output before business logic
│  (Pydantic + rules)  │              Schema, references, bounds, required fields
└──────────┬───────────┘
           ↓
Candidate Belief Retrieval          ← SQLite query by entity
           ↓
┌──────────────────────────────────────────────────────────────┐
│ Tier 1: Deterministic Conflict Detection                     │
│   • Same entity + same normalized attribute                  │
│   • Different quantitative value → DIRECT conflict           │
│   • Explicitly incompatible states → DIRECT conflict         │
│   • Clear temporal supersession → TEMPORAL_UPDATE            │
│   • No existing belief → NEW_BELIEF                          │
│   • Clearly irrelevant/noise → DISCARD_NOISE                 │
└───────────────────────────┬──────────────────────────────────┘
                            │
                     Can Tier 1 decide?
                      /            \
                    YES             NO
                     │               │
                     ▼               ▼
              Decision          ┌──────────────────────────────────────┐
           (deterministic)      │ Tier 2: LLM Inference Analysis       │
                                │   GPT-OSS 120B (high reasoning)      │
                                │   • Semantic attribute matching       │
                                │   • Cross-entity reasoning            │
                                │   • Relational claim conflicts        │
                                │   • Multi-fact logical inference       │
                                │                                       │
                                │   If ambiguous:                       │
                                │     → Optional Gemini second opinion  │
                                │     → Preserve both analyses          │
                                │     → Deterministic backend evaluates │
                                └───────────────┬──────────────────────┘
                                                │
                                         Analysis Validator
                                                │
                                                ▼
                                           Decision
                                                │
                      ┌─────────────────────────┘
                      ▼
          ┌───────────────────────────┐
          │ Conflict Resolution       │         ← Only for CONFLICT decisions
          │ Strategy (deterministic)  │         ← Strategies NEVER call the LLM
          ├───────────────────────────┤
          │ RecencyWeightedStrategy   │
          │ CorroborationWeighted     │
          │ Strategy                  │
          └─────────────┬─────────────┘
                        │
                        ▼
               ┌────────────────┐
               │ Belief Manager │               ← Applies decision to state
               └───────┬────────┘
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
         Beliefs    Decisions   Provenance
         History    Conflicts   Resolutions
            │          │          │
            └──────────┼──────────┘
                       ▼
                   SQLite
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
          CLI                  FastAPI
                             (Stretch)
