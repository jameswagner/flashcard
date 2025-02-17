from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models.enums import EditContext
from services.flashcard import FlashcardService
from api.models.requests.flashcard import FlashcardCreate, FlashcardUpdate, CardFeedbackCreate
from api.models.responses.flashcard import (
    FlashcardResponse,
    CardVersionResponse,
    CardEditHistoryResponse,
    CardFeedbackResponse
)

router = APIRouter()

@router.patch("/{card_id}", response_model=FlashcardResponse)
async def update_card(
    card_id: int,
    card_update: FlashcardUpdate,
    edit_context: EditContext | None = None,
    edit_summary: str | None = None,
    user_id: str | None = None,
    db: Session = Depends(get_db)
):
    """Update a card, creating a new version."""
    service = FlashcardService(db)
    return service.update_card(card_id, card_update, edit_context, edit_summary, user_id)

@router.delete("/{card_id}")
async def delete_card(
    card_id: int,
    user_id: str | None = None,
    db: Session = Depends(get_db)
):
    """Soft delete a card by marking its association as deleted."""
    service = FlashcardService(db)
    return service.delete_card(card_id, user_id)

@router.post("/{card_id}/feedback")
async def submit_card_feedback(
    card_id: int,
    feedback: CardFeedbackCreate,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Submit feedback for a flashcard."""
    service = FlashcardService(db)
    return service.submit_feedback(card_id, feedback, user_id)

@router.get("/{card_id}/versions", response_model=List[CardVersionResponse])
async def get_card_versions(
    card_id: int,
    db: Session = Depends(get_db)
):
    """Get version history for a card."""
    service = FlashcardService(db)
    return service.get_card_versions(card_id)

@router.get("/{card_id}/versions/{version_number}", response_model=CardVersionResponse)
async def get_card_version(
    card_id: int,
    version_number: int,
    db: Session = Depends(get_db)
):
    """Get a specific version of a card."""
    service = FlashcardService(db)
    return service.get_card_version(card_id, version_number)

@router.get("/{card_id}/history", response_model=List[CardEditHistoryResponse])
async def get_card_edit_history(
    card_id: int,
    db: Session = Depends(get_db)
):
    """Get edit history for a card."""
    service = FlashcardService(db)
    return service.get_card_edit_history(card_id)

@router.get("/{card_id}/feedback", response_model=List[CardFeedbackResponse])
async def get_card_feedback(
    card_id: int,
    db: Session = Depends(get_db)
):
    """Get all feedback for a card."""
    service = FlashcardService(db)
    return service.get_card_feedback(card_id)

@router.post("/set/{set_id}", response_model=FlashcardResponse)
async def add_card_to_set(
    set_id: int,
    card: FlashcardCreate,
    db: Session = Depends(get_db)
):
    """Add a new card to a flashcard set."""
    service = FlashcardService(db)
    return service.add_card_to_set(set_id, card) 