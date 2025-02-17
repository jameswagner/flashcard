from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Enum, Float, Table
from sqlalchemy.orm import relationship

from .base import Base
from .enums import StudySessionType, ReviewGrade, ReviewConfidence, AnswerMethod, ScoreType

class StudySession(Base):
    __tablename__ = "study_sessions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False)
    set_id = Column(Integer, ForeignKey('flashcard_sets.id'), nullable=False)
    session_type = Column(String, Enum(StudySessionType, name='studysessiontype', create_type=False, native_enum=False), nullable=False)
    
    # Session metadata
    started_at = Column(DateTime, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)
    cards_reviewed = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    average_confidence = Column(Float, nullable=True)
    
    # Session settings/parameters
    settings = Column(JSON, nullable=True)  # For storing session-specific settings (e.g., review order, timer settings)
    
    # Relationships
    flashcard_set = relationship("FlashcardSet", back_populates="study_sessions")
    reviews = relationship("CardReview", back_populates="session", order_by="CardReview.reviewed_at")

class CardReview(Base):
    __tablename__ = "card_reviews"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('study_sessions.id'), nullable=False)
    flashcard_id = Column(Integer, ForeignKey('flashcards.id'), nullable=False)
    
    # Review data
    answer_method = Column(String, Enum(AnswerMethod, name='answermethod', create_type=False, native_enum=False), nullable=False)
    user_answer = Column(Text, nullable=True)
    time_to_answer = Column(Float, nullable=True)  # Time in seconds
    
    # Metadata
    reviewed_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # Relationships
    session = relationship("StudySession", back_populates="reviews")
    flashcard = relationship("Flashcard")
    scores = relationship("ReviewScore", back_populates="review", order_by="ReviewScore.created_at")

class ReviewScore(Base):
    """Score for a card review."""
    __tablename__ = "review_scores"
    
    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey("card_reviews.id"), nullable=False)
    score_type = Column(String, Enum(ScoreType, name='scoretype', create_type=False, native_enum=False), nullable=False)
    score = Column(Float, nullable=False)
    grade = Column(String, Enum(ReviewGrade, name='reviewgrade', create_type=False, native_enum=False))  # Optional grade (for self-assessment)
    confidence = Column(String, Enum(ReviewConfidence, name='reviewconfidence', create_type=False, native_enum=False))  # Optional confidence level
    score_metadata = Column(JSON)  # Additional scoring metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Reference to the scoring configuration used
    scoring_config_id = Column(Integer, ForeignKey("scoring_configs.id"), nullable=True)
    scoring_config = relationship("DBScoringConfig", back_populates="scores")
    
    # Relationships
    review = relationship("CardReview", back_populates="scores") 