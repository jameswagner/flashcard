from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, UTC

from models.set import FlashcardSet
from models.flashcard import Flashcard, flashcard_set_association
from models.enums import CardStatus

from api.models.requests.flashcard_set import FlashcardSetCreate, FlashcardSetUpdate
from api.models.responses.flashcard_set import (
    FlashcardSetResponse,
    FlashcardSetDetailResponse,
    FlashcardResponse,
    CitationResponse
)

class FlashcardSetService:
    def __init__(self, db: Session):
        self.db = db

    def get_sets(self) -> List[FlashcardSetResponse]:
        """Get all flashcard sets."""
        sets = self.db.query(FlashcardSet).all()
        return [
            FlashcardSetResponse(
                id=s.id,
                title=s.title,
                description=s.description,
                card_count=s.total_card_count or 0
            )
            for s in sets
        ]

    def get_set(self, set_id: int) -> FlashcardSetDetailResponse:
        """Get a specific flashcard set with all its cards."""
        db_set = self.db.query(FlashcardSet).filter(FlashcardSet.id == set_id).first()
        if not db_set:
            raise HTTPException(status_code=404, detail="Flashcard set not found")

        # Format flashcards with their associations
        formatted_flashcards = []
        for card in db_set.flashcards:
            # Get the card_index from the association table
            assoc = self.db.query(flashcard_set_association).filter_by(
                flashcard_id=card.id,
                set_id=set_id,
                status=CardStatus.ACTIVE.value
            ).first()

            if not assoc or assoc.card_index is None:
                continue

            formatted_citations = [
                {
                    "preview_text": citation.preview_text,
                    "citation_data": citation.citation_data.get('range') if isinstance(citation.citation_data, dict) else citation.citation_data
                }
                for citation in card.citations
            ]

            formatted_flashcards.append(FlashcardResponse(
                id=card.id,
                front=card.front,
                back=card.back,
                is_ai_generated=card.is_ai_generated,
                citations=formatted_citations,
                card_index=assoc.card_index,
                key_terms=card.key_terms,
                key_concepts=card.key_concepts,
                abbreviations=card.abbreviations,
                created_at=card.created_at,
                updated_at=card.updated_at
            ))

        # Sort flashcards by card_index
        formatted_flashcards.sort(key=lambda x: x.card_index)

        response = FlashcardSetDetailResponse(
            id=db_set.id,
            title=db_set.title,
            description=db_set.description,
            card_count=db_set.total_card_count or 0,
            flashcards=formatted_flashcards
        )
        
        return response.model_dump()

    def create_set(self, set_data: FlashcardSetCreate) -> FlashcardSetResponse:
        """Create a new flashcard set with optional initial cards."""
        try:
            db_set = FlashcardSet(
                title=set_data.title,
                description=set_data.description
            )
            self.db.add(db_set)
            self.db.flush()

            if set_data.flashcards:
                for idx, card_data in enumerate(set_data.flashcards, 1):
                    card = Flashcard(
                        front=card_data.front,
                        back=card_data.back,
                        is_ai_generated=False
                    )
                    self.db.add(card)
                    self.db.flush()

                    # Create association with card_index
                    self.db.execute(
                        flashcard_set_association.insert().values(
                            flashcard_id=card.id,
                            set_id=db_set.id,
                            card_index=idx,
                            status=CardStatus.ACTIVE.value,
                            created_at=datetime.now(UTC)
                        )
                    )

            self.db.commit()
            self.db.refresh(db_set)

            return FlashcardSetResponse(
                id=db_set.id,
                title=db_set.title,
                description=db_set.description,
                card_count=len(db_set.flashcards)
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def update_set(self, set_id: int, set_update: FlashcardSetUpdate) -> FlashcardSetResponse:
        """Update a flashcard set's metadata."""
        db_set = self.db.query(FlashcardSet).filter(FlashcardSet.id == set_id).first()
        if not db_set:
            raise HTTPException(status_code=404, detail="Flashcard set not found")

        if set_update.title is not None:
            db_set.title = set_update.title
        if set_update.description is not None:
            db_set.description = set_update.description

        self.db.commit()
        self.db.refresh(db_set)

        return FlashcardSetResponse(
            id=db_set.id,
            title=db_set.title,
            description=db_set.description,
            card_count=len(db_set.flashcards)
        ) 