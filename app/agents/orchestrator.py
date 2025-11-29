"""
Orchestrator Agent for Agentic AI Tutor.

Coordinates multi-agent workflows:
- Intent classification from user input
- Agent selection and routing
- Multi-agent workflow coordination
- Response synthesis
- Conversation state management
"""
import logging
import re
from typing import Dict, Any, List, Optional
from enum import Enum
from sqlalchemy.orm import Session as DBSession

from app.agents.base_agent import BaseAgent, SimpleConversationAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.quiz_agent import QuizGeneratorAgent
from app.agents.feedback_agent import FeedbackAgent
from app.models.student import Student
from app.models.session import Session
from app.core.config import settings

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of user intents that can be classified"""
    PLAN = "plan"                    # Create/update study plan
    QUIZ = "quiz"                    # Generate quiz
    FEEDBACK = "feedback"            # View progress/feedback
    CONVERSATION = "conversation"    # General Q&A
    UNKNOWN = "unknown"              # Cannot classify


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent - Routes user requests to specialized agents.

    Capabilities:
    - Classify user intent from natural language
    - Route to appropriate specialized agent
    - Coordinate multi-agent workflows
    - Synthesize responses from multiple agents
    - Manage conversation state and context
    """

    def __init__(
        self,
        student: Student,
        session: Session,
        db: DBSession,
        **kwargs
    ):
        """
        Initialize Orchestrator Agent.

        Args:
            student: Student profile
            session: Current session
            db: Database session
            **kwargs: Additional arguments for BaseAgent
        """
        super().__init__(
            agent_name="Orchestrator",
            student=student,
            session=session,
            **kwargs
        )
        self.db = db

        # Initialize specialized agents (lazy loaded)
        self._planner_agent: Optional[PlannerAgent] = None
        self._quiz_agent: Optional[QuizGeneratorAgent] = None
        self._feedback_agent: Optional[FeedbackAgent] = None
        self._conversation_agent: Optional[SimpleConversationAgent] = None

        # Intent classification patterns
        self.intent_patterns = {
            IntentType.PLAN: [
                r"create.*plan", r"study plan", r"schedule", r"timeline",
                r"organize.*study", r"plan.*exam", r"prepare.*strategy"
            ],
            IntentType.QUIZ: [
                r"quiz", r"test", r"practice.*questions", r"assessment",
                r"mcq", r"questions on", r"give me.*problems"
            ],
            IntentType.FEEDBACK: [
                r"how.*doing", r"progress", r"performance", r"feedback",
                r"my.*score", r"weak.*areas", r"strengths", r"report"
            ],
            IntentType.CONVERSATION: [
                r"explain", r"what is", r"how does", r"tell me about",
                r"help.*understand", r"clarify", r"can you"
            ]
        }

        logger.info(f"Orchestrator initialized for student {student.id}")

    def execute(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Process user request by routing to appropriate agent.

        Args:
            user_input: User's natural language request
            **kwargs: Additional parameters for specialized agents

        Returns:
            Dict: Response from the appropriate agent
        """
        logger.info(f"[Orchestrator] Processing request: '{user_input[:50]}...'")

        # Classify intent
        intent = self._classify_intent(user_input, **kwargs)
        logger.info(f"[Orchestrator] Classified intent: {intent.value}")

        # Route to appropriate agent
        try:
            if intent == IntentType.PLAN:
                response = self._handle_plan(user_input, **kwargs)
            elif intent == IntentType.QUIZ:
                response = self._handle_quiz(user_input, **kwargs)
            elif intent == IntentType.FEEDBACK:
                response = self._handle_feedback(user_input, **kwargs)
            elif intent == IntentType.CONVERSATION:
                response = self._handle_conversation(user_input, **kwargs)
            else:
                # Unknown intent - try conversation agent
                logger.warning(f"[Orchestrator] Unknown intent, defaulting to conversation")
                response = self._handle_conversation(user_input, **kwargs)

            # Add orchestrator metadata
            response["orchestrator"] = {
                "intent": intent.value,
                "session_id": self.session.id
            }

            return response

        except Exception as e:
            logger.error(f"[Orchestrator] Error processing request: {e}")
            return {
                "agent": "Orchestrator",
                "intent": intent.value,
                "error": str(e),
                "message": "I encountered an error processing your request. Please try again."
            }

    def _classify_intent(self, user_input: str, **kwargs) -> IntentType:
        """
        Classify user intent from input text.

        Uses keyword matching and optional LLM classification.

        Args:
            user_input: User's input text
            **kwargs: May contain explicit 'intent' parameter

        Returns:
            IntentType: Classified intent
        """
        # Check if intent is explicitly provided
        if "intent" in kwargs:
            try:
                return IntentType(kwargs["intent"])
            except ValueError:
                logger.warning(f"Invalid explicit intent: {kwargs['intent']}")

        # Pattern-based classification
        user_input_lower = user_input.lower()

        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input_lower):
                    return intent_type

        # If no pattern matched, use LLM for classification
        return self._llm_classify_intent(user_input)

    def _llm_classify_intent(self, user_input: str) -> IntentType:
        """
        Use LLM to classify intent when patterns don't match.

        Args:
            user_input: User's input text

        Returns:
            IntentType: Classified intent
        """
        prompt = f"""Classify the following user request into ONE of these categories:
- PLAN: User wants to create/update a study plan or schedule
- QUIZ: User wants to practice with questions or take a quiz
- FEEDBACK: User wants to see their progress, performance, or get feedback
- CONVERSATION: User wants explanation, clarification, or general help

User request: "{user_input}"

Return ONLY the category name (PLAN, QUIZ, FEEDBACK, or CONVERSATION) with no explanation."""

        try:
            response = self.generate_response(prompt, temperature=0.1, max_tokens=20)
            response_clean = response.strip().upper()

            # Map response to IntentType
            intent_mapping = {
                "PLAN": IntentType.PLAN,
                "QUIZ": IntentType.QUIZ,
                "FEEDBACK": IntentType.FEEDBACK,
                "CONVERSATION": IntentType.CONVERSATION
            }

            return intent_mapping.get(response_clean, IntentType.CONVERSATION)

        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}, defaulting to CONVERSATION")
            return IntentType.CONVERSATION

    def _handle_plan(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Handle study plan request by routing to Planner Agent.

        Args:
            user_input: User's request
            **kwargs: Additional parameters (timeline_days, focus_topics)

        Returns:
            Dict: Plan generated by Planner Agent
        """
        logger.info("[Orchestrator] Routing to Planner Agent")

        # Lazy load Planner Agent
        if not self._planner_agent:
            self._planner_agent = PlannerAgent(
                student=self.student,
                session=self.session,
                db=self.db
            )

        # Execute planner
        return self._planner_agent.execute(user_input, **kwargs)

    def _handle_quiz(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Handle quiz request by routing to Quiz Generator Agent.

        May trigger feedback after quiz completion.

        Args:
            user_input: User's request
            **kwargs: Additional parameters (topic, difficulty, num_questions)

        Returns:
            Dict: Quiz generated by Quiz Agent
        """
        logger.info("[Orchestrator] Routing to Quiz Generator Agent")

        # Lazy load Quiz Agent
        if not self._quiz_agent:
            self._quiz_agent = QuizGeneratorAgent(
                student=self.student,
                session=self.session,
                db=self.db
            )

        # Execute quiz generator
        response = self._quiz_agent.execute(user_input, **kwargs)

        # Note: Feedback after quiz completion should be triggered
        # separately when quiz results are submitted
        return response

    def _handle_feedback(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Handle feedback request by routing to Feedback Agent.

        Args:
            user_input: User's request
            **kwargs: Additional parameters (report_type, format)

        Returns:
            Dict: Feedback report from Feedback Agent
        """
        logger.info("[Orchestrator] Routing to Feedback Agent")

        # Lazy load Feedback Agent
        if not self._feedback_agent:
            self._feedback_agent = FeedbackAgent(
                student=self.student,
                session=self.session,
                db=self.db
            )

        # Execute feedback agent
        response = self._feedback_agent.execute(user_input, **kwargs)

        # Check if replanning is needed
        if response.get("needs_replanning"):
            logger.info("[Orchestrator] Replanning recommended by Feedback Agent")
            # Add suggestion to response
            response["orchestrator_suggestion"] = (
                "Your progress shows significant changes. "
                "Would you like me to create an updated study plan?"
            )

        return response

    def _handle_conversation(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Handle general conversation by routing to Conversation Agent.

        Args:
            user_input: User's request
            **kwargs: Additional parameters

        Returns:
            Dict: Response from Conversation Agent
        """
        logger.info("[Orchestrator] Routing to Conversation Agent")

        # Lazy load Conversation Agent
        if not self._conversation_agent:
            self._conversation_agent = SimpleConversationAgent(
                student=self.student,
                session=self.session
            )

        # Execute conversation agent
        return self._conversation_agent.execute(user_input, **kwargs)

    def execute_workflow(
        self,
        workflow_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a multi-agent workflow.

        Workflows:
        - quiz_with_feedback: Generate quiz, then provide feedback after completion
        - assess_and_plan: Analyze progress, then create updated plan

        Args:
            workflow_type: Type of workflow to execute
            **kwargs: Parameters for the workflow

        Returns:
            Dict: Combined results from workflow
        """
        logger.info(f"[Orchestrator] Executing workflow: {workflow_type}")

        if workflow_type == "quiz_with_feedback":
            return self._workflow_quiz_with_feedback(**kwargs)
        elif workflow_type == "assess_and_plan":
            return self._workflow_assess_and_plan(**kwargs)
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

    def _workflow_quiz_with_feedback(self, **kwargs) -> Dict[str, Any]:
        """
        Workflow: Generate quiz, get results, provide feedback.

        Args:
            **kwargs: Quiz parameters (topic, difficulty, num_questions)

        Returns:
            Dict: Combined quiz and feedback results
        """
        # Step 1: Generate feedback on current performance
        feedback_response = self._handle_feedback(
            "Show my current progress",
            report_type="data"
        )

        # Step 2: Generate quiz based on weak areas
        weak_topics = feedback_response.get("data", {}).get("weak_topics", [])
        if weak_topics:
            topic = weak_topics[0]["topic"]  # Focus on weakest topic
            kwargs["topic"] = topic

        quiz_response = self._handle_quiz("Generate a quiz", **kwargs)

        return {
            "workflow": "quiz_with_feedback",
            "feedback": feedback_response,
            "quiz": quiz_response,
            "message": f"Here's a quiz on {kwargs.get('topic', 'your weak areas')}. "
                      f"Your current performance will be updated after completion."
        }

    def _workflow_assess_and_plan(self, **kwargs) -> Dict[str, Any]:
        """
        Workflow: Analyze progress, then create updated study plan.

        Args:
            **kwargs: Planning parameters (timeline_days)

        Returns:
            Dict: Combined feedback and plan
        """
        # Step 1: Get comprehensive feedback
        feedback_response = self._handle_feedback(
            "Show detailed progress report",
            report_type="data"
        )

        # Step 2: Create plan based on weak areas
        plan_response = self._handle_plan(
            "Create a study plan focusing on my weak areas",
            **kwargs
        )

        return {
            "workflow": "assess_and_plan",
            "feedback": feedback_response,
            "plan": plan_response,
            "message": "I've analyzed your progress and created an updated study plan."
        }


def create_orchestrator(
    student: Student,
    session: Session,
    db: DBSession
) -> OrchestratorAgent:
    """
    Factory function to create an Orchestrator Agent instance.

    Args:
        student: Student profile
        session: Current session
        db: Database session

    Returns:
        OrchestratorAgent: Initialized orchestrator
    """
    return OrchestratorAgent(
        student=student,
        session=session,
        db=db
    )
