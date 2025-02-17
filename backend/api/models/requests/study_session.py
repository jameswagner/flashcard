from pydantic import BaseModel, Field, validator
from typing import Optional, Dict
from datetime import datetime
from models.enums import StudySessionType, AnswerMethod, ReviewGrade, ReviewConfidence

class StudySessionCreate(BaseModel):
    set_id: int = Field(..., gt=0, description="ID of the flashcard set to study")
    session_type: StudySessionType = Field(..., description="Type of study session")
    settings: Optional[Dict] = Field(default=None, description="Optional session settings")

    @validator('settings')
    def validate_settings(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError('Settings must be a dictionary')
        return v or {}

class CardReviewCreate(BaseModel):
    flashcard_id: int = Field(..., gt=0, description="ID of the flashcard being reviewed")
    answer_method: AnswerMethod = Field(..., description="Method used to submit the answer")
    user_answer: Optional[str] = Field(default=None, description="User's submitted answer")
    time_to_answer: Optional[int] = Field(default=None, ge=0, description="Time taken to answer in seconds")

    @validator('user_answer')
    def validate_user_answer(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

class ReviewScoreCreate(BaseModel):
    score_type: str = Field(..., description="Type of score being recorded")
    score: float = Field(..., ge=0, le=1, description="Score value between 0 and 1")
    grade: Optional[ReviewGrade] = Field(default=None, description="Self-assessed grade")
    confidence: Optional[ReviewConfidence] = Field(default=None, description="Self-assessed confidence")
    score_metadata: Optional[Dict] = Field(default=None, description="Additional score metadata")

    @validator('score_metadata')
    def validate_metadata(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError('Score metadata must be a dictionary')
        return v or {} 