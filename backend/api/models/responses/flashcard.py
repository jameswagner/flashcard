from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from models.enums import FeedbackType, FeedbackCategory, EditType, EditContext, CardStatus

class FlashcardResponse(BaseModel):
    id: int
    front: str
    back: str
    is_ai_generated: bool
    citations: List[dict]
    card_index: int
    key_terms: Optional[List[str]] = None
    key_concepts: Optional[List[str]] = None
    abbreviations: Optional[List[List[str]]] = None
    
    model_config = ConfigDict(from_attributes=True)

class CardVersionResponse(BaseModel):
    id: int
    version_number: int
    front: str
    back: str
    status: str
    edit_type: str
    edit_context: str | None = None
    user_id: str | None = None
    created_at: datetime
    edit_summary: str | None = None
    
    model_config = ConfigDict(from_attributes=True)

class CardEditHistoryResponse(BaseModel):
    id: int
    previous_front: str
    previous_back: str
    edit_type: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class CardFeedbackResponse(BaseModel):
    id: int
    feedback_type: str
    feedback_category: str | None = None
    feedback_text: str | None = None
    feedback_context: str | None = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True) 