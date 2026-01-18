"""
Database configuration and connection management for Agentic AI Tutor.
Uses SQLAlchemy 2.0 with SQLite backend.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
import logging

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/tutor_app.db")


class Base(DeclarativeBase):
    """Base class for all ORM models using SQLAlchemy 2.0 declarative syntax"""

    pass


# Engine configuration with connection pooling for SQLite
engine = create_engine(
    DATABASE_URL,
    # SQLite-specific configurations
    poolclass=StaticPool,
    connect_args={
        "check_same_thread": False,  # Allow multiple threads
        "timeout": 20,  # Connection timeout
        "isolation_level": None,  # Use SQLite's default
    },
    echo=os.getenv("DB_ECHO", "false").lower() == "true",  # SQL logging
)

# Session factory using SQLAlchemy 2.0 syntax
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_database():
    """
    Database dependency injection for FastAPI routes.
    Provides a database session that automatically closes after use.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_database():
    """
    Initialize database by creating all tables.
    Creates data directory if it doesn't exist.
    """
    try:
        # Ensure data directory exists
        db_path = DATABASE_URL.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_db_session():
    """
    Get a database session for direct use (outside FastAPI).
    Remember to close the session after use.

    Returns:
        Session: SQLAlchemy database session
    """
    return SessionLocal()


# Health check function
def check_db_connection():
    """
    Check database connection health.

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
