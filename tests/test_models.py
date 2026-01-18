"""
Model unit tests for Agentic AI Tutor.

Tests cover:
- Student model functionality
- Session model functionality
- Progress model calculations
- Quiz model operations
"""
import pytest
from datetime import datetime, timedelta
import uuid

from app.models.student import Student
from app.models.session import Session as DBSession
from app.models.progress import Progress, DifficultyLevel, StrengthLevel
from app.models.quiz import Quiz, QuizStatus, QuestionType
from app.core.security import get_password_hash, verify_password


class TestStudentModel:
    """Test Student model functionality."""

    def test_student_creation(self, test_db):
        """Test creating a new student."""
        student = Student(
            id=str(uuid.uuid4()),
            name="Test Student",
            email="test@example.com",
            password_hash=get_password_hash("password123"),
            exam_type="JEE"
        )
        test_db.add(student)
        test_db.commit()

        assert student.id is not None
        assert student.name == "Test Student"
        assert student.exam_type == "JEE"
        assert student.is_active is True

    def test_student_password_verification(self, sample_student):
        """Test password verification."""
        assert sample_student.verify_password("testpassword123") is True
        assert sample_student.verify_password("wrongpassword") is False

    def test_student_default_preferences(self, sample_student):
        """Test default learning preferences are set."""
        assert sample_student.learning_preferences is not None
        assert "preferred_difficulty" in sample_student.learning_preferences

    def test_update_weak_areas(self, sample_student):
        """Test updating weak areas."""
        sample_student.update_weak_areas(["Calculus", "Physics"])
        assert "Calculus" in sample_student.weak_areas
        assert "Physics" in sample_student.weak_areas

    def test_update_strong_areas(self, sample_student):
        """Test updating strong areas."""
        sample_student.update_strong_areas(["Algebra", "Chemistry"])
        assert "Algebra" in sample_student.strong_areas
        assert "Chemistry" in sample_student.strong_areas

    def test_weak_strong_mutual_exclusion(self, sample_student):
        """Test that topics can't be both weak and strong."""
        sample_student.update_weak_areas(["Calculus"])
        assert "Calculus" in sample_student.weak_areas

        sample_student.update_strong_areas(["Calculus"])
        assert "Calculus" in sample_student.strong_areas
        assert "Calculus" not in sample_student.weak_areas

    def test_profile_summary(self, sample_student):
        """Test profile summary generation."""
        summary = sample_student.get_profile_summary()
        assert summary["student_id"] == sample_student.id
        assert summary["exam_type"] == sample_student.exam_type
        assert "weak_areas" in summary
        assert "strong_areas" in summary


class TestSessionModel:
    """Test Session model functionality."""

    def test_session_creation(self, test_db, sample_student):
        """Test creating a new session."""
        session = DBSession(
            id=str(uuid.uuid4()),
            student_id=sample_student.id,
            session_type="general"
        )
        test_db.add(session)
        test_db.commit()

        assert session.id is not None
        assert session.is_active is True
        assert session.student_id == sample_student.id

    def test_session_end(self, sample_session, test_db):
        """Test ending a session."""
        sample_session.is_active = False
        sample_session.ended_at = datetime.utcnow()
        test_db.commit()

        assert sample_session.is_active is False
        assert sample_session.ended_at is not None


class TestProgressModel:
    """Test Progress model functionality."""

    def test_progress_creation(self, test_db, sample_student):
        """Test creating progress record."""
        progress = Progress(
            student_id=sample_student.id,
            topic="Calculus",
            difficulty_level="medium"
        )
        test_db.add(progress)
        test_db.commit()

        assert progress.id is not None
        assert progress.accuracy_percentage == 0.0

    def test_accuracy_calculation(self, test_db, sample_student):
        """Test accuracy percentage calculation."""
        progress = Progress(
            student_id=sample_student.id,
            topic="Calculus",
            difficulty_level="medium",
            total_attempts=10,
            correct_answers=7
        )
        test_db.add(progress)
        test_db.commit()

        assert progress.accuracy_percentage == 70.0

    def test_record_attempt_correct(self, test_db, sample_student):
        """Test recording a correct attempt."""
        progress = Progress.get_or_create_progress(
            test_db,
            sample_student.id,
            "Calculus",
            "medium"
        )

        progress.record_attempt(is_correct=True, time_spent_minutes=2.0)
        test_db.commit()

        assert progress.total_attempts == 1
        assert progress.correct_answers == 1
        assert progress.consecutive_correct == 1

    def test_record_attempt_incorrect(self, test_db, sample_student):
        """Test recording an incorrect attempt."""
        progress = Progress.get_or_create_progress(
            test_db,
            sample_student.id,
            "Physics",
            "hard"
        )

        # First correct, then incorrect
        progress.record_attempt(is_correct=True)
        progress.record_attempt(is_correct=False, mistake_pattern="sign error")
        test_db.commit()

        assert progress.total_attempts == 2
        assert progress.correct_answers == 1
        assert progress.consecutive_correct == 0
        assert "sign error" in progress.common_mistakes

    def test_strength_level_weak(self, test_db, sample_student):
        """Test weak strength level classification."""
        progress = Progress(
            student_id=sample_student.id,
            topic="Physics",
            difficulty_level="hard",
            total_attempts=10,
            correct_answers=4  # 40% - weak
        )
        progress._update_strength_level()

        assert progress.current_strength_level == StrengthLevel.WEAK.value

    def test_strength_level_average(self, test_db, sample_student):
        """Test average strength level classification."""
        progress = Progress(
            student_id=sample_student.id,
            topic="Chemistry",
            difficulty_level="medium",
            total_attempts=10,
            correct_answers=7  # 70% - average
        )
        progress._update_strength_level()

        assert progress.current_strength_level == StrengthLevel.AVERAGE.value

    def test_strength_level_strong(self, test_db, sample_student):
        """Test strong strength level classification."""
        progress = Progress(
            student_id=sample_student.id,
            topic="Algebra",
            difficulty_level="easy",
            total_attempts=10,
            correct_answers=9  # 90% - strong
        )
        progress._update_strength_level()

        assert progress.current_strength_level == StrengthLevel.STRONG.value

    def test_recommended_difficulty_easy(self, test_db, sample_student):
        """Test difficulty recommendation for struggling students."""
        progress = Progress(
            student_id=sample_student.id,
            topic="Physics",
            difficulty_level="hard",
            total_attempts=10,
            correct_answers=3  # 30%
        )

        recommended = progress.get_recommended_difficulty()
        assert recommended == DifficultyLevel.EASY

    def test_recommended_difficulty_hard(self, test_db, sample_student):
        """Test difficulty recommendation for excelling students."""
        progress = Progress(
            student_id=sample_student.id,
            topic="Algebra",
            difficulty_level="easy",
            total_attempts=10,
            correct_answers=9  # 90%
        )

        recommended = progress.get_recommended_difficulty()
        assert recommended == DifficultyLevel.HARD

    def test_is_stale(self, test_db, sample_student):
        """Test stale topic detection."""
        progress = Progress(
            student_id=sample_student.id,
            topic="Chemistry",
            difficulty_level="medium",
            last_practiced=datetime.utcnow() - timedelta(days=10)
        )

        assert progress.is_stale is True

    def test_student_overview(self, test_db, sample_student_with_progress):
        """Test comprehensive student overview."""
        overview = Progress.get_student_overview(test_db, sample_student_with_progress.id)

        assert overview["total_topics"] > 0
        assert "weak_areas" in overview
        assert "strong_areas" in overview
        assert "recommendation" in overview


