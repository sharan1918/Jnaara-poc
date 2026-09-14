import json
from typing import Any
from uuid import uuid4
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from jnaara.models.db import (
    BeliefHistoryModel,
    BeliefModel,
    ClaimModel,
    ConflictModel,
    DecisionModel,
    FactModel,
    ResolutionModel,
    SourceModel,
    utc_now,
)
from jnaara.models.domain import (
    Belief,
    Claim,
    Conflict,
    Decision,
    Fact,
    ProvenanceChain,
    Resolution,
    Source,
)


class Repository:
    """Repository handling all database persistence and domain model conversion."""

    def __init__(self, session: Session):
        self.session = session

    # ─── Facts ───
    def save_fact(self, fact: Fact) -> None:
        """Save a raw fact if it doesn't already exist."""
        existing = self.session.get(FactModel, fact.id)
        if existing is None:
            model = FactModel(
                id=fact.id,
                timestamp=fact.timestamp,
                source=fact.source,
                source_reliability=fact.source_reliability,
                content=fact.content,
            )
            self.session.add(model)
            self.session.commit()

    def get_fact(self, fact_id: str) -> Fact | None:
        model = self.session.get(FactModel, fact_id)
        if model is None:
            return None
        return Fact(
            id=model.id,
            timestamp=model.timestamp,
            source=model.source,
            source_reliability=model.source_reliability,  # type: ignore
            content=model.content,
        )

    def fact_exists(self, fact_id: str) -> bool:
        stmt = select(FactModel.id).where(FactModel.id == fact_id)
        return self.session.scalar(stmt) is not None

    def get_all_facts(self) -> list[Fact]:
        stmt = select(FactModel).order_by(FactModel.timestamp.asc())
        models = self.session.scalars(stmt).all()
        return [
            Fact(
                id=m.id,
                timestamp=m.timestamp,
                source=m.source,
                source_reliability=m.source_reliability,  # type: ignore
                content=m.content,
            )
            for m in models
        ]

    # ─── Sources ───
    def upsert_source(self, source: Source) -> None:
        existing = self.session.get(SourceModel, source.source_id)
        if existing:
            existing.source_name = source.source_name
            existing.source_type = source.source_type
            existing.reliability = source.reliability
            existing.independence_group = source.independence_group
        else:
            model = SourceModel(
                source_id=source.source_id,
                source_name=source.source_name,
                source_type=source.source_type,
                reliability=source.reliability,
                independence_group=source.independence_group,
            )
            self.session.add(model)
        self.session.commit()

    def get_source(self, source_id: str) -> Source | None:
        model = self.session.get(SourceModel, source_id)
        if not model:
            return None
        return Source(
            source_id=model.source_id,
            source_name=model.source_name,
            source_type=model.source_type,  # type: ignore
            reliability=model.reliability,  # type: ignore
            independence_group=model.independence_group,
        )

    def get_sources_for_facts(self, fact_ids: list[str]) -> list[Source]:
        if not fact_ids:
            return []
        stmt = select(FactModel.source).where(FactModel.id.in_(fact_ids))
        source_names = list(set(self.session.scalars(stmt).all()))
        if not source_names:
            return []
        src_stmt = select(SourceModel).where(SourceModel.source_name.in_(source_names))
        models = self.session.scalars(src_stmt).all()
        return [
            Source(
                source_id=m.source_id,
                source_name=m.source_name,
                source_type=m.source_type,  # type: ignore
                reliability=m.reliability,  # type: ignore
                independence_group=m.independence_group,
            )
            for m in models
        ]

    # ─── Claims ───
    def save_claims(self, claims: list[Claim]) -> None:
        for claim in claims:
            existing = self.session.get(ClaimModel, claim.id)
            if existing is None:
                model = ClaimModel(
                    id=claim.id,
                    fact_id=claim.source_fact_id,
                    entity=claim.entity,
                    attribute=claim.attribute,
                    value=claim.value,
                    normalized_value=claim.normalized_value,
                    unit=claim.unit,
                    temporal_scope=claim.temporal_scope,
                    claim_type=claim.claim_type,
                    confidence=claim.confidence,
                )
                self.session.add(model)
        self.session.commit()

    def get_claim(self, claim_id: str) -> Claim | None:
        m = self.session.get(ClaimModel, claim_id)
        if not m:
            return None
        return Claim(
            id=m.id,
            entity=m.entity,
            attribute=m.attribute,
            value=m.value,
            normalized_value=m.normalized_value,
            unit=m.unit,
            temporal_scope=m.temporal_scope,
            claim_type=m.claim_type,  # type: ignore
            confidence=m.confidence,
            source_fact_id=m.fact_id,
        )

    def get_claims_for_fact(self, fact_id: str) -> list[Claim]:
        stmt = select(ClaimModel).where(ClaimModel.fact_id == fact_id)
        models = self.session.scalars(stmt).all()
        return [
            Claim(
                id=m.id,
                entity=m.entity,
                attribute=m.attribute,
                value=m.value,
                normalized_value=m.normalized_value,
                unit=m.unit,
                temporal_scope=m.temporal_scope,
                claim_type=m.claim_type,  # type: ignore
                confidence=m.confidence,
                source_fact_id=m.fact_id,
            )
            for m in models
        ]

    def get_claims_for_entity(self, entity: str) -> list[Claim]:
        stmt = select(ClaimModel).where(ClaimModel.entity == entity)
        models = self.session.scalars(stmt).all()
        return [
            Claim(
                id=m.id,
                entity=m.entity,
                attribute=m.attribute,
                value=m.value,
                normalized_value=m.normalized_value,
                unit=m.unit,
                temporal_scope=m.temporal_scope,
                claim_type=m.claim_type,  # type: ignore
                confidence=m.confidence,
                source_fact_id=m.fact_id,
            )
            for m in models
        ]

    # ─── Beliefs ───
    def _to_belief_domain(self, m: BeliefModel) -> Belief:
        supporting = json.loads(m.supporting_fact_ids) if m.supporting_fact_ids else []
        contradicting = json.loads(m.contradicting_fact_ids) if m.contradicting_fact_ids else []
        return Belief(
            id=m.id,
            entity=m.entity,
            attribute=m.attribute,
            value=m.value,
            confidence=m.confidence,
            supporting_fact_ids=supporting,
            contradicting_fact_ids=contradicting,
            last_updated=m.last_updated,
            version=m.version,
            status=m.status,  # type: ignore
        )

    def get_belief(self, belief_id: str) -> Belief | None:
        m = self.session.get(BeliefModel, belief_id)
        if not m:
            return None
        return self._to_belief_domain(m)

    def get_beliefs_for_entity(self, entity: str, status: str | None = "active") -> list[Belief]:
        clean_ent = entity.strip()
        stmt = select(BeliefModel).where(
            (BeliefModel.entity == clean_ent) | BeliefModel.entity.ilike(f"%{clean_ent}%")
        )
        if status:
            stmt = stmt.where(BeliefModel.status == status)
        models = self.session.scalars(stmt).all()
        return [self._to_belief_domain(m) for m in models]

    def get_belief_by_entity_attribute(
        self, entity: str, attribute: str, status: str | None = "active"
    ) -> Belief | None:
        clean_ent = entity.strip()
        clean_attr = attribute.strip()
        stmt = select(BeliefModel).where(
            (BeliefModel.entity == clean_ent) | BeliefModel.entity.ilike(f"%{clean_ent}%"),
            (BeliefModel.attribute == clean_attr) | BeliefModel.attribute.ilike(f"%{clean_attr}%"),
        )
        if status:
            stmt = stmt.where(BeliefModel.status == status)
        m = self.session.scalars(stmt).first()
        if not m:
            return None
        return self._to_belief_domain(m)

    def upsert_belief(
        self, belief: Belief, changed_by_fact_id: str, reason: str | None = None
    ) -> None:
        existing = self.session.get(BeliefModel, belief.id)
        supporting_json = json.dumps(belief.supporting_fact_ids)
        contradicting_json = json.dumps(belief.contradicting_fact_ids)

        if existing:
            # Record version history
            history_entry = BeliefHistoryModel(
                id=str(uuid4()),
                belief_id=existing.id,
                version=existing.version,
                old_value=existing.value,
                new_value=belief.value,
                old_confidence=existing.confidence,
                new_confidence=belief.confidence,
                changed_by_fact_id=changed_by_fact_id,
                reason=reason,
                changed_at=utc_now(),
            )
            self.session.add(history_entry)

            # Update existing
            existing.value = belief.value
            existing.confidence = belief.confidence
            existing.supporting_fact_ids = supporting_json
            existing.contradicting_fact_ids = contradicting_json
            existing.last_updated = belief.last_updated
            existing.version = belief.version
            existing.status = belief.status
        else:
            model = BeliefModel(
                id=belief.id,
                entity=belief.entity,
                attribute=belief.attribute,
                value=belief.value,
                confidence=belief.confidence,
                supporting_fact_ids=supporting_json,
                contradicting_fact_ids=contradicting_json,
                last_updated=belief.last_updated,
                version=belief.version,
                status=belief.status,
            )
            self.session.add(model)

            # Record initial history
            history_entry = BeliefHistoryModel(
                id=str(uuid4()),
                belief_id=belief.id,
                version=1,
                old_value=None,
                new_value=belief.value,
                old_confidence=None,
                new_confidence=belief.confidence,
                changed_by_fact_id=changed_by_fact_id,
                reason=reason or "Initial belief creation",
                changed_at=utc_now(),
            )
            self.session.add(history_entry)

        self.session.commit()

    def get_all_beliefs(self, status: str | None = None) -> list[Belief]:
        stmt = select(BeliefModel)
        if status:
            stmt = stmt.where(BeliefModel.status == status)
        stmt = stmt.order_by(BeliefModel.entity.asc(), BeliefModel.attribute.asc())
        models = self.session.scalars(stmt).all()
        return [self._to_belief_domain(m) for m in models]

    # ─── Decisions ───
    def save_decision(self, decision: Decision) -> None:
        existing = self.session.get(DecisionModel, decision.id)
        if existing is None:
            model = DecisionModel(
                id=decision.id,
                fact_id=decision.fact_id,
                claim_id=decision.claim_id,
                action=decision.action,
                reason=decision.reason,
                tier=decision.tier,
                created_at=decision.created_at,
            )
            self.session.add(model)
            self.session.commit()

    def get_decisions_for_fact(self, fact_id: str) -> list[Decision]:
        stmt = select(DecisionModel).where(DecisionModel.fact_id == fact_id)
        models = self.session.scalars(stmt).all()
        return [
            Decision(
                id=m.id,
                fact_id=m.fact_id,
                claim_id=m.claim_id,
                action=m.action,  # type: ignore
                reason=m.reason,
                tier=m.tier,  # type: ignore
                created_at=m.created_at,
            )
            for m in models
        ]

    def get_decisions_for_claim(self, claim_id: str) -> list[Decision]:
        stmt = select(DecisionModel).where(DecisionModel.claim_id == claim_id)
        models = self.session.scalars(stmt).all()
        return [
            Decision(
                id=m.id,
                fact_id=m.fact_id,
                claim_id=m.claim_id,
                action=m.action,  # type: ignore
                reason=m.reason,
                tier=m.tier,  # type: ignore
                created_at=m.created_at,
            )
            for m in models
        ]

    def get_all_decisions(self) -> list[Decision]:
        stmt = select(DecisionModel).order_by(DecisionModel.created_at.asc())
        models = self.session.scalars(stmt).all()
        return [
            Decision(
                id=m.id,
                fact_id=m.fact_id,
                claim_id=m.claim_id,
                action=m.action,  # type: ignore
                reason=m.reason,
                tier=m.tier,  # type: ignore
                created_at=m.created_at,
            )
            for m in models
        ]

    # ─── Conflicts & Resolutions ───
    def save_conflict(self, conflict: Conflict) -> None:
        existing = self.session.get(ConflictModel, conflict.id)
        if existing is None:
            model = ConflictModel(
                id=conflict.id,
                conflict_type=conflict.conflict_type,
                entity=conflict.entity,
                attribute=conflict.attribute,
                existing_belief_id=conflict.existing_belief_id,
                incoming_claim_id=conflict.incoming_claim_id,
                severity=conflict.severity,
                description=conflict.description,
                detected_at=conflict.detected_at,
            )
            self.session.add(model)
            self.session.commit()

    def get_conflict(self, conflict_id: str) -> Conflict | None:
        m = self.session.get(ConflictModel, conflict_id)
        if not m:
            return None
        res = self.get_resolution(m.id)
        return Conflict(
            id=m.id,
            conflict_type=m.conflict_type,  # type: ignore
            entity=m.entity,
            attribute=m.attribute,
            existing_belief_id=m.existing_belief_id,
            incoming_claim_id=m.incoming_claim_id,
            severity=m.severity,  # type: ignore
            description=m.description,
            detected_at=m.detected_at,
            resolution=res,
        )

    def get_conflicts(self, entity: str | None = None) -> list[Conflict]:
        stmt = select(ConflictModel)
        if entity:
            clean_ent = entity.strip()
            stmt = stmt.where(
                (ConflictModel.entity == clean_ent) | ConflictModel.entity.ilike(f"%{clean_ent}%")
            )
        stmt = stmt.order_by(ConflictModel.detected_at.asc())
        models = self.session.scalars(stmt).all()
        conflicts = []
        for m in models:
            res = self.get_resolution(m.id)
            conflicts.append(
                Conflict(
                    id=m.id,
                    conflict_type=m.conflict_type,  # type: ignore
                    entity=m.entity,
                    attribute=m.attribute,
                    existing_belief_id=m.existing_belief_id,
                    incoming_claim_id=m.incoming_claim_id,
                    severity=m.severity,  # type: ignore
                    description=m.description,
                    detected_at=m.detected_at,
                    resolution=res,
                )
            )
        return conflicts

    def save_resolution(self, resolution: Resolution) -> None:
        existing = self.session.get(ResolutionModel, resolution.id)
        if existing:
            existing.strategy_used = resolution.strategy_used
            existing.winner = resolution.winner
            existing.rationale = resolution.rationale
            existing.confidence_delta = resolution.confidence_delta
            existing.resolved_at = resolution.resolved_at
        else:
            model = ResolutionModel(
                id=resolution.id,
                conflict_id=resolution.conflict_id,
                strategy_used=resolution.strategy_used,
                winner=resolution.winner,
                rationale=resolution.rationale,
                confidence_delta=resolution.confidence_delta,
                resolved_at=resolution.resolved_at,
            )
            self.session.add(model)
        self.session.commit()

    def get_resolution(self, conflict_id: str) -> Resolution | None:
        stmt = select(ResolutionModel).where(ResolutionModel.conflict_id == conflict_id)
        m = self.session.scalars(stmt).first()
        if not m:
            return None
        return Resolution(
            id=m.id,
            conflict_id=m.conflict_id,
            strategy_used=m.strategy_used,
            winner=m.winner,  # type: ignore
            rationale=m.rationale,
            confidence_delta=m.confidence_delta,
            resolved_at=m.resolved_at,
        )

    # ─── Provenance & History ───
    def get_belief_history(self, belief_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(BeliefHistoryModel)
            .where(BeliefHistoryModel.belief_id == belief_id)
            .order_by(BeliefHistoryModel.version.asc())
        )
        models = self.session.scalars(stmt).all()
        return [
            {
                "id": m.id,
                "version": m.version,
                "old_value": m.old_value,
                "new_value": m.new_value,
                "old_confidence": m.old_confidence,
                "new_confidence": m.new_confidence,
                "changed_by_fact_id": m.changed_by_fact_id,
                "reason": m.reason,
                "changed_at": m.changed_at.isoformat() if m.changed_at else None,
            }
            for m in models
        ]

    def get_provenance_chain(self, belief_id: str) -> ProvenanceChain:
        belief = self.get_belief(belief_id)
        if not belief:
            raise ValueError(f"Belief {belief_id} not found")

        history = self.get_belief_history(belief_id)
        
        # Supporting facts
        supporting_facts = [
            f for fid in belief.supporting_fact_ids if (f := self.get_fact(fid)) is not None
        ]
        
        # Contradicting facts
        contradicting_facts = [
            f for fid in belief.contradicting_fact_ids if (f := self.get_fact(fid)) is not None
        ]

        # Conflicts on this belief
        stmt = select(ConflictModel).where(ConflictModel.existing_belief_id == belief_id)
        c_models = self.session.scalars(stmt).all()
        conflicts: list[Conflict] = []
        resolutions: list[Resolution] = []
        for cm in c_models:
            res = self.get_resolution(cm.id)
            if res:
                resolutions.append(res)
            conflicts.append(
                Conflict(
                    id=cm.id,
                    conflict_type=cm.conflict_type,  # type: ignore
                    entity=cm.entity,
                    attribute=cm.attribute,
                    existing_belief_id=cm.existing_belief_id,
                    incoming_claim_id=cm.incoming_claim_id,
                    severity=cm.severity,  # type: ignore
                    description=cm.description,
                    detected_at=cm.detected_at,
                    resolution=res,
                )
            )

        # Relevant decisions
        all_fact_ids = set(belief.supporting_fact_ids + belief.contradicting_fact_ids)
        decisions = []
        for fid in all_fact_ids:
            decisions.extend(self.get_decisions_for_fact(fid))

        return ProvenanceChain(
            belief=belief,
            history=history,
            supporting_facts=supporting_facts,
            contradicting_facts=contradicting_facts,
            conflicts=conflicts,
            resolutions=resolutions,
            decisions=decisions,
        )

    def get_timeline(self) -> list[dict[str, Any]]:
        """Construct the step-by-step chronological evolution timeline of facts and beliefs."""
        facts_stmt = select(FactModel).order_by(FactModel.timestamp.asc())
        facts = self.session.scalars(facts_stmt).all()
        if not facts:
            return []

        all_claims = self.session.scalars(select(ClaimModel)).all()
        claims_by_fact: dict[str, list[ClaimModel]] = {}
        for c in all_claims:
            claims_by_fact.setdefault(c.fact_id, []).append(c)

        all_decisions = self.session.scalars(select(DecisionModel).order_by(DecisionModel.created_at.asc())).all()
        decisions_by_fact: dict[str, list[DecisionModel]] = {}
        for d in all_decisions:
            decisions_by_fact.setdefault(d.fact_id, []).append(d)

        all_conflicts = self.session.scalars(select(ConflictModel).order_by(ConflictModel.detected_at.asc())).all()
        conflicts_by_claim: dict[str, list[ConflictModel]] = {}
        for conf in all_conflicts:
            conflicts_by_claim.setdefault(conf.incoming_claim_id, []).append(conf)

        all_history = self.session.scalars(select(BeliefHistoryModel).order_by(BeliefHistoryModel.changed_at.asc())).all()
        history_by_fact: dict[str, list[BeliefHistoryModel]] = {}
        for h in all_history:
            history_by_fact.setdefault(h.changed_by_fact_id, []).append(h)

        all_beliefs = self.session.scalars(select(BeliefModel)).all()
        belief_meta = {b.id: (b.entity, b.attribute) for b in all_beliefs}

        timeline: list[dict[str, Any]] = []
        running_beliefs: dict[str, dict[str, Any]] = {}

        for idx, f in enumerate(facts):
            step_num = idx + 1
            f_claims = claims_by_fact.get(f.id, [])
            f_decisions = decisions_by_fact.get(f.id, [])
            f_history = history_by_fact.get(f.id, [])

            f_claim_ids = {c.id for c in f_claims}
            f_conflicts: list[Conflict] = []
            for cid in f_claim_ids:
                if cid in conflicts_by_claim:
                    for cm in conflicts_by_claim[cid]:
                        res = self.get_resolution(cm.id)
                        f_conflicts.append(
                            Conflict(
                                id=cm.id,
                                conflict_type=cm.conflict_type,  # type: ignore
                                entity=cm.entity,
                                attribute=cm.attribute,
                                existing_belief_id=cm.existing_belief_id,
                                incoming_claim_id=cm.incoming_claim_id,
                                severity=cm.severity,  # type: ignore
                                description=cm.description,
                                detected_at=cm.detected_at,
                                resolution=res,
                            )
                        )

            updated_belief_ids: set[str] = set()
            for h in f_history:
                b_id = h.belief_id
                updated_belief_ids.add(b_id)
                ent, attr = belief_meta.get(b_id, ("Unknown", "Unknown"))
                running_beliefs[b_id] = {
                    "id": b_id,
                    "entity": ent,
                    "attribute": attr,
                    "value": h.new_value,
                    "confidence": h.new_confidence,
                    "version": h.version,
                    "last_updated_by": f.id,
                    "status": "active",
                }

            snapshot = []
            for b_id, b_data in running_beliefs.items():
                snapshot.append({
                    **b_data,
                    "is_updated_in_this_step": b_id in updated_belief_ids,
                })

            snapshot.sort(key=lambda item: (item["entity"], item["attribute"]))

            has_conflict = len(f_conflicts) > 0
            if has_conflict:
                conf = f_conflicts[0]
                action_summary = f"⚡ Contradiction Resolved: {conf.entity} • {conf.attribute}"
            elif f_history:
                mut = f_history[0]
                ent, attr = belief_meta.get(mut.belief_id, ("", ""))
                if mut.old_value is not None:
                    action_summary = f"⚡ Updated '{ent} • {attr}' to '{mut.new_value}'"
                else:
                    action_summary = f"🟢 Created Ground Truth: '{ent} • {attr}' = '{mut.new_value}'"
            elif f_decisions:
                action_summary = f"🔵 Action: {f_decisions[0].action}"
            else:
                action_summary = "ℹ️ Processed fact"

            timeline.append({
                "step_number": step_num,
                "fact": {
                    "id": f.id,
                    "timestamp": f.timestamp,
                    "source": f.source,
                    "source_reliability": f.source_reliability,
                    "content": f.content,
                },
                "claims": [
                    Claim(
                        id=c.id,
                        entity=c.entity,
                        attribute=c.attribute,
                        value=c.value,
                        normalized_value=c.normalized_value,
                        unit=c.unit,
                        temporal_scope=c.temporal_scope,
                        claim_type=c.claim_type,  # type: ignore
                        confidence=c.confidence,
                        source_fact_id=c.fact_id,
                    )
                    for c in f_claims
                ],
                "decisions": [
                    Decision(
                        id=d.id,
                        fact_id=d.fact_id,
                        claim_id=d.claim_id,
                        action=d.action,  # type: ignore
                        reason=d.reason,
                        tier=d.tier,  # type: ignore
                        created_at=d.created_at,
                    )
                    for d in f_decisions
                ],
                "conflicts": f_conflicts,
                "mutations": [
                    {
                        "version": h.version,
                        "old_value": h.old_value,
                        "new_value": h.new_value,
                        "old_confidence": h.old_confidence,
                        "new_confidence": h.new_confidence,
                        "changed_by_fact_id": h.changed_by_fact_id,
                        "reason": h.reason,
                        "changed_at": h.changed_at or utc_now(),
                    }
                    for h in f_history
                ],
                "action_summary": action_summary,
                "has_conflict": has_conflict,
                "beliefs_snapshot": snapshot,
            })

        return timeline

    def clear_all(self) -> None:
        """Clear all tables (for database reset or testing)."""
        self.session.execute(delete(ResolutionModel))
        self.session.execute(delete(ConflictModel))
        self.session.execute(delete(DecisionModel))
        self.session.execute(delete(BeliefHistoryModel))
        self.session.execute(delete(BeliefModel))
        self.session.execute(delete(ClaimModel))
        self.session.execute(delete(SourceModel))
        self.session.execute(delete(FactModel))
        self.session.commit()

