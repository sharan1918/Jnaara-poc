from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class Fact(BaseModel):
    """Raw ingested fact from sequential input."""

    id: str
    timestamp: datetime
    source: str
    source_reliability: Literal["high", "medium", "low"]
    content: str

    model_config = ConfigDict(extra="ignore")


class Source(BaseModel):
    """Source provenance and independence metadata for corroboration analysis."""

    source_id: str
    source_name: str
    source_type: Literal[
        "company_filing",
        "press_release",
        "analyst_report",
        "news",
        "regulatory",
        "leaked",
        "blog",
        "interview",
        "other",
    ]
    reliability: Literal["high", "medium", "low"]
    independence_group: str | None = None

    model_config = ConfigDict(extra="ignore")


class Claim(BaseModel):
    """Structured claim extracted from a fact by LLM analysis."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    entity: str
    attribute: str
    value: str
    normalized_value: str | None = None
    unit: str | None = None
    temporal_scope: str | None = None
    claim_type: Literal["quantitative", "qualitative", "relational", "event"]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_fact_id: str

    model_config = ConfigDict(extra="ignore")


class FactAnalysis(BaseModel):
    """Output container of LLM claim extraction for a single fact."""

    fact_id: str
    claims: list[Claim] = Field(default_factory=list)
    entities_mentioned: list[str] = Field(default_factory=list)
    temporal_context: str | None = None
    analysis_notes: str = ""

    model_config = ConfigDict(extra="ignore")


class Decision(BaseModel):
    """First-class record of what the system decided regarding a claim."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    fact_id: str
    claim_id: str
    action: Literal["NEW_BELIEF", "UPDATE", "CONFLICT", "DISCARD_NOISE", "ABSTAIN"]
    reason: str
    tier: Literal["deterministic", "inference"]
    uncertainty_score: float | None = None
    uncertainty_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(extra="ignore")


class Resolution(BaseModel):
    """Deterministic resolution of a detected conflict."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    conflict_id: str
    strategy_used: str
    winner: Literal["existing_belief", "incoming_claim"]
    rationale: str
    confidence_delta: float = 0.0
    resolved_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(extra="ignore")


class Conflict(BaseModel):
    """Contradiction detected between an incoming claim and an existing belief."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    conflict_type: Literal["direct", "temporal_update", "source_disagreement", "inference"]
    entity: str
    attribute: str
    existing_belief_id: str
    incoming_claim_id: str
    severity: Literal["high", "medium", "low"]
    description: str
    detected_at: datetime = Field(default_factory=utc_now)
    resolution: Resolution | None = None

    model_config = ConfigDict(extra="ignore")


class Belief(BaseModel):
    """Current state of belief held by the system."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    entity: str
    attribute: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    contradicting_fact_ids: list[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=utc_now)
    version: int = 1
    status: Literal["active", "superseded", "disputed"] = "active"

    model_config = ConfigDict(extra="ignore")


class ResolutionContext(BaseModel):
    """Evidence bundle provided to resolution strategies."""

    existing_belief: Belief
    incoming_claim: Claim
    existing_sources: list[Source] = Field(default_factory=list)
    incoming_source: Source
    all_related_facts: list[Fact] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class InferenceConflictResult(BaseModel):
    """Structured result from Tier 2 inference conflict analysis."""

    is_conflict: bool
    conflict_type: Literal["inference", "source_disagreement"] | None = None
    severity: Literal["high", "medium", "low"] | None = None
    explanation: str = ""
    related_belief_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="ignore")


class DualAnalysis(BaseModel):
    """Result when both Groq and Gemini are consulted."""

    groq_analysis: InferenceConflictResult
    gemini_analysis: InferenceConflictResult | None = None
    agreement: bool = True
    combined_notes: str | None = None

    model_config = ConfigDict(extra="ignore")


class ProcessingResult(BaseModel):
    """Result of processing a single fact through the pipeline."""

    fact_id: str
    skipped: bool = False
    claims: list[Claim] = Field(default_factory=list)
    results: list[tuple[Decision, Conflict | None]] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ProvenanceChain(BaseModel):
    """Full audit trail of how a belief came to be and evolved."""

    belief: Belief
    history: list[dict[str, Any]] = Field(default_factory=list)
    supporting_facts: list[Fact] = Field(default_factory=list)
    contradicting_facts: list[Fact] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    resolutions: list[Resolution] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
