from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Enum, Table
from sqlalchemy.orm import relationship

from .base import Base
from .enums import FileType, CitationType

# Junction table for source-file to flashcard-set relationship
source_file_set_association = Table(
    'source_file_set_association',
    Base.metadata,
    Column('source_file_id', Integer, ForeignKey('source_files.id'), primary_key=True),
    Column('set_id', Integer, ForeignKey('flashcard_sets.id'), primary_key=True),
    Column('created_at', DateTime, default=lambda: datetime.now(UTC))
)

class ProcessedTextType:
    SENTENCES = "sentences"
    LINE_NUMBERS = "line_numbers"
    HTML_STRUCTURE = "html_structure"

class SourceFile(Base):
    __tablename__ = "source_files"
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    s3_key = Column(String(512), nullable=False, unique=True)
    url = Column(String(2048), nullable=True)  # Store URL for HTML sources
    file_type = Column(String, Enum(FileType, name='filetype', create_type=False, native_enum=False), nullable=False)
    processed_text = Column(Text, nullable=True)  # Stores text with sentence/line markers
    processed_text_type = Column(String(50), nullable=True)  # 'sentences', 'line_numbers', or 'html_structure'
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    # Relationships
    flashcard_sets = relationship(
        "FlashcardSet",
        secondary=source_file_set_association,
        back_populates="source_files"
    )

class Citation(Base):
    __tablename__ = "citations"
    
    id = Column(Integer, primary_key=True)
    flashcard_id = Column(Integer, ForeignKey('flashcards.id'), nullable=False)
    source_file_id = Column(Integer, ForeignKey('source_files.id'), nullable=False)
    citation_type = Column(String, Enum(CitationType, name='citationtype', create_type=False, native_enum=False), nullable=False)
    citation_data = Column(JSON, nullable=False)  # Format depends on citation_type
    preview_text = Column(Text, nullable=True)  # Optional preview/excerpt of the cited text
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # Relationships
    flashcard = relationship("Flashcard", back_populates="citations")
    source_file = relationship("SourceFile") 