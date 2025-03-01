from sqlalchemy.orm import Session
from sqlalchemy import func
from models.flashcard import Flashcard, CardVersion, CardEditHistory, flashcard_set_association
from models.feedback import CardFeedback
from models.set import FlashcardSet
from models.enums import CardStatus, FeedbackType, FeedbackCategory, EditType, AIModel
from models.prompt import PromptTemplate
from api.models.requests.flashcard import FlashcardCreate, FlashcardUpdate, CardFeedbackCreate
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
import traceback

class FlashcardService:
    def __init__(self, db: Session):
        self.db = db

    def add_card_to_set(self, set_id: int, card: FlashcardCreate) -> dict:
        """Add a new card to a flashcard set."""
        db_set = self.db.query(FlashcardSet).filter(FlashcardSet.id == set_id).first()
        if not db_set:
            raise HTTPException(status_code=404, detail="Flashcard set not found")

        try:
            # Create new card
            new_card = Flashcard(
                front=card.front,
                back=card.back,
                is_ai_generated=False
            )
            self.db.add(new_card)
            self.db.flush()  # Get the card ID

            # Get next card index
            next_index = self.db.query(
                func.coalesce(
                    func.max(flashcard_set_association.c.card_index) + 1,
                    1
                )
            ).filter(
                flashcard_set_association.c.set_id == set_id,
                flashcard_set_association.c.status == CardStatus.ACTIVE.value
            ).scalar() or 1

            # Create association with card_index
            self.db.execute(
                flashcard_set_association.insert().values(
                    flashcard_id=new_card.id,
                    set_id=set_id,
                    card_index=next_index,
                    status=CardStatus.ACTIVE.value
                )
            )

            # Update set statistics
            db_set.total_card_count = (db_set.total_card_count or 0) + 1

            self.db.commit()
            self.db.refresh(new_card)

            return {
                "id": new_card.id,
                "front": new_card.front,
                "back": new_card.back,
                "is_ai_generated": new_card.is_ai_generated,
                "citations": [],
                "card_index": next_index
            }
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def get_card_edit_history(self, card_id: int) -> List[CardEditHistory]:
        """Get edit history for a card."""
        card = self.db.get(Flashcard, card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        
        return self.db.query(CardEditHistory)\
            .filter(CardEditHistory.flashcard_id == card_id)\
            .order_by(CardEditHistory.created_at.desc())\
            .all()

    def get_card_feedback(self, card_id: int) -> List[CardFeedback]:
        """Get all feedback for a card."""
        card = self.db.get(Flashcard, card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        
        return self.db.query(CardFeedback)\
            .filter(CardFeedback.flashcard_id == card_id)\
            .order_by(CardFeedback.created_at.desc())\
            .all()

    def delete_card(self, card_id: int, user_id: Optional[str] = None) -> dict:
        """Soft delete a card by marking its association as deleted."""
        try:
            # Get the card and verify it exists
            card = self.db.get(Flashcard, card_id)
            if not card:
                raise HTTPException(status_code=404, detail="Card not found")

            # Get all active associations for this card
            associations = self.db.query(flashcard_set_association).filter(
                flashcard_set_association.c.flashcard_id == card_id,
                flashcard_set_association.c.status == CardStatus.ACTIVE.value
            ).all()

            if not associations:
                raise HTTPException(status_code=400, detail="Card is not actively associated with any sets")

            # Process each active association
            for assoc in associations:
                # Get the set for updating statistics
                flashcard_set = self.db.get(FlashcardSet, assoc.set_id)
                if flashcard_set:
                    # Soft delete from set (handles reindexing)
                    success = card.soft_delete_from_set(assoc.set_id, user_id, self.db)
                    if success:
                        # Update set statistics
                        flashcard_set.total_card_count = max(0, (flashcard_set.total_card_count or 1) - 1)
                        if card.is_ai_generated:
                            flashcard_set.ai_card_count = max(0, (flashcard_set.ai_card_count or 1) - 1)

            self.db.commit()
            return {"status": "success", "message": "Card deleted successfully"}

        except Exception as e:
            self.db.rollback()
            print(f"Error in delete_card: {str(e)}")
            print(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete card: {str(e)}"
            )

    def update_card(
        self,
        card_id: int,
        card_update: FlashcardUpdate,
        edit_context: Optional[str] = None,
        edit_summary: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> dict:
        """Update a card, creating a new version if content changes."""
        try:
            # Get the card and verify it exists
            card = self.db.get(Flashcard, card_id)
            if not card:
                raise HTTPException(status_code=404, detail="Card not found")
            
            # Get current version or create initial version if none exists
            current = card.current_content
            if not current:
                # Create initial version from base card data
                initial_version = CardVersion(
                    flashcard_id=card.id,
                    version_number=1,
                    front=card.front,
                    back=card.back,
                    status=CardStatus.ACTIVE.value,
                    edit_type=EditType.MANUAL.value,
                    user_id=user_id
                )
                self.db.add(initial_version)
                card.versions.append(initial_version)
                card.current_version = 1
                current = initial_version
            
            # Check if this is a content update or just index update
            content_changed = (
                (card_update.front is not None and card_update.front != current.front) or
                (card_update.back is not None and card_update.back != current.back)
            )
            
            if content_changed:
                # Create new version
                version = CardVersion(
                    flashcard_id=card.id,
                    version_number=card.current_version + 1,
                    front=card_update.front if card_update.front is not None else current.front,
                    back=card_update.back if card_update.back is not None else current.back,
                    status=current.status,
                    edit_type=EditType.MANUAL.value,
                    edit_context=edit_context,
                    user_id=user_id,
                    edit_summary=edit_summary
                )
                self.db.add(version)
                
                # Create edit history entry
                history = CardEditHistory(
                    flashcard_id=card.id,
                    previous_front=current.front,
                    previous_back=current.back,
                    edit_type=EditType.MANUAL.value,
                    created_at=datetime.now(UTC),
                    user_id=user_id or "anonymous"
                )
                self.db.add(history)
                
                # Update card's version pointer
                card.versions.append(version)
                card.current_version += 1
                
                # Update base card content
                if card_update.front is not None:
                    card.front = card_update.front
                if card_update.back is not None:
                    card.back = card_update.back
            
            # Handle card index update if specified
            if card_update.card_index is not None:
                # Find the set this card belongs to
                assoc = self.db.query(flashcard_set_association).filter(
                    flashcard_set_association.c.flashcard_id == card_id,
                    flashcard_set_association.c.status == CardStatus.ACTIVE.value
                ).first()
                
                if assoc:
                    # Update the card's index
                    self.db.execute(
                        flashcard_set_association.update().where(
                            flashcard_set_association.c.flashcard_id == card_id,
                            flashcard_set_association.c.set_id == assoc.set_id
                        ).values(card_index=card_update.card_index)
                    )
                    
                    # Reindex other cards if needed
                    self.db.execute(
                        flashcard_set_association.update().where(
                            flashcard_set_association.c.set_id == assoc.set_id,
                            flashcard_set_association.c.flashcard_id != card_id,
                            flashcard_set_association.c.card_index >= card_update.card_index
                        ).values(
                            card_index=flashcard_set_association.c.card_index + 1
                        )
                    )
            
            self.db.commit()
            
            # Get updated card index
            current_assoc = self.db.query(flashcard_set_association).filter(
                flashcard_set_association.c.flashcard_id == card_id,
                flashcard_set_association.c.status == CardStatus.ACTIVE.value
            ).first()
            
            return {
                "id": card.id,
                "front": card.front,
                "back": card.back,
                "is_ai_generated": card.is_ai_generated,
                "citations": [
                    {
                        "preview_text": c.preview_text,
                        "citation_data": c.citation_data
                    } for c in card.citations
                ],
                "card_index": current_assoc.card_index if current_assoc else None
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error in update_card: {str(e)}")
            print(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update card: {str(e)}"
            )

    def create_ai_flashcard(
        self, 
        card_data: Dict[str, Any], 
        model: 'AIModel', 
        db_template: 'PromptTemplate', 
        generation_request: Any,
        total_cards: int,
        transaction=None
    ) -> Flashcard:
        """Create a flashcard object from AI-generated card data.
        
        Args:
            card_data: Dictionary containing the generated card data
            model: The AI model used for generation
            db_template: The prompt template used for generation
            generation_request: The original generation request
            total_cards: Total number of cards being generated
            transaction: Optional transaction to use
            
        Returns:
            The created Flashcard object
        """
        flashcard = Flashcard(
            front=card_data["front"],
            back=card_data["back"],
            is_ai_generated=True,
            generation_model=model.value.lower(),
            prompt_template_id=db_template.id,
            prompt_parameters={"num_cards": total_cards},
            model_parameters=generation_request.model_params,
            answer_key_terms=card_data.get("answer_key_terms", []),
            key_concepts=card_data.get("key_concepts", []),
            abbreviations=card_data.get("abbreviations", [])
        )
        
        session = transaction or self.db
        session.add(flashcard)
        session.flush()
        
        return flashcard 