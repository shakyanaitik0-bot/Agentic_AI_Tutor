"""
Flashcard Generation Agent for Agentic AI Tutor.

Generates spaced-repetition flashcards from:
1. User's uploaded documents
2. Current study topics
3. Weak areas identified by progress tracking
4. Web search results for comprehensive coverage

Supports multiple flashcard types:
- Basic Q&A
- Cloze deletion (fill in the blank)
- Definition cards
- Concept mapping cards
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.agents.base_agent import BaseAgent, AgentResponse
from app.services.llm_service import get_llm_service
from app.services.unified_retrieval_service import get_unified_retrieval_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class FlashcardType(Enum):
    """Types of flashcards"""
    BASIC = "basic"  # Simple question and answer
    CLOZE = "cloze"  # Fill in the blank
    DEFINITION = "definition"  # Term and definition
    CONCEPT = "concept"  # Concept explanation
    FORMULA = "formula"  # Formula/equation card
    EXAMPLE = "example"  # Worked example


@dataclass
class Flashcard:
    """Represents a single flashcard"""
    id: str
    card_type: FlashcardType
    front: str  # Question or prompt
    back: str  # Answer or explanation
    topic: str
    subtopic: Optional[str] = None
    difficulty: str = "medium"  # easy, medium, hard
    hints: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source_citation: Optional[str] = None  # Where the info came from
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Spaced repetition fields
    ease_factor: float = 2.5
    interval_days: int = 1
    repetitions: int = 0
    next_review: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.card_type.value,
            "front": self.front,
            "back": self.back,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "difficulty": self.difficulty,
            "hints": self.hints,
            "tags": self.tags,
            "source": self.source_citation,
            "created_at": self.created_at.isoformat(),
            "ease_factor": self.ease_factor,
            "interval_days": self.interval_days,
            "next_review": self.next_review.isoformat() if self.next_review else None
        }

    def update_after_review(self, quality: int):
        """
        Update card scheduling based on review quality (0-5 scale).
        Uses SM-2 algorithm variant.
        """
        if quality < 3:
            # Failed - reset
            self.repetitions = 0
            self.interval_days = 1
        else:
            if self.repetitions == 0:
                self.interval_days = 1
            elif self.repetitions == 1:
                self.interval_days = 6
            else:
                self.interval_days = int(self.interval_days * self.ease_factor)

            self.repetitions += 1

        # Update ease factor
        self.ease_factor = max(1.3, self.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

        # Set next review
        from datetime import timedelta
        self.next_review = datetime.utcnow() + timedelta(days=self.interval_days)


@dataclass
class FlashcardDeck:
    """Collection of flashcards for a topic"""
    id: str
    name: str
    description: str
    topic: str
    cards: List[Flashcard] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    student_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "topic": self.topic,
            "card_count": len(self.cards),
            "cards": [c.to_dict() for c in self.cards],
            "created_at": self.created_at.isoformat()
        }

    def get_due_cards(self) -> List[Flashcard]:
        """Get cards due for review"""
        now = datetime.utcnow()
        return [c for c in self.cards if c.next_review is None or c.next_review <= now]


class FlashcardAgent(BaseAgent):
    """
    Agent for generating and managing study flashcards.

    Capabilities:
    - Generate flashcards from documents
    - Create topic-specific decks
    - Support multiple card types
    - Include citations for source material
    """

    def __init__(self):
        super().__init__(
            name="FlashcardAgent",
            description="Generates study flashcards with spaced repetition support"
        )
        self.llm_service = None
        self.retrieval_service = None

    def _init_services(self):
        """Lazy initialize services"""
        if self.llm_service is None:
            self.llm_service = get_llm_service()
        if self.retrieval_service is None:
            self.retrieval_service = get_unified_retrieval_service()

    async def process(
        self,
        topic: str,
        num_cards: int = 10,
        card_types: Optional[List[FlashcardType]] = None,
        difficulty: str = "medium",
        student_id: Optional[str] = None,
        use_documents: bool = True,
        context: Optional[str] = None
    ) -> AgentResponse:
        """
        Generate flashcards for a topic.

        Args:
            topic: Topic to generate flashcards for
            num_cards: Number of cards to generate
            card_types: Types of cards to generate (default: all)
            difficulty: Target difficulty level
            student_id: Student ID for personalized content
            use_documents: Whether to use uploaded documents
            context: Optional additional context

        Returns:
            AgentResponse with generated flashcards
        """
        self._init_services()

        try:
            # Get context from retrieval
            retrieval_context = ""
            citations = []

            if use_documents or context is None:
                retrieval_response = self.retrieval_service.retrieve(
                    query=f"Key concepts, definitions, and formulas about {topic}",
                    student_id=student_id,
                    topic=topic,
                    include_web=True,
                    max_results=5
                )
                retrieval_context = retrieval_response.context
                citations = retrieval_response.citations

            # Combine contexts
            full_context = f"{retrieval_context}\n\n{context}" if context else retrieval_context

            # Generate flashcards using LLM
            cards = await self._generate_cards_with_llm(
                topic=topic,
                context=full_context,
                num_cards=num_cards,
                card_types=card_types or list(FlashcardType),
                difficulty=difficulty,
                citations=citations
            )

            # Create deck
            import uuid
            deck = FlashcardDeck(
                id=str(uuid.uuid4()),
                name=f"{topic} Flashcards",
                description=f"Study deck for {topic} with {len(cards)} cards",
                topic=topic,
                cards=cards,
                student_id=student_id
            )

            return AgentResponse(
                success=True,
                message=f"Generated {len(cards)} flashcards for {topic}",
                data=deck.to_dict(),
                metadata={
                    "topic": topic,
                    "card_count": len(cards),
                    "sources_used": [c.to_dict() for c in citations] if citations else []
                }
            )

        except Exception as e:
            logger.error(f"Flashcard generation failed: {e}")
            return AgentResponse(
                success=False,
                message=f"Failed to generate flashcards: {str(e)}",
                data=None
            )

    async def _generate_cards_with_llm(
        self,
        topic: str,
        context: str,
        num_cards: int,
        card_types: List[FlashcardType],
        difficulty: str,
        citations: List
    ) -> List[Flashcard]:
        """Generate flashcards using LLM"""

        card_type_instructions = {
            FlashcardType.BASIC: "Basic Q&A: Simple question with direct answer",
            FlashcardType.CLOZE: "Cloze: Sentence with key term blanked out using ___",
            FlashcardType.DEFINITION: "Definition: Term on front, definition on back",
            FlashcardType.CONCEPT: "Concept: Concept name on front, explanation on back",
            FlashcardType.FORMULA: "Formula: Formula name on front, formula and usage on back",
            FlashcardType.EXAMPLE: "Example: Problem on front, step-by-step solution on back"
        }

        type_instructions = "\n".join([card_type_instructions[t] for t in card_types if t in card_type_instructions])

        prompt = f"""Generate {num_cards} high-quality flashcards about "{topic}" for studying.

