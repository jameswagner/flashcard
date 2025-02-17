from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from database import get_db

from api.models.requests.study_session import StudySessionCreate, CardReviewCreate, ReviewScoreCreate
from api.models.responses.study_session import (
    StudySessionResponse,
    CardReviewResponse,
    ReviewScoreResponse,
    SessionCompletionResponse
)
from services.study_session import StudySessionService

router = APIRouter()

@router.post("/", response_model=StudySessionResponse)
async def create_study_session(
    session_data: StudySessionCreate,
    user_id: str = None,
    db: Session = Depends(get_db)
):
    """Create a new study session."""
    service = StudySessionService(db)
    return service.create_session(session_data, user_id)

@router.get("/{session_id}", response_model=StudySessionResponse)
async def get_study_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """Get details of a study session."""
    service = StudySessionService(db)
    return service.get_session(session_id)

@router.post("/{session_id}/reviews", response_model=CardReviewResponse)
async def create_card_review(
    session_id: int,
    review_data: CardReviewCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new card review in a study session."""
    service = StudySessionService(db)
    return service.create_review(session_id, review_data, background_tasks)

@router.get("/reviews/{review_id}/scores", response_model=List[ReviewScoreResponse])
async def get_review_scores(
    review_id: int,
    db: Session = Depends(get_db)
):
    """Get all scores for a review, including NLI scores if available."""
    service = StudySessionService(db)
    return service.get_review_scores(review_id)

@router.post("/reviews/{review_id}/scores", response_model=ReviewScoreResponse)
async def create_review_score(
    review_id: int,
    score_data: ReviewScoreCreate,
    db: Session = Depends(get_db)
):
    """Create a new score for a review."""
    service = StudySessionService(db)
    return service.create_review_score(review_id, score_data)

@router.patch("/{session_id}/complete", response_model=SessionCompletionResponse)
async def complete_study_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """Mark a study session as completed and calculate final statistics."""
    service = StudySessionService(db)
    return service.complete_session(session_id) 