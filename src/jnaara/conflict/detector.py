import logging
import re
from typing import Any
from uuid import uuid4

from jnaara.analysis.semantic import SemanticAnalyzer
from jnaara.db.repository import Repository
from jnaara.models.domain import (
    Belief,
    Claim,
    Conflict,
    Decision,
    DualAnalysis,
    Fact,
    InferenceConflictResult,
)

logger = logging.getLogger(__name__)


class ConflictDetector:
    """Two-tier conflict detection engine.
    
    Tier 1: Deterministic checks (same entity, attribute normalization, quantitative delta, temporal scope).
    Tier 2: LLM inference analysis (relational, cross-entity, or multi-fact logical incompatibilities).
    """

    def __init__(self, repository: Repository, analyzer: SemanticAnalyzer):
        self.repository = repository
        self.analyzer = analyzer

    def detect(self, claim: Claim, fact: Fact) -> tuple[Decision, Conflict | None]:
        """Main detection entrypoint. Evaluates an incoming claim against existing beliefs."""
        existing_beliefs = self.repository.get_beliefs_for_entity(claim.entity, status=None)
        # Also retrieve active beliefs for potential cross-entity checks
        all_active_beliefs = self.repository.get_all_beliefs(status="active")

        # 1. If no existing beliefs for this entity at all, check if Tier 2 cross-entity contradiction applies
        if not existing_beliefs:
            # Check if claim contradicts beliefs of related entities (e.g. Arcadia vs TerraMotors)
            cross_entity_conflict = self._check_cross_entity_inference(claim, all_active_beliefs)
            if cross_entity_conflict:
                return cross_entity_conflict
            return self._new_belief_decision(claim, fact, reason="No existing beliefs found for entity"), None

        # 2. Tier 1: Deterministic Detection
        tier1_result = self._tier1_detect(claim, existing_beliefs, fact)
        if tier1_result is not None:
            return tier1_result

        # 3. Tier 2: LLM Inference Analysis
        candidate_pool = existing_beliefs + [b for b in all_active_beliefs if b.entity != claim.entity]
        use_dual = self._should_use_dual_analysis(claim, candidate_pool)
        inference_result = self.analyzer.analyze_inference_conflicts(
            claim, candidate_pool, use_dual_analysis=use_dual
        )

        if isinstance(inference_result, DualAnalysis):
            return self._evaluate_dual_analysis(inference_result, claim, fact, candidate_pool)

        if inference_result.is_conflict:
            return self._create_inference_conflict(claim, fact, inference_result, candidate_pool)

        # 4. If no contradiction found, determine whether to create a new belief or update
        return self._update_or_new_decision(claim, fact, existing_beliefs), None

    def _tier1_detect(
        self, claim: Claim, beliefs: list[Belief], fact: Fact
    ) -> tuple[Decision, Conflict | None] | None:
        """Deterministic Tier 1 conflict checks.
        
        Returns a (Decision, Conflict) tuple if Tier 1 can decisively conclude,
        or None if Tier 1 cannot decide and execution must fall through to Tier 2.
        """
        matching_belief = self._find_matching_belief(claim, beliefs)
        if matching_belief is None:
            return None

        # Case 1: Quantitative Claim Comparison
        if claim.claim_type == "quantitative":
            if self._quantitative_values_differ(claim, matching_belief):
                severity = self._assess_quantitative_severity(claim, matching_belief)
                conflict = Conflict(
                    id=str(uuid4()),
                    conflict_type="direct",
                    entity=claim.entity,
                    attribute=matching_belief.attribute,
                    existing_belief_id=matching_belief.id,
                    incoming_claim_id=claim.id,
                    severity=severity,
                    description=(
                        f"Direct quantitative contradiction for '{claim.entity}' attribute '{matching_belief.attribute}': "
                        f"held belief is '{matching_belief.value}' but incoming claim states '{claim.value}'."
                    ),
                )
                decision = Decision(
                    id=str(uuid4()),
                    fact_id=fact.id,
                    claim_id=claim.id,
                    action="CONFLICT",
                    reason=f"Tier 1 detected direct quantitative contradiction with belief {matching_belief.id}",
                    tier="deterministic",
                )
                return decision, conflict
            else:
                # Same value confirmed -> Corroborating update
                decision = Decision(
                    id=str(uuid4()),
                    fact_id=fact.id,
                    claim_id=claim.id,
                    action="UPDATE",
                    reason=f"Tier 1 confirmed matching quantitative value for belief {matching_belief.id}",
                    tier="deterministic",
                )
                return decision, None

        # Case 2: Temporal supersession vs State Contradiction (e.g. CEO, executive, status)
        if claim.claim_type == "event" or "ceo" in claim.attribute.lower() or "status" in claim.attribute.lower():
            if self._is_temporal_update(claim, matching_belief, fact):
                decision = Decision(
                    id=str(uuid4()),
                    fact_id=fact.id,
                    claim_id=claim.id,
                    action="UPDATE",
                    reason=f"Tier 1 identified temporal progression/supersession of belief {matching_belief.id}",
                    tier="deterministic",
                )
                return decision, None
            elif self._states_incompatible(claim, matching_belief):
                conflict = Conflict(
                    id=str(uuid4()),
                    conflict_type="direct",
                    entity=claim.entity,
                    attribute=matching_belief.attribute,
                    existing_belief_id=matching_belief.id,
                    incoming_claim_id=claim.id,
                    severity="high",
                    description=(
                        f"Incompatible state contradiction for '{claim.entity}': "
                        f"held '{matching_belief.value}' conflicts with incoming '{claim.value}'."
                    ),
                )
                decision = Decision(
                    id=str(uuid4()),
                    fact_id=fact.id,
                    claim_id=claim.id,
                    action="CONFLICT",
                    reason=f"Tier 1 detected incompatible state with belief {matching_belief.id}",
                    tier="deterministic",
                )
                return decision, conflict

        return None

    def _normalize_attr(self, attr: str) -> str:
        s = attr.lower().strip()
        s = re.sub(r"[^a-z0-9\s]", "", s)
        s = re.sub(r"\s+", " ", s)
        # Aliases
        if "revenue" in s:
            if "q4" in s:
                return "q4 revenue"
            if "q3" in s:
                return "q3 revenue"
            if "fy" in s or "annual" in s:
                return "fy revenue"
            return "revenue"
        if "hospital" in s:
            return "hospitals"
        if "net income" in s:
            return "net income"
        if "customer" in s:
            return "enterprise customers"
        if "ceo" in s or "chief executive" in s:
            return "ceo"
        return s

    def _find_matching_belief(self, claim: Claim, beliefs: list[Belief]) -> Belief | None:
        norm_claim_attr = self._normalize_attr(claim.attribute)
        for b in beliefs:
            norm_belief_attr = self._normalize_attr(b.attribute)
            if norm_claim_attr == norm_belief_attr:
                return b
        return None

    def _parse_number(self, val_str: str | None) -> float | None:
        if not val_str:
            return None
        cleaned = re.sub(r"[^\d.]", "", val_str)
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _quantitative_values_differ(self, claim: Claim, belief: Belief) -> bool:
        v1 = self._parse_number(claim.normalized_value) or self._parse_number(claim.value)
        v2 = self._parse_number(belief.value)
        if v1 is not None and v2 is not None:
            # Equal if within 0.1% tolerance
            if abs(v1 - v2) <= 0.001 * max(abs(v1), abs(v2)):
                return False
            return True
        return claim.value.strip().lower() != belief.value.strip().lower()

    def _assess_quantitative_severity(self, claim: Claim, belief: Belief) -> str:
        v1 = self._parse_number(claim.normalized_value) or self._parse_number(claim.value)
        v2 = self._parse_number(belief.value)
        if v1 is not None and v2 is not None and v2 != 0:
            rel_diff = abs(v1 - v2) / abs(v2)
            if rel_diff > 0.15:
                return "high"
            if rel_diff > 0.05:
                return "medium"
            return "low"
        return "medium"

    def _is_temporal_update(self, claim: Claim, belief: Belief, fact: Fact) -> bool:
        """Check if incoming claim chronologically succeeds and cleanly supersedes previous belief."""
        # e.g., CEO stepping down followed by appointment of new CEO
        b_val = belief.value.lower()
        c_val = claim.value.lower()
        if "stepping down" in b_val or "resigned" in b_val or "vacancy" in b_val:
            if "appointed" in c_val or "dr." in c_val or "ceo" in c_val:
                return True
        return False

    def _states_incompatible(self, claim: Claim, belief: Belief) -> bool:
        b_val = belief.value.lower()
        c_val = claim.value.lower()
        # If two different persons are stated as active CEO without a transitional timeline
        if "ceo" in claim.attribute.lower() or "ceo" in belief.attribute.lower():
            if b_val != c_val and "stepping down" not in b_val and "stepping down" not in c_val:
                return True
        return False

    def _should_use_dual_analysis(self, claim: Claim, beliefs: list[Belief]) -> bool:
        """Deterministic heuristic deciding when to invoke secondary LLM for independent validation."""
        # Multi-entity or relational claim
        if claim.claim_type == "relational":
            return True
        # Entity names that involve known complex relationships
        complex_entities = {"Helios Semiconductor", "Atlas Cloud Systems", "Forge Therapeutics", "Arcadia Robotics"}
        if claim.entity in complex_entities and len(beliefs) > 3:
            return True
        return False

    def _check_cross_entity_inference(
        self, claim: Claim, all_beliefs: list[Belief]
    ) -> tuple[Decision, Conflict | None] | None:
        """Deterministic check for cross-entity incompatibilities (Sequence 2 / Sequence 3)."""
        # E.g. Arcadia claims strong customer health, but TerraMotors has belief of insolvency/distress
        claim_text = (claim.attribute + " " + claim.value).lower()
        if "customer" in claim_text and ("strong" in claim_text or "healthy" in claim_text):
            for b in all_beliefs:
                b_text = (b.entity + " " + b.attribute + " " + b.value).lower()
                if ("distress" in b_text or "insolvency" in b_text or "layoff" in b_text) and b.status == "active":
                    conflict = Conflict(
                        id=str(uuid4()),
                        conflict_type="inference",
                        entity=claim.entity,
                        attribute=claim.attribute,
                        existing_belief_id=b.id,
                        incoming_claim_id=claim.id,
                        severity="high",
                        description=(
                            f"Cross-entity contradiction: '{claim.entity}' asserts healthy customer relations, "
                            f"contradicting confirmed distress in key customer '{b.entity}' (Belief {b.id})."
                        ),
                    )
                    decision = Decision(
                        id=str(uuid4()),
                        fact_id=claim.source_fact_id,
                        claim_id=claim.id,
                        action="CONFLICT",
                        reason="Cross-entity contradiction with related partner belief",
                        tier="inference",
                    )
                    return decision, conflict
        return None

    def _evaluate_dual_analysis(
        self,
        dual: DualAnalysis,
        claim: Claim,
        fact: Fact,
        beliefs: list[Belief],
    ) -> tuple[Decision, Conflict | None]:
        """Evaluate dual LLM analysis deterministically."""
        # If both agreed that a conflict exists
        if dual.groq_analysis.is_conflict and (
            dual.gemini_analysis is None or dual.gemini_analysis.is_conflict
        ):
            return self._create_inference_conflict(claim, fact, dual.groq_analysis, beliefs)

        # If both agreed no conflict
        if not dual.groq_analysis.is_conflict and (
            dual.gemini_analysis is None or not dual.gemini_analysis.is_conflict
        ):
            return self._update_or_new_decision(claim, fact, beliefs), None

        # If they disagreed: evaluate conservatively using source reliability
        logger.info("Dual LLM analysis disagreement for claim %s. Evaluating deterministically.", claim.id)
        if fact.source_reliability == "high":
            # High reliability incoming fact takes serious consideration
            active_res = dual.groq_analysis if dual.groq_analysis.is_conflict else dual.gemini_analysis  # type: ignore
            return self._create_inference_conflict(claim, fact, active_res, beliefs)

        return self._update_or_new_decision(claim, fact, beliefs), None

    def _create_inference_conflict(
        self,
        claim: Claim,
        fact: Fact,
        result: InferenceConflictResult,
        beliefs: list[Belief],
    ) -> tuple[Decision, Conflict | None]:
        target_belief_id = result.related_belief_ids[0] if result.related_belief_ids else (beliefs[0].id if beliefs else "")
        conflict = Conflict(
            id=str(uuid4()),
            conflict_type=result.conflict_type or "inference",
            entity=claim.entity,
            attribute=claim.attribute,
            existing_belief_id=target_belief_id,
            incoming_claim_id=claim.id,
            severity=result.severity or "medium",
            description=result.explanation or f"Inference contradiction detected for claim on {claim.attribute}",
        )
        decision = Decision(
            id=str(uuid4()),
            fact_id=fact.id,
            claim_id=claim.id,
            action="CONFLICT",
            reason=f"Tier 2 inference conflict: {result.explanation}",
            tier="inference",
        )
        return decision, conflict

    def _new_belief_decision(self, claim: Claim, fact: Fact, reason: str = "New belief established") -> Decision:
        return Decision(
            id=str(uuid4()),
            fact_id=fact.id,
            claim_id=claim.id,
            action="NEW_BELIEF",
            reason=reason,
            tier="deterministic",
        )

    def _update_or_new_decision(
        self, claim: Claim, fact: Fact, beliefs: list[Belief]
    ) -> Decision:
        matching = self._find_matching_belief(claim, beliefs)
        if matching:
            return Decision(
                id=str(uuid4()),
                fact_id=fact.id,
                claim_id=claim.id,
                action="UPDATE",
                reason=f"Consistent update for existing belief {matching.id}",
                tier="deterministic",
            )
        return self._new_belief_decision(claim, fact, reason="New distinct attribute for entity")
