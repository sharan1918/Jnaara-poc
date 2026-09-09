from collections import defaultdict
from uuid import uuid4
from jnaara.conflict.strategies.base import ResolutionStrategy
from jnaara.models.domain import Conflict, Resolution, ResolutionContext, Source


class CorroborationWeightedStrategy(ResolutionStrategy):
    """Prefers claims backed by multiple independent sources rather than mere recency.
    
    Distinguishes independent confirmation from echo chambers by grouping sources
    into independence groups.
    """

    RELIABILITY_WEIGHTS = {"high": 1.0, "medium": 0.7, "low": 0.4}

    def resolve(self, conflict: Conflict, context: ResolutionContext) -> Resolution:
        # 1. Evaluate Existing Belief Corroboration
        existing_groups: dict[str, list[Source]] = defaultdict(list)
        for s in context.existing_sources:
            group_key = s.independence_group or s.source_name
            existing_groups[group_key].append(s)

        # In case existing_sources list was empty, synthesize from supporting facts
        if not existing_groups and context.existing_belief.supporting_fact_ids:
            for fid in context.existing_belief.supporting_fact_ids:
                matching_fact = next((f for f in context.all_related_facts if f.id == fid), None)
                if matching_fact:
                    group_key = matching_fact.source.split()[0].lower()
                    existing_groups[group_key].append(
                        Source(
                            source_id=f"src_{fid}",
                            source_name=matching_fact.source,
                            source_type="press_release",
                            reliability=matching_fact.source_reliability,
                            independence_group=group_key,
                        )
                    )

        score_existing = self._calculate_group_score(existing_groups)

        # 2. Evaluate Incoming Claim Corroboration
        incoming_groups: dict[str, list[Source]] = defaultdict(list)
        inc_group = context.incoming_source.independence_group or context.incoming_source.source_name
        incoming_groups[inc_group].append(context.incoming_source)

        score_incoming = self._calculate_group_score(incoming_groups)

        # Compare scores
        if score_existing >= score_incoming:
            winner = "existing_belief"
        else:
            winner = "incoming_claim"

        conf_delta = round(abs(score_incoming - score_existing) * 0.15, 3)

        rationale = (
            f"[CorroborationStrategy] Existing score={score_existing:.2f} ({len(existing_groups)} independent groups: {list(existing_groups.keys())}) vs "
            f"Incoming score={score_incoming:.2f} ({len(incoming_groups)} independent groups: {list(incoming_groups.keys())}). "
            f"Winner: '{winner}' determined by independent corroboration diversity."
        )

        return Resolution(
            id=str(uuid4()),
            conflict_id=conflict.id,
            strategy_used="corroboration",
            winner=winner,
            rationale=rationale,
            confidence_delta=conf_delta,
        )

    def _calculate_group_score(self, groups: dict[str, list[Source]]) -> float:
        if not groups:
            return 0.5

        total = 0.0
        for group_sources in groups.values():
            best_rel = max(
                (self.RELIABILITY_WEIGHTS.get(s.reliability, 0.5) for s in group_sources),
                default=0.5,
            )
            total += best_rel

        # Multi-source diversity bonus: each additional independent group adds a boost
        diversity_multiplier = 1.0 + 0.2 * (len(groups) - 1)
        return total * diversity_multiplier
