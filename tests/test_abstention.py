from datetime import datetime, timezone
from uuid import uuid4
import pytest

from jnaara.models.domain import Fact, Decision
from jnaara.evaluation.evaluator import EvaluatorEngine
from jnaara.evaluation.schemas import EvaluationExample


def test_decision_model_abstain_action():
    """Verify that Decision model accepts ABSTAIN action with uncertainty metadata."""
    decision = Decision(
        id=str(uuid4()),
        fact_id="TEST_01",
        claim_id=str(uuid4()),
        action="ABSTAIN",
        reason="High epistemic uncertainty due to unconfirmed hearsay.",
        tier="deterministic",
        uncertainty_score=0.75,
        uncertainty_reason="Unverified rumor with low source reliability.",
    )
    assert decision.action == "ABSTAIN"
    assert decision.uncertainty_score == 0.75
    assert "hearsay" in decision.reason
    assert decision.uncertainty_reason == "Unverified rumor with low source reliability."


def test_conflict_detector_abstains_on_unverified_rumor(manager, repository):
    """Verify ConflictDetector issues an ABSTAIN decision when encountering low-reliability speculation."""
    f1 = Fact(
        id="RUMOR_01",
        timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
        source="Official Press Release",
        source_reliability="high",
        content="Apex Dynamics reported Q3 operating margin of 24.5%.",
    )
    res1 = manager.process_fact(f1)
    assert len(res1.results) > 0
    assert res1.results[0][0].action == "NEW_BELIEF"

    # Conflicting statement from low reliability source with speculative phrasing
    f2 = Fact(
        id="RUMOR_02",
        timestamp=datetime(2025, 1, 20, 10, 0, tzinfo=timezone.utc),
        source="Anonymous Blog Post",
        source_reliability="low",
        content="Unverified rumors suggest Apex Dynamics operating margin might actually be negative due to fraud.",
    )
    res2 = manager.process_fact(f2)

    assert len(res2.results) > 0
    decision = res2.results[0][0]
    assert decision.action == "ABSTAIN"
    assert decision.uncertainty_score is not None and decision.uncertainty_score >= 0.5
    assert "speculation" in decision.reason.lower() or "reliable" in decision.reason.lower() or "uncertain" in decision.reason.lower()

    # Active belief must remain intact and NOT overwritten by the rumor
    active_beliefs = repository.get_beliefs_for_entity("Apex Dynamics", status="active")
    assert len(active_beliefs) == 1
    assert active_beliefs[0].status == "active"
    assert "RUMOR_01" in active_beliefs[0].supporting_fact_ids


def test_conflict_detector_abstains_on_preliminary_estimates(manager, repository):
    """Verify detector abstains when claims are explicitly marked as preliminary or unconfirmed."""
    f1 = Fact(
        id="EST_01",
        timestamp=datetime(2025, 2, 1, 10, 0, tzinfo=timezone.utc),
        source="Audited 10-K Filing",
        source_reliability="high",
        content="Horizon Solar completed 45 solar installations across Nevada.",
    )
    res1 = manager.process_fact(f1)
    assert len(res1.results) > 0

    f2 = Fact(
        id="EST_02",
        timestamp=datetime(2025, 2, 5, 10, 0, tzinfo=timezone.utc),
        source="Local News Blog",
        source_reliability="low",
        content="Unconfirmed rumor that Horizon Solar only completed 20 installations.",
    )
    res2 = manager.process_fact(f2)

    assert len(res2.results) > 0
    decision = res2.results[0][0]
    assert decision.action == "ABSTAIN"
    assert decision.uncertainty_score is not None and decision.uncertainty_score > 0.0

    # The confirmed belief remains intact
    beliefs = repository.get_beliefs_for_entity("Horizon Solar", status="active")
    assert len(beliefs) == 1
    assert "EST_01" in beliefs[0].supporting_fact_ids


def test_abstention_evaluation_example():
    """Verify that EvaluatorEngine records abstention accurately for an UNCERTAIN benchmark example."""
    engine = EvaluatorEngine()

    ex = EvaluationExample(
        id="T_UNC_SPEC",
        category="speculative_vs_settled_assertions",
        entity="Vanguard Aerospace",
        memory_a="Vanguard Aerospace confirmed delivery of 12 commercial satellites in 2024.",
        memory_b="Unverified rumors claim Vanguard Aerospace delivered only 4 satellites amid propulsion defects.",
        ground_truth="UNCERTAIN",
        source_b_reliability="low",
    )

    result = engine.evaluate_example(ex)
    assert result.predicted == "UNCERTAIN"
    assert result.is_correct is True
    assert result.action_taken == "ABSTAIN"
