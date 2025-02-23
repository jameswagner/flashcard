from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from api.models.responses.flashcard import FlashcardResponse

class Citation(BaseModel):
    id: int = Field(..., description="Citation ID")
    source_file_id: int = Field(..., description="Source file ID")
    citation_type: str = Field(..., description="Type of citation (e.g., sentence_range, html_paragraph)")
    citation_data: List[List[int]] = Field(..., description="Citation data as list of [start, end] integer pairs")
    preview_text: Optional[str] = Field(None, description="Preview text of the cited content")

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

class SourceTextWithCitations(BaseModel):
    """Response model for source text with citation highlights."""
    source_file_id: int
    filename: str
    text_content: str
    citations: List[Dict[str, Any]] = Field(
        ...,
        description="List of citation data with card references. Each citation includes citation_id, citation_type, citation_data, preview_text, card_id, card_front, card_back, and card_index."
    )
    file_type: str
    processed_text_type: Optional[str] = None

class FlashcardSetSourceResponse(BaseModel):
    """Response model for a flashcard set's source text with citations."""
    set_id: int
    title: str
    sources: List[SourceTextWithCitations] 