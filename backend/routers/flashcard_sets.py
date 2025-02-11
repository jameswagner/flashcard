from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import FlashcardSet
from pydantic import BaseModel

router = APIRouter()

class FlashcardSetCreate(BaseModel):
    title: str
    description: str | None = None

class FlashcardSetResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    card_count: int

    class Config:
        from_attributes = True

@router.get("/", response_model=List[FlashcardSetResponse])
async def get_flashcard_sets(db: Session = Depends(get_db)):
    sets = db.query(FlashcardSet).all()
    return [{
        "id": s.id,
        "title": s.title,
        "description": s.description,
        "card_count": len(s.flashcards)
    } for s in sets]

@router.post("/", response_model=FlashcardSetResponse)
async def create_flashcard_set(
    flashcard_set: FlashcardSetCreate,
    db: Session = Depends(get_db)
):
    db_set = FlashcardSet(
        title=flashcard_set.title,
        description=flashcard_set.description
    )
    db.add(db_set)
    db.commit()
    db.refresh(db_set)
    return {
        "id": db_set.id,
        "title": db_set.title,
        "description": db_set.description,
        "card_count": 0
    } 