Context information:
{context[:3000] if context else "Use your knowledge about the topic."}

Card types to include:
{type_instructions}

Difficulty level: {difficulty}

Generate flashcards in the following JSON format:
```json
[
  {{
    "type": "basic|cloze|definition|concept|formula|example",
    "front": "Question or prompt",
    "back": "Answer or explanation",
    "hints": ["optional hint 1"],
    "tags": ["tag1", "tag2"],
    "difficulty": "easy|medium|hard"
  }}
]
```

Requirements:
- Make cards clear and focused on one concept each
- Include practical hints when helpful
- Vary card types for better learning
- For cloze cards, use ___ for blanks
- For formula cards, include when to use the formula
- For example cards, show step-by-step solutions

Generate exactly {num_cards} cards as a JSON array:"""

        try:
            response = await self.llm_service.generate(prompt)

            # Extract JSON from response
            cards_data = self._parse_cards_json(response, num_cards, topic)

            # Convert to Flashcard objects
            import uuid
            cards = []
            citation_text = f"Generated from: {topic}"
            if citations:
                citation_text = f"Sources: {', '.join([c.title for c in citations[:3]])}"

            for i, card_data in enumerate(cards_data):
                card_type = FlashcardType(card_data.get("type", "basic"))
                cards.append(Flashcard(
                    id=f"card_{uuid.uuid4().hex[:8]}",
                    card_type=card_type,
                    front=card_data.get("front", ""),
                    back=card_data.get("back", ""),
                    topic=topic,
                    difficulty=card_data.get("difficulty", difficulty),
                    hints=card_data.get("hints", []),
                    tags=card_data.get("tags", [topic.lower()]),
                    source_citation=citation_text
                ))

            return cards

        except Exception as e:
            logger.error(f"LLM flashcard generation failed: {e}")
            # Return fallback cards
            return self._generate_fallback_cards(topic, num_cards, difficulty)

    def _parse_cards_json(self, response: str, num_cards: int, topic: str) -> List[Dict]:
        """Parse JSON cards from LLM response"""
        try:
            # Try to find JSON array in response
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                cards_data = json.loads(json_match.group())
                if isinstance(cards_data, list):
                    return cards_data[:num_cards]
        except json.JSONDecodeError:
            pass

        # Fallback parsing
        logger.warning("Could not parse LLM response as JSON, using fallback")
        return []

    def _generate_fallback_cards(self, topic: str, num_cards: int, difficulty: str) -> List[Flashcard]:
        """Generate basic fallback cards when LLM fails"""
        import uuid
        cards = []

        fallback_prompts = [
            ("What is", "the definition of"),
            ("Explain", "the concept of"),
            ("What are", "the key characteristics of"),
            ("How does", "work"),
            ("Why is", "important"),
        ]

        for i in range(min(num_cards, len(fallback_prompts))):
            prefix, suffix = fallback_prompts[i]
            cards.append(Flashcard(
                id=f"card_{uuid.uuid4().hex[:8]}",
                card_type=FlashcardType.BASIC,
                front=f"{prefix} {topic} {suffix}?",
                back=f"[Answer about {topic}]",
                topic=topic,
                difficulty=difficulty,
                tags=[topic.lower()]
            ))

        return cards

    def generate_from_weak_areas(
        self,
        weak_areas: List[str],
        num_per_topic: int = 5
    ) -> List[FlashcardDeck]:
        """
        Generate flashcard decks for student's weak areas.

        Args:
            weak_areas: List of weak topic areas
            num_per_topic: Cards per topic

        Returns:
            List of FlashcardDeck objects
        """
        decks = []
        import asyncio

        for topic in weak_areas[:5]:  # Limit to 5 topics
            try:
                # Run async in sync context
                loop = asyncio.get_event_loop()
                response = loop.run_until_complete(
                    self.process(
                        topic=topic,
                        num_cards=num_per_topic,
                        difficulty="easy"  # Start easy for weak areas
                    )
                )
                if response.success and response.data:
                    from dataclasses import asdict
                    deck = FlashcardDeck(
                        id=response.data["id"],
                        name=response.data["name"],
                        description=response.data["description"],
                        topic=topic,
                        cards=[]  # Cards are in data
                    )
                    decks.append(deck)
            except Exception as e:
                logger.error(f"Failed to generate deck for {topic}: {e}")

        return decks


# Singleton instance
_flashcard_agent: Optional[FlashcardAgent] = None


def get_flashcard_agent() -> FlashcardAgent:
    """Get or create singleton flashcard agent"""
    global _flashcard_agent
    if _flashcard_agent is None:
        _flashcard_agent = FlashcardAgent()
    return _flashcard_agent
