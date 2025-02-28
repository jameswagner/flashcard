from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC
import json
import math

from models.source import SourceFile, Citation
from models.set import FlashcardSet
from models.flashcard import Flashcard, flashcard_set_association
from models.prompt import PromptTemplate
from models.enums import FileType, AIModel, CitationType

from utils.ai_flashcard_creation import create_flashcards_from_text, get_latest_prompt_template
from utils.citation_processing import HTMLCitationProcessor, TextCitationProcessor, CitationProcessor
from utils.citation_processing.youtube_citation_processor import YouTubeCitationProcessor
from utils.citation_processing.pdf_citation_processor import PDFCitationProcessor
from utils.citation_processing.image_citation_processor import ImageCitationProcessor
from services.content_manager import ContentManager
from utils.s3 import get_processed_text as s3_get_processed_text
from utils.html_processing import HTMLContent
from utils.pdf_processing.processor import ProcessedDocument

logger = logging.getLogger(__name__)

class AIFlashcardService:
    def __init__(self, db: Session, content_manager: 'ContentManager'):
        self.db = db
        self.content_manager = content_manager

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
        generation_request: 'FlashcardGenerationRequest'
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
                
                # Generate prompt text from structured JSON
                prompt_text = processor.to_prompt_text(structured_json)
                logger.debug(f"Successfully generated prompt text from {source_file.file_type} JSON")
                
                # Store both formats in params
                document_json_str = json.dumps(structured_json) if isinstance(structured_json, dict) else text_content
                params = {
                    'source_text': prompt_text,  # LLM gets human-readable prompt text
                    'content_structure': content_structure,
                    'original_json': document_json_str  # Store structured JSON for citation processing
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
        flashcard_set = await self._create_flashcard_set(
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
        document_json: str
    ) -> None:
        """Create flashcards and their citations."""
        # Get the appropriate citation processor based on file type
        citation_processor = self._get_citation_processor(source_file)
        
        # Process each generated card
        for i, card in enumerate(generated_cards):
            # Create the flashcard and add it to the set
            flashcard = self._create_flashcard(
                card, 
                model, 
                db_template, 
                generation_request, 
                len(generated_cards)
            )
            self.db.add(flashcard)
            self.db.flush()
            
            # Create association with explicit card_index
            self._create_flashcard_set_association(flashcard.id, flashcard_set.id, i + 1)
            
            # Process and create citations for this flashcard
            citations = card.get("citations", [])
            citation_count = self._process_flashcard_citations(
                citations=citations, 
                flashcard_id=flashcard.id,
                source_file=source_file,
                citation_processor=citation_processor,
                document_json=document_json,
                use_sentences=use_sentences,
                card_index=i+1,
                total_cards=len(generated_cards)
            )
            
            logger.debug(f"Created {citation_count} citations for flashcard {flashcard.id}")

        # Verify total citations created
        total_citations_created = self.db.query(Citation).join(Flashcard).filter(
            Flashcard.id.in_([f.id for f in flashcard_set.flashcards])
        ).count()
        logger.debug(f"Total citations created for set {flashcard_set.id}: {total_citations_created}")

    def _get_citation_processor(self, source_file):
        """Get the appropriate citation processor based on file type."""
        if source_file.file_type == FileType.HTML.value:
            processor = HTMLCitationProcessor()
            logger.debug(f"Using HTML citation processor for file {source_file.id} ({source_file.filename})")
        elif source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
            processor = YouTubeCitationProcessor()
            logger.debug(f"Using YouTube citation processor for file {source_file.id} ({source_file.filename})")
        elif source_file.file_type == FileType.TXT.value:
            processor = TextCitationProcessor()
            logger.debug(f"Using Text citation processor for file {source_file.id} ({source_file.filename})")
        elif source_file.file_type == FileType.PDF.value:
            processor = PDFCitationProcessor()
            logger.debug(f"Using PDF citation processor for file {source_file.id} ({source_file.filename})")
        elif source_file.file_type == FileType.IMAGE.value:
            processor = ImageCitationProcessor()
            logger.debug(f"Using Image citation processor for file {source_file.id} ({source_file.filename})")
        else:
            processor = CitationProcessor()
            logger.debug(f"Using base citation processor for file {source_file.id} ({source_file.filename}) with type {source_file.file_type}")
        
        return processor

    def _create_flashcard(self, card, model, db_template, generation_request, total_cards):
        """Create a flashcard object from a generated card."""
        return Flashcard(
            front=card["front"],
            back=card["back"],
            is_ai_generated=True,
            generation_model=model.value.lower(),
            prompt_template_id=db_template.id,
            prompt_parameters={"num_cards": total_cards},
            model_parameters=generation_request.model_params,
            answer_key_terms=card.get("answer_key_terms", []),
            key_concepts=card.get("key_concepts", []),
            abbreviations=card.get("abbreviations", [])
        )

    def _create_flashcard_set_association(self, flashcard_id, set_id, card_index):
        """Create association between flashcard and set with explicit card index."""
        stmt = flashcard_set_association.insert().values(
            flashcard_id=flashcard_id,
            set_id=set_id,
            card_index=card_index,
            created_at=datetime.now(UTC)
        )
        self.db.execute(stmt)

    def _process_flashcard_citations(self, citations, flashcard_id, source_file, citation_processor, document_json, use_sentences, card_index, total_cards):
        """Process all citations for a single flashcard."""
        logger.debug(f"Processing {len(citations)} citations for flashcard {flashcard_id} (card {card_index} of {total_cards})")
        citation_count = 0
        
        for citation_idx, citation in enumerate(citations):
            logger.debug(f"Processing citation #{citation_idx+1}: {citation}")
            
            # Parse citation with the appropriate processor
            parsed_citation = self._parse_citation_data(
                citation=citation, 
                citation_processor=citation_processor,
                file_type=source_file.file_type
            )
            
            if not parsed_citation:
                logger.warning(f"Failed to parse citation: {citation}")
                continue
            
            # Create citation record
            db_citation = self._create_citation_record(
                parsed_citation=parsed_citation,
                flashcard_id=flashcard_id,
                source_file=source_file,
                citation_processor=citation_processor,
                document_json=document_json,
                use_sentences=use_sentences
            )
            
            if db_citation:
                self.db.add(db_citation)
                self.db.flush()
                citation_count += 1
                logger.debug(f"Created citation record: id={db_citation.id}, type={db_citation.citation_type}")
        
        return citation_count

    def _create_citation_record(self, parsed_citation, flashcard_id, source_file, citation_processor, document_json, use_sentences):
        """Create a citation record from parsed citation data."""
        # Unpack the standardized citation data
        start_value, end_value, citation_type, context = parsed_citation
        logger.debug(f"Parsed citation: start={start_value}, end={end_value}, type={citation_type}")
        
        # Get preview text using parameter names compatible with all processors
        preview_text = citation_processor.get_preview_text(
            text_content=document_json,
            start_num=start_value,
            end_num=end_value,
            citation_type=citation_type
        )
        
        # Log a sample of the preview text
        preview_sample = preview_text[:100] + "..." if len(preview_text) > 100 else preview_text
        logger.debug(f"Generated preview text: '{preview_sample}'")
        
        # Format citation data
        citation_data_value = [[start_value, end_value]]
        
        # Determine default citation type based on file type and settings
        if source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
            default_type = CitationType.video_timestamp.value
        else:
            default_type = CitationType.sentence_range.value if use_sentences else CitationType.line_numbers.value
            
        logger.debug(f"Using citation data value: {citation_data_value}, type: {citation_type or default_type}")
        
        # Create citation record with appropriate values
        return Citation(
            flashcard_id=flashcard_id,
            source_file_id=source_file.id,
            citation_type=citation_type or default_type,
            citation_data=citation_data_value,
            preview_text=preview_text
        )

    def _parse_citation_data(self, citation, citation_processor, file_type):
        """Parse citation data into standardized components for all content types."""
        try:
            # Simple, unified code path for all processors
            logger.debug(f"Parsing citation for {file_type}: {citation}")
            
            # All processors return the same tuple structure: (start, end, type, context)
            result = citation_processor.parse_citation(citation)
            
            if not result:
                logger.warning(f"Failed to parse citation: {citation}")
                return None
            
            logger.debug(f"Citation processor returned: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing citation: {str(e)}", exc_info=True)
            return None

    def _parse_citation(self, citation) -> Optional[tuple[Optional[int], Optional[int], Optional[str], Optional[str]]]:
        """Parse citation data into components."""
        try:
            if isinstance(citation, dict):
                citation_type = citation.get('citation_type')
                if not citation_type:
                    logger.warning("Missing citation_type in citation dict")
                    return None
                    
                context = citation.get('context')
                
                # Handle range-based citations
                if 'range' in citation:
                    range_data = citation['range']
                    if not isinstance(range_data, (list, tuple)) or len(range_data) != 2:
                        logger.warning(f"Invalid range format: {range_data}")
                        return None
                    start_int, end_int = range_data
                    logger.debug(f"Parsed range citation: {start_int}-{end_int}")
                    
                # Handle element-based citations
                elif 'id' in citation:
                    element_id = citation['id']
                    if not isinstance(element_id, int):
                        logger.warning(f"Invalid element ID: {element_id}")
                        return None
                    start_int = end_int = element_id
                    logger.debug(f"Parsed element citation with ID {element_id} (converted to range {start_int}-{end_int})")
                    
                else:
                    logger.warning("Citation dict missing both range and id")
                    return None
                    
            elif isinstance(citation, (list, tuple)):
                if len(citation) != 2:
                    logger.warning(f"Invalid citation list length: {len(citation)}")
                    return None
                start_int, end_int = citation
                citation_type = None
                context = None
                logger.debug(f"Parsed legacy citation format: {start_int}-{end_int}")
                
            else:
                logger.warning(f"Unexpected citation format: {type(citation)}")
                return None
                
            return start_int, end_int, citation_type, context
            
        except Exception as e:
            logger.error(f"Error parsing citation: {str(e)}", exc_info=True)
            return None 