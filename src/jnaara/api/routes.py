import json
import logging
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from jnaara.api.dependencies import get_belief_manager, get_conflict_resolver, get_db
from jnaara.api.schemas import (
    BeliefResponse,
    BeliefsListResponse,
    BulkFactsRequest,
    BulkProcessResponse,
    ClaimResponse,
    ConflictResponse,
    DecisionResponse,
    FactCreateRequest,
    FactProcessResponse,
    GenericSuccessResponse,
    ProvenanceHistoryItem,
    ProvenanceResponse,
    ResolutionResponse,
    StatsResponse,
    StrategySwitchRequest,
)
from jnaara.api.security import limiter
from jnaara.belief.manager import BeliefManager
from jnaara.conflict.resolver import ConflictResolver
from jnaara.db.repository import Repository
from jnaara.models.domain import Fact, utc_now
from jnaara.config import get_settings

logger = logging.getLogger("jnaara.routes")
router = APIRouter(prefix="/api", tags=["Belief Engine"])


def _to_claim_response(claim) -> ClaimResponse:
    return ClaimResponse(
        id=claim.id,
        entity=claim.entity,
        attribute=claim.attribute,
        value=claim.value,
        normalized_value=claim.normalized_value,
        unit=claim.unit,
        temporal_scope=claim.temporal_scope,
        claim_type=claim.claim_type,
        confidence=claim.confidence,
        source_fact_id=claim.source_fact_id,
    )


def _to_decision_response(dec) -> DecisionResponse:
    return DecisionResponse(
        id=dec.id,
        fact_id=dec.fact_id,
        claim_id=dec.claim_id,
        action=dec.action,
        reason=dec.reason,
        tier=dec.tier,
        created_at=dec.created_at,
    )


def _to_conflict_response(conf) -> ConflictResponse:
    res_resp = None
    if conf.resolution:
        res_resp = ResolutionResponse(
            id=conf.resolution.id,
            conflict_id=conf.resolution.conflict_id,
            strategy_used=conf.resolution.strategy_used,
            winner=conf.resolution.winner,
            rationale=conf.resolution.rationale,
            confidence_delta=conf.resolution.confidence_delta,
            resolved_at=conf.resolution.resolved_at,
        )
    return ConflictResponse(
        id=conf.id,
        conflict_type=conf.conflict_type,
        entity=conf.entity,
        attribute=conf.attribute,
        existing_belief_id=conf.existing_belief_id,
        incoming_claim_id=conf.incoming_claim_id,
        severity=conf.severity,
        description=conf.description,
        detected_at=conf.detected_at,
        resolution=res_resp,
    )


def _to_belief_response(b) -> BeliefResponse:
    return BeliefResponse(
        id=b.id,
        entity=b.entity,
        attribute=b.attribute,
        value=b.value,
        confidence=b.confidence,
        supporting_fact_ids=b.supporting_fact_ids,
        contradicting_fact_ids=b.contradicting_fact_ids,
        last_updated=b.last_updated,
        version=b.version,
        status=b.status,
    )


@router.post(
    "/facts",
    response_model=FactProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit and evaluate a single fact in real time",
)
@limiter.limit("60/minute")
def submit_fact(
    request: Request,
    payload: FactCreateRequest,
    pipeline: tuple[Repository, BeliefManager, ConflictResolver, Session] = Depends(get_belief_manager),
):
    """Submit a single factual statement to the belief engine.

    The fact will be analyzed by LLM (or mock fallback if API keys are absent),
    claims will be extracted, conflicts detected, and beliefs updated deterministically.
    """
    repo, manager, resolver, session = pipeline

    fact_id = payload.id or f"fact_{int(datetime.now().timestamp())}_{uuid4().hex[:6]}"
    timestamp = payload.timestamp or utc_now()

    logger.info(
        "[API] POST /api/facts -> fact_id='%s', source='%s' (rel=%s)",
        fact_id,
        payload.source,
        payload.source_reliability,
    )

    fact = Fact(
        id=fact_id,
        timestamp=timestamp,
        source=payload.source,
        source_reliability=payload.source_reliability,
        content=payload.content,
    )

    result = manager.process_fact(fact)

    claims_resp = [_to_claim_response(c) for c in result.claims]
    decisions_resp = [_to_decision_response(dec) for dec, _ in result.results]
    conflicts_resp = [
        _to_conflict_response(conf) for _, conf in result.results if conf is not None
    ]

    logger.info(
        "[API] POST /api/facts completed: fact_id='%s', claims=%d, conflicts=%d",
        result.fact_id,
        len(claims_resp),
        len(conflicts_resp),
    )

    return FactProcessResponse(
        fact_id=result.fact_id,
        skipped=result.skipped,
        claims_count=len(result.claims),
        claims=claims_resp,
        decisions=decisions_resp,
        conflicts=conflicts_resp,
    )


