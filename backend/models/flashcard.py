from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Enum, Boolean, UniqueConstraint, Index, Table, text
from sqlalchemy.orm import relationship
import sqlalchemy as sa
import traceback

from .base import Base
from .enums import AIModel, CardStatus, EditType, EditContext

# Junction table for flashcard-set relationship
flashcard_set_association = Table(
    'flashcard_set_association',
    Base.metadata,
    Column('flashcard_id', Integer, ForeignKey('flashcards.id'), primary_key=True),
    Column('set_id', Integer, ForeignKey('flashcard_sets.id'), primary_key=True),
    Column('card_index', Integer, nullable=True),
    Column('status', String, Enum(CardStatus, name='cardstatus', create_type=False, native_enum=False), nullable=False, default=CardStatus.ACTIVE.value),
    Column('created_at', DateTime, default=lambda: datetime.now(UTC)),
    Index('uq_active_card_index_per_set', 'set_id', 'card_index', unique=True, postgresql_where=text("status = 'active' AND card_index IS NOT NULL")),
    Index('ix_flashcard_set_association_set_id', 'set_id')
)

def _get_next_card_index(context):
    """Get the next available card_index for a set."""
    # Get connection from context
    connection = context.get_current_parameters()
    set_id = connection.get('set_id')
    if not set_id:
        return 1
        
    # Find the highest existing card_index for this set using proper SQLAlchemy text()
    stmt = sa.text(
        "SELECT COALESCE(MAX(card_index), 0) + 1 FROM flashcard_set_association WHERE set_id = :set_id AND status = 'active'"
    ).bindparams(set_id=set_id)
    result = context.connection.execute(stmt).scalar()
    return result or 1

class CardEditHistory(Base):
    __tablename__ = "card_edit_history"
    
    id = Column(Integer, primary_key=True)
    flashcard_id = Column(Integer, ForeignKey('flashcards.id'), nullable=False)
    user_id = Column(String(255), nullable=False)
    previous_front = Column(Text, nullable=False)
    previous_back = Column(Text, nullable=False)
    edit_type = Column(String(50), nullable=False)  # 'manual' or 'ai_assisted'
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # Relationships
    flashcard = relationship("Flashcard", back_populates="edit_history")

class CardVersion(Base):
    __tablename__ = "card_versions"
    
    id = Column(Integer, primary_key=True)
    flashcard_id = Column(Integer, ForeignKey('flashcards.id'), nullable=False)
    version_number = Column(Integer, nullable=False)  # Increments with each edit
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    status = Column(String, Enum(CardStatus, name='cardstatus', create_type=False, native_enum=False), nullable=False, default=CardStatus.ACTIVE.value)
    edit_type = Column(String, Enum(EditType, name='edittype', create_type=False, native_enum=False), nullable=False)
    edit_context = Column(String, Enum(EditContext, name='editcontext', create_type=False, native_enum=False), nullable=True)
    user_id = Column(String(255), nullable=True)  # NULL for AI-generated versions
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    edit_summary = Column(Text, nullable=True)  # Optional description of changes
    
    # Relationships
    flashcard = relationship("Flashcard", back_populates="versions")
    
    __table_args__ = (
        # Ensure unique version numbers per card
        UniqueConstraint('flashcard_id', 'version_number', name='uq_card_version'),
        # Index for efficient version lookup
        Index('ix_card_versions_flashcard_version', 'flashcard_id', 'version_number'),
    )

