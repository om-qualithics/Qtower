from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from apps.api.core.settings import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def org_scoped_session(org_id: str) -> Generator[Session, None, None]:
    """Yields a session with Postgres RLS scoped to org_id for the duration
    of one transaction. Every org-scoped table's RLS policy reads this
    session variable, so this is the only way feature code should touch
    tenant data once the identity module wires it into request handling.
    """
    db = SessionLocal()
    try:
        # set_config (not "SET LOCAL ...") because SET does not accept bind
        # parameters in Postgres; this keeps org_id safely parameterized.
        db.execute(text("SELECT set_config('app.current_org_id', :org_id, true)"), {"org_id": org_id})
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
