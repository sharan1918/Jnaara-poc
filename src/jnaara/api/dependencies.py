from collections.abc import Generator
from fastapi import Request
from sqlalchemy.orm import Session

from jnaara.analysis.semantic import SemanticAnalyzer
from jnaara.analysis.validator import AnalysisValidator
from jnaara.belief.manager import BeliefManager
from jnaara.config import Settings, get_settings
from jnaara.conflict.detector import ConflictDetector
from jnaara.conflict.resolver import ConflictResolver
from jnaara.db.engine import get_db_engine, get_session_factory, init_db
from jnaara.db.repository import Repository
from jnaara.llm.factory import create_providers
from jnaara.llm.mock import MockLLMProvider

import logging

logger = logging.getLogger("jnaara.dependencies")

# Engine cache
_engine = None
_session_factory = None
_resolver = None


def get_configured_engine(settings: Settings):
    global _engine, _session_factory
    if _engine is None:
        _engine = get_db_engine(settings.db_path)
        init_db(_engine)
        _session_factory = get_session_factory(_engine)
    return _engine


def get_configured_session_factory(settings: Settings):
    global _session_factory
    if _session_factory is None:
        get_configured_engine(settings)
    return _session_factory


def get_db(request: Request) -> Generator[Session, None, None]:
    """Dependency that yields a database session and safely closes it."""
    settings = get_settings()
    factory = get_configured_session_factory(settings)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_conflict_resolver(request: Request) -> ConflictResolver:
    """Dependency for obtaining the active ConflictResolver singleton."""
    global _resolver
    if _resolver is None:
        settings = get_settings()
        _resolver = ConflictResolver(settings.default_strategy)
    return _resolver


def get_belief_manager(
    request: Request,
) -> Generator[tuple[Repository, BeliefManager, ConflictResolver, Session], None, None]:
    """Dependency that constructs the full belief pipeline for a request."""
    settings = get_settings()
    factory = get_configured_session_factory(settings)
    session = factory()
    repo = Repository(session)

    # Initialize providers: fallback to mock if keys missing
    has_groq = bool(settings.groq_api_key and settings.groq_api_key.get_secret_value().strip())
    has_google = bool(settings.google_api_key and settings.google_api_key.get_secret_value().strip())

    if (settings.primary_llm == "groq" and not has_groq) or (
        settings.secondary_llm == "gemini" and not has_google
    ):
        logger.info(
            "[Pipeline] Live API keys not set for configured providers (groq=%s, google=%s). Using MockLLMProvider.",
            has_groq,
            has_google,
        )
        primary = MockLLMProvider("mock-primary")
        secondary = MockLLMProvider("mock-secondary")
    else:
        try:
            primary, secondary = create_providers(settings)
            logger.info(
                "[Pipeline] Initialized live LLM providers: Primary=%s (%s), Secondary=%s (%s)",
                settings.primary_llm,
                settings.primary_model,
                settings.secondary_llm,
                settings.secondary_model,
            )
        except Exception as exc:
            logger.warning(
                "[Pipeline] Failed to create live LLM providers (%s). Falling back to mock providers.",
                exc,
            )
            primary = MockLLMProvider("mock-primary")
            secondary = MockLLMProvider("mock-secondary")

    analyzer = SemanticAnalyzer(primary, secondary, AnalysisValidator())
    detector = ConflictDetector(repo, analyzer)
    resolver = get_conflict_resolver(request)
    manager = BeliefManager(repo, analyzer, detector, resolver)

    try:
        yield repo, manager, resolver, session
    finally:
        session.close()