class Flashcard(Base):
    __tablename__ = "flashcards"
    
    id = Column(Integer, primary_key=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    is_ai_generated = Column(Boolean, default=False)
    status = Column(String, Enum(CardStatus, name='cardstatus', create_type=False, native_enum=False), nullable=False, default=CardStatus.ACTIVE.value)
    
    # AI generation metadata
    generation_model = Column(String, Enum(AIModel, name='aimodel', create_type=False, native_enum=False), nullable=True)
    prompt_template_id = Column(Integer, ForeignKey('prompt_templates.id'), nullable=True)
    prompt_parameters = Column(JSON, nullable=True)  # Parameters for template substitution (except source_text)
    model_parameters = Column(JSON, nullable=True)  # Model-specific parameters (temperature, etc.)
    
    # Learning metadata
    key_terms = Column(sa.ARRAY(String), nullable=True)  # List of key terms from the answer
    key_concepts = Column(sa.ARRAY(String), nullable=True)  # List of underlying concepts/principles
    abbreviations = Column(sa.ARRAY(String, dimensions=2), nullable=True)  # List of [full_term, abbreviation] pairs
    
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    # Version tracking
    current_version = Column(Integer, nullable=False, default=1)  # Points to latest version number
    
    # Relationships
    flashcard_sets = relationship(
        "FlashcardSet",
        secondary=flashcard_set_association,
        back_populates="flashcards"
    )
    citations = relationship("Citation", back_populates="flashcard")
    prompt_template = relationship("PromptTemplate", back_populates="flashcards")
    feedback = relationship("CardFeedback", back_populates="flashcard")
    versions = relationship("CardVersion", back_populates="flashcard", order_by="CardVersion.version_number")
    edit_history = relationship("CardEditHistory", back_populates="flashcard")

    @property
    def current_content(self):
        """Get the current version of the card content."""
        return next(
            (v for v in self.versions if v.version_number == self.current_version),
            None
        )
    
    def create_deleted_version(self, user_id: str, summary: str = None, db = None):
        """Soft delete the card by creating a new version with deleted status."""
        print(f"\n=== Creating deleted version for card {self.id} ===")
        print(f"Current version: {self.current_version}")
        print(f"Current status: {self.status}")
        
        current = self.current_content
        print(f"Current content found: {current is not None}")
        
        if current:
            print(f"Current version details: number={current.version_number}, status={current.status}")
        
        # Create version if either:
        # 1. This is the first version (no current content) OR
        # 2. Card exists and isn't already deleted
        if (not current) or (current and self.status != CardStatus.DELETED.value):
            print("Creating new version...")
            version = CardVersion(
                flashcard_id=self.id,
                version_number=self.current_version + 1,
                front=current.front if current else self.front,
                back=current.back if current else self.back,
                status=CardStatus.DELETED.value,
                edit_type=EditType.DELETION.value,
                user_id=user_id,
                edit_summary=summary
            )
            if db:
                print("Adding version to database session")
                db.add(version)
                db.flush()  # Force the insert to get the ID
                print(f"Version created with ID: {version.id}")
            else:
                print("WARNING: No database session provided!")
                
            print("Appending version to card's versions list")
            self.versions.append(version)
            print("Updating card's current version")
            self.current_version += 1
            print("Updating card's status")
            self.status = CardStatus.DELETED.value
            return version
        else:
            print(f"Skipping version creation: current={current is not None}, status={self.status}")
            return None
    
    def undelete(self, user_id: str, summary: str = None, db = None):
        """Restore the card by creating a new version with active status."""
        current = self.current_content
        if current and self.status == CardStatus.DELETED.value:
            version = CardVersion(
                flashcard_id=self.id,
                version_number=self.current_version + 1,
                front=current.front,
                back=current.back,
                status=CardStatus.ACTIVE.value,
                edit_type=EditType.UNDELETION.value,
                user_id=user_id,
                edit_summary=summary
            )
            if db:
                db.add(version)
            self.versions.append(version)
            self.current_version += 1
            self.status = CardStatus.ACTIVE.value
            return version
    
    def soft_delete_from_set(self, set_id: int, user_id: str | None = None, db = None) -> bool:
        """Soft delete a card from a set, handling all necessary updates.
        
        Args:
            set_id: The ID of the set to remove the card from
            user_id: Optional user ID performing the deletion
            db: SQLAlchemy session (required)
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            print(f"\n=== Soft deleting card {self.id} from set {set_id} ===")
            
            # Check current versions
            print(f"Current versions count: {len(self.versions)}")
            for v in self.versions:
                print(f"Version {v.version_number}: status={v.status}, type={v.edit_type}")
            
            # Update the association using an UPDATE statement
            result = db.query(flashcard_set_association).filter_by(
                flashcard_id=self.id,
                set_id=set_id
            ).update({
                "status": CardStatus.DELETED.value,
                "card_index": None
            }, synchronize_session=False)
            print(f"Updated {result} association records")
            
            # Get all active cards for reindexing, using ORM
            active_cards = db.query(flashcard_set_association).filter(
                flashcard_set_association.c.set_id == set_id,
                flashcard_set_association.c.status == CardStatus.ACTIVE.value,
                flashcard_set_association.c.card_index != None
            ).order_by(
                flashcard_set_association.c.card_index
            ).all()
            
            # Reindex remaining cards using ORM
            for idx, card_assoc in enumerate(active_cards, 1):
                db.query(flashcard_set_association).filter_by(
                    flashcard_id=card_assoc.flashcard_id,
                    set_id=set_id
                ).update(
                    {"card_index": idx},
                    synchronize_session=False
                )
            
            print(f"Reindexed {len(active_cards)} cards")
            
            # Create a soft delete version of the card
            print("\nCreating soft delete version...")
            version = self.create_deleted_version(user_id or "anonymous", "Card removed from set", db)
            if version:
                print(f"Created delete version {version.version_number} for card {self.id}")
                # Verify version was added
                db.flush()
                versions_count = db.query(CardVersion).filter_by(flashcard_id=self.id).count()
                print(f"Total versions in database for card {self.id}: {versions_count}")
            else:
                print("WARNING: No version was created!")
            
            return True
            
        except Exception as e:
            print(f"Error in soft_delete_from_set: {str(e)}")
            print(f"Full traceback: {traceback.format_exc()}")
            raise 