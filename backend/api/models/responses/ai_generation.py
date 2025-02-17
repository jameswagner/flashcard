from pydantic import BaseModel, Field
from typing import Dict

class SourceFileUploadResponse(BaseModel):
    id: int = Field(..., description="ID of the uploaded source file")
    filename: str = Field(..., description="Name of the uploaded file")

class FlashcardGenerationResponse(BaseModel):
    set_id: int = Field(..., description="ID of the generated flashcard set")
    num_cards: int = Field(..., description="Number of cards generated") 