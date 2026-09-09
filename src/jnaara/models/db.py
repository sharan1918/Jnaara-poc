from datetime import datetime, timezone
import json
from typing import Any
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class FactModel(Base):
    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(256), nullable=False)
    source_reliability: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    claims: Mapped[list["ClaimModel"]] = relationship("ClaimModel", back_populates="fact", cascade="all, delete-orphan")
    decisions: Mapped[list["DecisionModel"]] = relationship("DecisionModel", back_populates="fact", cascade="all, delete-orphan")


class SourceModel(Base):
    __tablename__ = "sources"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reliability: Mapped[str] = mapped_column(String(16), nullable=False)
    independence_group: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ClaimModel(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fact_id: Mapped[str] = mapped_column(String(64), ForeignKey("facts.id"), nullable=False)
    entity: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attribute: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    temporal_scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    fact: Mapped["FactModel"] = relationship("FactModel", back_populates="claims")
    decisions: Mapped[list["DecisionModel"]] = relationship("DecisionModel", back_populates="claim", cascade="all, delete-orphan")


class BeliefModel(Base):
    __tablename__ = "beliefs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attribute: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    supporting_fact_ids: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    contradicting_fact_ids: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)

    history: Mapped[list["BeliefHistoryModel"]] = relationship("BeliefHistoryModel", back_populates="belief", cascade="all, delete-orphan")
    conflicts: Mapped[list["ConflictModel"]] = relationship("ConflictModel", back_populates="existing_belief")


class BeliefHistoryModel(Base):
    __tablename__ = "belief_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    belief_id: Mapped[str] = mapped_column(String(64), ForeignKey("beliefs.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    old_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    changed_by_fact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    belief: Mapped["BeliefModel"] = relationship("BeliefModel", back_populates="history")


class DecisionModel(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fact_id: Mapped[str] = mapped_column(String(64), ForeignKey("facts.id"), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(64), ForeignKey("claims.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    fact: Mapped["FactModel"] = relationship("FactModel", back_populates="decisions")
    claim: Mapped["ClaimModel"] = relationship("ClaimModel", back_populates="decisions")


class ConflictModel(Base):
    __tablename__ = "conflicts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conflict_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attribute: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    existing_belief_id: Mapped[str] = mapped_column(String(64), ForeignKey("beliefs.id"), nullable=False)
    incoming_claim_id: Mapped[str] = mapped_column(String(64), ForeignKey("claims.id"), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    existing_belief: Mapped["BeliefModel"] = relationship("BeliefModel", back_populates="conflicts")
    incoming_claim: Mapped["ClaimModel"] = relationship("ClaimModel")
    resolution: Mapped["ResolutionModel | None"] = relationship("ResolutionModel", back_populates="conflict", uselist=False, cascade="all, delete-orphan")


class ResolutionModel(Base):
    __tablename__ = "resolutions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conflict_id: Mapped[str] = mapped_column(String(64), ForeignKey("conflicts.id"), nullable=False, unique=True)
    strategy_used: Mapped[str] = mapped_column(String(64), nullable=False)
    winner: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_delta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    conflict: Mapped["ConflictModel"] = relationship("ConflictModel", back_populates="resolution")
