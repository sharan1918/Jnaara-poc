import time
from datetime import datetime, timezone
import hashlib
import logging
import re
from uuid import uuid4

from jnaara.analysis.semantic import SemanticAnalyzer
from jnaara.conflict.detector import ConflictDetector
from jnaara.conflict.resolver import ConflictResolver
from jnaara.db.repository import Repository
from jnaara.models.domain import (
    Belief,
    Claim,
    Conflict,
    Decision,
    Fact,
    ProcessingResult,
    Resolution,
    ResolutionContext,
    Source,
)

logger = logging.getLogger(__name__)


class BeliefManager:
    """Core orchestrator managing belief state transitions, conflict handling, and provenance."""

    def __init__(
        self,
        repository: Repository,
        analyzer: SemanticAnalyzer,
        detector: ConflictDetector,
        resolver: ConflictResolver,
    ):
        self.repository = repository
        self.analyzer = analyzer
        self.detector = detector
        self.resolver = resolver

    def process_fact(self, fact: Fact) -> ProcessingResult:
        """Process a single incoming fact idempotently through the belief pipeline."""
        content_preview = fact.content.replace("\n", " ")
        if len(content_preview) > 90:
            content_preview = content_preview[:90] + "..."

        # 1. Idempotency check: skip already processed facts
        if self.repository.fact_exists(fact.id):
            logger.info("[FACT SKIP] Fact '%s' already processed. Skipping (idempotent).", fact.id)
            return ProcessingResult(fact_id=fact.id, skipped=True)

        logger.info(
            "[FACT INGEST] ID: %s | Source: '%s' (rel: %s) | Content: '%s'",
            fact.id,
            fact.source,
            fact.source_reliability,
            content_preview,
        )

        # 2. Persist raw fact and derived source metadata
        self.repository.save_fact(fact)
        source = self._derive_source(fact)
        self.repository.upsert_source(source)

        # 3. LLM claim extraction with validation
        analysis = self.analyzer.extract_claims(fact)
        self.repository.save_claims(analysis.claims)
        logger.info(
            "[CLAIMS EXTRACTED] Fact '%s' produced %d claim(s):",
            fact.id,
            len(analysis.claims),
        )
        for c in analysis.claims:
            logger.info(
                "  • [%s] %s = '%s' (type: %s, conf: %.2f)",
                c.entity,
                c.attribute,
                c.value,
                c.claim_type,
                c.confidence,
            )

        # 4. Evaluate each extracted claim
        step_results: list[tuple[Decision, Conflict | None]] = []

        for claim in analysis.claims:
            decision, conflict = self.detector.detect(claim, fact)
            self.repository.save_decision(decision)

            logger.info(
                "[DECISION] [%s - %s] -> Action: %s (Tier: %s) | Reason: %s",
                claim.entity,
                claim.attribute,
                decision.action,
                decision.tier,
                decision.reason,
            )

            match decision.action:
                case "NEW_BELIEF":
                    self._handle_new_belief(claim, fact, decision)

                case "UPDATE":
                    self._handle_update_belief(claim, fact, decision)

                case "CONFLICT":
                    if conflict is not None:
                        self._handle_conflict(claim, fact, conflict, source)

                case "DISCARD_NOISE":
                    logger.debug("Claim %s discarded as noise. Decision logged.", claim.id)

            step_results.append((decision, conflict))

        return ProcessingResult(
            fact_id=fact.id,
            skipped=False,
            claims=analysis.claims,
            results=step_results,
        )

    def process_sequence(
        self, facts: list[Fact], delay_seconds: float = 0.0
    ) -> list[ProcessingResult]:
        """Process an entire sequence of facts in chronological order with optional inter-fact delay."""
        sorted_facts = sorted(facts, key=lambda f: f.timestamp)
        results: list[ProcessingResult] = []
        total = len(sorted_facts)

        for idx, f in enumerate(sorted_facts):
            res = self.process_fact(f)
            results.append(res)
            # Apply delay between facts (except after the final fact) to respect LLM rate limits
            if delay_seconds > 0 and idx < total - 1:
                logger.info(
                    "[RateLimiter] Ingestion pacing: sleeping %.1fs before next fact (%d/%d)...",
                    delay_seconds,
                    idx + 2,
                    total,
                )
                time.sleep(delay_seconds)

        return results

    def _handle_new_belief(self, claim: Claim, fact: Fact, decision: Decision) -> None:
        belief = Belief(
            id=str(uuid4()),
            entity=claim.entity,
            attribute=claim.attribute,
            value=claim.value,
            confidence=claim.confidence,
            supporting_fact_ids=[fact.id],
            contradicting_fact_ids=[],
            last_updated=fact.timestamp,
            version=1,
            status="active",
        )
        self.repository.upsert_belief(belief, changed_by_fact_id=fact.id, reason=decision.reason)
        logger.info(
            "[NEW BELIEF] Created belief '%s' for [%s - %s] = '%s' (conf: %.2f)",
            belief.id[:8],
            belief.entity,
            belief.attribute,
            belief.value,
            belief.confidence,
        )

    def _handle_update_belief(self, claim: Claim, fact: Fact, decision: Decision) -> None:
        existing = self.repository.get_belief_by_entity_attribute(claim.entity, claim.attribute)
        if existing is None:
            # Fallback search by normalized attribute
            for b in self.repository.get_beliefs_for_entity(claim.entity):
                if self.detector._normalize_attr(b.attribute) == self.detector._normalize_attr(claim.attribute):
                    existing = b
                    break

        if existing is not None:
            existing.version += 1
            existing.value = claim.value
            existing.last_updated = fact.timestamp
            # Corroborating update slightly boosts confidence
            existing.confidence = min(1.0, round((existing.confidence + claim.confidence) / 2.0 + 0.05, 3))
            if fact.id not in existing.supporting_fact_ids:
                existing.supporting_fact_ids.append(fact.id)
            self.repository.upsert_belief(existing, changed_by_fact_id=fact.id, reason=decision.reason)
            logger.info(
                "[UPDATE BELIEF] Updated belief '%s' for [%s - %s] -> '%s' (v%d, conf: %.2f)",
                existing.id[:8],
                existing.entity,
                existing.attribute,
                existing.value,
                existing.version,
                existing.confidence,
            )
        else:
            self._handle_new_belief(claim, fact, decision)

    def _handle_conflict(
        self, claim: Claim, fact: Fact, conflict: Conflict, incoming_source: Source
    ) -> None:
        existing_belief = self.repository.get_belief(conflict.existing_belief_id)
        if existing_belief is None:
            # If referenced belief not found, fallback to any matching belief
            existing_belief = self.repository.get_belief_by_entity_attribute(claim.entity, claim.attribute)
            if existing_belief is None:
                self._handle_new_belief(
                    claim,
                    fact,
                    Decision(
                        id=str(uuid4()),
                        fact_id=fact.id,
                        claim_id=claim.id,
                        action="NEW_BELIEF",
                        reason="Conflict target missing; established as new belief",
                        tier="deterministic",
                    ),
                )
                return

        logger.info(
            "[CONFLICT DETECTED] Type: %s on [%s - %s] (Severity: %s) | Existing: '%s' vs Incoming: '%s'",
            conflict.conflict_type,
            claim.entity,
            claim.attribute,
            conflict.severity,
            existing_belief.value,
            claim.value,
        )

        # Build comprehensive resolution context
        existing_sources = self.repository.get_sources_for_facts(existing_belief.supporting_fact_ids)
        all_related_facts = self.repository.get_all_facts()

        context = ResolutionContext(
            existing_belief=existing_belief,
            incoming_claim=claim,
            existing_sources=existing_sources,
            incoming_source=incoming_source,
            all_related_facts=all_related_facts,
        )

        # Resolve conflict deterministically
        resolution = self.resolver.resolve(conflict, context)
        conflict.resolution = resolution
        self.repository.save_conflict(conflict)
        self.repository.save_resolution(resolution)

        logger.info(
            "[CONFLICT RESOLVED] Winner: %s via strategy '%s' (delta: %+.2f) | Rationale: %s",
            resolution.winner,
            self.resolver.active_strategy,
            resolution.confidence_delta,
            resolution.rationale,
        )

        # Apply resolution result to persistent belief state
        if resolution.winner == "incoming_claim":
            existing_belief.version += 1
            # Move old supporting facts that disagree to contradicting facts
            for fid in list(existing_belief.supporting_fact_ids):
                if fid not in existing_belief.contradicting_fact_ids:
                    existing_belief.contradicting_fact_ids.append(fid)
            existing_belief.supporting_fact_ids = [fact.id]
            existing_belief.value = claim.value
            existing_belief.last_updated = fact.timestamp
            existing_belief.confidence = min(
                1.0, max(0.1, round(claim.confidence + resolution.confidence_delta, 3))
            )
            existing_belief.status = "active"
            self.repository.upsert_belief(
                existing_belief,
                changed_by_fact_id=fact.id,
                reason=f"Resolved conflict via {self.resolver.active_strategy}: {resolution.rationale}",
            )
        else:
            # Existing belief retained
            if fact.id not in existing_belief.contradicting_fact_ids:
                existing_belief.contradicting_fact_ids.append(fact.id)
            existing_belief.confidence = min(
                1.0, max(0.1, round(existing_belief.confidence + resolution.confidence_delta, 3))
            )
            self.repository.upsert_belief(
                existing_belief,
                changed_by_fact_id=fact.id,
                reason=f"Retained existing belief via {self.resolver.active_strategy}: {resolution.rationale}",
            )

    def _derive_source(self, fact: Fact) -> Source:
        """Classify a fact's source string into a structured Source model with independence grouping."""
        s_lower = fact.source.lower()
        src_id = f"src_{hashlib.sha256(fact.source.encode()).hexdigest()[:12]}"

        # Classify source type
        if any(w in s_lower for w in ["sec", "10-k", "10-q", "8-k", "filing", "amended"]):
            source_type = "company_filing"
        elif any(w in s_lower for w in ["press release", "press", "official announcement", "investor presentation"]):
            source_type = "press_release"
        elif any(w in s_lower for w in ["analyst", "equity research", "morgan", "goldman", "peakfin"]):
            source_type = "analyst_report"
        elif any(w in s_lower for w in ["epa", "doj", "regulator", "inspector"]):
            source_type = "regulatory"
        elif any(w in s_lower for w in ["leak", "internal memo", "whistleblower", "audit"]):
            source_type = "leaked"
        elif any(w in s_lower for w in ["blog", "forum", "insider"]):
            source_type = "blog"
        elif any(w in s_lower for w in ["reuters", "bloomberg", "wsj", "times", "journal", "herald"]):
            source_type = "news"
        else:
            source_type = "other"

        # Determine independence group
        # Corporate releases from the same company share an independence group
        corp_keywords = [
            "novatech", "meridian", "crestline", "arcadia", "vantage",
            "terramotors", "helios", "atlas", "forge", "pinnacle"
        ]
        independence_group = None
        for kw in corp_keywords:
            if kw in s_lower:
                if source_type in ["company_filing", "press_release"]:
                    independence_group = f"{kw}_internal"
                elif source_type == "leaked":
                    independence_group = f"{kw}_internal_leak"
                break

        if independence_group is None:
            if source_type == "regulatory":
                independence_group = "regulatory_enforcement"
            elif source_type == "news":
                # Each major outlet is an independent press source
                first_word = s_lower.split()[0]
                independence_group = f"press_{first_word}"
            elif source_type == "analyst_report":
                first_word = s_lower.split()[0]
                independence_group = f"analyst_{first_word}"
            else:
                independence_group = f"source_{source_type}"

        return Source(
            source_id=src_id,
            source_name=fact.source,
            source_type=source_type,
            reliability=fact.source_reliability,
            independence_group=independence_group,
        )
