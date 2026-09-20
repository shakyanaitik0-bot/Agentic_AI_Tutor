"""
Base Agent Architecture for Agentic AI Tutor.

Provides foundational agent capabilities:
- Reasoning and planning
- Tool usage
- State management
- LLM interaction
- Progress tracking
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod

from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.models.student import Student
from app.models.session import Session

logger = logging.getLogger(__name__)


# Phrases that point at something the student uploaded rather than at a
# subject. A question like "analyse the file I uploaded" shares no words with
# the file's contents, so similarity search has nothing to match and the tutor
# used to answer that no file had been uploaded at all.
_UPLOAD_REFERENCES = (
    "uploaded",
    "upload",
    "my file",
    "the file",
    "my document",
    "the document",
    "my doc",
    "the doc",
    "my notes",
    "my pdf",
    "attached",
    "attachment",
    "library",
)


def refers_to_uploaded_material(text: str) -> bool:
    """Whether a message points at the student's own uploads"""
    lowered = text.lower()
    return any(phrase in lowered for phrase in _UPLOAD_REFERENCES)


@dataclass
class AgentResponse:
    """
    Standard envelope for an agent result.

    Agents that are invoked directly by an API route (rather than through the
    orchestrator) return this instead of a bare dict, so callers can branch on
    ``success`` without guessing at the payload shape.
    """

    success: bool
    message: str = ""
    data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response to a JSON-serialisable dictionary"""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "metadata": self.metadata,
        }


class AgentState:
    """
    Represents the current state of an agent's execution.

    Tracks workflow progress, context, and intermediate results.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        """Initialize agent state"""
        self.data = initial_state or {}
        self.history: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def update(self, key: str, value: Any):
        """Update a state value"""
        old_value = self.data.get(key)
        self.data[key] = value
        self.updated_at = datetime.now()

        # Log state change
        self.history.append(
            {
                "timestamp": self.updated_at.isoformat(),
                "key": key,
                "old_value": old_value,
                "new_value": value,
            }
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value"""
        return self.data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary"""
        return {
            "data": self.data,
            "history_length": len(self.history),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"AgentState({len(self.data)} keys, {len(self.history)} changes)"


class BaseAgent(ABC):
    """
    Abstract base class for all AI tutor agents.

    Provides core agent capabilities:
    - LLM interaction with configurable parameters
    - RAG-based knowledge retrieval
    - State management
    - Session and student context
    - Structured reasoning (think → plan → act)

    All specialized agents (Planner, Quiz Generator, Feedback) inherit from this.
    """

    def __init__(
        self,
        agent_name: str,
        student: Student,
        session: Session,
        llm_service: Optional[LLMService] = None,
        rag_service: Optional[RAGService] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize base agent.

        Args:
            agent_name: Name/type of the agent
            student: Student profile
            session: Current learning session
            llm_service: Optional LLM service instance
            rag_service: Optional RAG service instance
            config: Optional agent-specific configuration
        """
        self.agent_name = agent_name
        self.student = student
        self.session = session
        self.config = config or {}

        # Initialize services
        self.llm = llm_service or LLMService()
        self.rag = rag_service or RAGService()

        # Initialize state
        self.state = AgentState(initial_state=session.agent_state or {})

        # Agent metadata
        self.created_at = datetime.now()
        self.total_calls = 0

        logger.info(f"Initialized {agent_name} for student {student.name} (session: {session.id})")

    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent.

        Should be overridden by subclasses to define agent personality and role.

        Returns:
            str: System prompt describing agent's role and behavior
        """
        return f"""You are a {self.agent_name} agent in an adaptive learning system.

Student Profile:
- Name: {self.student.name}
- Exam: {self.student.exam_type}

Your role is to provide personalized educational assistance based on the student's
weak areas and progress. Always be encouraging, clear, and adaptive to the student's needs."""

    @abstractmethod
    def execute(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Main execution method for the agent.

        Must be implemented by all subclasses.

        Args:
            user_input: User's message or query
            **kwargs: Additional agent-specific parameters

        Returns:
            Dict: Agent response with output, metadata, and state updates
        """
        pass

    def think(self, context: str, question: str) -> str:
        """
        Reasoning step: Analyze the situation and determine approach.

        Args:
            context: Relevant background information
            question: Question or task to think about

        Returns:
            str: Reasoning and analysis
        """
        prompt = f"""Given this context:
{context}

Question/Task: {question}

Think through this step by step. What's the key information? What approach should we take?
Provide your reasoning:"""

        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat_completion(
            messages=messages,
            system_prompt=self.get_system_prompt(),
            temperature=0.7,
            max_tokens=500,
        )

        self.state.update("last_reasoning", response)
        return response

    def retrieve_knowledge(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Retrieve relevant knowledge from RAG system.

        Args:
            query: Search query
            top_k: Number of results (defaults to config)
            metadata_filter: Optional metadata filters

        Returns:
            str: Retrieved context
        """
        # An explicit filter is the caller's business; leave it alone.
        if metadata_filter is not None:
            context, sources = self.rag.get_context(
                query=query, top_k=top_k, metadata_filter=metadata_filter
            )
            self._record_sources(sources)
            return context

        # Otherwise search the student's own uploads first, then the shared
        # material. Filtering only on exam_type used to skip their uploads
        # entirely: RAGService scores a student-scoped search against a much
        # lower similarity threshold, so a document that clears the bar for
        # the person who uploaded it was being held to the general one and
        # dropped. That is why the Library could show a document indexed
        # while the tutor insisted nothing had been uploaded.
        own_context, own_sources = self.rag.get_context(
            query=query, top_k=top_k, metadata_filter={"student_id": self.student.id}
        )
        shared_context, shared_sources = self.rag.get_context(
            query=query, top_k=top_k, metadata_filter={"exam_type": self.student.exam_type}
        )

        self._record_sources(own_sources + shared_sources)

        parts = [part for part in (own_context, shared_context) if part]
        return "\n\n".join(parts)

    def _record_sources(self, sources: List[Dict[str, Any]]):
        """Note what the last retrieval matched, for the session state"""
        self.state.update(
            "last_retrieval_sources", [{"id": src["id"], "score": src["score"]} for src in sources]
        )

    def describe_student_documents(self) -> str:
        """
        Name the documents this student has uploaded, if any.

        Returns:
            str: A one-line summary, or "" when they have uploaded nothing
        """
        try:
            documents = self.rag.list_student_documents(self.student.id)
        except Exception as e:
            logger.warning(f"Could not list documents for student {self.student.id}: {e}")
            return ""

        names = [doc.get("filename", "a document") for doc in documents]
        return ", ".join(names)

    def read_student_documents(self, limit: int = 3) -> str:
        """
        Read from the student's uploaded documents directly.

        For questions about the upload itself rather than its subject, where
        similarity search has nothing to match on.

        Args:
            limit: Maximum number of chunks to include

        Returns:
            str: The chunk text, or "" when there is nothing to read
        """
        try:
            chunks = self.rag.get_student_chunks(self.student.id, limit=limit)
        except Exception as e:
            logger.warning(f"Could not read documents for student {self.student.id}: {e}")
            return ""

        return "\n\n".join(
            f"From {chunk['filename']}:\n{chunk['content']}" for chunk in chunks
        )

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate a response using the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt override
            temperature: Optional temperature override
            max_tokens: Optional max tokens override

        Returns:
            str: Generated response
        """
        self.total_calls += 1

        # Format as chat messages
        messages = [{"role": "user", "content": prompt}]

        response = self.llm.chat_completion(
            messages=messages,
            system_prompt=system_prompt or self.get_system_prompt(),
            temperature=temperature or self.config.get("temperature", 0.7),
            max_tokens=max_tokens or self.config.get("max_tokens", 1000),
        )

        return response

    def explain_decision(self, decision: str, reasoning: str) -> str:
        """
        Provide an explanation for an agent decision.

        Addresses objective: "Provide explainable recommendations"

        Args:
            decision: The decision made
            reasoning: The reasoning behind it

        Returns:
            str: User-friendly explanation
        """
        prompt = f"""Explain this decision to the student in a clear, encouraging way:

Decision: {decision}
Reasoning: {reasoning}

Provide a brief (2-3 sentences) explanation that helps the student understand WHY
this decision was made and HOW it will help their learning:"""

        messages = [{"role": "user", "content": prompt}]
        explanation = self.llm.chat_completion(
            messages=messages,
            system_prompt=self.get_system_prompt(),
            temperature=0.5,
            max_tokens=200,
        )

        return explanation

    def update_session_state(self):
        """Update the session with current agent state"""
        from sqlalchemy.orm.attributes import flag_modified

        self.session.agent_state = self.state.to_dict()
        self.session.last_interaction = datetime.now()

        # Mark JSON column as modified so SQLAlchemy detects the change
        flag_modified(self.session, "agent_state")
        logger.info(
            f"Session state updated and marked as modified: {list(self.state.to_dict().keys())}"
        )

    def get_student_context(self) -> str:
        """
        Get formatted student context for prompts.

        Returns:
            str: Student profile summary
        """
        weak_areas = self.student.weak_areas or []
        strong_areas = self.student.strong_areas or []
        preferences = self.student.learning_preferences or {}

        context = f"""Student Profile:
- Name: {self.student.name}
- Exam: {self.student.exam_type}
- Preferred Difficulty: {preferences.get("preferred_difficulty", "medium")}
"""

        if weak_areas:
            context += f"\nWeak Areas (need practice):\n"
            for area in weak_areas[:5]:  # Top 5
                context += f"  - {area}\n"

        if strong_areas:
            context += f"\nStrong Areas:\n"
            for area in strong_areas[:5]:  # Top 5
                context += f"  - {area}\n"

        return context

    def log_interaction(
        self, user_input: str, agent_output: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log agent interaction for progress tracking.

        Args:
            user_input: User's message
            agent_output: Agent's response
            metadata: Optional additional metadata
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name,
            "student_id": self.student.id,
            "session_id": self.session.id,
            "user_input": user_input[:200],  # Truncate for storage
            "agent_output": agent_output[:200],
            "metadata": metadata or {},
        }

        logger.info(f"[{self.agent_name}] Interaction logged: {log_entry}")

    def __repr__(self) -> str:
        return (
            f"{self.agent_name}(student={self.student.name}, "
            f"session={self.session.id[:8]}, "
            f"calls={self.total_calls})"
        )


class SimpleConversationAgent(BaseAgent):
    """
    Simple conversation agent for testing.

    Demonstrates base agent usage with basic Q&A functionality.
    """

    def __init__(self, student: Student, session: Session, **kwargs):
        """Initialize simple conversation agent"""
        super().__init__(
            agent_name="SimpleConversation", student=student, session=session, **kwargs
        )

    def get_system_prompt(self, reading_documents: bool = False) -> str:
        """
        Override system prompt for conversation.

        Args:
            reading_documents: True when the prompt carries the text of a
                document the student uploaded. The usual Socratic framing is
                wrong there: asked to look at their own file, a tutor told to
                draw answers out of the student answers with a question about
                what they would like to do with it, which is no use to
                someone who just asked what is in it.
        """
        opening = (
            f"You are a friendly AI tutor helping {self.student.name} "
            f"prepare for {self.student.exam_type}."
        )

        if reading_documents:
            return f"""{opening}

Be encouraging, patient, and adaptive.

The student is asking about material they uploaded themselves, and the text of
it is in front of you. Work from that text:

1. Say what the document actually is - its subject and how it is laid out
2. Go through what it contains: the questions it sets, the topics it covers,
   the definitions or figures it gives, quoting its own wording where that is
   clearer than paraphrasing
3. Then, and only then, suggest how to study it, keeping their weak areas in mind

Do not open with a question, do not ask what they would like to do with the
document, and do not offer help conditional on them telling you more. If the
text you were given is too short or too garbled to describe, say plainly what
you can see of it and what appears to be missing rather than filling the gap
with generalities."""

        return f"""{opening}

Be encouraging, patient, and adaptive. Use the Socratic method when appropriate -
guide students to discover answers rather than just providing them.

When answering questions:
1. Check if the topic is a weak area and provide extra support
2. Use examples relevant to {self.student.exam_type} preparation
3. Break down complex concepts into simpler parts
4. Encourage active learning"""

    def execute(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        Execute conversation agent.

        Args:
            user_input: User's question or message
            **kwargs: Additional parameters

        Returns:
            Dict: Response with answer and metadata
        """
        logger.info(f"[SimpleConversation] Processing: '{user_input[:50]}...'")

        # Step 1: Retrieve relevant knowledge
        context = self.retrieve_knowledge(user_input, top_k=3)

        # Step 2: If they are asking about their own upload, read it directly.
        # Similarity search cannot answer "what is in the file I gave you".
        uploaded_files = ""
        document_text = ""
        if refers_to_uploaded_material(user_input):
            uploaded_files = self.describe_student_documents()
            document_text = self.read_student_documents(limit=6)
            if document_text:
                context = f"{document_text}\n\n{context}" if context else document_text

        # Step 3: Get student context
        student_context = self.get_student_context()

        library = (
            f"\nDocuments this student has uploaded: {uploaded_files}" if uploaded_files else ""
        )

        # Step 4: Generate response. Having the document is not enough on its
        # own - told only that it may use the text, the model would
        # acknowledge the upload and ask what to do with it. Reading it out is
        # the thing being asked for, so say so.
        if document_text:
            instruction = """Answer from the student's own document above. Start with what it
actually says: its subject, how it is organised, and the specific questions or
points it contains. Then suggest how to work through it, bearing their weak
areas in mind. Do not ask what they would like to do with the document."""
        else:
            instruction = """Provide a helpful, educational response. If this relates to a weak
area, offer extra support and practice suggestions."""

        prompt = f"""Student Context:
{student_context}{library}

Relevant Knowledge:
{context}

Student's Question: {user_input}

{instruction}"""

        response = self.generate_response(
            prompt,
            system_prompt=self.get_system_prompt(reading_documents=bool(document_text)),
        )

        # Step 4: Update state
        self.state.update("last_query", user_input)
        self.state.update("last_response", response)
        self.update_session_state()

        # Step 5: Log interaction
        self.log_interaction(
            user_input,
            response,
            {
                "context_retrieved": len(context) > 0,
                "sources_used": len(self.state.get("last_retrieval_sources", [])),
            },
        )

        return {
            "response": response,
            "agent": self.agent_name,
            "sources_used": len(self.state.get("last_retrieval_sources", [])),
            "metadata": {"total_calls": self.total_calls, "session_id": self.session.id},
        }