@router.post(
    "/facts/bulk",
    response_model=BulkProcessResponse,
    summary="Submit multiple facts in bulk as JSON",
)
@limiter.limit("15/minute")
def submit_bulk_facts(
    request: Request,
    payload: BulkFactsRequest,
    pipeline: tuple[Repository, BeliefManager, ConflictResolver, Session] = Depends(get_belief_manager),
):
    """Submit a list of facts to be processed sequentially."""
    repo, manager, resolver, session = pipeline

    logger.info("[API] POST /api/facts/bulk -> received %d facts", len(payload.facts))

    facts_to_process: list[Fact] = []
    for f in payload.facts:
        fact_id = f.id or f"fact_{int(datetime.now().timestamp())}_{uuid4().hex[:6]}"
        facts_to_process.append(
            Fact(
                id=fact_id,
                timestamp=f.timestamp or utc_now(),
                source=f.source,
                source_reliability=f.source_reliability,
                content=f.content,
            )
        )

    # Sort facts by timestamp to ensure causal/chronological ordering
    facts_to_process.sort(key=lambda item: item.timestamp)

    results: list[FactProcessResponse] = []
    total_claims = 0
    total_conflicts = 0
    total_skipped = 0

    for fact in facts_to_process:
        res = manager.process_fact(fact)
        if res.skipped:
            total_skipped += 1
        claims_resp = [_to_claim_response(c) for c in res.claims]
        decisions_resp = [_to_decision_response(dec) for dec, _ in res.results]
        conflicts_resp = [
            _to_conflict_response(conf) for _, conf in res.results if conf is not None
        ]

        total_claims += len(claims_resp)
        total_conflicts += len(conflicts_resp)

        results.append(
            FactProcessResponse(
                fact_id=res.fact_id,
                skipped=res.skipped,
                claims_count=len(claims_resp),
                claims=claims_resp,
                decisions=decisions_resp,
                conflicts=conflicts_resp,
            )
        )

    logger.info(
        "[API] POST /api/facts/bulk completed: %d submitted, %d processed, %d skipped, %d claims, %d conflicts",
        len(facts_to_process),
        len(facts_to_process) - total_skipped,
        total_skipped,
        total_claims,
        total_conflicts,
    )

    return BulkProcessResponse(
        total_submitted=len(facts_to_process),
        total_processed=len(facts_to_process) - total_skipped,
        total_skipped=total_skipped,
        total_claims=total_claims,
        total_conflicts=total_conflicts,
        results=results,
    )


