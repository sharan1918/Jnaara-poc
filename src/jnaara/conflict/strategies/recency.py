from datetime import datetime, timezone
from uuid import uuid4
from jnaara.conflict.strategies.base import ResolutionStrategy
from jnaara.models.domain import Conflict, Resolution, ResolutionContext


class RecencyWeightedStrategy(ResolutionStrategy):
    """Prefers more recent information, strongly weighted by source reliability."""

    RELIABILITY_WEIGHTS = {"high": 1.0, "medium": 0.7, "low": 0.4}

    def resolve(self, conflict: Conflict, context: ResolutionContext) -> Resolution:
        # Existing belief metrics
        existing_facts = [
            f for f in context.all_related_facts if f.id in context.existing_belief.supporting_fact_ids
        ]
        if existing_facts:
            existing_ts = max(f.timestamp for f in existing_facts)
            existing_rel = max(
                (self.RELIABILITY_WEIGHTS.get(f.source_reliability, 0.5) for f in existing_facts),
                default=0.7,
            )
        else:
            existing_ts = context.existing_belief.last_updated
            existing_rel = 0.7

        # Incoming claim metrics
        incoming_facts = [f for f in context.all_related_facts if f.id == context.incoming_claim.source_fact_id]
        if incoming_facts:
            incoming_ts = incoming_facts[0].timestamp
            incoming_rel = self.RELIABILITY_WEIGHTS.get(incoming_facts[0].source_reliability, 0.5)
        else:
            incoming_ts = datetime.now(timezone.utc)
            incoming_rel = self.RELIABILITY_WEIGHTS.get(context.incoming_source.reliability, 0.5)

        # Normalize timezones for comparison
        if existing_ts.tzinfo is None:
            existing_ts = existing_ts.replace(tzinfo=timezone.utc)
        if incoming_ts.tzinfo is None:
            incoming_ts = incoming_ts.replace(tzinfo=timezone.utc)

        # Recency calculation
        is_incoming_newer = incoming_ts >= existing_ts
        recency_gap_days = abs((incoming_ts - existing_ts).total_seconds()) / 86400.0

        # Recency boost (up to 30% for significantly newer information)
        recency_multiplier = 1.0 + min(recency_gap_days / 30.0, 0.3) if is_incoming_newer else 1.0
        
        score_incoming = incoming_rel * recency_multiplier
        score_existing = existing_rel * (1.0 if is_incoming_newer else (1.0 + min(recency_gap_days / 30.0, 0.3)))

        # Tie-breaker: prefer newer
        if abs(score_incoming - score_existing) < 0.05:
            if is_incoming_newer:
                winner = "incoming_claim"
            else:
                winner = "existing_belief"
        elif score_incoming > score_existing:
            winner = "incoming_claim"
        else:
            winner = "existing_belief"

        conf_delta = round(abs(score_incoming - score_existing) * 0.2, 3)

        rationale = (
            f"[RecencyStrategy] Existing score={score_existing:.2f} (rel={existing_rel}, ts={existing_ts.strftime('%Y-%m-%d')}) vs "
            f"Incoming score={score_incoming:.2f} (rel={incoming_rel}, ts={incoming_ts.strftime('%Y-%m-%d')}). "
            f"Winner: '{winner}' based on chronologically recent update and reliability weighting."
        )

        return Resolution(
            id=str(uuid4()),
            conflict_id=conflict.id,
            strategy_used="recency",
            winner=winner,
            rationale=rationale,
            confidence_delta=conf_delta,
        )
