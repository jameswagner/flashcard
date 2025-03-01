from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, UTC
import logging

from models.set import FlashcardSet
from models.flashcard import Flashcard, flashcard_set_association
from models.enums import CardStatus
from utils.s3 import get_s3_body

from api.models.requests.flashcard_set import FlashcardSetCreate, FlashcardSetUpdate
from api.models.responses.flashcard_set import (
    FlashcardSetResponse,
    FlashcardSetDetailResponse,
    FlashcardResponse,
    CitationResponse,
    FlashcardSetSourceResponse,
    SourceTextWithCitations
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
                    "id": citation.id,
                    "source_file_id": citation.source_file_id,
                    "citation_type": citation.citation_type,
                    "citation_data": citation.citation_data,
                    "preview_text": citation.preview_text
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
                answer_key_terms=card.answer_key_terms,
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

    def _create_flashcard_set_entity(
        self,
        title: str,
        description: str,
        user_id: int = None,
        is_ai_generated: bool = False,
        ai_metadata: dict = None
    ) -> FlashcardSet:
        """Internal helper to create a FlashcardSet entity with common logic."""
        flashcard_set = FlashcardSet(
            title=title,
            description=description,
            user_id=user_id
        )
        
        # Add AI-specific metadata if applicable
        if is_ai_generated and ai_metadata:
            flashcard_set.total_card_count = ai_metadata.get('total_card_count', 0)
            flashcard_set.ai_card_count = ai_metadata.get('ai_card_count', 0)
            flashcard_set.initial_generation_model = ai_metadata.get('model', '').lower()
            flashcard_set.prompt_template_id = ai_metadata.get('prompt_template_id')
            flashcard_set.prompt_parameters = ai_metadata.get('prompt_parameters', {})
            flashcard_set.model_parameters = ai_metadata.get('model_parameters', {})
            
            # Add source file if provided
            source_file = ai_metadata.get('source_file')
            if source_file:
                flashcard_set.source_files.append(source_file)
        
        self.db.add(flashcard_set)
        self.db.flush()
        return flashcard_set

    def create_set(self, set_data: FlashcardSetCreate) -> FlashcardSetResponse:
        """Create a new flashcard set with optional initial cards."""
        try:
            # Use the common helper
            db_set = self._create_flashcard_set_entity(
                title=set_data.title,
                description=set_data.description
            )

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

    def get_set_source_text(self, set_id: int) -> FlashcardSetSourceResponse:
        """Get source text with citation highlights for a flashcard set."""
        logger = logging.getLogger(__name__)
        logger.info(f"Fetching source text for set {set_id}")
        
        db_set = self.db.query(FlashcardSet).filter(FlashcardSet.id == set_id).first()
        if not db_set:
            logger.error(f"Set {set_id} not found")
            raise HTTPException(status_code=404, detail="Flashcard set not found")

        logger.info(f"Found set {set_id} with {len(db_set.source_files)} source files")
        sources = []
        for source_file in db_set.source_files:
            logger.info(f"Processing source file {source_file.id} ({source_file.filename})")
            logger.info(f"S3 key: {source_file.processed_text_s3_key}")
            
            if not source_file.processed_text_s3_key:
                logger.warning(f"Source file {source_file.id} has no processed text key")
                continue  # Skip sources without processed text

            # Get processed text from S3
            text_content = get_s3_body(source_file.processed_text_s3_key)
            if not text_content:
                logger.warning(f"Could not retrieve text content for source {source_file.id} from S3")
                continue  # Skip if text content couldn't be retrieved

            logger.info(f"Retrieved {len(text_content)} chars of text content for source {source_file.id}")

            # Get all citations for this source file from the set's flashcards
            citations_data = []
            logger.info(f"\n=== Processing flashcards for source {source_file.id} ===")
            for card in db_set.flashcards:
                # Get the card_index from the association table
                assoc = self.db.query(flashcard_set_association).filter_by(
                    flashcard_id=card.id,
                    set_id=set_id,
                    status=CardStatus.ACTIVE.value
                ).first()
                

                
                if not assoc:
                    logger.error(f"No association found for card {card.id} in set {set_id}")
                    continue
                    
                for citation in card.citations:
                    if citation.source_file_id == source_file.id:
                        citation_data = {
                            "citation_id": citation.id,
                            "citation_type": citation.citation_type,
                            "citation_data": citation.citation_data,
                            "preview_text": citation.preview_text,
                            "card_id": card.id,
                            "card_front": card.front,
                            "card_back": card.back,
                            "card_index": assoc.card_index
                        }
                        citations_data.append(citation_data)

            sources.append(SourceTextWithCitations(
                source_file_id=source_file.id,
                filename=source_file.filename,
                text_content=text_content,
                citations=citations_data,
                file_type=source_file.file_type,
                processed_text_type=source_file.processed_text_type
            ))
            logger.info(f"Added source {source_file.id} to response")

        if not sources:
            logger.error("No valid sources found with processed text")
            raise HTTPException(
                status_code=404, 
                detail="No processed source text available for this flashcard set"
            )

        logger.info(f"Returning response with {len(sources)} sources")
        return FlashcardSetSourceResponse(
            set_id=db_set.id,
            title=db_set.title,
            sources=sources
        )

    async def create_ai_flashcard_set(
        self,
        generated_cards: list,
        source_file,
        model,
        db_template,
        generation_request
    ):
        """Create flashcard set with AI-generated cards."""
        ai_info = f"\n\nGenerated using {model.value} AI model"
        
        # Prepare AI metadata
        ai_metadata = {
            'total_card_count': len(generated_cards),
            'ai_card_count': len(generated_cards),
            'model': model.value,
            'prompt_template_id': db_template.id,
            'prompt_parameters': {"num_cards": len(generated_cards)},
            'model_parameters': generation_request.model_params,
            'source_file': source_file
        }
        
        # Use the common helper
        flashcard_set = self._create_flashcard_set_entity(
            title=generation_request.title or f"Generated from {source_file.filename}",
            description=(generation_request.description + ai_info if generation_request.description 
                      else f"AI-generated flashcards using {model.value}"),
            user_id=generation_request.user_id,
            is_ai_generated=True,
            ai_metadata=ai_metadata
        )
        
        return flashcard_set

    def create_flashcard_set_association(self, flashcard_id, set_id, card_index):
        """Create association between flashcard and set with explicit card index."""
        stmt = flashcard_set_association.insert().values(
            flashcard_id=flashcard_id,
            set_id=set_id,
            card_index=card_index,
            created_at=datetime.now(UTC)
        )
        self.db.execute(stmt) 