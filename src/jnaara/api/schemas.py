from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class FactCreateRequest(BaseModel):
    """Schema for creating/submitting a single fact."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="The statement or fact content.",
        examples=["Acme Corp announced Q3 revenue of $10M."],
    )
    source: str = Field(
        default="web_ui",
        min_length=1,
        max_length=100,
        description="Source identifier or channel.",
    )
    source_reliability: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Assessed reliability of the source.",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="Optional timestamp of the fact. Defaults to current UTC time if not provided.",
    )
    id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Optional unique fact identifier. Generated automatically if omitted.",
    )


class BulkFactsRequest(BaseModel):
    """Schema for submitting multiple facts in bulk."""

    model_config = ConfigDict(extra="forbid")

    facts: list[FactCreateRequest] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of facts to ingest and process.",
    )
    sequence_name: str | None = Field(
        default=None,
        max_length=100,
        description="Optional label for this sequence/batch.",
    )


class StrategySwitchRequest(BaseModel):
    """Schema for switching conflict resolution strategy."""

    model_config = ConfigDict(extra="forbid")

    strategy: Literal["recency", "corroboration"] = Field(
        ...,
        description="The conflict resolution strategy to activate.",
    )


class ClaimResponse(BaseModel):
    """Schema representing an extracted claim."""

    id: str
    entity: str
    attribute: str
    value: str
    normalized_value: str | None = None
    unit: str | None = None
    temporal_scope: str | None = None
    claim_type: str
    confidence: float
    source_fact_id: str


class DecisionResponse(BaseModel):
    """Schema representing a deterministic or inference decision."""

    id: str
    fact_id: str
    claim_id: str
    action: str
    reason: str
    tier: str
    created_at: datetime


class ResolutionResponse(BaseModel):
    """Schema representing conflict resolution."""

    id: str
    conflict_id: str
    strategy_used: str
    winner: str
    rationale: str
    confidence_delta: float
    resolved_at: datetime


class ConflictResponse(BaseModel):
    """Schema representing a detected conflict."""

    id: str
    conflict_type: str
    entity: str
    attribute: str
    existing_belief_id: str
    incoming_claim_id: str
    severity: str
    description: str
    detected_at: datetime
    resolution: ResolutionResponse | None = None


class FactProcessResponse(BaseModel):
    """Schema for the result of fact ingestion."""

    fact_id: str
    skipped: bool
    claims_count: int
    claims: list[ClaimResponse]
    decisions: list[DecisionResponse]
    conflicts: list[ConflictResponse]
    output_file: str | None = None


class BulkProcessResponse(BaseModel):
    """Schema for bulk fact processing results."""

    total_submitted: int
    total_processed: int
    total_skipped: int
    total_claims: int
    total_conflicts: int
    results: list[FactProcessResponse]
    output_file: str | None = None


class BeliefResponse(BaseModel):
    """Schema for a belief entity."""

    id: str
    entity: str
    attribute: str
    value: str
    confidence: float
    supporting_fact_ids: list[str]
    contradicting_fact_ids: list[str]
    last_updated: datetime
    version: int
    status: str


class BeliefsListResponse(BaseModel):
    """Paginated list of beliefs."""

    total: int
    beliefs: list[BeliefResponse]


class ProvenanceHistoryItem(BaseModel):
    """Belief historical mutation event."""

    version: int
    old_value: str | None
    new_value: str
    old_confidence: float | None
    new_confidence: float
    changed_by_fact_id: str
    reason: str | None
    changed_at: datetime


class ProvenanceResponse(BaseModel):
    """Complete provenance chain for auditability."""

    belief: BeliefResponse
    history: list[ProvenanceHistoryItem]
    supporting_facts: list[dict[str, Any]]
    contradicting_facts: list[dict[str, Any]]
    conflicts: list[ConflictResponse]
    decisions: list[DecisionResponse]


class StatsResponse(BaseModel):
    """Summary statistics for the belief engine."""

    total_facts: int
    active_beliefs: int
    total_conflicts: int
    active_strategy: str
    available_strategies: list[str]
    primary_llm: str
    secondary_llm: str


class GenericSuccessResponse(BaseModel):
    """Generic message response."""

    message: str
    status: str = "success"
