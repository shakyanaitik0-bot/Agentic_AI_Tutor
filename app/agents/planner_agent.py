"""
Planner Agent for Agentic AI Tutor.

Generates personalized study plans based on:
- Student's weak/strong areas
- Progress history
- Exam timeline
- Learning preferences

Addresses Problem Statement objective:
"Adapt study plans based on progress, weak topics, and learning pace"
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession

from app.agents.base_agent import BaseAgent
from app.models.student import Student
from app.models.session import Session
from app.models.progress import Progress
from app.core.config import settings

logger = logging.getLogger(__name__)


class StudyPlan:
    """Structured study plan representation"""

    def __init__(
        self,
        student_id: str,
        exam_type: str,
        timeline_days: int,
        generated_at: datetime,
        plan_id: Optional[str] = None,
    ):
        self.plan_id = plan_id or f"plan_{int(generated_at.timestamp() * 1000)}"
        self.student_id = student_id
        self.exam_type = exam_type
        self.timeline_days = timeline_days
        self.generated_at = generated_at
        self.topics: List[Dict[str, Any]] = []
        self.daily_schedule: List[Dict[str, Any]] = []
        self.milestones: List[Dict[str, Any]] = []
        self.reasoning: str = ""

    def add_topic(
        self,
        topic: str,
        priority: int,
        difficulty_level: str,
        estimated_hours: float,
        reason: str,
        urgency: str = "medium",
        subtopics: Optional[List[str]] = None,
    ):
        """Add a topic to the study plan"""
        self.topics.append(
            {
                "topic": topic,
                "priority": priority,
                "urgency": urgency,
                "reason": reason,
                "estimated_hours": estimated_hours,
                "difficulty_level": difficulty_level,
                "subtopics": subtopics or [],
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/display"""
        return {
            "plan_id": self.plan_id,
            "student_id": self.student_id,
            "exam_type": self.exam_type,
            "timeline_days": self.timeline_days,
            "generated_at": self.generated_at.isoformat(),
            "topics": self.topics,
            "daily_schedule": self.daily_schedule,
            "milestones": self.milestones,
            "reasoning": self.reasoning,
            "total_topics": len(self.topics),
            "total_hours": sum(t["estimated_hours"] for t in self.topics),
        }


