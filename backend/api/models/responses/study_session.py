from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List
from datetime import datetime
from models.enums import StudySessionType, AnswerMethod, ReviewGrade, ReviewConfidence

class ReviewScoreResponse(BaseModel):
    id: int = Field(..., description="Score ID")
    review_id: int = Field(..., description="ID of the associated review")
    score_type: str = Field(..., description="Type of score")
    score: float = Field(..., description="Score value between 0 and 1")
    grade: Optional[ReviewGrade] = Field(default=None, description="Self-assessed grade if applicable")
    confidence: Optional[ReviewConfidence] = Field(default=None, description="Self-assessed confidence if applicable")
    score_metadata: Dict = Field(default_factory=dict, description="Additional score metadata")
    created_at: datetime = Field(..., description="When the score was created")

    model_config = ConfigDict(from_attributes=True)

class CardReviewResponse(BaseModel):
    id: int = Field(..., description="Review ID")
    session_id: int = Field(..., description="ID of the associated study session")
    flashcard_id: int = Field(..., description="ID of the flashcard reviewed")
    answer_method: str = Field(..., description="Method used to submit the answer")
    user_answer: Optional[str] = Field(default=None, description="User's submitted answer")
    time_to_answer: Optional[int] = Field(default=None, description="Time taken to answer in seconds")
    reviewed_at: datetime = Field(..., description="When the review was created")
    scores: List[ReviewScoreResponse] = Field(default_factory=list, description="Associated scores")

    model_config = ConfigDict(from_attributes=True)

class StudySessionResponse(BaseModel):
    id: int = Field(..., description="Session ID")
    set_id: int = Field(..., description="ID of the flashcard set being studied")
    session_type: StudySessionType = Field(..., description="Type of study session")
    settings: Dict = Field(default_factory=dict, description="Session settings")
    cards_reviewed: int = Field(default=0, description="Number of cards reviewed")
    correct_count: int = Field(default=0, description="Number of correct answers")
    incorrect_count: int = Field(default=0, description="Number of incorrect answers")
    average_nli_score: Optional[float] = Field(default=None, description="Average NLI score")
    average_self_assessed_score: Optional[float] = Field(default=None, description="Average self-assessed score")
    average_confidence: Optional[float] = Field(default=None, description="Average confidence score")
    created_at: datetime = Field(..., description="When the session was created")
    completed_at: Optional[datetime] = Field(default=None, description="When the session was completed")
    reviews: List[CardReviewResponse] = Field(default_factory=list, description="Associated reviews")

    model_config = ConfigDict(from_attributes=True)

class SessionCompletionResponse(BaseModel):
    status: str = Field(..., description="Status of the completion request")
    message: str = Field(..., description="Completion message")
    statistics: Dict = Field(..., description="Session statistics")

    model_config = ConfigDict(from_attributes=True) 