@router.post(
    "/facts/upload",
    response_model=BulkProcessResponse,
    summary="Upload a JSON file containing facts or sequences",
)
@limiter.limit("15/minute")
async def upload_facts_file(
    request: Request,
    file: UploadFile = File(..., description="JSON file containing facts"),
    sequence: str | None = Query(None, description="Optional sequence key if dataset is keyed by sequence"),
    pipeline: tuple[Repository, BeliefManager, ConflictResolver, Session] = Depends(get_belief_manager),
):
    """Upload a JSON file containing facts or structured benchmark sequences."""
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a JSON file (.json extension).",
        )

    contents = await file.read()
    logger.info(
        "[API] POST /api/facts/upload -> filename='%s', size=%d bytes, sequence=%s",
        file.filename,
        len(contents),
        sequence,
    )
    try:
        data = json.loads(contents.decode("utf-8"))
    except Exception as exc:
        logger.warning("[API] POST /api/facts/upload -> failed to parse JSON from file '%s': %s", file.filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON format in file: {exc}",
        )

    raw_facts = []
    if isinstance(data, list):
        raw_facts = data
    elif isinstance(data, dict):
        if "facts" in data and isinstance(data["facts"], list):
            raw_facts = data["facts"]
        elif sequence and sequence in data and isinstance(data[sequence], list):
            raw_facts = data[sequence]
        else:
            # Flatten all sequences found in dictionary
            for seq_name, facts in data.items():
                if isinstance(facts, list):
                    raw_facts.extend(facts)

    if not raw_facts:
        logger.warning("[API] POST /api/facts/upload -> file '%s' contained 0 valid facts", file.filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid facts found in uploaded JSON file.",
        )

    repo, manager, resolver, session = pipeline
    facts_to_process: list[Fact] = []

    for item in raw_facts:
        if not isinstance(item, dict) or "content" not in item:
            continue
        ts = item.get("timestamp")
        parsed_ts = utc_now()
        if ts:
            try:
                parsed_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                pass

        fact_id = item.get("id") or f"fact_{int(datetime.now().timestamp())}_{uuid4().hex[:6]}"
        facts_to_process.append(
            Fact(
                id=str(fact_id),
                timestamp=parsed_ts,
                source=str(item.get("source", "uploaded_file")),
                source_reliability=item.get("source_reliability", "medium"),
                content=str(item["content"]),
            )
        )

    facts_to_process.sort(key=lambda item: item.timestamp)
    logger.info("[API] POST /api/facts/upload -> sorted and queued %d facts to process", len(facts_to_process))

    results: list[FactProcessResponse] = []
    total_claims = 0
    total_conflicts = 0
    total_skipped = 0

    for fact in facts_to_process:
        res = manager.process_fact(fact)
        if res.skipped:
            total_skipped += 1
        claims_resp = [_to_claim_response(c) for c in res.claims]
        decisions_resp = [_to_decision_response(dec) for dec, _ in res.results]
        conflicts_resp = [
            _to_conflict_response(conf) for _, conf in res.results if conf is not None
        ]

        total_claims += len(claims_resp)
        total_conflicts += len(conflicts_resp)

        results.append(
            FactProcessResponse(
                fact_id=res.fact_id,
                skipped=res.skipped,
                claims_count=len(claims_resp),
                claims=claims_resp,
                decisions=decisions_resp,
                conflicts=conflicts_resp,
            )
        )

    logger.info(
        "[API] POST /api/facts/upload completed for '%s': %d facts processed, %d skipped, %d claims extracted, %d conflicts",
        file.filename,
        len(facts_to_process) - total_skipped,
        total_skipped,
        total_claims,
        total_conflicts,
    )

    return BulkProcessResponse(
        total_submitted=len(facts_to_process),
        total_processed=len(facts_to_process) - total_skipped,
        total_skipped=total_skipped,
        total_claims=total_claims,
        total_conflicts=total_conflicts,
        results=results,
    )


@router.get(
    "/beliefs",
    response_model=BeliefsListResponse,
    summary="List currently held beliefs",
)
@limiter.limit("120/minute")
def get_beliefs(
    request: Request,
    entity: str | None = Query(None, description="Filter beliefs by entity name"),
    status: Literal["active", "superseded", "disputed"] | None = Query(
        "active", description="Filter by status (default 'active')"
    ),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: Session = Depends(get_db),
):
    """Retrieve held beliefs with entity and status filtering."""
    repo = Repository(session)
    if entity:
        beliefs = repo.get_beliefs_for_entity(entity, status=status)
    else:
        beliefs = repo.get_all_beliefs(status=status)

    total = len(beliefs)
    paginated = beliefs[offset : offset + limit]

    return BeliefsListResponse(
        total=total,
        beliefs=[_to_belief_response(b) for b in paginated],
    )


@router.get(
    "/beliefs/{belief_id}",
    response_model=BeliefResponse,
    summary="Get single belief by ID",
)
@limiter.limit("120/minute")
def get_belief_by_id(
    request: Request,
    belief_id: str,
    session: Session = Depends(get_db),
):
    """Retrieve details for a specific belief."""
    repo = Repository(session)
    belief = repo.get_belief(belief_id)
    if not belief:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Belief with ID '{belief_id}' not found.",
        )
    return _to_belief_response(belief)


