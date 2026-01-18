"""
Flashcard API routes for Agentic AI Tutor.

Endpoints for:
- Generating flashcard decks
- Studying flashcards with spaced repetition
- Managing decks and cards
- Tracking review progress
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.dependencies import get_db, get_student_by_id
from app.models.student import Student
from app.models.flashcard import FlashcardDeck, Flashcard, FlashcardReview

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


# ============== Request/Response Schemas ==============

class FlashcardGenerateRequest(BaseModel):
    """Request to generate flashcards"""
    topic: str = Field(..., description="Topic to generate flashcards for")
    num_cards: int = Field(default=10, ge=1, le=50, description="Number of cards to generate")
    difficulty: str = Field(default="medium", description="Difficulty level: easy, medium, hard")
    card_types: Optional[List[str]] = Field(default=None, description="Card types to include")
    use_documents: bool = Field(default=True, description="Use uploaded documents for context")


class FlashcardReviewRequest(BaseModel):
    """Request to record a flashcard review"""
    card_id: str = Field(..., description="ID of the card reviewed")
    quality: int = Field(..., ge=0, le=5, description="Review quality (0-5 scale)")
    response_time_ms: Optional[float] = Field(default=None, description="Response time in milliseconds")


class FlashcardResponse(BaseModel):
    """Response containing flashcard data"""
    id: str
    type: str
    front: str
    back: Optional[str] = None
    topic: Optional[str] = None
    difficulty: str
    hints: List[str] = []
    tags: List[str] = []
    is_due: bool = False
    is_mastered: bool = False
    accuracy: float = 0.0


class DeckResponse(BaseModel):
    """Response containing deck data"""
    id: str
    name: str
    description: Optional[str] = None
    topic: str
    card_count: int
    mastered_count: int
    due_count: int
    new_count: int


class StudySessionResponse(BaseModel):
    """Response containing cards for study session"""
    deck_id: str
    deck_name: str
    cards: List[FlashcardResponse]
    total_due: int
    total_new: int


# ============== API Endpoints ==============

@router.post("/generate/{student_id}", response_model=DeckResponse)
async def generate_flashcards(
    student_id: str,
    request: FlashcardGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generate flashcards for a topic.

    Creates a new deck with AI-generated flashcards based on:
    - User's uploaded documents (if available)
    - Knowledge graph context
    - Web search results (fallback)

    All cards include source citations.
    """
    # Verify student exists
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    try:
        # Import flashcard agent
        from app.agents.flashcard_agent import get_flashcard_agent

        agent = get_flashcard_agent()
        response = await agent.process(
            topic=request.topic,
            num_cards=request.num_cards,
            difficulty=request.difficulty,
            student_id=student_id,
            use_documents=request.use_documents
        )

        if not response.success:
            raise HTTPException(status_code=500, detail=response.message)

        # Create deck in database
        deck = FlashcardDeck(
            student_id=student_id,
            name=response.data["name"],
            description=response.data["description"],
            topic=request.topic,
            card_count=response.data["card_count"]
        )
        db.add(deck)
        db.flush()

        # Add cards to deck
        for card_data in response.data.get("cards", []):
            card = Flashcard(
                deck_id=deck.id,
                card_type=card_data.get("type", "basic"),
                front=card_data.get("front", ""),
                back=card_data.get("back", ""),
                topic=request.topic,
                difficulty=card_data.get("difficulty", request.difficulty),
                hints=card_data.get("hints", []),
                tags=card_data.get("tags", []),
                source_citation=card_data.get("source")
            )
            db.add(card)

        db.commit()
        db.refresh(deck)

        logger.info(f"Generated {deck.card_count} flashcards for student {student_id}, topic: {request.topic}")

        return DeckResponse(
            id=deck.id,
            name=deck.name,
            description=deck.description,
            topic=deck.topic,
            card_count=deck.card_count,
            mastered_count=0,
            due_count=deck.card_count,
            new_count=deck.card_count
        )

    except Exception as e:
        logger.error(f"Flashcard generation failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to generate flashcards: {str(e)}")


