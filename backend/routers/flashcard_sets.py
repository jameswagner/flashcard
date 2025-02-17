from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from services.flashcard_set import FlashcardSetService
from api.models.requests.flashcard_set import FlashcardSetCreate, FlashcardSetUpdate
from api.models.responses.flashcard_set import FlashcardSetResponse, FlashcardSetDetailResponse

router = APIRouter()

@router.get("/", response_model=List[FlashcardSetResponse])
async def get_flashcard_sets(db: Session = Depends(get_db)):
    """Get all flashcard sets."""
    service = FlashcardSetService(db)
    return service.get_sets()

@router.get("/{set_id}", response_model=FlashcardSetDetailResponse)
async def get_flashcard_set(set_id: int, db: Session = Depends(get_db)):
    """Get a specific flashcard set with all its cards."""
    service = FlashcardSetService(db)
    return service.get_set(set_id)

@router.post("/", response_model=FlashcardSetResponse)
async def create_flashcard_set(
    flashcard_set: FlashcardSetCreate,
    db: Session = Depends(get_db)
):
    """Create a new flashcard set with optional initial cards."""
    service = FlashcardSetService(db)
    return service.create_set(flashcard_set)

@router.patch("/{set_id}", response_model=FlashcardSetResponse)
async def update_flashcard_set(
    set_id: int,
    set_update: FlashcardSetUpdate,
    db: Session = Depends(get_db)
):
    """Update a flashcard set's metadata."""
    service = FlashcardSetService(db)
    return service.update_set(set_id, set_update) 