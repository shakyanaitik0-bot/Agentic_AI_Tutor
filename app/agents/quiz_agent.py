"""
Quiz Generator Agent for Agentic AI Tutor.

Generates adaptive multiple-choice quizzes based on:
- Student's current performance and weak areas
- Topic and difficulty level
- RAG-retrieved content for context

Addresses Problem Statement objectives:
- "Dynamically assess student performance (via quizzes, Q&A)"
- "Adapt based on progress, weak topics, and learning pace"
- "Introduce active recall techniques (self-testing) into learning loop"
"""
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.agents.base_agent import BaseAgent
from app.models.student import Student
from app.models.session import Session
from app.models.progress import Progress, DifficultyLevel
from app.core.config import settings

logger = logging.getLogger(__name__)


class QuizQuestion:
    """Represents a single quiz question"""

    def __init__(
        self,
        question_text: str,
        options: List[str],
        correct_answer_index: int,
        explanation: str,
        topic: str,
        difficulty: str,
        question_id: Optional[str] = None
    ):
        self.question_id = question_id or f"q_{hash(question_text) % 10000}"
        self.question_text = question_text
        self.options = options
        self.correct_answer_index = correct_answer_index
        self.explanation = explanation
        self.topic = topic
        self.difficulty = difficulty

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "options": self.options,
            "correct_answer_index": self.correct_answer_index,
            "explanation": self.explanation,
            "topic": self.topic,
            "difficulty": self.difficulty
        }

    def check_answer(self, selected_index: int) -> bool:
        """Check if selected answer is correct"""
        return selected_index == self.correct_answer_index


class Quiz:
    """Represents a complete quiz"""

    def __init__(
        self,
        topic: str,
        difficulty: str,
        num_questions: int
    ):
        self.topic = topic
        self.difficulty = difficulty
        self.num_questions = num_questions
        self.questions: List[QuizQuestion] = []
        self.created_at = datetime.now()

    def add_question(self, question: QuizQuestion):
        """Add a question to the quiz"""
        self.questions.append(question)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "topic": self.topic,
            "difficulty": self.difficulty,
            "num_questions": len(self.questions),
            "questions": [q.to_dict() for q in self.questions],
            "created_at": self.created_at.isoformat()
        }


