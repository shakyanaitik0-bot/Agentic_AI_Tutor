"""
Pytest configuration and fixtures for Agentic AI Tutor tests.

Provides:
- Test database setup and teardown
- Mock services (LLM, embedding, RAG)
- Test client for API testing
- Sample data fixtures
"""
import os
import sys
import pytest
from typing import Generator, Dict, Any
from datetime import datetime
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_database
from app.models.student import Student
from app.models.session import Session as DBSession
from app.models.progress import Progress
from app.models.quiz import Quiz
from app.core.security import create_tokens, get_password_hash


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """
    Create a fresh test database for each test function.

    Uses in-memory SQLite for speed.
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create session
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with overridden database dependency.
    """
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_database] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_student(test_db: Session) -> Student:
    """Create a sample student for testing."""
    student = Student(
        id=str(uuid.uuid4()),
        name="Test Student",
        email="test@example.com",
        password_hash=get_password_hash("testpassword123"),
        exam_type="JEE",
        is_active=True
    )
    test_db.add(student)
    test_db.commit()
    test_db.refresh(student)
    return student


@pytest.fixture
def sample_student_with_progress(test_db: Session, sample_student: Student) -> Student:
    """Create a student with progress records."""
    # Add some progress records
    topics = [
        ("Calculus", "medium", 10, 7),  # 70% accuracy
        ("Algebra", "easy", 15, 12),    # 80% accuracy
        ("Physics", "hard", 8, 3),      # 37.5% accuracy (weak)
    ]

    for topic, difficulty, attempts, correct in topics:
        progress = Progress(
            student_id=sample_student.id,
            topic=topic,
            difficulty_level=difficulty,
            total_attempts=attempts,
            correct_answers=correct
        )
        test_db.add(progress)

    test_db.commit()
    return sample_student


@pytest.fixture
def sample_session(test_db: Session, sample_student: Student) -> DBSession:
    """Create a sample session for testing."""
    session = DBSession(
        id=str(uuid.uuid4()),
        student_id=sample_student.id,
        is_active=True,
        session_type="general"
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session


@pytest.fixture
def sample_quiz(test_db: Session, sample_student: Student) -> Quiz:
    """Create a sample quiz for testing."""
    quiz = Quiz(
        id=str(uuid.uuid4()),
        student_id=sample_student.id,
        topic="Calculus",
        difficulty="medium",
        num_questions=5
    )

    # Add some questions
    quiz.add_question(
        question_text="What is the derivative of x^2?",
        options=["2x", "x^2", "2", "x"],
        correct_answer="2x",
        explanation="Using the power rule: d/dx(x^n) = nx^(n-1)"
    )

    quiz.add_question(
        question_text="What is the integral of 2x?",
        options=["x^2 + C", "2x^2 + C", "x + C", "2 + C"],
        correct_answer="x^2 + C",
        explanation="The antiderivative of 2x is x^2 + C"
    )

    test_db.add(quiz)
    test_db.commit()
    test_db.refresh(quiz)
    return quiz


@pytest.fixture
def auth_headers(sample_student: Student) -> Dict[str, str]:
    """Generate authentication headers for a sample student."""
    tokens = create_tokens(sample_student.id, sample_student.email)
    return {"Authorization": f"Bearer {tokens.access_token}"}


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_response() -> str:
    """Sample LLM response for testing."""
    return "This is a mock LLM response for testing purposes."


@pytest.fixture
def mock_quiz_questions() -> list:
    """Sample quiz questions for testing."""
    return [
        {
            "id": "q_1",
            "text": "What is 2 + 2?",
            "options": ["3", "4", "5", "6"],
            "correct_answer": "4",
            "explanation": "Basic arithmetic",
            "difficulty": "easy"
        },
        {
            "id": "q_2",
            "text": "What is the capital of France?",
            "options": ["London", "Berlin", "Paris", "Madrid"],
            "correct_answer": "Paris",
            "explanation": "Paris is the capital of France",
            "difficulty": "easy"
        }
    ]


@pytest.fixture
def mock_embedding() -> list:
    """Sample embedding vector for testing (384 dimensions like MiniLM)."""
    import random
    return [random.uniform(-1, 1) for _ in range(384)]


# ============================================================================
# Environment Setup
# ============================================================================

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing-only")
    monkeypatch.setenv("DEBUG", "true")


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_student(
    db: Session,
    name: str = "Test User",
    email: str = None,
    exam_type: str = "JEE"
) -> Student:
    """Helper to create test students."""
    if email is None:
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    student = Student(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        password_hash=get_password_hash("password123"),
        exam_type=exam_type,
        is_active=True
    )
    db.add(student)
    db.commit()
    return student