class TestQuizModel:
    """Test Quiz model functionality."""

    def test_quiz_creation(self, test_db, sample_student):
        """Test creating a new quiz."""
        quiz = Quiz(
            student_id=sample_student.id,
            topic="Calculus",
            difficulty="medium",
            num_questions=5
        )
        test_db.add(quiz)
        test_db.commit()

        assert quiz.id is not None
        assert quiz.status == QuizStatus.CREATED.value
        assert quiz.topic == "Calculus"

    def test_add_question(self, sample_quiz):
        """Test adding questions to quiz."""
        initial_count = len(sample_quiz.questions)

        q_id = sample_quiz.add_question(
            question_text="What is 2 + 2?",
            options=["3", "4", "5", "6"],
            correct_answer="4",
            explanation="Basic arithmetic"
        )

        assert len(sample_quiz.questions) == initial_count + 1
        assert q_id.startswith("q_")

    def test_submit_correct_response(self, sample_quiz):
        """Test submitting a correct response."""
        result = sample_quiz.submit_response("q_1", "2x")

        assert result["is_correct"] is True
        assert result["points_earned"] == 1.0
        assert "q_1" in sample_quiz.responses

    def test_submit_incorrect_response(self, sample_quiz):
        """Test submitting an incorrect response."""
        result = sample_quiz.submit_response("q_1", "wrong answer")

        assert result["is_correct"] is False
        assert result["points_earned"] == 0
        assert result["correct_answer"] == "2x"

    def test_complete_quiz(self, sample_quiz):
        """Test completing a quiz."""
        # Submit all answers
        sample_quiz.submit_response("q_1", "2x")  # Correct
        sample_quiz.submit_response("q_2", "x^2 + C")  # Correct

        result = sample_quiz.complete_quiz()

        assert sample_quiz.status == QuizStatus.COMPLETED.value
        assert result["total_questions"] == 2
        assert result["correct"] == 2
        assert result["percentage"] == 100.0
        assert result["passed"] is True

    def test_quiz_failing_score(self, sample_quiz):
        """Test quiz with failing score."""
        # Submit wrong answers
        sample_quiz.submit_response("q_1", "wrong")
        sample_quiz.submit_response("q_2", "wrong")

        result = sample_quiz.complete_quiz()

        assert result["percentage"] == 0.0
        assert result["passed"] is False

    def test_quiz_start(self, sample_quiz):
        """Test starting a quiz."""
        sample_quiz.start_quiz()

        assert sample_quiz.status == QuizStatus.IN_PROGRESS.value
        assert sample_quiz.started_at is not None

    def test_quiz_abandon(self, sample_quiz):
        """Test abandoning a quiz."""
        sample_quiz.start_quiz()
        sample_quiz.abandon_quiz()

        assert sample_quiz.status == QuizStatus.ABANDONED.value

    def test_questions_for_display(self, sample_quiz):
        """Test getting questions for display."""
        # Without answers
        questions = sample_quiz.get_questions_for_display(include_answers=False)
        assert len(questions) == 2
        assert "correct_answer" not in questions[0]

        # With answers
        questions_with_answers = sample_quiz.get_questions_for_display(include_answers=True)
        assert "correct_answer" in questions_with_answers[0]

    def test_performance_by_difficulty(self, sample_quiz):
        """Test performance breakdown by difficulty."""
        sample_quiz.submit_response("q_1", "2x")

        performance = sample_quiz.get_performance_by_difficulty()
        assert "medium" in performance
        assert performance["medium"]["total"] > 0

    def test_quiz_to_dict(self, sample_quiz):
        """Test quiz serialization."""
        quiz_dict = sample_quiz.to_dict()

        assert quiz_dict["id"] == sample_quiz.id
        assert quiz_dict["topic"] == sample_quiz.topic
        assert "questions" in quiz_dict