@router.get("/decks/{student_id}", response_model=List[DeckResponse])
def get_student_decks(
    student_id: str,
    db: Session = Depends(get_db)
):
    """Get all flashcard decks for a student"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    decks = db.query(FlashcardDeck).filter(FlashcardDeck.student_id == student_id).all()

    return [
        DeckResponse(
            id=deck.id,
            name=deck.name,
            description=deck.description,
            topic=deck.topic,
            card_count=deck.card_count,
            mastered_count=deck.mastered_count,
            due_count=len(deck.get_due_cards()),
            new_count=len(deck.get_new_cards())
        )
        for deck in decks
    ]


@router.get("/deck/{deck_id}", response_model=DeckResponse)
def get_deck(
    deck_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific flashcard deck"""
    deck = db.query(FlashcardDeck).filter(FlashcardDeck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    return DeckResponse(
        id=deck.id,
        name=deck.name,
        description=deck.description,
        topic=deck.topic,
        card_count=deck.card_count,
        mastered_count=deck.mastered_count,
        due_count=len(deck.get_due_cards()),
        new_count=len(deck.get_new_cards())
    )


@router.get("/study/{deck_id}", response_model=StudySessionResponse)
def get_study_session(
    deck_id: str,
    max_cards: int = Query(default=20, ge=1, le=50),
    include_new: bool = Query(default=True),
    db: Session = Depends(get_db)
):
    """
    Get cards for a study session.

    Returns due cards plus optionally new cards.
    Cards are returned without answers for initial display.
    """
    deck = db.query(FlashcardDeck).filter(FlashcardDeck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    # Get due cards
    due_cards = deck.get_due_cards(limit=max_cards)
    remaining_slots = max_cards - len(due_cards)

    # Add new cards if requested and space available
    cards_to_study = list(due_cards)
    if include_new and remaining_slots > 0:
        new_cards = deck.get_new_cards(limit=remaining_slots)
        cards_to_study.extend(new_cards)

    return StudySessionResponse(
        deck_id=deck.id,
        deck_name=deck.name,
        cards=[
            FlashcardResponse(
                id=card.id,
                type=card.card_type,
                front=card.front,
                back=None,  # Don't show answer initially
                topic=card.topic,
                difficulty=card.difficulty,
                hints=card.hints or [],
                tags=card.tags or [],
                is_due=card.is_due,
                is_mastered=card.is_mastered,
                accuracy=card.accuracy
            )
            for card in cards_to_study
        ],
        total_due=len(deck.get_due_cards()),
        total_new=len(deck.get_new_cards())
    )


@router.get("/card/{card_id}/reveal")
def reveal_card(
    card_id: str,
    db: Session = Depends(get_db)
):
    """Get a card with its answer revealed"""
    card = db.query(Flashcard).filter(Flashcard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return {
        "id": card.id,
        "type": card.card_type,
        "front": card.front,
        "back": card.back,
        "hints": card.hints or [],
        "source": card.source_citation
    }


@router.post("/review")
def record_review(
    request: FlashcardReviewRequest,
    db: Session = Depends(get_db)
):
    """
    Record a flashcard review.

    Quality scale (0-5):
    - 0: Complete blackout
    - 1: Wrong, but recognized answer
    - 2: Wrong, but answer was easy to recall
    - 3: Correct with serious difficulty
    - 4: Correct with some hesitation
    - 5: Perfect response

    Updates card scheduling using SM-2 algorithm.
    """
    card = db.query(Flashcard).filter(Flashcard.id == request.card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Get deck for student_id
    deck = card.deck

    # Record review history
    review = FlashcardReview(
        card_id=card.id,
        student_id=deck.student_id,
        quality=request.quality,
        response_time_ms=request.response_time_ms,
        was_correct=request.quality >= 3,
        ease_factor_before=card.ease_factor,
        interval_before=card.interval_days,
        repetitions_before=card.repetitions
    )
    db.add(review)

    # Update card scheduling
    card.record_review(request.quality, request.response_time_ms)

    # Update deck statistics
    deck.update_statistics()
    deck.last_studied = card.last_reviewed

    db.commit()

    return {
        "success": True,
        "card_id": card.id,
        "next_review": card.next_review.isoformat() if card.next_review else None,
        "interval_days": card.interval_days,
        "is_mastered": card.is_mastered
    }


@router.delete("/deck/{deck_id}")
def delete_deck(
    deck_id: str,
    db: Session = Depends(get_db)
):
    """Delete a flashcard deck and all its cards"""
    deck = db.query(FlashcardDeck).filter(FlashcardDeck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    db.delete(deck)
    db.commit()

    return {"success": True, "message": "Deck deleted"}


@router.get("/stats/{student_id}")
def get_flashcard_stats(
    student_id: str,
    db: Session = Depends(get_db)
):
    """Get flashcard statistics for a student"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    decks = db.query(FlashcardDeck).filter(FlashcardDeck.student_id == student_id).all()

    total_cards = sum(deck.card_count for deck in decks)
    total_mastered = sum(deck.mastered_count for deck in decks)
    total_due = sum(len(deck.get_due_cards()) for deck in decks)

    # Get recent review stats
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_reviews = db.query(FlashcardReview).filter(
        FlashcardReview.student_id == student_id,
        FlashcardReview.reviewed_at >= week_ago
    ).all()

    reviews_this_week = len(recent_reviews)
    correct_this_week = len([r for r in recent_reviews if r.was_correct])

    return {
        "total_decks": len(decks),
        "total_cards": total_cards,
        "total_mastered": total_mastered,
        "total_due": total_due,
        "mastery_percentage": round((total_mastered / total_cards * 100) if total_cards > 0 else 0, 1),
        "reviews_this_week": reviews_this_week,
        "accuracy_this_week": round((correct_this_week / reviews_this_week * 100) if reviews_this_week > 0 else 0, 1)
    }
