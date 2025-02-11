from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Table
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, UTC

Base = declarative_base()

# Junction table for many-to-many relationship
flashcard_set_association = Table(
    'flashcard_set_association',
    Base.metadata,
    Column('flashcard_id', Integer, ForeignKey('flashcards.id'), primary_key=True),
    Column('set_id', Integer, ForeignKey('flashcard_sets.id'), primary_key=True),
    Column('created_at', DateTime, default=lambda: datetime.now(UTC))
)

class FlashcardSet(Base):
    __tablename__ = "flashcard_sets"
    __table_args__ = {'schema': 'flashcards'}
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    # Relationships
    flashcards = relationship(
        "Flashcard",
        secondary=flashcard_set_association,
        back_populates="flashcard_sets"
    )

class Flashcard(Base):
    __tablename__ = "flashcards"
    
    id = Column(Integer, primary_key=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    # Relationships
    flashcard_sets = relationship(
        "FlashcardSet",
        secondary=flashcard_set_association,
        back_populates="flashcards"
    ) 