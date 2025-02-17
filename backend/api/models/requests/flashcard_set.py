from pydantic import BaseModel, Field
from typing import List, Optional

class FlashcardCreate(BaseModel):
    front: str = Field(..., description="Front text of the flashcard")
    back: str = Field(..., description="Back text of the flashcard")

class FlashcardSetCreate(BaseModel):
    title: str = Field(..., description="Title of the flashcard set")
    description: Optional[str] = Field(default=None, description="Optional description of the set")
    flashcards: Optional[List[FlashcardCreate]] = Field(default=None, description="Optional list of initial flashcards")

class FlashcardSetUpdate(BaseModel):
    title: Optional[str] = Field(default=None, description="New title for the set")
    description: Optional[str] = Field(default=None, description="New description for the set") 