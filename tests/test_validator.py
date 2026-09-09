from datetime import datetime, timezone
from jnaara.analysis.validator import AnalysisValidator
from jnaara.models.domain import (
    Belief,
    Claim,
    Fact,
    FactAnalysis,
    InferenceConflictResult,
)


def test_validator_valid_fact_analysis():
    validator = AnalysisValidator()
    fact = Fact(
        id="E1",
        timestamp=datetime.now(timezone.utc),
        source="NovaTech Press",
        source_reliability="high",
        content="Revenue was $480M",
    )
    claim = Claim(
        entity="NovaTech Inc.",
        attribute="revenue",
        value="$480M",
        normalized_value="480000000",
        unit="USD",
        temporal_scope="Q4 2024",
        claim_type="quantitative",
        confidence=0.95,
        source_fact_id="E1",
    )
    analysis = FactAnalysis(fact_id="E1", claims=[claim])
    val = validator.validate_fact_analysis(analysis, fact)
    assert val.is_valid
    assert len(val.errors) == 0


def test_validator_catches_mismatched_fact_id():
    validator = AnalysisValidator()
    fact = Fact(
        id="E1",
        timestamp=datetime.now(timezone.utc),
        source="NovaTech Press",
        source_reliability="high",
        content="Revenue was $480M",
    )
    claim = Claim(
        entity="NovaTech Inc.",
        attribute="revenue",
        value="$480M",
        normalized_value="480000000",
        claim_type="quantitative",
        confidence=0.95,
        source_fact_id="E2",  # Mismatch!
    )
    analysis = FactAnalysis(fact_id="E1", claims=[claim])
    val = validator.validate_fact_analysis(analysis, fact)
    assert not val.is_valid
    assert any("source_fact_id" in err for err in val.errors)


def test_validator_catches_missing_normalized_value():
    validator = AnalysisValidator()
    fact = Fact(
        id="E1",
        timestamp=datetime.now(timezone.utc),
        source="Press",
        source_reliability="high",
        content="Revenue was $480M",
    )
    claim = Claim(
        entity="NovaTech Inc.",
        attribute="revenue",
        value="$480M",
        normalized_value=None,  # Missing!
        claim_type="quantitative",
        confidence=0.95,
        source_fact_id="E1",
    )
    analysis = FactAnalysis(fact_id="E1", claims=[claim])
    val = validator.validate_fact_analysis(analysis, fact)
    assert not val.is_valid
    assert any("normalized_value" in err for err in val.errors)


def test_validator_inference_result():
    validator = AnalysisValidator()
    claim = Claim(
        entity="Helios Semiconductor",
        attribute="inventory",
        value="Surged 85%",
        claim_type="quantitative",
        source_fact_id="H21",
    )
    beliefs = [
        Belief(
            id="b-1",
            entity="Helios Semiconductor",
            attribute="capacity",
            value="Capacity-constrained",
            confidence=0.9,
        )
    ]

    # Valid conflict result
    valid_res = InferenceConflictResult(
        is_conflict=True,
        conflict_type="inference",
        severity="high",
        explanation="Capacity constrained conflicts with massive inventory buildup",
        related_belief_ids=["b-1"],
        confidence=0.95,
    )
    val = validator.validate_inference_result(valid_res, claim, beliefs)
    assert val.is_valid

    # Missing explanation & severity when is_conflict=True
    invalid_res = InferenceConflictResult(
        is_conflict=True,
        conflict_type="inference",
        severity=None,
        explanation="",
        related_belief_ids=[],
        confidence=0.95,
    )
    val2 = validator.validate_inference_result(invalid_res, claim, beliefs)
    assert not val2.is_valid
    assert len(val2.errors) >= 2
