from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging
from typing import Optional
import json

from models.source import SourceFile, Citation
from models.set import FlashcardSet
from models.flashcard import Flashcard
from models.prompt import PromptTemplate
from models.enums import FileType, AIModel, CitationType

from utils.ai_flashcard_creation import create_flashcards_from_text, get_latest_prompt_template
from utils.citation_processing import HTMLCitationProcessor, TextCitationProcessor, CitationProcessor
from utils.citation_processing.youtube_citation_processor import YouTubeCitationProcessor
from utils.citation_processing.pdf_citation_processor import PDFCitationProcessor
from utils.citation_processing.image_citation_processor import ImageCitationProcessor
from services.content_manager import ContentManager
from services.flashcard import FlashcardService
from services.flashcard_set import FlashcardSetService
from services.citation_service import CitationService

logger = logging.getLogger(__name__)

class AIFlashcardService:
    def __init__(self, db: Session, content_manager: 'ContentManager'):
        self.db = db
        self.content_manager = content_manager
        self.flashcard_service = FlashcardService(db)
        self.flashcard_set_service = FlashcardSetService(db)
        self.citation_service = CitationService(db)

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
            text_content, content_structure = await self.content_manager.process_content(source_file)
            
            # Check if we have selected content for text files
            selected_content = None
            if source_file.file_type == FileType.TXT.value and hasattr(generation_request, 'selected_content'):
                selected_content = generation_request.selected_content
                if selected_content:
                    logger.info(f"Using selected content for file type {source_file.file_type}")
            
            # Generate and save flashcards, passing selected content if available
            return await self._generate_and_save_flashcards(
                text_content=text_content,
                content_structure=content_structure,
                source_file=source_file,
                model=model,
                generation_request=generation_request,
                selected_content=selected_content
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
        """Validate and retrieve a source file."""
        source_file = self.db.query(SourceFile).filter(SourceFile.id == source_file_id).first()
        if not source_file:
            raise HTTPException(status_code=404, detail=f"Source file {source_file_id} not found")

        # Validate file type
        supported_types = {
            FileType.TXT.value,
            FileType.HTML.value,
            FileType.PDF.value,
            FileType.YOUTUBE_TRANSCRIPT.value,
            FileType.IMAGE.value  # Add support for images
        }
        
        if source_file.file_type not in supported_types:
            raise HTTPException(
                status_code=400,
                detail="Only .txt, HTML, PDF, images, and YouTube transcripts are currently supported"
            )

        return source_file

    async def _generate_and_save_flashcards(
        self,
        text_content: str,  # This is actually raw/structured content, not plain text
        content_structure: str,
        source_file: SourceFile,
        model: AIModel,
        generation_request: 'FlashcardGenerationRequest',
        selected_content: list = None
    ) -> dict:
        """Generate flashcards from text content."""
        logger.info("Preparing for flashcard generation")
        
        # For structured content types, use prompt text for LLM but keep JSON for citations
        if source_file.file_type in [FileType.PDF.value, FileType.TXT.value, FileType.HTML.value, FileType.YOUTUBE_TRANSCRIPT.value, FileType.IMAGE.value]:
            try:
                # Get the appropriate processor and generate prompt text
                processor = self.content_manager._processor._get_processor(source_file.file_type)
                
                # Parse or process the content into structured JSON
                if isinstance(text_content, dict):
                    structured_json = text_content
                else:
                    # Try to parse as JSON
                    try:
                        structured_json = json.loads(text_content)
                        logger.debug(f"Successfully parsed JSON content for {source_file.file_type}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON content for {source_file.file_type}")
                        raise HTTPException(status_code=500, detail="Failed to process content: invalid JSON")
                
                # Log if we're using selected content (only supported for TXT files in this proof of concept)
                if selected_content and source_file.file_type == FileType.TXT.value:
                    logger.info(f"Generating flashcards from {len(selected_content)} selected sections instead of full document")
                    # Generate prompt text from structured JSON with selected content
                    prompt_text = processor.to_prompt_text(structured_json, selected_content)
                else:
                    # Generate prompt text from structured JSON (without selected content for other file types)
                    prompt_text = processor.to_prompt_text(structured_json)
                
                logger.debug(f"Successfully generated prompt text from {source_file.file_type} JSON")
                
                # Store both formats in params
                document_json_str = json.dumps(structured_json) if isinstance(structured_json, dict) else text_content
                params = {
                    'source_text': prompt_text,  # LLM gets human-readable prompt text
                    'content_structure': content_structure,
                    'original_json': document_json_str,  # Store structured JSON for citation processing
                    'is_partial_content': selected_content is not None  # Flag indicating if this is selected content
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse content JSON: {e}")
                raise HTTPException(status_code=500, detail="Failed to process content")
            except Exception as e:
                logger.error(f"Error processing content: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to process content")
        else:
            # Non-structured content uses regular parameters
            document_json_str = text_content
            params = {
                'source_text': text_content,
                'content_structure': content_structure
            }
        
        # Get template and parameters
        db_template = get_latest_prompt_template(self.db, model)
        if not db_template:
            raise HTTPException(status_code=500, detail="No suitable prompt template found")
        
        # Convert file_type string to enum
        try:
            # Map string values to enum values
            file_type_map = {
                'txt': FileType.TXT,
                'html': FileType.HTML,
                'youtube_transcript': FileType.YOUTUBE_TRANSCRIPT,
                'pdf': FileType.PDF,
                'image': FileType.IMAGE
            }
            file_type = file_type_map.get(source_file.file_type.lower()) if source_file.file_type else None
            logger.debug(f"Converted file type from {source_file.file_type} to {file_type}")
        except Exception as e:
            logger.warning(f"Invalid file type {source_file.file_type}, defaulting to None: {str(e)}")
            file_type = None
        
        # Generate flashcards
        generated_cards = await create_flashcards_from_text(
            text=params['source_text'],  # Use prompt text for LLM
            processed_text=params['source_text'],  # Use prompt text for LLM
            model=model,
            db=self.db,
            params=params,
            use_sentences=True,
            model_params=generation_request.model_params or {},
            file_type=file_type
        )
        
        if not generated_cards:
            raise HTTPException(status_code=500, detail="No flashcards were generated")
        
        # Log citation information from generated cards
        total_citations = sum(len(card.get("citations", [])) for card in generated_cards)
        logger.info(f"Generated {len(generated_cards)} cards with {total_citations} total citations")
        for i, card in enumerate(generated_cards):
            citations = card.get("citations", [])
        
        # Create and populate flashcard set
        flashcard_set = await self.flashcard_set_service.create_ai_flashcard_set(
            generated_cards=generated_cards,
            source_file=source_file,
            model=model,
            db_template=db_template,
            generation_request=generation_request
        )
        self.db.add(flashcard_set)
        self.db.flush()
        
        # Add flashcards and citations - pass the already processed JSON
        await self._create_flashcards_and_citations(
            generated_cards=generated_cards,
            flashcard_set=flashcard_set,
            source_file=source_file,
            model=model,
            db_template=db_template,
            generation_request=generation_request,
            use_sentences=True,
            document_json=document_json_str  # Use already processed JSON instead of redownloading
        )
        
        self.db.commit()
        logger.info(f"Successfully saved all flashcards and citations for set {flashcard_set.id}")
        return {"set_id": flashcard_set.id, "num_cards": len(generated_cards)}

    async def _create_flashcards_and_citations(
        self,
        generated_cards: list,
        flashcard_set: FlashcardSet,
        source_file: SourceFile,
        model: AIModel,
        db_template: PromptTemplate,
        generation_request: 'FlashcardGenerationRequest',
        use_sentences: bool,
        document_json: str
    ) -> None:
        """Create flashcards and their citations."""
        # Get the appropriate citation processor based on file type
        citation_processor = self.citation_service.get_citation_processor(source_file)
        
        # Process each generated card
        for i, card in enumerate(generated_cards):
            # Create the flashcard using FlashcardService
            flashcard = self.flashcard_service.create_ai_flashcard(
                card_data=card, 
                model=model, 
                db_template=db_template, 
                generation_request=generation_request, 
                total_cards=len(generated_cards)
            )
            
            # Create association with explicit card_index
            self.flashcard_set_service.create_flashcard_set_association(flashcard.id, flashcard_set.id, i + 1)
            
            # Process and create citations for this flashcard
            citations = card.get("citations", [])
            citation_count = self.citation_service.process_flashcard_citations(
                citations=citations, 
                flashcard_id=flashcard.id,
                source_file=source_file,
                document_json=document_json,
                use_sentences=use_sentences,
                card_index=i+1,
                total_cards=len(generated_cards),
                citation_processor=citation_processor
            )
            
            logger.debug(f"Created {citation_count} citations for flashcard {flashcard.id}")

        # Verify total citations created
        total_citations_created = self.db.query(Citation).join(Flashcard).filter(
            Flashcard.id.in_([f.id for f in flashcard_set.flashcards])
        ).count()
        logger.debug(f"Total citations created for set {flashcard_set.id}: {total_citations_created}") 