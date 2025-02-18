from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, ARRAY, Enum, Table
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY  # PostgreSQL-specific ARRAY
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
    citations = relationship("Citation", back_populates="source_file")

class Citation(Base):
    """Citation model for linking flashcards to source content.
    
    Each citation represents a reference to a specific part of source content.
    The citation_data field is a 2D array of integers representing ranges.
    Each inner array MUST contain exactly 2 integers: [start, end].
    
    Example:
        [[1, 3]] means sentences/lines 1 through 3
        [[1, 1]] means just sentence/line 1
        [[1, 3], [5, 7]] means sentences/lines 1-3 AND 5-7
    
    The citation_type field indicates how to interpret these numbers:
    - sentence_range: Numbers refer to sentence markers [SENTENCE X]
    - line_numbers: Numbers refer to line numbers
    - html_paragraph: Numbers refer to paragraph IDs
    - html_section: Numbers refer to section IDs
    - html_table: Numbers refer to table IDs
    - html_list: Numbers refer to list IDs
    - video_timestamp: Numbers refer to video timestamps in seconds
    """
    __tablename__ = "citations"
    
    id = Column(Integer, primary_key=True)
    flashcard_id = Column(Integer, ForeignKey('flashcards.id', ondelete='CASCADE'), nullable=False)
    source_file_id = Column(Integer, ForeignKey('source_files.id', ondelete='CASCADE'), nullable=False)
    citation_type = Column(String, Enum(CitationType, name='citationtype', create_type=False, native_enum=False), nullable=False)
    citation_data = Column(PG_ARRAY(Integer, dimensions=2), nullable=False)  # Strictly 2D array of integers [[start, end], ...]
    preview_text = Column(Text, nullable=True)  # Optional preview/excerpt of the cited text
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    # Relationships
    flashcard = relationship("Flashcard", back_populates="citations")
    source_file = relationship("SourceFile", back_populates="citations")

    def __repr__(self):
        return f"<Citation(id={self.id}, type={self.citation_type}, data={self.citation_data})>" 