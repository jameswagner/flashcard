from pydantic import BaseModel, Field
from typing import Optional
from models.enums import EditContext, FeedbackType, FeedbackCategory

class FlashcardCreate(BaseModel):
    front: str = Field(..., description="Front text of the flashcard")
    back: str = Field(..., description="Back text of the flashcard")

class FlashcardUpdate(BaseModel):
    front: Optional[str] = Field(default=None, description="New front text of the flashcard")
    back: Optional[str] = Field(default=None, description="New back text of the flashcard")
    card_index: Optional[int] = Field(default=None, description="New position of the card in the set")

class CardFeedbackCreate(BaseModel):
    feedback_type: FeedbackType = Field(..., description="Type of feedback (thumbs up/down)")
    feedback_category: Optional[FeedbackCategory] = Field(default=None, description="Category of feedback if applicable")
    feedback_text: Optional[str] = Field(default=None, description="Additional feedback text") 