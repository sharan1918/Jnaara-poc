from pathlib import Path
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from jnaara.models.db import Base


def get_db_engine(db_path: Path | str = "data/jnaara.db") -> Engine:
    """Create and return a SQLAlchemy engine for SQLite."""
    if isinstance(db_path, str) and db_path != ":memory:":
        db_path = Path(db_path)
    
    if db_path == ":memory:":
        engine = create_engine(
            "sqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    elif isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path.resolve()}"
        engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
    else:
        url = f"sqlite:///{db_path}"
        engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})

    # Enable SQLite foreign key enforcement
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create and return a sessionmaker bound to the engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Initialize all database tables."""
    Base.metadata.create_all(bind=engine)
