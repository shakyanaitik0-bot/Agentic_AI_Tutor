"""
Quiz model for Agentic AI Tutor.
Stores generated quizzes, student responses, and grading results.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import flag_modified
from enum import Enum
import logging

from app.core.database import Base

logger = logging.getLogger(__name__)

# A quiz is considered passed at 60% or above
PASSING_PERCENTAGE = 60.0


class QuizStatus(Enum):
    """Enum for the lifecycle states of a quiz"""

    CREATED = "created"  # Generated, not yet started
    IN_PROGRESS = "in_progress"  # Student is answering
    COMPLETED = "completed"  # All answers submitted and graded
    ABANDONED = "abandoned"  # Started but never finished


class QuestionType(Enum):
    """Enum for the kinds of questions a quiz can contain"""

    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    NUMERICAL = "numerical"
    DESCRIPTIVE = "descriptive"


class Quiz(Base):
    """
    Quiz model holding an adaptive quiz generated for a student.

    Questions and responses are stored as JSON so the Quiz Generator Agent can
    shape them freely, while the columns carry everything needed for analytics:
    which topic, which difficulty, how the student scored and how long it took.
    """

    __tablename__ = "quizzes"

    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Student relationship
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    student = relationship("Student", back_populates="quizzes")

    # Quiz definition
    topic = Column(String(100), nullable=False, index=True)
    subtopic = Column(String(100), nullable=True)
    difficulty = Column(String(20), default="medium", nullable=False, index=True)
    num_questions = Column(Integer, default=0, nullable=False)  # Requested question count

    # Question bank and student answers (JSON for flexibility)
    questions = Column(JSON, nullable=True, default=list)  # List of question dicts
    responses = Column(JSON, nullable=True, default=dict)  # question_id -> response dict

    # Lifecycle
    status = Column(String(20), default=QuizStatus.CREATED.value, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Results (populated by complete_quiz)
    score = Column(Float, default=0.0, nullable=False)  # Points earned
    correct_answers = Column(Integer, default=0, nullable=False)
    time_spent_seconds = Column(Float, default=0.0, nullable=False)

    def __init__(self, **kwargs):
        """Initialize quiz with empty question and response containers"""
        super().__init__(**kwargs)

        if not self.questions:
            self.questions = []
        if not self.responses:
            self.responses = {}
        if not self.status:
            self.status = QuizStatus.CREATED.value

    @property
    def total_questions(self) -> int:
        """
        Number of questions actually present in the quiz.

        Returns:
            int: Question count (may differ from the requested num_questions)
        """
        return len(self.questions or [])

    @property
    def answered_count(self) -> int:
        """
        Number of questions the student has responded to.

        Returns:
            int: Count of submitted responses
        """
        return len(self.responses or {})

    @property
    def accuracy_percentage(self) -> float:
        """
        Accuracy across answered questions.

        Returns:
            float: Accuracy as percentage (0-100)
        """
        if self.answered_count == 0:
            return 0.0
        return (self.correct_answers / self.answered_count) * 100

    @property
    def is_complete(self) -> bool:
        """
        Check whether every question has been answered.

        Returns:
            bool: True if all questions have a response
        """
        return self.total_questions > 0 and self.answered_count >= self.total_questions

    def add_question(
        self,
        question_text: str,
        options: List[str],
        correct_answer: str,
        explanation: str = "",
        difficulty: Optional[str] = None,
        question_type: str = QuestionType.MULTIPLE_CHOICE.value,
        topic: Optional[str] = None,
    ) -> str:
        """
        Add a question to the quiz.

        Args:
            question_text: The question being asked
            options: Answer options to choose from
            correct_answer: The correct option
            explanation: Why the correct answer is correct
            difficulty: Question difficulty, defaults to the quiz difficulty
            question_type: Type of question (multiple_choice, numerical, etc.)
            topic: Question topic, defaults to the quiz topic

        Returns:
            str: Generated question ID (e.g. "q_1")
        """
        if self.questions is None:
            self.questions = []

        question_id = f"q_{len(self.questions) + 1}"
        question = {
            "id": question_id,
            "question_text": question_text,
            "options": list(options or []),
            "correct_answer": correct_answer,
            "explanation": explanation,
            "difficulty": difficulty or self.difficulty or "medium",
            "question_type": question_type,
            "topic": topic or self.topic,
        }

        # Reassign so SQLAlchemy detects the mutation on the JSON column
        self.questions = self.questions + [question]
        flag_modified(self, "questions")

        return question_id

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up a question by its ID.

        Args:
            question_id: The question ID to find

        Returns:
            Optional[Dict]: The question dict, or None if not found
        """
        for question in self.questions or []:
            if question.get("id") == question_id:
                return question
        return None

    def start_quiz(self) -> None:
        """Mark the quiz as started and record the start time"""
        self.status = QuizStatus.IN_PROGRESS.value
        self.started_at = datetime.utcnow()
        logger.debug(f"Quiz {self.id} started for student {self.student_id}")

    def submit_response(
        self,
        question_id: str,
        selected_answer: str,
        time_spent_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Record the student's answer to a single question and grade it.

        Args:
            question_id: ID of the question being answered
            selected_answer: The option the student chose
            time_spent_seconds: Time spent on this question

        Returns:
            Dict: Grading result with is_correct, correct_answer, explanation
                  and points_earned. Contains an "error" key if the question
                  does not exist.
        """
        question = self.get_question(question_id)
        if not question:
            logger.warning(f"Question {question_id} not found in quiz {self.id}")
            return {
                "error": f"Question {question_id} not found",
                "is_correct": False,
                "points_earned": 0,
            }

        # First answer implicitly starts the quiz
        if self.status == QuizStatus.CREATED.value:
            self.start_quiz()

        is_correct = str(selected_answer).strip() == str(question["correct_answer"]).strip()
        points_earned = 1.0 if is_correct else 0

        if self.responses is None:
            self.responses = {}

        already_answered = question_id in self.responses
        was_correct_before = already_answered and self.responses[question_id].get("is_correct")

        response = {
            "question_id": question_id,
            "selected_answer": selected_answer,
            "correct_answer": question["correct_answer"],
            "is_correct": is_correct,
            "points_earned": points_earned,
            "time_spent_seconds": time_spent_seconds,
            "answered_at": datetime.utcnow().isoformat(),
        }

        # Reassign so SQLAlchemy detects the mutation on the JSON column
        self.responses = {**self.responses, question_id: response}
        flag_modified(self, "responses")

        # Keep running totals in sync, including when an answer is revised
        if self.correct_answers is None:
            self.correct_answers = 0
        if self.score is None:
            self.score = 0.0
        if self.time_spent_seconds is None:
            self.time_spent_seconds = 0.0

        if was_correct_before and not is_correct:
            self.correct_answers -= 1
            self.score -= 1.0
        elif is_correct and not was_correct_before:
            self.correct_answers += 1
            self.score += 1.0

        self.time_spent_seconds += time_spent_seconds

        return {
            "question_id": question_id,
            "is_correct": is_correct,
            "points_earned": points_earned,
            "correct_answer": question["correct_answer"],
            "explanation": question.get("explanation", ""),
        }

    def complete_quiz(self) -> Dict[str, Any]:
        """
        Finish the quiz and compute the final result.

        Returns:
            Dict: Summary with total_questions, correct, percentage, passed,
                  score and time spent
        """
        self.status = QuizStatus.COMPLETED.value
        self.completed_at = datetime.utcnow()

        total = self.total_questions
        correct = self.correct_answers or 0
        percentage = (correct / total * 100) if total > 0 else 0.0

        result = {
            "quiz_id": self.id,
            "student_id": self.student_id,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "total_questions": total,
            "answered": self.answered_count,
            "correct": correct,
            "percentage": round(percentage, 1),
            "passed": percentage >= PASSING_PERCENTAGE,
            "score": self.score or 0.0,
            "time_spent_seconds": round(self.time_spent_seconds or 0.0, 1),
        }

        logger.info(
            f"Quiz {self.id} completed: {correct}/{total} ({result['percentage']}%) "
            f"for student {self.student_id}"
        )
        return result

    def abandon_quiz(self) -> None:
        """Mark the quiz as abandoned without grading it"""
        self.status = QuizStatus.ABANDONED.value
        self.completed_at = datetime.utcnow()
        logger.debug(f"Quiz {self.id} abandoned by student {self.student_id}")

    def get_questions_for_display(self, include_answers: bool = False) -> List[Dict[str, Any]]:
        """
        Get questions formatted for the client.

        Args:
            include_answers: Whether to include correct answers and explanations

        Returns:
            List[Dict]: Questions, stripped of answers unless requested
        """
        display_questions = []

        for question in self.questions or []:
            item = {
                "id": question.get("id"),
                "question_text": question.get("question_text"),
                "options": question.get("options", []),
                "difficulty": question.get("difficulty"),
                "question_type": question.get("question_type"),
                "topic": question.get("topic"),
            }

            if include_answers:
                item["correct_answer"] = question.get("correct_answer")
                item["explanation"] = question.get("explanation", "")

            display_questions.append(item)

        return display_questions

    def get_performance_by_difficulty(self) -> Dict[str, Dict[str, Any]]:
        """
        Break down performance across the difficulty levels in this quiz.

        Returns:
            Dict: difficulty -> {total, correct, accuracy}
        """
        performance: Dict[str, Dict[str, Any]] = {}

        for question_id, response in (self.responses or {}).items():
            question = self.get_question(question_id)
            if not question:
                continue

            difficulty = question.get("difficulty", "medium")
            bucket = performance.setdefault(difficulty, {"total": 0, "correct": 0, "accuracy": 0.0})

            bucket["total"] += 1
            if response.get("is_correct"):
                bucket["correct"] += 1

        for bucket in performance.values():
            bucket["accuracy"] = round(bucket["correct"] / bucket["total"] * 100, 1)

        return performance

    def get_topics_to_review(self) -> List[str]:
        """
        Get the topics the student answered incorrectly.

        Returns:
            List[str]: Unique topics needing review
        """
        topics = []

        for question_id, response in (self.responses or {}).items():
            if response.get("is_correct"):
                continue
            question = self.get_question(question_id)
            topic = (question or {}).get("topic") or self.topic
            if topic and topic not in topics:
                topics.append(topic)

        return topics

    def to_dict(self, include_answers: bool = True) -> Dict[str, Any]:
        """
        Serialize the quiz for API responses and agent context.

        Args:
            include_answers: Whether questions should carry their answers

        Returns:
            Dict: Quiz representation
        """
        return {
            "id": self.id,
            "quiz_id": self.id,
            "student_id": self.student_id,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "difficulty": self.difficulty,
            "status": self.status,
            "num_questions": self.num_questions,
            "total_questions": self.total_questions,
            "questions": self.get_questions_for_display(include_answers=include_answers),
            "responses": self.responses or {},
            "correct_answers": self.correct_answers,
            "score": self.score,
            "accuracy_percentage": round(self.accuracy_percentage, 1),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self):
        return (
            f"<Quiz(id='{self.id}', topic='{self.topic}', "
            f"difficulty='{self.difficulty}', status='{self.status}')>"
        )

    def __str__(self):
        return (
            f"{self.topic} quiz ({self.difficulty}): "
            f"{self.correct_answers}/{self.total_questions} correct - {self.status}"
        )
