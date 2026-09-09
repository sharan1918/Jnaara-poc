from datetime import datetime, timezone
from jnaara.conflict.strategies.corroboration import CorroborationWeightedStrategy
from jnaara.conflict.strategies.recency import RecencyWeightedStrategy
from jnaara.models.domain import (
    Belief,
    Claim,
    Conflict,
    Fact,
    ResolutionContext,
    Source,
)


def test_recency_strategy_prefers_newer_high_reliability():
    strat = RecencyWeightedStrategy()

    conflict = Conflict(
        conflict_type="direct",
        entity="NovaTech Inc.",
        attribute="revenue",
        existing_belief_id="b-1",
        incoming_claim_id="c-2",
        severity="high",
        description="Revenue restatement",
    )

    context = ResolutionContext(
        existing_belief=Belief(
            id="b-1",
            entity="NovaTech Inc.",
            attribute="revenue",
            value="$480M",
            confidence=0.95,
            supporting_fact_ids=["E1"],
            last_updated=datetime(2025, 1, 10, tzinfo=timezone.utc),
        ),
        incoming_claim=Claim(
            id="c-2",
            entity="NovaTech Inc.",
            attribute="revenue",
            value="$412M",
            claim_type="quantitative",
            confidence=0.98,
            source_fact_id="E7",
        ),
        existing_sources=[
            Source(
                source_id="s1",
                source_name="NovaTech Earnings Release",
                source_type="press_release",
                reliability="high",
                independence_group="novatech_internal",
            )
        ],
        incoming_source=Source(
            source_id="s2",
            source_name="SEC Filing (8-K)",
            source_type="company_filing",
            reliability="high",
            independence_group="regulatory_enforcement",
        ),
        all_related_facts=[
            Fact(
                id="E1",
                timestamp=datetime(2025, 1, 10, tzinfo=timezone.utc),
                source="NovaTech Earnings Release",
                source_reliability="high",
                content="Reported $480M",
            ),
            Fact(
                id="E7",
                timestamp=datetime(2025, 1, 22, tzinfo=timezone.utc),
                source="SEC Filing (8-K)",
                source_reliability="high",
                content="Restatement to $412M",
            ),
        ],
    )

    res = strat.resolve(conflict, context)
    assert res.winner == "incoming_claim"
    assert "RecencyStrategy" in res.rationale


def test_recency_strategy_low_reliability_newer_does_not_beat_high_rel():
    strat = RecencyWeightedStrategy()

    conflict = Conflict(
        conflict_type="direct",
        entity="PeakFin Capital",
        attribute="rating",
        existing_belief_id="b-1",
        incoming_claim_id="c-2",
        severity="medium",
        description="Rating discrepancy",
    )

    context = ResolutionContext(
        existing_belief=Belief(
            id="b-1",
            entity="PeakFin Capital",
            attribute="rating",
            value="Target $85 Buy",
            confidence=0.95,
            supporting_fact_ids=["M8"],
            last_updated=datetime(2025, 3, 5, tzinfo=timezone.utc),
        ),
        incoming_claim=Claim(
            id="c-2",
            entity="PeakFin Capital",
            attribute="rating",
            value="Rumored exit at $62",
            claim_type="qualitative",
            confidence=0.5,
            source_fact_id="M10",
        ),
        existing_sources=[
            Source(
                source_id="s1",
                source_name="PeakFin Research",
                source_type="analyst_report",
                reliability="high",
                independence_group="analyst_peakfin",
            )
        ],
        incoming_source=Source(
            source_id="s2",
            source_name="Anonymous Forum Post",
            source_type="blog",
            reliability="low",
            independence_group="forum_rumors",
        ),
        all_related_facts=[
            Fact(
                id="M8",
                timestamp=datetime(2025, 3, 5, tzinfo=timezone.utc),
                source="PeakFin Research",
                source_reliability="high",
                content="Target $85 Buy",
            ),
            Fact(
                id="M10",
                timestamp=datetime(2025, 3, 7, tzinfo=timezone.utc),
                source="Anonymous Forum Post",
                source_reliability="low",
                content="Rumored exit at $62",
            ),
        ],
    )

    res = strat.resolve(conflict, context)
    assert res.winner == "existing_belief"


def test_corroboration_strategy_independent_sources_beat_single_group():
    strat = CorroborationWeightedStrategy()

    conflict = Conflict(
        conflict_type="direct",
        entity="NovaTech Inc.",
        attribute="customers",
        existing_belief_id="b-1",
        incoming_claim_id="c-2",
        severity="medium",
        description="Customer count disagreement",
    )

    # Existing belief has 2 independent source groups (internal + press)
    context = ResolutionContext(
        existing_belief=Belief(
            id="b-1",
            entity="NovaTech Inc.",
            attribute="customers",
            value="340",
            confidence=0.9,
            supporting_fact_ids=["E4", "E10"],
        ),
        incoming_claim=Claim(
            id="c-2",
            entity="NovaTech Inc.",
            attribute="customers",
            value="298",
            claim_type="quantitative",
            confidence=0.85,
            source_fact_id="E26",
        ),
        existing_sources=[
            Source(
                source_id="s1",
                source_name="Investor Presentation",
                source_type="press_release",
                reliability="high",
                independence_group="novatech_internal",
            ),
            Source(
                source_id="s2",
                source_name="CNBC Interview",
                source_type="news",
                reliability="high",
                independence_group="press_cnbc",
            ),
        ],
        incoming_source=Source(
            source_id="s3",
            source_name="CEO Announcement",
            source_type="press_release",
            reliability="high",
            independence_group="novatech_internal",
        ),
    )

    res = strat.resolve(conflict, context)
    assert res.winner == "existing_belief"
    assert "CorroborationStrategy" in res.rationale
