from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from models.enums import EditContext, FeedbackType, FeedbackCategory

class AnswerKeyTerm(BaseModel):
    terms: List[str] = Field(..., description="List of acceptable forms of the term")
    weight: float = Field(..., description="1.0 = required, 0.5-0.9 = important, <0.5 = helpful")
    exact_match: bool = Field(..., description="True if one of the exact forms must be used")
    explanation: str = Field(..., description="Why this term is important and what forms are acceptable")

class FlashcardCreate(BaseModel):
    front: str = Field(..., description="Front text of the flashcard")
    back: str = Field(..., description="Back text of the flashcard")
    answer_key_terms: Optional[List[AnswerKeyTerm]] = Field(default=None, description="List of key terms with their weights and matching rules")
    key_concepts: Optional[List[str]] = Field(default=None, description="List of underlying concepts/principles")
    abbreviations: Optional[List[List[str]]] = Field(default=None, description="List of [full_term, abbreviation] pairs")

class FlashcardUpdate(BaseModel):
    front: Optional[str] = Field(default=None, description="New front text of the flashcard")
    back: Optional[str] = Field(default=None, description="New back text of the flashcard")
    card_index: Optional[int] = Field(default=None, description="New position of the card in the set")
    answer_key_terms: Optional[List[AnswerKeyTerm]] = Field(default=None, description="List of key terms with their weights and matching rules")
    key_concepts: Optional[List[str]] = Field(default=None, description="List of underlying concepts/principles")
    abbreviations: Optional[List[List[str]]] = Field(default=None, description="List of [full_term, abbreviation] pairs")

class CardFeedbackCreate(BaseModel):
    feedback_type: FeedbackType = Field(..., description="Type of feedback (thumbs up/down)")
    feedback_category: Optional[FeedbackCategory] = Field(default=None, description="Category of feedback if applicable")
    feedback_text: Optional[str] = Field(default=None, description="Additional feedback text") 