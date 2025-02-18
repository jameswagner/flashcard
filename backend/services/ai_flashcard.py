from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC

from models.source import SourceFile, Citation
from models.set import FlashcardSet
from models.flashcard import Flashcard, flashcard_set_association
from models.prompt import PromptTemplate
from models.enums import FileType, AIModel, CitationType

from utils.ai_flashcard_creation import create_flashcards_from_text, get_latest_prompt_template
from services.content_processing import ContentProcessingService

logger = logging.getLogger(__name__)

class AIFlashcardService:
    def __init__(self, db: Session, content_processor: ContentProcessingService):
        self.db = db
        self.content_processor = content_processor

    async def generate_flashcards(
        self,
        source_file_id: int,
        generation_request: 'FlashcardGenerationRequest'
    ) -> dict:
        """Generate flashcards from a source file using AI."""
        logger.info(f"Starting flashcard generation for source file {source_file_id}")
        
        try:
            # Validate model and source file
            model = self._validate_model(generation_request.model)
            source_file = await self._validate_and_get_source(source_file_id)
            
            # Process content based on file type
            text_content, content_structure = await self.content_processor.process_content(source_file)
            
            # Generate and save flashcards
            return await self._generate_and_save_flashcards(
                text_content=text_content,
                content_structure=content_structure,
                source_file=source_file,
                model=model,
                generation_request=generation_request
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during flashcard generation: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    def _validate_model(self, model_name: str) -> AIModel:
        """Validate and return AI model enum."""
        try:
            return AIModel(model_name)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported model: {model_name}")

    async def _validate_and_get_source(self, source_file_id: int) -> SourceFile:
        """Validate and retrieve source file."""
        source_file = self.db.get(SourceFile, source_file_id)
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        if source_file.file_type not in [
            FileType.TXT.value,
            FileType.HTML.value,
            FileType.YOUTUBE_TRANSCRIPT.value
        ]:
            raise HTTPException(
                status_code=400,
                detail="Only .txt, HTML, and YouTube transcripts are currently supported"
            )
        
        return source_file

    async def _generate_and_save_flashcards(
        self,
        text_content: str,
        content_structure: str,
        source_file: SourceFile,
        model: AIModel,
        generation_request: 'FlashcardGenerationRequest'
    ) -> dict:
        """Generate and save flashcards from text content."""
        logger.info("Preparing for flashcard generation")
        
        # Get template and parameters
        params = {
            'source_text': text_content,
            'content_structure': content_structure
        }
        
        db_template = get_latest_prompt_template(self.db, model)
        if not db_template:
            raise HTTPException(status_code=500, detail="No suitable prompt template found")
        
        # Generate flashcards
        generated_cards = await create_flashcards_from_text(
            text=text_content,
            processed_text=text_content,
            model=model,
            db=self.db,
            params=params,
            use_sentences=True,
            model_params=generation_request.model_params or {},
            file_type=source_file.file_type
        )
        
        if not generated_cards:
            raise HTTPException(status_code=500, detail="No flashcards were generated")
        
        # Create and populate flashcard set
        flashcard_set = await self._create_flashcard_set(
            generated_cards=generated_cards,
            source_file=source_file,
            model=model,
            db_template=db_template,
            generation_request=generation_request
        )
        self.db.add(flashcard_set)
        self.db.flush()
        
        # Add flashcards and citations
        await self._create_flashcards_and_citations(
            generated_cards=generated_cards,
            flashcard_set=flashcard_set,
            source_file=source_file,
            model=model,
            db_template=db_template,
            generation_request=generation_request,
            use_sentences=True,
            text_content=text_content
        )
        
        self.db.commit()
        return {"set_id": flashcard_set.id, "num_cards": len(generated_cards)}

    async def _create_flashcard_set(
        self,
        generated_cards: list,
        source_file: SourceFile,
        model: AIModel,
        db_template: PromptTemplate,
        generation_request: 'FlashcardGenerationRequest'
    ) -> FlashcardSet:
        """Create flashcard set with generated cards."""
        ai_info = f"\n\nGenerated using {model.value} AI model"
        flashcard_set = FlashcardSet(
            title=generation_request.title or f"Generated from {source_file.filename}",
            description=(generation_request.description + ai_info if generation_request.description 
                        else f"AI-generated flashcards using {model.value}"),
            user_id=generation_request.user_id,
            total_card_count=len(generated_cards),
            ai_card_count=len(generated_cards),
            initial_generation_model=model.value.lower(),
            prompt_template_id=db_template.id,
            prompt_parameters={"num_cards": len(generated_cards)},
            model_parameters=generation_request.model_params
        )
        flashcard_set.source_files.append(source_file)
        return flashcard_set

    async def _create_flashcards_and_citations(
        self,
        generated_cards: list,
        flashcard_set: FlashcardSet,
        source_file: SourceFile,
        model: AIModel,
        db_template: PromptTemplate,
        generation_request: 'FlashcardGenerationRequest',
        use_sentences: bool,
        text_content: str
    ) -> None:
        """Create flashcards and their citations."""
        for i, card in enumerate(generated_cards):
            flashcard = Flashcard(
                front=card["front"],
                back=card["back"],
                is_ai_generated=True,
                generation_model=model.value.lower(),
                prompt_template_id=db_template.id,
                prompt_parameters={"num_cards": len(generated_cards)},
                model_parameters=generation_request.model_params,
                key_terms=card.get("key_terms", []),
                key_concepts=card.get("key_concepts", []),
                abbreviations=card.get("abbreviations", [])
            )
            
            self.db.add(flashcard)
            self.db.flush()
            
            # Create association with explicit card_index
            stmt = flashcard_set_association.insert().values(
                flashcard_id=flashcard.id,
                set_id=flashcard_set.id,
                card_index=i + 1,
                created_at=datetime.now(UTC)
            )
            self.db.execute(stmt)
            
            # Process citations
            citations = card.get("citations", [])
            for citation in citations:
                citation_data = self._parse_citation(citation)
                if citation_data:
                    start_num, end_num, citation_type, context = citation_data
                    
                    # Create citation record
                    db_citation = Citation(
                        flashcard_id=flashcard.id,
                        source_file_id=source_file.id,
                        citation_type=citation_type or (CitationType.sentence_range.value if use_sentences else CitationType.line_numbers.value),
                        citation_data={
                            "range": [start_num, end_num] if start_num is not None else None,
                            "context": context
                        }
                    )
                    self.db.add(db_citation)

    def _parse_citation(self, citation) -> Optional[tuple[Optional[int], Optional[int], Optional[str], Optional[str]]]:
        """Parse citation data into components."""
        try:
            if isinstance(citation, dict):
                citation_type = citation.get('citation_type')
                if not citation_type:
                    return None
                    
                context = citation.get('context')
                
                # Handle range-based citations
                if 'range' in citation:
                    range_data = citation['range']
                    if not isinstance(range_data, (list, tuple)) or len(range_data) != 2:
                        return None
                    start_num, end_num = range_data
                    
                # Handle element-based citations
                elif 'id' in citation:
                    element_id = citation['id']
                    if not isinstance(element_id, int):
                        return None
                    start_num = end_num = element_id
                    
                else:
                    return None
                    
            # Handle legacy format [[start, end]]
            elif isinstance(citation, (list, tuple)):
                if len(citation) != 2:
                    return None
                start_num, end_num = citation
                citation_type = None
                context = None
                
            else:
                return None
                
            return start_num, end_num, citation_type, context
            
        except Exception as e:
            logger.error(f"Error parsing citation: {str(e)}", exc_info=True)
            return None 