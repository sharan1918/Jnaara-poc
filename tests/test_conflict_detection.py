from datetime import datetime, timezone
from jnaara.conflict.detector import ConflictDetector
from jnaara.db.repository import Repository
from jnaara.models.domain import (
    Belief,
    Claim,
    DualAnalysis,
    Fact,
    InferenceConflictResult,
)


def test_tier1_direct_quantitative_conflict(detector: ConflictDetector, repository: Repository):
    # Setup initial belief for NovaTech Q4 revenue = $480M
    b = Belief(
        entity="NovaTech Inc.",
        attribute="Q4 2024 revenue",
        value="$480M",
        confidence=0.95,
        supporting_fact_ids=["E1"],
    )
    repository.upsert_belief(b, changed_by_fact_id="E1")

    # Incoming claim: restatement to $412M
    claim = Claim(
        entity="NovaTech Inc.",
        attribute="Q4 2024 revenue",
        value="$412M",
        normalized_value="412000000",
        unit="USD",
        temporal_scope="Q4 2024",
        claim_type="quantitative",
        confidence=0.95,
        source_fact_id="E7",
    )
    fact = Fact(
        id="E7",
        timestamp=datetime(2025, 1, 22, tzinfo=timezone.utc),
        source="SEC Filing",
        source_reliability="high",
        content="Restatement to $412M",
    )

    decision, conflict = detector.detect(claim, fact)
    assert decision.action == "CONFLICT"
    assert decision.tier == "deterministic"
    assert conflict is not None
    assert conflict.conflict_type == "direct"
    assert conflict.severity == "high"


def test_tier1_temporal_update(detector: ConflictDetector, repository: Repository):
    # Setup initial belief: CEO stepping down
    b = Belief(
        entity="Meridian Healthcare",
        attribute="CEO status",
        value="David Park stepping down",
        confidence=0.9,
        supporting_fact_ids=["E2"],
    )
    repository.upsert_belief(b, changed_by_fact_id="E2")

    # Incoming claim: Dr. Sarah Chen appointed CEO
    claim = Claim(
        entity="Meridian Healthcare",
        attribute="CEO",
        value="Dr. Sarah Chen appointed",
        claim_type="event",
        confidence=0.95,
        source_fact_id="E8",
    )
    fact = Fact(
        id="E8",
        timestamp=datetime(2025, 1, 25, tzinfo=timezone.utc),
        source="Reuters",
        source_reliability="high",
        content="Appointed Dr. Sarah Chen",
    )

    decision, conflict = detector.detect(claim, fact)
    assert decision.action == "UPDATE"
    assert decision.tier == "deterministic"
    assert conflict is None


def test_tier2_inference_conflict(detector: ConflictDetector, repository: Repository):
    # Setup initial belief: Helios Semiconductor capacity-constrained
    b = Belief(
        entity="Helios Semiconductor",
        attribute="capacity",
        value="Capacity-constrained at fab facilities",
        confidence=0.9,
        supporting_fact_ids=["H13"],
    )
    repository.upsert_belief(b, changed_by_fact_id="H13")

    # Incoming claim: inventory surged by 85%
    claim = Claim(
        entity="Helios Semiconductor",
        attribute="inventory",
        value="Finished goods inventory surged 85%",
        claim_type="qualitative",
        confidence=0.9,
        source_fact_id="H21",
    )
    fact = Fact(
        id="H21",
        timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
        source="Supply Chain Report",
        source_reliability="medium",
        content="Inventory up 85%",
    )

    decision, conflict = detector.detect(claim, fact)
    assert decision.action == "CONFLICT"
    assert decision.tier == "inference"
    assert conflict is not None
    assert conflict.conflict_type == "inference"
