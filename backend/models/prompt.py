from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from .base import Base
from .enums import AIModel

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(Text)
    template = Column(Text, nullable=False)  # The actual prompt template
    model_id = Column(String, Enum(AIModel, name='aimodel', create_type=False, native_enum=False), nullable=True)  # NULL means generic/all models
    parameter_schema = Column(JSON, nullable=False)  # JSON Schema for prompt parameters (e.g., num_cards, focus_area)
    model_parameter_schema = Column(JSON, nullable=False)  # JSON Schema for model parameters (e.g., temperature, top_p)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    created_by = Column(String(255), nullable=True)  # User who created this template
    is_active = Column(Boolean, default=True)  # Soft delete/deprecation flag
    
    # Ensure unique combination of name and version
    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_prompt_template_name_version'),
        # Index for quick lookup of latest version
        Index('ix_prompt_templates_name_version', 'name', 'version'),
    )
    
    # Relationships
    flashcard_sets = relationship("FlashcardSet", back_populates="prompt_template")
    flashcards = relationship("Flashcard", back_populates="prompt_template") 