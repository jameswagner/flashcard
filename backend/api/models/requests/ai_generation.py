from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, Literal, List
from models.enums import AIModel

class SourceFileUploadRequest(BaseModel):
    filename: str
    user_id: Optional[str] = Field(default=None, description="Optional user ID for the upload")

class URLUploadRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL to scrape content from")
    user_id: Optional[str] = Field(default=None, description="Optional user ID for the upload")

class FlashcardGenerationRequest(BaseModel):
    model: str = Field(..., description="AI model to use for generation")
    user_id: Optional[str] = Field(default=None, description="Optional user ID")
    model_params: Optional[Dict[str, Any]] = Field(default=None, description="Optional model parameters")
    title: Optional[str] = Field(default=None, description="Optional title for the flashcard set")
    description: Optional[str] = Field(default=None, description="Optional description for the flashcard set")
    use_sentences: bool = Field(default=True, description="Whether to use sentence-based citations")
    selected_content: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional list of selected content sections. Format: [{'citation_type': 'paragraph'|'sentence_range', 'range': [start, end]}]")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "gpt-4",
                "title": "My Flashcard Set",
                "description": "Generated from YouTube video",
                "selected_content": [
                    {"citation_type": "paragraph", "range": [1, 3]},
                    {"citation_type": "sentence_range", "range": [5, 10]}
                ]
            }
        }

class YouTubeUploadRequest(BaseModel):
    """Request model for uploading YouTube video transcripts."""
    video_id: str
    title: str
    description: Optional[str] = None
    user_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "dQw4w9WgXcQ",
                "title": "Never Gonna Give You Up",
                "description": "00:00 - Intro\n01:23 - Verse 1\n02:45 - Chorus",
                "user_id": "user123"
            }
        } 