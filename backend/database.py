"""
Database connection setup.

We use SQLAlchemy's classic engine + session pattern. This is the standard,
well-documented way to talk to PostgreSQL from FastAPI, and it keeps the
door open for adding more tables later without rewriting this file.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

# The engine manages the pool of connections to PostgreSQL.
# pool_pre_ping=True avoids using a dead connection after e.g. Postgres restarts.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# Each request gets its own Session from this factory.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# All ORM models (see models.py) inherit from this Base.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a database session and guarantees
    it is closed afterwards, even if the request raises an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