class QuizGeneratorAgent(BaseAgent):
    """
    Quiz Generator Agent - Creates adaptive multiple-choice quizzes.

    Capabilities:
    - Selects appropriate difficulty based on student progress
    - Uses RAG to retrieve relevant content
    - Generates MCQs with LLM
    - Creates distractors (wrong but plausible answers)
    - Provides detailed explanations
    - Validates quiz quality
    """

    def __init__(
        self,
        student: Student,
        session: Session,
        db: DBSession,
        **kwargs
    ):
        """
        Initialize Quiz Generator Agent.

        Args:
            student: Student profile
            session: Current session
            db: Database session for Progress queries
            **kwargs: Additional arguments for BaseAgent
        """
        super().__init__(
            agent_name="QuizGeneratorAgent",
            student=student,
            session=session,
            **kwargs
        )
        self.db = db

        # Get quiz configuration
        self.questions_per_quiz = settings.get("quiz.questions_per_quiz", 5)
        self.easy_threshold = settings.get("quiz.difficulty_thresholds.easy_below", 50.0)
        self.hard_threshold = settings.get("quiz.difficulty_thresholds.hard_above", 80.0)

    def get_system_prompt(self) -> str:
        """Override system prompt for quiz generation"""
        return f"""You are a Quiz Generator helping {self.student.name} prepare for {self.student.exam_type}.

Your role is to:
1. Create high-quality multiple-choice questions (MCQs)
2. Generate plausible but incorrect distractors
3. Provide clear, educational explanations
4. Ensure questions test understanding, not just memorization

Always create questions that:
- Test conceptual understanding
- Have one clearly correct answer
- Include 4 options (1 correct + 3 distractors)
- Are appropriate for {self.student.exam_type} level"""

    def execute(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Generate a quiz based on user request.

        Args:
            user_input: User's request (e.g., "Create a quiz on Calculus")
            **kwargs: Additional parameters
                - topic: Topic for the quiz
                - difficulty: Difficulty level (easy/medium/hard)
                - num_questions: Number of questions

        Returns:
            Dict: Generated quiz with questions and metadata
        """
        logger.info(f"[QuizGeneratorAgent] Processing request: '{user_input[:50]}...'")

        # Extract parameters
        topic = kwargs.get("topic")
        difficulty = kwargs.get("difficulty")
        num_questions = kwargs.get("num_questions", self.questions_per_quiz)

        # If topic not provided, try to extract from user input
        if not topic:
            topic = self._extract_topic(user_input)

        # If difficulty not provided, select adaptively
        if not difficulty:
            difficulty = self._select_difficulty(topic)

        logger.info(f"Generating {num_questions} {difficulty} questions on {topic}")

        # Step 1: Retrieve relevant content from RAG
        context = self._retrieve_content(topic, difficulty)

        # Step 2: Generate quiz questions
        quiz = self._generate_quiz(topic, difficulty, num_questions, context)

        # Step 3: Validate quiz quality
        if not self._validate_quiz(quiz):
            logger.warning("Quiz validation failed, regenerating...")
            quiz = self._generate_quiz(topic, difficulty, num_questions, context)

        # Update session state
        self.state.update("last_quiz", quiz.to_dict())
        self.state.update("quiz_generated_at", datetime.now().isoformat())
        self.update_session_state()

        # Log interaction
        self.log_interaction(
            user_input,
            f"Generated {len(quiz.questions)}-question quiz on {topic} ({difficulty})",
            {
                "topic": topic,
                "difficulty": difficulty,
                "num_questions": len(quiz.questions)
            }
        )

        return {
            "quiz": quiz.to_dict(),
            "metadata": {
                "topic": topic,
                "difficulty": difficulty,
                "num_questions": len(quiz.questions),
                "has_rag_context": len(context) > 0
            },
            "agent": self.agent_name
        }

    def _extract_topic(self, user_input: str) -> str:
        """
        Extract topic from user input.

        Args:
            user_input: User's message

        Returns:
            str: Extracted topic
        """
        # Simple keyword extraction (can be improved with NLP)
        common_topics = [
            "algebra", "calculus", "geometry", "trigonometry", "probability",
            "physics", "mechanics", "thermodynamics", "electromagnetism",
            "chemistry", "organic", "inorganic", "mathematics"
        ]

        user_input_lower = user_input.lower()
        for topic in common_topics:
            if topic in user_input_lower:
                return topic.capitalize()

        # Default fallback
        return "General"

    def _select_difficulty(self, topic: str) -> str:
        """
        Select appropriate difficulty based on student's progress.

        Args:
            topic: Quiz topic

        Returns:
            str: Difficulty level (easy/medium/hard)
        """
        # Query student's progress for this topic
        progress = self.db.query(Progress).filter(
            Progress.student_id == self.student.id,
            Progress.topic == topic
        ).first()

        if not progress:
            # No progress data, start with easy
            logger.info(f"No progress data for {topic}, defaulting to easy")
            return "easy"

        accuracy = progress.accuracy_percentage

        # Select difficulty based on accuracy thresholds
        if accuracy < self.easy_threshold:
            return "easy"
        elif accuracy > self.hard_threshold:
            return "hard"
        else:
            return "medium"

    def _retrieve_content(self, topic: str, difficulty: str) -> str:
        """
        Retrieve relevant content from RAG for quiz generation.

        Args:
            topic: Quiz topic
            difficulty: Difficulty level

        Returns:
            str: Retrieved content
        """
        query = f"{topic} {difficulty} level concepts explanations examples"

        # Use RAG to get relevant content
        context, sources = self.rag.get_context(
            query=query,
            top_k=3,
            metadata_filter={"exam_type": self.student.exam_type}
        )

        logger.info(f"Retrieved {len(sources)} sources for quiz generation")
        return context

    def _generate_quiz(
        self,
        topic: str,
        difficulty: str,
        num_questions: int,
        context: str
    ) -> Quiz:
        """
        Generate quiz using LLM.

        Args:
            topic: Quiz topic
            difficulty: Difficulty level
            num_questions: Number of questions to generate
            context: RAG-retrieved content

        Returns:
            Quiz: Generated quiz
        """
        quiz = Quiz(topic=topic, difficulty=difficulty, num_questions=num_questions)

        # Generate questions one by one for better quality
        for i in range(num_questions):
            question = self._generate_question(topic, difficulty, context, i + 1)
            if question:
                quiz.add_question(question)

        return quiz

    def _generate_question(
        self,
        topic: str,
        difficulty: str,
        context: str,
        question_num: int
    ) -> Optional[QuizQuestion]:
        """
        Generate a single MCQ using LLM.

        Args:
            topic: Question topic
            difficulty: Difficulty level
            context: Relevant content
            question_num: Question number

        Returns:
            QuizQuestion: Generated question or None if failed
        """
        prompt = f"""Based on this content about {topic}:

{context[:1500] if context else f"Generate a {difficulty} level question about {topic}"}

Create a high-quality multiple-choice question (MCQ) for {self.student.exam_type} preparation.

Requirements:
- Difficulty: {difficulty}
- Topic: {topic}
- 4 options (1 correct + 3 plausible distractors)
- Tests conceptual understanding
- Clear and unambiguous
- Appropriate for {self.student.exam_type} level

Return ONLY a JSON object in this exact format:
{{
    "question": "Your question here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_index": 0,
    "explanation": "Detailed explanation of why the answer is correct and why others are wrong"
}}

Question {question_num}:"""

        try:
            response = self.generate_response(
                prompt,
                temperature=0.8,  # Higher for creativity
                max_tokens=500
            )

            # Parse JSON response
            # Extract JSON from response (might have extra text)
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                question_data = json.loads(json_str)

                return QuizQuestion(
                    question_text=question_data["question"],
                    options=question_data["options"],
                    correct_answer_index=question_data["correct_index"],
                    explanation=question_data["explanation"],
                    topic=topic,
                    difficulty=difficulty
                )
            else:
                logger.error("No valid JSON found in LLM response")
                return None

        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error(f"Failed to generate question: {e}")
            # Return a fallback question
            return self._create_fallback_question(topic, difficulty)

    def _create_fallback_question(
        self,
        topic: str,
        difficulty: str
    ) -> QuizQuestion:
        """
        Create a simple fallback question if LLM generation fails.

        Args:
            topic: Question topic
            difficulty: Difficulty level

        Returns:
            QuizQuestion: Fallback question
        """
        return QuizQuestion(
            question_text=f"What is a fundamental concept in {topic}?",
            options=[
                f"Core principle of {topic}",
                f"Unrelated concept A",
                f"Unrelated concept B",
                f"Unrelated concept C"
            ],
            correct_answer_index=0,
            explanation=f"This is a {difficulty} level question about {topic}. Review your study materials for detailed explanations.",
            topic=topic,
            difficulty=difficulty
        )

    def _validate_quiz(self, quiz: Quiz) -> bool:
        """
        Validate quiz quality.

        Args:
            quiz: Generated quiz

        Returns:
            bool: True if valid
        """
        if len(quiz.questions) == 0:
            logger.warning("Quiz has no questions")
            return False

        for question in quiz.questions:
            # Check all required fields
            if not question.question_text or not question.options:
                logger.warning(f"Question {question.question_id} missing required fields")
                return False

            # Check options count
            if len(question.options) != 4:
                logger.warning(f"Question {question.question_id} has {len(question.options)} options (need 4)")
                return False

            # Check correct answer index is valid
            if not (0 <= question.correct_answer_index < 4):
                logger.warning(f"Question {question.question_id} has invalid correct_index")
                return False

        return True

    def grade_quiz(
        self,
        quiz_data: Dict[str, Any],
        student_answers: List[int]
    ) -> Dict[str, Any]:
        """
        Grade a completed quiz and update progress.

        Args:
            quiz_data: Quiz dictionary
            student_answers: List of selected answer indices

        Returns:
            Dict: Grading results
        """
        questions = quiz_data["questions"]
        num_questions = len(questions)
        correct_count = 0
        results = []

        for idx, (question, answer) in enumerate(zip(questions, student_answers)):
            correct_index = question["correct_answer_index"]
            is_correct = (answer == correct_index)

            if is_correct:
                correct_count += 1

            results.append({
                "question_id": question["question_id"],
                "selected_answer": answer,
                "correct_answer": correct_index,
                "is_correct": is_correct,
                "explanation": question["explanation"]
            })

        accuracy = (correct_count / num_questions) * 100

        # Update Progress record
        self._update_progress(
            topic=quiz_data["topic"],
            difficulty=quiz_data["difficulty"],
            results=results
        )

        return {
            "total_questions": num_questions,
            "correct_answers": correct_count,
            "accuracy": accuracy,
            "results": results,
            "passed": accuracy >= 60.0  # 60% passing threshold
        }

    def _update_progress(
        self,
        topic: str,
        difficulty: str,
        results: List[Dict[str, Any]]
    ):
        """
        Update student's progress record after quiz.

        Args:
            topic: Quiz topic
            difficulty: Difficulty level
            results: List of question results with is_correct field
        """
        # Find or create progress record
        progress = self.db.query(Progress).filter(
            Progress.student_id == self.student.id,
            Progress.topic == topic,
            Progress.difficulty_level == difficulty
        ).first()

        if not progress:
            # Create new progress record
            progress = Progress(
                student_id=self.student.id,
                topic=topic,
                difficulty_level=difficulty,
                total_attempts=0,
                correct_answers=0
            )
            self.db.add(progress)

        # Record each question attempt
        for result in results:
            progress.record_attempt(
                is_correct=result["is_correct"],
                question_type="multiple_choice"
            )

        # Commit changes
        self.db.commit()

        logger.info(
            f"Updated progress for {topic} ({difficulty}): "
            f"{progress.accuracy_percentage:.1f}% accuracy"
        )


def create_quiz_agent(
    student: Student,
    session: Session,
    db: DBSession,
    **kwargs
) -> QuizGeneratorAgent:
    """
    Factory function to create a Quiz Generator Agent instance.

    Args:
        student: Student profile
        session: Current session
        db: Database session

    Returns:
        QuizGeneratorAgent: Configured quiz generator agent
    """
    return QuizGeneratorAgent(student=student, session=session, db=db, **kwargs)