class PlannerAgent(BaseAgent):
    """
    Planner Agent - Generates personalized, adaptive study plans.

    Capabilities:
    - Analyzes progress data to identify weak areas
    - Prioritizes topics based on urgency and difficulty
    - Creates structured daily schedules
    - Sets realistic milestones
    - Provides explainable recommendations
    """

    def __init__(self, student: Student, session: Session, db: DBSession, **kwargs):
        """
        Initialize Planner Agent.

        Args:
            student: Student profile
            session: Current session
            db: Database session for querying Progress
            **kwargs: Additional arguments for BaseAgent
        """
        super().__init__(agent_name="PlannerAgent", student=student, session=session, **kwargs)
        self.db = db

        # Get planning configuration
        self.min_hours_per_day = settings.get("planner.min_hours_per_day", 2)
        self.max_hours_per_day = settings.get("planner.max_hours_per_day", 6)
        self.weak_threshold = settings.get("progress.thresholds.weak_below", 60.0)
        self.strong_threshold = settings.get("progress.thresholds.strong_above", 80.0)

    def get_system_prompt(self) -> str:
        """Override system prompt for planning tasks"""
        return f"""You are a Study Planner Agent helping {self.student.name} prepare for {self.student.exam_type}.

Your role is to:
1. Analyze their performance data to identify weak and strong areas
2. Create realistic, achievable study plans
3. Prioritize topics that need the most attention
4. Provide clear explanations for why each topic is included
5. Be encouraging and motivating

Always explain your reasoning in a way that helps students understand the 'why' behind the plan."""

    def execute(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Generate a study plan based on user request.

        Args:
            user_input: User's request (e.g., "Create a 30-day study plan")
            **kwargs: Additional parameters
                - timeline_days: Number of days for the plan
                - focus_topics: Specific topics to focus on

        Returns:
            Dict: Study plan with topics, schedule, and explanations
        """
        logger.info(f"[PlannerAgent] Processing request: '{user_input[:50]}...'")

        # Extract timeline from kwargs or use default
        timeline_days = kwargs.get("timeline_days", 30)
        focus_topics = kwargs.get("focus_topics", [])

        # Step 1: Analyze student progress
        analysis = self._analyze_progress()

        # Step 2: Prioritize topics
        prioritized_topics = self._prioritize_topics(analysis, focus_topics)

        # Step 3: Generate study plan
        study_plan = self._generate_plan(
            timeline_days=timeline_days, prioritized_topics=prioritized_topics, analysis=analysis
        )

        # Step 4: Create daily schedule
        daily_schedule = self._create_daily_schedule(study_plan, timeline_days)
        study_plan.daily_schedule = daily_schedule

        # Step 5: Set milestones
        milestones = self._set_milestones(study_plan, timeline_days)
        study_plan.milestones = milestones

        # Step 6: Generate explanation using LLM
        explanation = self._generate_explanation(study_plan, analysis)
        study_plan.reasoning = explanation

        # Update session state
        self.state.update("last_study_plan", study_plan.to_dict())
        self.state.update("plan_generated_at", datetime.now().isoformat())
        self.update_session_state()

        # Log interaction
        self.log_interaction(
            user_input,
            f"Generated {timeline_days}-day study plan with {len(study_plan.topics)} topics",
            {"topics_count": len(study_plan.topics), "timeline_days": timeline_days},
        )

        return {
            "study_plan": study_plan.to_dict(),
            "explanation": explanation,
            "summary": {
                "total_topics": len(study_plan.topics),
                "weak_areas": len([t for t in prioritized_topics if t["priority"] == "high"]),
                "timeline_days": timeline_days,
                "estimated_hours": sum(t["estimated_hours"] for t in study_plan.topics),
            },
            "agent": self.agent_name,
        }

    def _analyze_progress(self) -> Dict[str, Any]:
        """
        Analyze student's progress data.

        Returns:
            Dict: Analysis with weak areas, strong areas, needs review
        """
        # Query all progress records for this student
        progress_records = (
            self.db.query(Progress).filter(Progress.student_id == self.student.id).all()
        )

        weak_areas = []
        strong_areas = []
        needs_review = []
        average_areas = []

        for record in progress_records:
            accuracy = record.accuracy_percentage

            topic_info = {
                "topic": record.topic,
                "accuracy": accuracy,
                "attempts": record.total_attempts,
                "difficulty": record.difficulty_level
                if isinstance(record.difficulty_level, str)
                else record.difficulty_level.value,
                "last_practiced": record.last_practiced,
                "needs_review": record.needs_review,
                "mastery": record.mastery_achieved,
            }

            # Classify by performance
            if accuracy < self.weak_threshold:
                weak_areas.append(topic_info)
            elif accuracy > self.strong_threshold:
                strong_areas.append(topic_info)
            else:
                average_areas.append(topic_info)

            # Check if needs review (stale)
            if record.needs_review and not record.mastery_achieved:
                needs_review.append(topic_info)

        return {
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "average_areas": average_areas,
            "needs_review": needs_review,
            "total_topics_practiced": len(progress_records),
            "topics_with_mastery": sum(1 for r in progress_records if r.mastery_achieved),
        }

    def _prioritize_topics(
        self, analysis: Dict[str, Any], focus_topics: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Prioritize topics based on performance and urgency.

        Args:
            analysis: Progress analysis
            focus_topics: Optional list of topics to focus on

        Returns:
            List[Dict]: Prioritized topics with metadata
        """
        prioritized = []

        # High priority: Weak areas that need review
        for topic_info in analysis["weak_areas"]:
            priority = "high"
            if topic_info["needs_review"]:
                priority = "urgent"

            prioritized.append(
                {
                    **topic_info,
                    "priority": priority,
                    "priority_score": 100
                    - topic_info["accuracy"],  # Lower accuracy = higher priority
                    "reason": f"Weak area ({topic_info['accuracy']:.1f}% accuracy)",
                }
            )

        # Medium priority: Average areas that need review
        for topic_info in analysis["needs_review"]:
            if topic_info not in prioritized:  # Avoid duplicates
                prioritized.append(
                    {
                        **topic_info,
                        "priority": "medium",
                        "priority_score": 50,
                        "reason": "Needs review (not practiced recently)",
                    }
                )

        # Medium priority: Average areas
        for topic_info in analysis["average_areas"]:
            if topic_info not in prioritized:
                prioritized.append(
                    {
                        **topic_info,
                        "priority": "medium",
                        "priority_score": 75 - topic_info["accuracy"],
                        "reason": f"Moderate area ({topic_info['accuracy']:.1f}% accuracy)",
                    }
                )

        # Low priority: Strong areas (maintenance practice)
        for topic_info in analysis["strong_areas"]:
            if not topic_info["mastery"]:  # Only if not mastered
                prioritized.append(
                    {
                        **topic_info,
                        "priority": "low",
                        "priority_score": 25,
                        "reason": f"Strong area - maintain with light practice",
                    }
                )

        # Sort by priority score (highest first)
        prioritized.sort(key=lambda x: x["priority_score"], reverse=True)

        # If focus_topics specified, boost their priority
        if focus_topics:
            for item in prioritized:
                if item["topic"] in focus_topics:
                    item["priority_score"] += 50
                    item["priority"] = "urgent"
                    item["reason"] += " (user requested)"

            prioritized.sort(key=lambda x: x["priority_score"], reverse=True)

        return prioritized

    def _generate_plan(
        self, timeline_days: int, prioritized_topics: List[Dict[str, Any]], analysis: Dict[str, Any]
    ) -> StudyPlan:
        """
        Generate structured study plan.

        Args:
            timeline_days: Number of days for the plan
            prioritized_topics: Sorted list of topics
            analysis: Progress analysis

        Returns:
            StudyPlan: Structured study plan
        """
        plan = StudyPlan(
            student_id=self.student.id,
            exam_type=self.student.exam_type,
            timeline_days=timeline_days,
            generated_at=datetime.now(),
        )

        # Calculate available study hours
        available_hours = timeline_days * self.min_hours_per_day

        # Allocate hours to topics based on priority
        hours_allocated = 0
        for idx, topic_info in enumerate(prioritized_topics):
            if hours_allocated >= available_hours:
                break  # No more time available

            # Estimate hours needed based on priority and current performance
            if topic_info["priority"] in ["urgent", "high"]:
                estimated_hours = 5  # More time for weak areas
            elif topic_info["priority"] == "medium":
                estimated_hours = 3
            else:
                estimated_hours = 2  # Light practice for strong areas

            # Adjust based on current accuracy
            if topic_info["accuracy"] < 40:
                estimated_hours += 2  # Very weak, needs more time

            # Don't exceed available hours
            if hours_allocated + estimated_hours > available_hours:
                estimated_hours = available_hours - hours_allocated

            # Map string priority to urgency and numeric priority
            string_priority = topic_info.get("priority", "medium")
            urgency_map = {"urgent": "high", "high": "high", "medium": "medium", "low": "low"}
            urgency = urgency_map.get(string_priority, "medium")

            # Numeric priority: 1=highest, 5=lowest (based on order in list)
            numeric_priority = idx + 1

            plan.add_topic(
                topic=topic_info["topic"],
                priority=numeric_priority,
                difficulty_level=topic_info["difficulty"],
                estimated_hours=estimated_hours,
                reason=topic_info["reason"],
                urgency=urgency,
            )

            hours_allocated += estimated_hours

        return plan

    def _create_daily_schedule(self, plan: StudyPlan, timeline_days: int) -> List[Dict[str, Any]]:
        """
        Create day-by-day study schedule.

        Args:
            plan: Study plan with topics
            timeline_days: Number of days

        Returns:
            List[Dict]: Daily schedule
        """
        schedule = []
        topics = plan.topics.copy()
        hours_per_day = self.min_hours_per_day

        current_date = datetime.now()

        for day in range(1, timeline_days + 1):
            day_topics = []
            hours_remaining = hours_per_day

            # Allocate topics to this day
            topic_names = []
            focus_areas = []
            while hours_remaining > 0 and topics:
                topic = topics[0]
                hours_needed = topic["estimated_hours"]

                if hours_needed <= hours_remaining:
                    # Topic fits entirely in this day
                    topic_names.append(topic["topic"])
                    focus_areas.append(f"{topic['topic']} ({hours_needed:.1f}h)")
                    hours_remaining -= hours_needed
                    topics.pop(0)
                else:
                    # Topic needs to be split across days
                    topic_names.append(topic["topic"])
                    focus_areas.append(f"{topic['topic']} - Part 1 ({hours_remaining:.1f}h)")
                    topic["estimated_hours"] -= hours_remaining
                    hours_remaining = 0

            # Only add days that have topics (schema requires min_items=1)
            if topic_names:
                schedule.append(
                    {
                        "day": day,
                        "date": (current_date + timedelta(days=day - 1)).strftime("%Y-%m-%d"),
                        "topics": topic_names,
                        "hours_allocated": hours_per_day,
                        "focus_areas": focus_areas,
                    }
                )

        return schedule

    def _set_milestones(self, plan: StudyPlan, timeline_days: int) -> List[Dict[str, Any]]:
        """
        Set achievement milestones throughout the plan.

        Args:
            plan: Study plan
            timeline_days: Timeline in days

        Returns:
            List[Dict]: Milestones
        """
        milestones = []

        # Milestone at 25%, 50%, 75%, 100%
        intervals = [0.25, 0.5, 0.75, 1.0]

        for interval in intervals:
            milestone_day = int(timeline_days * interval)
            if milestone_day == 0:
                milestone_day = 1  # Avoid day 0

            topics_by_day = int(len(plan.topics) * interval)

            # Get topics that should be covered by this milestone
            topics_covered = [t["topic"] for t in plan.topics[:topics_by_day]]

            milestones.append(
                {
                    "day": milestone_day,
                    "percentage": int(interval * 100),
                    "description": f"{int(interval * 100)}% plan completion - {topics_by_day} topics completed",
                    "topics_covered": topics_covered,
                }
            )

        return milestones

    def _generate_explanation(self, plan: StudyPlan, analysis: Dict[str, Any]) -> str:
        """
        Generate natural language explanation of the study plan.

        Args:
            plan: Study plan
            analysis: Progress analysis

        Returns:
            str: Explanation
        """
        # Build fallback explanation
        weak_count = len(analysis["weak_areas"])
        strong_count = len(analysis["strong_areas"])

        fallback = f"""Your {plan.timeline_days}-day study plan focuses on {len(plan.topics)} topics, with priority given to {weak_count} weak areas that need improvement. The plan allocates {sum(t["estimated_hours"] for t in plan.topics):.1f} total hours, with more time dedicated to challenging topics. By following this structured approach and staying consistent, you'll build a strong foundation for your {self.student.exam_type} preparation."""

        try:
            # Build context for LLM
            context = f"""
Student: {self.student.name}
Exam: {self.student.exam_type}
Timeline: {plan.timeline_days} days

Progress Analysis:
- Weak areas: {weak_count} topics
- Strong areas: {strong_count} topics
- Topics needing review: {len(analysis["needs_review"])} topics

Study Plan Generated:
- Total topics: {len(plan.topics)}
- Total estimated hours: {sum(t["estimated_hours"] for t in plan.topics):.1f}
- High priority topics: {len([t for t in plan.topics if t["priority"] <= 3])}
"""

            prompt = f"""{context}

Generate a motivating, personalized explanation of this study plan for the student.
Include:
1. Why these topics were prioritized
2. How the plan addresses their weak areas
3. What they can expect to achieve
4. Encouragement to stay consistent

Keep it concise (3-4 sentences) and encouraging:"""

            explanation = self.generate_response(prompt, temperature=0.7, max_tokens=300)
            return explanation

        except (ValueError, Exception) as e:
            # Fallback if LLM fails (e.g., safety filters)
            logger.warning(f"Failed to generate LLM explanation, using fallback: {e}")
            return fallback


def create_planner_agent(
    student: Student, session: Session, db: DBSession, **kwargs
) -> PlannerAgent:
    """
    Factory function to create a Planner Agent instance.

    Args:
        student: Student profile
        session: Current session
        db: Database session

    Returns:
        PlannerAgent: Configured planner agent
    """
    return PlannerAgent(student=student, session=session, db=db, **kwargs)
