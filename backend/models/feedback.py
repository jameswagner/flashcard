from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import relationship

from .base import Base
from .enums import FeedbackType, FeedbackCategory, EditContext

class CardFeedback(Base):
    __tablename__ = "card_feedback"
    
    id = Column(Integer, primary_key=True)
    flashcard_id = Column(Integer, ForeignKey('flashcards.id'), nullable=False)
    user_id = Column(String(255), nullable=False)
    feedback_type = Column(String, Enum(FeedbackType, name='feedbacktype', create_type=False, native_enum=False), nullable=False)
    feedback_category = Column(String, Enum(FeedbackCategory, name='feedbackcategory', create_type=False, native_enum=False), nullable=True)
    feedback_text = Column(Text, nullable=True)
    feedback_context = Column(String, Enum(EditContext, name='editcontext', create_type=False, native_enum=False), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # Relationships
    flashcard = relationship("Flashcard", back_populates="feedback")

    @classmethod
    def create_feedback(cls, 
        flashcard_id: int,
        feedback_type: FeedbackType,
        user_id: str | None = None,
        feedback_category: FeedbackCategory | None = None,
        feedback_text: str | None = None,
        feedback_context: EditContext | None = None,
        db = None
    ) -> "CardFeedback":
        """Create a new feedback record for a card.
        
        Args:
            flashcard_id: ID of the card receiving feedback
            feedback_type: Type of feedback (thumbs up/down)
            user_id: Optional ID of user giving feedback
            feedback_category: Optional category of feedback
            feedback_text: Optional text feedback
            feedback_context: Optional context of the feedback
            db: SQLAlchemy session (required)
            
        Returns:
            CardFeedback: The created feedback record
        """
        feedback = cls(
            flashcard_id=flashcard_id,
            user_id=user_id or "anonymous",
            feedback_type=feedback_type.value,
            feedback_category=feedback_category.value if feedback_category else None,
            feedback_text=feedback_text,
            feedback_context=feedback_context.value if feedback_context else None
        )
        
        db.add(feedback)
        db.flush()
        return feedback 