@router.get(
    "/beliefs/{belief_id}/provenance",
    response_model=ProvenanceResponse,
    summary="Inspect complete provenance audit chain for a belief",
)
@limiter.limit("60/minute")
def get_belief_provenance(
    request: Request,
    belief_id: str,
    session: Session = Depends(get_db),
):
    """Retrieve full audit trail: history mutations, supporting & contradicting facts, conflicts, and decisions."""
    repo = Repository(session)
    try:
        prov = repo.get_provenance_chain(belief_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    history_items = [
        ProvenanceHistoryItem(
            version=h["version"],
            old_value=h.get("old_value"),
            new_value=h.get("new_value", ""),
            old_confidence=h.get("old_confidence"),
            new_confidence=h.get("new_confidence", 0.0),
            changed_by_fact_id=h.get("changed_by_fact_id", ""),
            reason=h.get("reason"),
            changed_at=h.get("changed_at") or utc_now(),
        )
        for h in prov.history
    ]

    conflicts_resp = [_to_conflict_response(c) for c in prov.conflicts]
    decisions_resp = [_to_decision_response(d) for d in prov.decisions]

    return ProvenanceResponse(
        belief=_to_belief_response(prov.belief),
        history=history_items,
        supporting_facts=[f.model_dump() for f in prov.supporting_facts],
        contradicting_facts=[f.model_dump() for f in prov.contradicting_facts],
        conflicts=conflicts_resp,
        decisions=decisions_resp,
    )


@router.get(
    "/conflicts",
    response_model=list[ConflictResponse],
    summary="List all detected conflicts",
)
@limiter.limit("120/minute")
def get_conflicts(
    request: Request,
    entity: str | None = Query(None, description="Filter conflicts by entity name"),
    session: Session = Depends(get_db),
):
    """Retrieve detected conflicts and how they were resolved."""
    repo = Repository(session)
    conflicts = repo.get_conflicts(entity=entity)
    return [_to_conflict_response(c) for c in conflicts]


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get overall knowledge base and system statistics",
)
@limiter.limit("120/minute")
def get_stats(
    request: Request,
    resolver: ConflictResolver = Depends(get_conflict_resolver),
    session: Session = Depends(get_db),
):
    """Retrieve executive statistics on facts, active beliefs, conflicts, and active strategy."""
    settings = get_settings()
    repo = Repository(session)
    all_facts = repo.get_all_facts()
    active_beliefs = repo.get_all_beliefs(status="active")
    all_conflicts = repo.get_conflicts()

    return StatsResponse(
        total_facts=len(all_facts),
        active_beliefs=len(active_beliefs),
        total_conflicts=len(all_conflicts),
        active_strategy=resolver.active_strategy,
        available_strategies=resolver.list_strategies(),
        primary_llm=settings.primary_llm,
        secondary_llm=settings.secondary_llm,
    )


@router.post(
    "/strategy",
    response_model=GenericSuccessResponse,
    summary="Switch active conflict resolution strategy",
)
@limiter.limit("30/minute")
def switch_strategy(
    request: Request,
    payload: StrategySwitchRequest,
    resolver: ConflictResolver = Depends(get_conflict_resolver),
):
    """Switch between 'recency' and 'corroboration' conflict resolution strategies."""
    try:
        old_strategy = resolver.active_strategy
        resolver.switch_strategy(payload.strategy)
        logger.info("[API] POST /api/strategy -> switched strategy from '%s' to '%s'", old_strategy, payload.strategy)
        return GenericSuccessResponse(
            message=f"Conflict resolution strategy successfully switched to '{payload.strategy}'.",
        )
    except ValueError as exc:
        logger.warning("[API] POST /api/strategy -> failed to switch strategy: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/reset",
    response_model=GenericSuccessResponse,
    summary="Reset database and clear all knowledge",
)
@limiter.limit("10/minute")
def reset_database(
    request: Request,
    session: Session = Depends(get_db),
):
    """Clear all facts, beliefs, claims, conflicts, and provenance history."""
    logger.warning("[API] POST /api/reset -> user requested complete database reset")
    repo = Repository(session)
    repo.clear_all()
    logger.info("[API] POST /api/reset -> database cleared successfully")
    return GenericSuccessResponse(
        message="Belief database cleared successfully.",
    )
