from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from jnaara.analysis.semantic import SemanticAnalyzer
from jnaara.analysis.validator import AnalysisValidator
from jnaara.belief.manager import BeliefManager
from jnaara.conflict.detector import ConflictDetector
from jnaara.conflict.resolver import ConflictResolver
from jnaara.db.engine import get_db_engine, get_session_factory, init_db
from jnaara.db.repository import Repository
from jnaara.llm.mock import MockLLMProvider
from jnaara.models.domain import Fact


@pytest.fixture
def db_engine() -> Engine:
    """Create in-memory SQLite engine with all tables initialized."""
    engine = get_db_engine(":memory:")
    init_db(engine)
    return engine


@pytest.fixture
def db_session(db_engine: Engine):
    """Provide a transactional database session for tests."""
    session = get_session_factory(db_engine)()
    yield session
    session.close()


@pytest.fixture
def repository(db_session: Session) -> Repository:
    """Provide a Repository instance bound to the test session."""
    return Repository(db_session)


@pytest.fixture
def mock_primary() -> MockLLMProvider:
    return MockLLMProvider("mock-primary")


@pytest.fixture
def mock_secondary() -> MockLLMProvider:
    return MockLLMProvider("mock-secondary")


@pytest.fixture
def validator() -> AnalysisValidator:
    return AnalysisValidator()


@pytest.fixture
def analyzer(mock_primary: MockLLMProvider, mock_secondary: MockLLMProvider, validator: AnalysisValidator) -> SemanticAnalyzer:
    return SemanticAnalyzer(mock_primary, mock_secondary, validator)


@pytest.fixture
def detector(repository: Repository, analyzer: SemanticAnalyzer) -> ConflictDetector:
    return ConflictDetector(repository, analyzer)


@pytest.fixture
def resolver() -> ConflictResolver:
    return ConflictResolver("recency")


@pytest.fixture
def manager(
    repository: Repository,
    analyzer: SemanticAnalyzer,
    detector: ConflictDetector,
    resolver: ConflictResolver,
) -> BeliefManager:
    return BeliefManager(repository, analyzer, detector, resolver)


@pytest.fixture
def sample_fact_e1() -> Fact:
    return Fact(
        id="E1",
        timestamp=datetime(2025, 1, 10, 9, 0, tzinfo=timezone.utc),
        source="NovaTech Q4 Earnings Release",
        source_reliability="high",
        content="NovaTech Inc. reported Q4 2024 revenue of $480M, representing 32% year-over-year growth.",
    )


@pytest.fixture
def sample_fact_e7() -> Fact:
    return Fact(
        id="E7",
        timestamp=datetime(2025, 1, 22, 8, 0, tzinfo=timezone.utc),
        source="SEC Filing (8-K)",
        source_reliability="high",
        content="NovaTech Inc. issued a restatement: Q4 2024 revenue was $412M, not $480M as previously reported.",
    )


@pytest.fixture
def dataset_path() -> Path:
    return Path("data/jnaara_memory_facts_dataset.json")
