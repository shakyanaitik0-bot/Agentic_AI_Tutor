"""
Progress tracking model for Agentic AI Tutor.
Handles learning analytics, performance tracking, and adaptive difficulty assessment.
"""

from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import flag_modified
from enum import Enum
import logging

from app.core.database import Base

logger = logging.getLogger(__name__)


class DifficultyLevel(Enum):
    """Enum for difficulty levels used in adaptive learning"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class StrengthLevel(Enum):
    """Enum for student strength levels in topics"""

    WEAK = "weak"  # < 60% accuracy
    AVERAGE = "average"  # 60-80% accuracy
    STRONG = "strong"  # > 80% accuracy


class Progress(Base):
    """
    Progress model tracking student performance across topics and difficulty levels.

    This model enables the Progress Tracker Agent to:
    - Assess student strengths and weaknesses
    - Recommend appropriate difficulty levels
    - Track learning gains over time
    - Identify topics needing review
    """

    __tablename__ = "progress"

    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Student relationship
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    student = relationship("Student", back_populates="progress_records")

    # Topic and difficulty tracking
    topic = Column(String(100), nullable=False, index=True)
    subtopic = Column(String(100), nullable=True, index=True)  # More granular tracking
    difficulty_level = Column(String(20), nullable=False, index=True)  # easy, medium, hard

    # Performance metrics
    total_attempts = Column(Integer, default=0, nullable=False)
    correct_answers = Column(Integer, default=0, nullable=False)
    total_time_spent_minutes = Column(Float, default=0.0, nullable=False)  # Time spent on topic

    # Learning progression
    first_attempted = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_practiced = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    consecutive_correct = Column(Integer, default=0, nullable=False)  # Current streak
    max_streak = Column(Integer, default=0, nullable=False)  # Best streak achieved

    # Adaptive learning state
    current_strength_level = Column(String(20), default=StrengthLevel.WEAK.value, nullable=False)
    needs_review = Column(Boolean, default=False, nullable=False, index=True)
    mastery_achieved = Column(
        Boolean, default=False, nullable=False
    )  # 85%+ accuracy, recent practice

    # Detailed analytics (JSON for flexibility)
    question_types_performance = Column(
        JSON, nullable=True, default=dict
    )  # MCQ vs. descriptive etc.
    common_mistakes = Column(JSON, nullable=True, default=list)  # Patterns in wrong answers
    learning_velocity = Column(Float, nullable=True)  # Rate of improvement

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs):
        """Initialize progress record with default values"""
        super().__init__(**kwargs)

        if not self.question_types_performance:
            self.question_types_performance = {
                "multiple_choice": {"attempts": 0, "correct": 0},
                "descriptive": {"attempts": 0, "correct": 0},
                "numerical": {"attempts": 0, "correct": 0},
            }
        if not self.common_mistakes:
            self.common_mistakes = []

    @property
    def accuracy_percentage(self) -> float:
        """
        Calculate accuracy percentage for this topic/difficulty.

        Returns:
            float: Accuracy as percentage (0-100)
        """
        if self.total_attempts == 0:
            return 0.0
        return (self.correct_answers / self.total_attempts) * 100

    @property
    def average_time_per_question(self) -> float:
        """
        Calculate average time spent per question in minutes.

        Returns:
            float: Average time in minutes, 0 if no attempts
        """
        if self.total_attempts == 0:
            return 0.0
        return self.total_time_spent_minutes / self.total_attempts

    @property
    def days_since_last_practice(self) -> int:
        """
        Calculate days since last practice.

        Returns:
            int: Number of days since last practice
        """
        return (datetime.utcnow() - self.last_practiced).days

    @property
    def is_stale(self) -> bool:
        """
        Check if topic is stale (not practiced in 7+ days).

        Returns:
            bool: True if topic needs refresher
        """
        return self.days_since_last_practice >= 7

    @property
    def improvement_rate(self) -> float:
        """
        Calculate improvement rate based on recent performance.
        Uses last 10 attempts vs first 10 attempts.

        Returns:
            float: Improvement rate (-1.0 to 1.0), 0 if insufficient data
        """
        if self.total_attempts < 10:
            return 0.0

        # This is a simplified calculation - in real implementation,
        # you'd track individual attempt results
        current_accuracy = self.accuracy_percentage
        if current_accuracy >= 80:
            return 0.5  # Good improvement
        elif current_accuracy >= 60:
            return 0.2  # Moderate improvement
        else:
            return -0.1  # Needs work

    def record_attempt(
        self,
        is_correct: bool,
        time_spent_minutes: float = 0.0,
        question_type: str = "multiple_choice",
        mistake_pattern: Optional[str] = None,
    ) -> None:
        """
        Record a new attempt on this topic.

        Args:
            is_correct: Whether the student answered correctly
            time_spent_minutes: Time spent on this question
            question_type: Type of question (multiple_choice, descriptive, etc.)
            mistake_pattern: Common mistake pattern if incorrect
        """
        # Ensure fields are initialized (handle None values)
        if self.total_attempts is None:
            self.total_attempts = 0
        if self.total_time_spent_minutes is None:
            self.total_time_spent_minutes = 0.0
        if self.correct_answers is None:
            self.correct_answers = 0
        if self.consecutive_correct is None:
            self.consecutive_correct = 0
        if self.max_streak is None:
            self.max_streak = 0

        # Update basic metrics
        self.total_attempts += 1
        self.total_time_spent_minutes += time_spent_minutes
        self.last_practiced = datetime.utcnow()

        if is_correct:
            self.correct_answers += 1
            self.consecutive_correct += 1
            self.max_streak = max(self.max_streak, self.consecutive_correct)
        else:
            self.consecutive_correct = 0
            if mistake_pattern and mistake_pattern not in self.common_mistakes:
                if len(self.common_mistakes) < 10:  # Limit stored mistakes
                    # Use list concatenation to ensure SQLAlchemy detects the change
                    self.common_mistakes = self.common_mistakes + [mistake_pattern]
                    flag_modified(self, "common_mistakes")

        # Update question type performance
        if question_type in self.question_types_performance:
            self.question_types_performance[question_type]["attempts"] += 1
            if is_correct:
                self.question_types_performance[question_type]["correct"] += 1
            flag_modified(self, "question_types_performance")

        # Recalculate derived properties
        self._update_strength_level()
        self._update_mastery_status()
        self._update_review_status()

        logger.debug(
            f"Recorded attempt for student {self.student_id}, topic {self.topic}: "
            f"{'correct' if is_correct else 'incorrect'}, accuracy now {self.accuracy_percentage:.1f}%"
        )

    def _update_strength_level(self) -> None:
        """Update the current strength level based on accuracy"""
        accuracy = self.accuracy_percentage

        if accuracy < 60:
            self.current_strength_level = StrengthLevel.WEAK.value
        elif accuracy < 80:
            self.current_strength_level = StrengthLevel.AVERAGE.value
        else:
            self.current_strength_level = StrengthLevel.STRONG.value

    def _update_mastery_status(self) -> None:
        """Update mastery status based on accuracy and recent practice"""
        # Mastery criteria: 85%+ accuracy with at least 10 attempts and practiced recently
        self.mastery_achieved = (
            self.accuracy_percentage >= 85
            and self.total_attempts >= 10
            and self.days_since_last_practice <= 3
        )

    def _update_review_status(self) -> None:
        """Update whether topic needs review"""
        # Needs review if: low accuracy, declining performance, or stale
        self.needs_review = (
            self.accuracy_percentage < 70 or self.is_stale or self.consecutive_correct == 0
        )

    def get_recommended_difficulty(self) -> DifficultyLevel:
        """
        Get recommended difficulty level for next questions.

        Returns:
            DifficultyLevel: Recommended difficulty based on performance
        """
        accuracy = self.accuracy_percentage

        # Not enough data - start with easy
        if self.total_attempts < 3:
            return DifficultyLevel.EASY

        # Performance-based recommendations
        if accuracy < 50:
            return DifficultyLevel.EASY
        elif accuracy < 80:
            return DifficultyLevel.MEDIUM
        else:
            return DifficultyLevel.HARD

    def get_performance_summary(self) -> Dict:
        """
        Get comprehensive performance summary for agents.

        Returns:
            Dict: Performance summary with all key metrics
        """
        return {
            "topic": self.topic,
            "subtopic": self.subtopic,
            "difficulty_level": self.difficulty_level,
            "accuracy_percentage": round(self.accuracy_percentage, 1),
            "total_attempts": self.total_attempts,
            "current_strength_level": self.current_strength_level,
            "consecutive_correct": self.consecutive_correct,
            "max_streak": self.max_streak,
            "needs_review": self.needs_review,
            "mastery_achieved": self.mastery_achieved,
            "days_since_last_practice": self.days_since_last_practice,
            "is_stale": self.is_stale,
            "average_time_per_question": round(self.average_time_per_question, 2),
            "recommended_next_difficulty": self.get_recommended_difficulty().value,
            "improvement_rate": round(self.improvement_rate, 2),
            "question_types_performance": self.question_types_performance,
            "common_mistakes": self.common_mistakes[:3],  # Top 3 mistakes
        }

    @classmethod
    def get_or_create_progress(
        cls,
        session,
        student_id: str,
        topic: str,
        difficulty_level: str = DifficultyLevel.MEDIUM.value,
        subtopic: Optional[str] = None,
    ) -> "Progress":
        """
        Get existing progress record or create new one.

        Args:
            session: Database session
            student_id: Student's ID
            topic: Topic name
            difficulty_level: Difficulty level
            subtopic: Optional subtopic

        Returns:
            Progress: Existing or newly created progress record
        """
        # Try to find existing record
        existing = (
            session.query(cls)
            .filter_by(
                student_id=student_id,
                topic=topic,
                difficulty_level=difficulty_level,
                subtopic=subtopic,
            )
            .first()
        )

        if existing:
            return existing

        # Create new record
        new_progress = cls(
            student_id=student_id, topic=topic, difficulty_level=difficulty_level, subtopic=subtopic
        )
        session.add(new_progress)
        session.flush()  # Get ID without committing

        logger.info(f"Created new progress record for student {student_id}, topic {topic}")
        return new_progress

    @classmethod
    def get_student_overview(cls, session, student_id: str) -> Dict:
        """
        Get comprehensive overview of student's progress across all topics.

        Args:
            session: Database session
            student_id: Student's ID

        Returns:
            Dict: Overview with weak areas, strong areas, recommendations
        """
        # Get all progress records for student
        records = session.query(cls).filter_by(student_id=student_id).all()

        if not records:
            return {
                "total_topics": 0,
                "weak_areas": [],
                "strong_areas": [],
                "needs_review": [],
                "overall_accuracy": 0.0,
                "total_time_spent": 0.0,
                "recommendation": "Start with a basic assessment to identify your current level.",
            }

        # Aggregate metrics
        total_attempts = sum(r.total_attempts for r in records)
        total_correct = sum(r.correct_answers for r in records)
        total_time = sum(r.total_time_spent_minutes for r in records)

        overall_accuracy = (total_correct / total_attempts * 100) if total_attempts > 0 else 0

        # Categorize topics
        weak_areas = [
            r.topic for r in records if r.current_strength_level == StrengthLevel.WEAK.value
        ]
        strong_areas = [
            r.topic for r in records if r.current_strength_level == StrengthLevel.STRONG.value
        ]
        needs_review = [r.topic for r in records if r.needs_review]

        # Generate recommendation
        recommendation = cls._generate_recommendation(weak_areas, strong_areas, needs_review)

        return {
            "total_topics": len(set(r.topic for r in records)),
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "needs_review": needs_review,
            "overall_accuracy": round(overall_accuracy, 1),
            "total_time_spent_hours": round(total_time / 60, 1),
            "mastered_topics": len([r for r in records if r.mastery_achieved]),
            "recommendation": recommendation,
        }

    @staticmethod
    def _generate_recommendation(
        weak_areas: List[str], strong_areas: List[str], needs_review: List[str]
    ) -> str:
        """Generate learning recommendation based on progress"""
        if not weak_areas and not needs_review:
            return "Excellent progress! Consider tackling more advanced topics or helping others."

        if len(weak_areas) > 3:
            return f"Focus on strengthening fundamentals in {weak_areas[0]} and {weak_areas[1]}. Take it step by step."

        if needs_review:
            return f"Review {needs_review[0]} to maintain your progress, then work on {weak_areas[0] if weak_areas else 'new topics'}."

        if weak_areas:
            return f"Great job on {strong_areas[0] if strong_areas else 'your strong areas'}! Now let's improve {weak_areas[0]}."

        return "Keep practicing regularly to maintain your excellent progress!"

    def __repr__(self):
        return f"<Progress(student_id='{self.student_id}', topic='{self.topic}', accuracy={self.accuracy_percentage:.1f}%)>"

    def __str__(self):
        return f"{self.topic} ({self.difficulty_level}): {self.accuracy_percentage:.1f}% in {self.total_attempts} attempts"
