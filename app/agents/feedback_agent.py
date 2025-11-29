"""
Feedback Agent for Agentic AI Tutor.

Provides comprehensive performance analysis and personalized recommendations:
- Quiz performance analysis
- Weak/strong area identification
- Learning trend detection
- Personalized recommendations
- Progress reports for students/teachers/parents
- Determines when replanning is needed
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent, AgentState
from app.models.student import Student
from app.models.progress import Progress, StrengthLevel
from app.core.config import settings

logger = logging.getLogger(__name__)


class PerformanceReport:
    """Represents a comprehensive performance analysis report."""

    def __init__(
        self,
        student_id: str,
        overall_stats: Dict[str, Any],
        weak_topics: List[Dict[str, Any]],
        strong_topics: List[Dict[str, Any]],
        improving_topics: List[Dict[str, Any]],
        declining_topics: List[Dict[str, Any]],
        recommendations: List[str],
        needs_replanning: bool
    ):
        """Initialize performance report."""
        self.student_id = student_id
        self.overall_stats = overall_stats
        self.weak_topics = weak_topics
        self.strong_topics = strong_topics
        self.improving_topics = improving_topics
        self.declining_topics = declining_topics
        self.recommendations = recommendations
        self.needs_replanning = needs_replanning
        self.generated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "student_id": self.student_id,
            "generated_at": self.generated_at.isoformat(),
            "overall_stats": self.overall_stats,
            "weak_topics": self.weak_topics,
            "strong_topics": self.strong_topics,
            "improving_topics": self.improving_topics,
            "declining_topics": self.declining_topics,
            "recommendations": self.recommendations,
            "needs_replanning": self.needs_replanning
        }


class FeedbackAgent(BaseAgent):
    """
    Agent responsible for analyzing student performance and providing feedback.

    Capabilities:
    - Analyze quiz performance and progress trends
    - Identify weak areas needing attention
    - Recognize strong areas and achievements
    - Detect learning velocity (improving/declining)
    - Generate personalized recommendations
    - Create reports for different audiences
    - Trigger replanning when needed
    """

    def __init__(
        self,
        student: Student,
        db_session: Session,
        session_id: Optional[str] = None,
        agent_state: Optional[AgentState] = None
    ):
        """
        Initialize Feedback Agent.

        Args:
            student: Student model instance
            db_session: Database session
            session_id: Optional session ID
            agent_state: Optional initial agent state
        """
        super().__init__(
            student=student,
            db_session=db_session,
            session_id=session_id,
            agent_state=agent_state
        )

        # Load feedback configuration
        feedback_config = settings.get("agents.feedback", {})

        # Thresholds for categorization
        self.weak_threshold = feedback_config.get("weak_threshold", 60.0)
        self.strong_threshold = feedback_config.get("strong_threshold", 80.0)
        self.mastery_threshold = feedback_config.get("mastery_threshold", 85.0)

        # Trend detection
        self.min_attempts_for_trend = feedback_config.get("min_attempts_for_trend", 5)
        self.improvement_threshold = feedback_config.get("improvement_threshold", 10.0)  # % increase

        # Replanning triggers
        self.new_weak_topics_threshold = feedback_config.get("new_weak_topics_threshold", 2)
        self.stale_practice_days = feedback_config.get("stale_practice_days", 7)

        logger.info(f"FeedbackAgent initialized for student {student.id}")

    def analyze_performance(self) -> PerformanceReport:
        """
        Analyze student's overall performance across all topics.

        Returns:
            PerformanceReport: Comprehensive performance analysis
        """
        logger.info(f"Analyzing performance for student {self.student.id}")

        # Retrieve all progress records
        progress_records = self.db.query(Progress).filter(
            Progress.student_id == self.student.id
        ).all()

        if not progress_records:
            logger.warning(f"No progress records found for student {self.student.id}")
            return self._create_empty_report()

        # Calculate overall statistics
        overall_stats = self._calculate_overall_stats(progress_records)

        # Categorize topics by strength
        weak_topics = []
        strong_topics = []
        improving_topics = []
        declining_topics = []

        for record in progress_records:
            topic_info = self._analyze_topic(record)

            # Categorize by current strength
            if topic_info["accuracy"] < self.weak_threshold:
                weak_topics.append(topic_info)
            elif topic_info["accuracy"] > self.strong_threshold:
                strong_topics.append(topic_info)

            # Categorize by trend
            if topic_info["trend"] == "improving":
                improving_topics.append(topic_info)
            elif topic_info["trend"] == "declining":
                declining_topics.append(topic_info)

        # Sort topics by urgency/performance
        weak_topics.sort(key=lambda x: (x["accuracy"], -x["days_since_practice"]))
        strong_topics.sort(key=lambda x: -x["accuracy"])
        improving_topics.sort(key=lambda x: -x["trend_value"])
        declining_topics.sort(key=lambda x: x["trend_value"])

        # Generate personalized recommendations
        recommendations = self._generate_recommendations(
            weak_topics=weak_topics,
            strong_topics=strong_topics,
            improving_topics=improving_topics,
            declining_topics=declining_topics,
            overall_stats=overall_stats
        )

        # Determine if replanning is needed
        needs_replanning = self._should_replan(
            weak_topics=weak_topics,
            declining_topics=declining_topics,
            progress_records=progress_records
        )

        report = PerformanceReport(
            student_id=self.student.id,
            overall_stats=overall_stats,
            weak_topics=weak_topics,
            strong_topics=strong_topics,
            improving_topics=improving_topics,
            declining_topics=declining_topics,
            recommendations=recommendations,
            needs_replanning=needs_replanning
        )

        logger.info(
            f"Performance analysis complete: {len(weak_topics)} weak, "
            f"{len(strong_topics)} strong, {len(improving_topics)} improving, "
            f"{len(declining_topics)} declining"
        )

        return report

    def _calculate_overall_stats(self, progress_records: List[Progress]) -> Dict[str, Any]:
        """Calculate overall statistics across all topics."""
        total_attempts = sum(p.total_attempts for p in progress_records)
        total_correct = sum(p.correct_answers for p in progress_records)
        total_time = sum(p.total_time_spent_minutes for p in progress_records)

        overall_accuracy = (total_correct / total_attempts * 100) if total_attempts > 0 else 0.0

        # Count topics by strength level
        weak_count = sum(1 for p in progress_records if p.accuracy_percentage < self.weak_threshold)
        strong_count = sum(1 for p in progress_records if p.accuracy_percentage > self.strong_threshold)
        mastery_count = sum(1 for p in progress_records if p.mastery_achieved)

        # Recent activity
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_practice = sum(1 for p in progress_records if p.last_practiced > recent_cutoff)

        return {
            "total_topics": len(progress_records),
            "total_attempts": total_attempts,
            "total_correct": total_correct,
            "overall_accuracy": round(overall_accuracy, 1),
            "total_time_minutes": round(total_time, 1),
            "weak_topics_count": weak_count,
            "strong_topics_count": strong_count,
            "mastery_topics_count": mastery_count,
            "recently_practiced_count": recent_practice
        }

    def _analyze_topic(self, record: Progress) -> Dict[str, Any]:
        """
        Analyze a single topic's progress record.

        Returns:
            Dict: Topic analysis with trend information
        """
        accuracy = record.accuracy_percentage
        days_since_practice = (datetime.utcnow() - record.last_practiced).days

        # Detect trend (simplified - could use more sophisticated methods)
        trend = "stable"
        trend_value = 0.0

        if record.total_attempts >= self.min_attempts_for_trend:
            # Use learning_velocity if available
            if record.learning_velocity is not None:
                trend_value = record.learning_velocity
                if trend_value > self.improvement_threshold:
                    trend = "improving"
                elif trend_value < -self.improvement_threshold:
                    trend = "declining"

        return {
            "topic": record.topic,
            "difficulty": record.difficulty_level,
            "accuracy": round(accuracy, 1),
            "attempts": record.total_attempts,
            "correct": record.correct_answers,
            "time_spent_minutes": round(record.total_time_spent_minutes, 1),
            "last_practiced": record.last_practiced.isoformat(),
            "days_since_practice": days_since_practice,
            "consecutive_correct": record.consecutive_correct,
            "max_streak": record.max_streak,
            "mastery_achieved": record.mastery_achieved,
            "needs_review": record.needs_review,
            "trend": trend,
            "trend_value": round(trend_value, 1),
            "common_mistakes": record.common_mistakes or []
        }

    def _generate_recommendations(
        self,
        weak_topics: List[Dict[str, Any]],
        strong_topics: List[Dict[str, Any]],
        improving_topics: List[Dict[str, Any]],
        declining_topics: List[Dict[str, Any]],
        overall_stats: Dict[str, Any]
    ) -> List[str]:
        """
        Generate personalized recommendations with LLM or fallback.

        Returns:
            List[str]: List of personalized recommendations
        """
        # Build context for LLM
        context = self._build_recommendations_context(
            weak_topics, strong_topics, improving_topics, declining_topics, overall_stats
        )

        prompt = f"""You are an AI tutor analyzing a student's performance. Based on the following data, provide 3-5 specific, actionable recommendations to help the student improve.

