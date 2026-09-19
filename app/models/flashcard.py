"""
Flashcard models for Agentic AI Tutor.
Handles flashcard decks, individual cards and spaced-repetition review history.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
import logging

from app.core.database import Base

logger = logging.getLogger(__name__)

# SM-2 tuning constants
MIN_EASE_FACTOR = 1.3
DEFAULT_EASE_FACTOR = 2.5
PASSING_QUALITY = 3  # Quality below this counts as a lapse
MASTERY_REPETITIONS = 5  # Successful repetitions needed for mastery
MASTERY_ACCURACY = 80.0  # Accuracy needed for mastery


class FlashcardDeck(Base):
    """
    A collection of flashcards generated for one topic.

    Decks are the unit a student studies: they carry cached counts so deck
    listings stay cheap, and expose the due/new card queues the study session
    endpoint builds its card list from.
    """

    __tablename__ = "flashcard_decks"

    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Student relationship
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    student = relationship("Student", back_populates="flashcard_decks")

    # Deck definition
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    topic = Column(String(100), nullable=False, index=True)

    # Cached statistics, refreshed by update_statistics()
    card_count = Column(Integer, default=0, nullable=False)
    mastered_count = Column(Integer, default=0, nullable=False)

    # Study tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_studied = Column(DateTime, nullable=True)

    # Relationships
    cards = relationship(
        "Flashcard", back_populates="deck", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def due_count(self) -> int:
        """
        Number of previously-seen cards due for review right now.

        Returns:
            int: Count of due cards
        """
        return len(self.get_due_cards())

    @property
    def new_count(self) -> int:
        """
        Number of cards that have never been reviewed.

        Returns:
            int: Count of new cards
        """
        return len(self.get_new_cards())

    @property
    def mastery_percentage(self) -> float:
        """
        Share of the deck the student has mastered.

        Returns:
            float: Mastery as percentage (0-100)
        """
        if not self.card_count:
            return 0.0
        return (self.mastered_count / self.card_count) * 100

    def get_due_cards(self, limit: Optional[int] = None) -> List["Flashcard"]:
        """
        Get cards that have been reviewed before and are due again.

        Args:
            limit: Maximum number of cards to return

        Returns:
            List[Flashcard]: Due cards, soonest due first
        """
        due = [card for card in self.cards if card.is_due]
        due.sort(key=lambda c: c.next_review or datetime.utcnow())

        return due[:limit] if limit is not None else due

    def get_new_cards(self, limit: Optional[int] = None) -> List["Flashcard"]:
        """
        Get cards the student has never reviewed.

        Args:
            limit: Maximum number of cards to return

        Returns:
            List[Flashcard]: New cards in creation order
        """
        new_cards = [card for card in self.cards if card.is_new]

        return new_cards[:limit] if limit is not None else new_cards

    def update_statistics(self) -> None:
        """Recalculate the cached card and mastery counts from the deck's cards"""
        self.card_count = len(self.cards)
        self.mastered_count = len([card for card in self.cards if card.is_mastered])

        logger.debug(
            f"Deck {self.id} statistics updated: "
            f"{self.mastered_count}/{self.card_count} mastered"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the deck for API responses.

        Returns:
            Dict: Deck representation with live queue counts
        """
        return {
            "id": self.id,
            "student_id": self.student_id,
            "name": self.name,
            "description": self.description,
            "topic": self.topic,
            "card_count": self.card_count,
            "mastered_count": self.mastered_count,
            "due_count": self.due_count,
            "new_count": self.new_count,
            "mastery_percentage": round(self.mastery_percentage, 1),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_studied": self.last_studied.isoformat() if self.last_studied else None,
        }

    def __repr__(self):
        return f"<FlashcardDeck(id='{self.id}', name='{self.name}', cards={self.card_count})>"

    def __str__(self):
        return f"{self.name} ({self.topic}): {self.mastered_count}/{self.card_count} mastered"


class Flashcard(Base):
    """
    A single flashcard with its spaced-repetition schedule.

    Scheduling follows the SM-2 algorithm: each review's quality (0-5) adjusts
    the ease factor and the interval until the card comes back.
    """

    __tablename__ = "flashcards"

    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Deck relationship
    deck_id = Column(String, ForeignKey("flashcard_decks.id"), nullable=False, index=True)
    deck = relationship("FlashcardDeck", back_populates="cards")

    # Card content
    card_type = Column(String(20), default="basic", nullable=False)  # basic, cloze, definition, ...
    front = Column(Text, nullable=False)  # Question or prompt
    back = Column(Text, nullable=True)  # Answer or explanation
    topic = Column(String(100), nullable=True, index=True)
    subtopic = Column(String(100), nullable=True)
    difficulty = Column(String(20), default="medium", nullable=False)

    # Study aids and provenance
    hints = Column(JSON, nullable=True, default=list)
    tags = Column(JSON, nullable=True, default=list)
    source_citation = Column(Text, nullable=True)  # Where the content came from

    # Spaced repetition state (SM-2)
    ease_factor = Column(Float, default=DEFAULT_EASE_FACTOR, nullable=False)
    interval_days = Column(Integer, default=0, nullable=False)
    repetitions = Column(Integer, default=0, nullable=False)  # Consecutive successful reviews
    next_review = Column(DateTime, nullable=True, index=True)
    last_reviewed = Column(DateTime, nullable=True)

    # Review tallies
    total_reviews = Column(Integer, default=0, nullable=False)
    correct_reviews = Column(Integer, default=0, nullable=False)
    lapses = Column(Integer, default=0, nullable=False)  # Times forgotten after learning it

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    reviews = relationship("FlashcardReview", back_populates="card", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Initialize card with empty hint and tag lists"""
        super().__init__(**kwargs)

        if self.hints is None:
            self.hints = []
        if self.tags is None:
            self.tags = []

    @property
    def is_new(self) -> bool:
        """
        Check whether the card has never been reviewed.

        Returns:
            bool: True if the card has no review history
        """
        return not self.total_reviews

    @property
    def is_due(self) -> bool:
        """
        Check whether a previously-reviewed card is due again.

        New cards are not due: they are studied through the new-card queue.

        Returns:
            bool: True if the card is scheduled for review now or earlier
        """
        if self.is_new:
            return False
        if self.next_review is None:
            return True
        return self.next_review <= datetime.utcnow()

    @property
    def is_mastered(self) -> bool:
        """
        Check whether the card counts as mastered.

        Returns:
            bool: True after enough successful repetitions at high accuracy
        """
        return (self.repetitions or 0) >= MASTERY_REPETITIONS and self.accuracy >= MASTERY_ACCURACY

    @property
    def accuracy(self) -> float:
        """
        Share of reviews answered correctly.

        Returns:
            float: Accuracy as percentage (0-100)
        """
        if not self.total_reviews:
            return 0.0
        return (self.correct_reviews / self.total_reviews) * 100

    def record_review(self, quality: int, response_time_ms: Optional[float] = None) -> None:
        """
        Apply a review result and reschedule the card using SM-2.

        Args:
            quality: Review quality on the 0-5 scale (3 and above is a pass)
            response_time_ms: How long the student took, for analytics only
        """
        quality = max(0, min(5, int(quality)))
        was_correct = quality >= PASSING_QUALITY

        # Ensure counters are initialized (columns default at flush, not in memory)
        if self.total_reviews is None:
            self.total_reviews = 0
        if self.correct_reviews is None:
            self.correct_reviews = 0
        if self.lapses is None:
            self.lapses = 0
        if self.repetitions is None:
            self.repetitions = 0
        if self.ease_factor is None:
            self.ease_factor = DEFAULT_EASE_FACTOR
        if self.interval_days is None:
            self.interval_days = 0

        self.total_reviews += 1
        if was_correct:
            self.correct_reviews += 1

        if not was_correct:
            # Lapse: relearn from the start
            if self.repetitions > 0:
                self.lapses += 1
            self.repetitions = 0
            self.interval_days = 1
        else:
            if self.repetitions == 0:
                self.interval_days = 1
            elif self.repetitions == 1:
                self.interval_days = 6
            else:
                self.interval_days = max(1, int(self.interval_days * self.ease_factor))

            self.repetitions += 1

        # SM-2 ease factor adjustment, floored so cards never collapse to daily forever
        self.ease_factor = max(
            MIN_EASE_FACTOR,
            self.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
        )

        self.last_reviewed = datetime.utcnow()
        self.next_review = self.last_reviewed + timedelta(days=self.interval_days)

        logger.debug(
            f"Card {self.id} reviewed (quality={quality}): "
            f"next review in {self.interval_days}d, ease {self.ease_factor:.2f}"
        )

    def reset_schedule(self) -> None:
        """Put the card back into the new-card queue without losing its content"""
        self.ease_factor = DEFAULT_EASE_FACTOR
        self.interval_days = 0
        self.repetitions = 0
        self.next_review = None
        self.last_reviewed = None
        self.total_reviews = 0
        self.correct_reviews = 0
        self.lapses = 0

    def to_dict(self, include_answer: bool = True) -> Dict[str, Any]:
        """
        Serialize the card for API responses.

        Args:
            include_answer: Whether to include the back of the card

        Returns:
            Dict: Card representation
        """
        data = {
            "id": self.id,
            "deck_id": self.deck_id,
            "type": self.card_type,
            "front": self.front,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "difficulty": self.difficulty,
            "hints": self.hints or [],
            "tags": self.tags or [],
            "source": self.source_citation,
            "is_new": self.is_new,
            "is_due": self.is_due,
            "is_mastered": self.is_mastered,
            "accuracy": round(self.accuracy, 1),
            "interval_days": self.interval_days,
            "next_review": self.next_review.isoformat() if self.next_review else None,
        }

        if include_answer:
            data["back"] = self.back

        return data

    def __repr__(self):
        front_preview = (self.front or "")[:40]
        return f"<Flashcard(id='{self.id}', type='{self.card_type}', front='{front_preview}')>"

    def __str__(self):
        return f"[{self.card_type}] {self.front} ({self.accuracy:.0f}% over {self.total_reviews})"


class FlashcardReview(Base):
    """
    A single review event on a flashcard.

    Kept as history so weekly study statistics and per-card analytics can be
    computed without inferring them from the card's current schedule.
    """

    __tablename__ = "flashcard_reviews"

    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Relationships
    card_id = Column(String, ForeignKey("flashcards.id"), nullable=False, index=True)
    card = relationship("Flashcard", back_populates="reviews")
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)

    # Review outcome
    quality = Column(Integer, nullable=False)  # 0-5 SM-2 quality rating
    was_correct = Column(Boolean, default=False, nullable=False)
    response_time_ms = Column(Float, nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Scheduling state before this review, for analyzing the schedule itself
    ease_factor_before = Column(Float, nullable=True)
    interval_before = Column(Integer, nullable=True)
    repetitions_before = Column(Integer, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the review for API responses.

        Returns:
            Dict: Review representation
        """
        return {
            "id": self.id,
            "card_id": self.card_id,
            "student_id": self.student_id,
            "quality": self.quality,
            "was_correct": self.was_correct,
            "response_time_ms": self.response_time_ms,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

    def __repr__(self):
        return (
            f"<FlashcardReview(card_id='{self.card_id}', "
            f"quality={self.quality}, correct={self.was_correct})>"
        )

    def __str__(self):
        outcome = "correct" if self.was_correct else "incorrect"
        return f"Review of card {self.card_id[:8]}: {outcome} (quality {self.quality})"
