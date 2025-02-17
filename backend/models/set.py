from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Enum, Boolean
from sqlalchemy.orm import relationship

from .base import Base
from .enums import AIModel
from .source import source_file_set_association
from .flashcard import flashcard_set_association

class FlashcardSet(Base):
    __tablename__ = "flashcard_sets"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(String(255), nullable=True)  # NULL means public set
    
    # Statistics and metadata about AI generation
    ai_card_count = Column(Integer, default=0)
    total_card_count = Column(Integer, default=0)
    initial_generation_model = Column(String, Enum(AIModel, name='aimodel', create_type=False, native_enum=False), nullable=True)
    
    # AI Generation Configuration
    prompt_template_id = Column(Integer, ForeignKey('prompt_templates.id'), nullable=True)
    prompt_parameters = Column(JSON, nullable=True)  # Parameters for template substitution (except source_text)
    model_parameters = Column(JSON, nullable=True)  # Model-specific parameters (temperature, etc.)
    
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    # Relationships
    flashcards = relationship(
        "Flashcard",
        secondary=flashcard_set_association,
        back_populates="flashcard_sets"
    )
    source_files = relationship(
        "SourceFile",
        secondary=source_file_set_association,
        back_populates="flashcard_sets"
    )
    prompt_template = relationship("PromptTemplate", back_populates="flashcard_sets")
    study_sessions = relationship("StudySession", back_populates="flashcard_set") 