{context}

Generate recommendations that:
1. Prioritize the weakest topics that need immediate attention
2. Suggest specific study strategies (practice more, review concepts, try harder problems)
3. Acknowledge progress and strengths to maintain motivation
4. Are concrete and actionable (not generic advice)
5. Consider time management (focus on highest-impact areas)

Return ONLY a JSON array of recommendation strings:
["Recommendation 1", "Recommendation 2", ...]
"""

        try:
            # Try to generate with LLM
            response = self.generate_response(prompt, temperature=0.7, max_tokens=400)

            # Parse JSON recommendations
            import json
            # Extract JSON array from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                recommendations = json.loads(json_str)

                if isinstance(recommendations, list) and len(recommendations) > 0:
                    logger.info(f"Generated {len(recommendations)} LLM recommendations")
                    return recommendations

        except Exception as e:
            logger.warning(f"Failed to generate LLM recommendations: {e}")

        # Fallback recommendations
        return self._create_fallback_recommendations(
            weak_topics, strong_topics, improving_topics, declining_topics, overall_stats
        )

    def _build_recommendations_context(
        self,
        weak_topics: List[Dict[str, Any]],
        strong_topics: List[Dict[str, Any]],
        improving_topics: List[Dict[str, Any]],
        declining_topics: List[Dict[str, Any]],
        overall_stats: Dict[str, Any]
    ) -> str:
        """Build context string for recommendations prompt."""
        context_parts = []

        context_parts.append(f"Overall Performance:")
        context_parts.append(f"- Topics studied: {overall_stats['total_topics']}")
        context_parts.append(f"- Overall accuracy: {overall_stats['overall_accuracy']}%")
        context_parts.append(f"- Total practice time: {overall_stats['total_time_minutes']} minutes")

        if weak_topics:
            context_parts.append(f"\nWeak Topics ({len(weak_topics)}):")
            for topic in weak_topics[:3]:  # Top 3 weakest
                context_parts.append(
                    f"- {topic['topic']} ({topic['difficulty']}): {topic['accuracy']}% accuracy, "
                    f"{topic['attempts']} attempts, last practiced {topic['days_since_practice']} days ago"
                )

        if declining_topics:
            context_parts.append(f"\nDeclining Topics ({len(declining_topics)}):")
            for topic in declining_topics[:2]:
                context_parts.append(f"- {topic['topic']}: {topic['accuracy']}% accuracy, declining trend")

        if improving_topics:
            context_parts.append(f"\nImproving Topics ({len(improving_topics)}):")
            for topic in improving_topics[:2]:
                context_parts.append(f"- {topic['topic']}: {topic['accuracy']}% accuracy, improving trend")

        if strong_topics:
            context_parts.append(f"\nStrong Topics ({len(strong_topics)}):")
            for topic in strong_topics[:2]:
                context_parts.append(f"- {topic['topic']}: {topic['accuracy']}% accuracy")

        return "\n".join(context_parts)

    def _create_fallback_recommendations(
        self,
        weak_topics: List[Dict[str, Any]],
        strong_topics: List[Dict[str, Any]],
        improving_topics: List[Dict[str, Any]],
        declining_topics: List[Dict[str, Any]],
        overall_stats: Dict[str, Any]
    ) -> List[str]:
        """Create fallback recommendations when LLM fails."""
        recommendations = []

        # Prioritize weakest topics
        if weak_topics:
            weakest = weak_topics[0]
            recommendations.append(
                f"Focus on {weakest['topic']} ({weakest['difficulty']} level) - "
                f"your weakest area at {weakest['accuracy']}% accuracy. "
                f"Practice 3-5 more quizzes to build confidence."
            )

        # Address declining topics
        if declining_topics:
            declining = declining_topics[0]
            recommendations.append(
                f"Review {declining['topic']} soon - performance has been declining. "
                f"Revisit core concepts before attempting more practice."
            )

        # Encourage improvement
        if improving_topics:
            improving = improving_topics[0]
            recommendations.append(
                f"Great progress on {improving['topic']}! Keep up the momentum with regular practice."
            )

        # Suggest advancing difficulty
        if strong_topics:
            for topic in strong_topics:
                if topic['difficulty'] != 'hard' and topic['accuracy'] > 85:
                    recommendations.append(
                        f"You've mastered {topic['topic']} at {topic['difficulty']} level. "
                        f"Try advancing to harder questions to challenge yourself."
                    )
                    break

        # Time management
        if overall_stats['recently_practiced_count'] < overall_stats['total_topics'] / 2:
            recommendations.append(
                "Try to practice all topics regularly to maintain retention. "
                "Aim for at least 2-3 practice sessions per week."
            )

        # Default if no specific recommendations
        if not recommendations:
            recommendations.append(
                "Continue practicing consistently across all topics. "
                "Focus on understanding concepts deeply rather than memorizing."
            )

        return recommendations

    def _should_replan(
        self,
        weak_topics: List[Dict[str, Any]],
        declining_topics: List[Dict[str, Any]],
        progress_records: List[Progress]
    ) -> bool:
        """
        Determine if student needs a new study plan.

        Triggers:
        - Multiple new weak topics appeared
        - Several topics are declining
        - Many topics haven't been practiced recently

        Returns:
            bool: True if replanning is recommended
        """
        # Trigger 1: Too many weak topics
        if len(weak_topics) >= self.new_weak_topics_threshold:
            logger.info(f"Replanning triggered: {len(weak_topics)} weak topics")
            return True

        # Trigger 2: Multiple declining topics
        if len(declining_topics) >= 2:
            logger.info(f"Replanning triggered: {len(declining_topics)} declining topics")
            return True

        # Trigger 3: Stale practice (topics not practiced recently)
        stale_cutoff = datetime.utcnow() - timedelta(days=self.stale_practice_days)
        stale_topics = [p for p in progress_records if p.last_practiced < stale_cutoff]

        if len(stale_topics) >= len(progress_records) / 2:  # More than half are stale
            logger.info(f"Replanning triggered: {len(stale_topics)} stale topics")
            return True

        return False

    def _create_empty_report(self) -> PerformanceReport:
        """Create an empty report when no progress data exists."""
        return PerformanceReport(
            student_id=self.student.id,
            overall_stats={
                "total_topics": 0,
                "total_attempts": 0,
                "total_correct": 0,
                "overall_accuracy": 0.0,
                "total_time_minutes": 0.0,
                "weak_topics_count": 0,
                "strong_topics_count": 0,
                "mastery_topics_count": 0,
                "recently_practiced_count": 0
            },
            weak_topics=[],
            strong_topics=[],
            improving_topics=[],
            declining_topics=[],
            recommendations=["Start practicing to track your progress!"],
            needs_replanning=False
        )

    def create_student_report(self, report: PerformanceReport) -> str:
        """
        Create a student-friendly text report.

        Args:
            report: PerformanceReport object

        Returns:
            str: Formatted report for student
        """
        lines = []
        lines.append("=" * 60)
        lines.append("YOUR PROGRESS REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Overall stats
        stats = report.overall_stats
        lines.append(f"Overall Performance: {stats['overall_accuracy']}% accuracy")
        lines.append(f"Topics studied: {stats['total_topics']}")
        lines.append(f"Total practice time: {stats['total_time_minutes']} minutes")
        lines.append("")

        # Weak topics
        if report.weak_topics:
            lines.append(f"Topics Needing Attention ({len(report.weak_topics)}):")
            for topic in report.weak_topics[:5]:
                lines.append(f"  - {topic['topic']}: {topic['accuracy']}% ({topic['attempts']} attempts)")
            lines.append("")

        # Strong topics
        if report.strong_topics:
            lines.append(f"Your Strengths ({len(report.strong_topics)}):")
            for topic in report.strong_topics[:5]:
                lines.append(f"  - {topic['topic']}: {topic['accuracy']}%")
            lines.append("")

        # Recommendations
        lines.append("Personalized Recommendations:")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

        if report.needs_replanning:
            lines.append("NOTE: Consider creating a new study plan to address recent changes in your progress.")

        lines.append("=" * 60)

        return "\n".join(lines)

    def create_teacher_report(self, report: PerformanceReport) -> Dict[str, Any]:
        """
        Create a detailed report for teachers/parents with analytics.

        Args:
            report: PerformanceReport object

        Returns:
            Dict: Comprehensive report with detailed metrics
        """
        return {
            "student_id": report.student_id,
            "report_date": report.generated_at.isoformat(),
            "summary": {
                "overall_accuracy": report.overall_stats["overall_accuracy"],
                "total_topics": report.overall_stats["total_topics"],
                "mastery_count": report.overall_stats["mastery_topics_count"],
                "weak_count": report.overall_stats["weak_topics_count"],
                "total_practice_minutes": report.overall_stats["total_time_minutes"]
            },
            "areas_of_concern": {
                "weak_topics": report.weak_topics,
                "declining_topics": report.declining_topics
            },
            "areas_of_strength": {
                "strong_topics": report.strong_topics,
                "improving_topics": report.improving_topics
            },
            "recommendations": report.recommendations,
            "action_required": report.needs_replanning,
            "next_steps": "Create new study plan" if report.needs_replanning else "Continue current plan"
        }


def create_feedback_agent(
    student: Student,
    db_session: Session,
    session_id: Optional[str] = None
) -> FeedbackAgent:
    """
    Factory function to create a Feedback Agent instance.

    Args:
        student: Student model instance
        db_session: Database session
        session_id: Optional session ID

    Returns:
        FeedbackAgent: Initialized agent
    """
    return FeedbackAgent(
        student=student,
        db_session=db_session,
        session_id=session_id
    )
