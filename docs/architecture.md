                    ┌─────────────────────┐
                    │   JSON Dataset      │
                    │   84 Facts          │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Fact Ingestor     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Semantic Analyzer   │
                    │     LangChain       │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
             ┌────────────┐        ┌────────────┐
             │   Groq     │        │   Gemini   │
             └────────────┘        └────────────┘
                    │
                    ▼
             Structured Analysis
                    │
                    ▼
        ┌───────────────────────────┐
        │   Conflict Detection      │
        │   Engine                  │
        └─────────────┬─────────────┘
                      │
             ┌────────┴────────┐
             ▼                 ▼
       Direct Conflict     Inference
                          / Conflict
             │                 │
             └────────┬────────┘
                      ▼
        ┌───────────────────────────┐
        │ Conflict Resolution       │
        │ Strategy                  │
        ├───────────────────────────┤
        │ RecencyWeighted           │
        │ CorroborationWeighted     │
        └─────────────┬─────────────┘
                      │
                      ▼
             ┌────────────────┐
             │ Belief Manager │
             └───────┬────────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Beliefs     Conflicts  Provenance
          │          │          │
          └──────────┼──────────┘
                     ▼
                 SQLite
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
        CLI                  FastAPI
                           (Stretch)