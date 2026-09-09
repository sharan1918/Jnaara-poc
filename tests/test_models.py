from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from jnaara.models.domain import (
    Belief,
    Claim,
    Conflict,
    Decision,
    Fact,
    FactAnalysis,
    Resolution,
    ResolutionContext,
    Source,
)


def test_fact_model():
    fact = Fact(
        id="E1",
        timestamp=datetime(2025, 1, 10, 9, 0, tzinfo=timezone.utc),
        source="NovaTech Press",
        source_reliability="high",
        content="Revenue was $480M",
    )
    assert fact.id == "E1"
    assert fact.source_reliability == "high"


def test_fact_model_invalid_reliability():
    with pytest.raises(ValidationError):
        Fact(
            id="E1",
            timestamp=datetime.now(timezone.utc),
            source="Test",
            source_reliability="extreme",  # type: ignore
            content="Content",
        )


def test_claim_model_normalization():
    claim = Claim(
        entity="NovaTech Inc.",
        attribute="Q4 2024 revenue",
        value="$480M",
        normalized_value="480000000",
        unit="USD",
        temporal_scope="Q4 2024",
        claim_type="quantitative",
        confidence=0.95,
        source_fact_id="E1",
    )
    assert claim.normalized_value == "480000000"
    assert claim.unit == "USD"
    assert claim.confidence == 0.95


def test_decision_model_actions():
    d = Decision(
        fact_id="E1",
        claim_id="c-123",
        action="NEW_BELIEF",
        reason="Initial fact ingestion",
        tier="deterministic",
    )
    assert d.action == "NEW_BELIEF"
    assert d.tier == "deterministic"


def test_conflict_and_resolution():
    conflict = Conflict(
        conflict_type="direct",
        entity="NovaTech Inc.",
        attribute="Q4 2024 revenue",
        existing_belief_id="b-1",
        incoming_claim_id="c-2",
        severity="high",
        description="Restatement from $480M to $412M",
    )
    resolution = Resolution(
        conflict_id=conflict.id,
        strategy_used="recency",
        winner="incoming_claim",
        rationale="SEC Restatement supersedes prior earnings release",
        confidence_delta=0.08,
    )
    conflict.resolution = resolution
    assert conflict.resolution.winner == "incoming_claim"
    assert conflict.resolution.confidence_delta == 0.08


def test_source_independence_group():
    s1 = Source(
        source_id="s1",
        source_name="NovaTech Earnings Release",
        source_type="press_release",
        reliability="high",
        independence_group="novatech_internal",
    )
    s2 = Source(
        source_id="s2",
        source_name="NovaTech Investor Presentation",
        source_type="press_release",
        reliability="high",
        independence_group="novatech_internal",
    )
    assert s1.independence_group == s2.independence_group
