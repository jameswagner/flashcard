from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime
from api.models.responses.flashcard import FlashcardResponse

class CitationResponse(BaseModel):
    preview_text: str = Field(..., description="Preview text of the citation")
    citation_data: List[Dict[str, int]] = Field(..., description="Citation data containing location information")

    model_config = ConfigDict(from_attributes=True)

class FlashcardSetResponse(BaseModel):
    id: int = Field(..., description="Set ID")
    title: str = Field(..., description="Title of the set")
    description: Optional[str] = Field(default=None, description="Description of the set")
    card_count: int = Field(..., description="Total number of cards in the set")

    model_config = ConfigDict(from_attributes=True)

class FlashcardSetDetailResponse(FlashcardSetResponse):
    flashcards: List[FlashcardResponse] = Field(default_factory=list, description="List of flashcards in the set")

    model_config = ConfigDict(from_attributes=True) 