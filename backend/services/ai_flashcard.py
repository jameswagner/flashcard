from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC
import json

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
        text_content: str,
        content_structure: str,
        source_file: SourceFile,
        model: AIModel,
        generation_request: 'FlashcardGenerationRequest'
    ) -> dict:
        """Generate and save flashcards from text content."""
        logger.info("Preparing for flashcard generation")
        
        # For structured content types, use prompt text for LLM but keep JSON for citations
        if source_file.file_type in [FileType.PDF.value, FileType.TXT.value, FileType.HTML.value, FileType.YOUTUBE_TRANSCRIPT.value, FileType.IMAGE.value]:
            try:
                # Get the appropriate processor and generate prompt text
                processor = self.content_manager._processor._get_processor(source_file.file_type)
                
                # Check if text_content is already JSON or needs to be parsed
                if isinstance(text_content, dict):
                    structured_json = text_content
                else:
                    # Try to parse as JSON
                    try:
                        structured_json = json.loads(text_content)
                        logger.info(f"Successfully parsed JSON content for {source_file.file_type}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON content for {source_file.file_type}")
                        raise HTTPException(status_code=500, detail="Failed to process content: invalid JSON")
                
                # Generate prompt text from structured JSON
                prompt_text = processor.to_prompt_text(structured_json)
                logger.info(f"Successfully generated prompt text from {source_file.file_type} JSON")
                
                # Store both formats in params
                params = {
                    'source_text': prompt_text,  # LLM gets prompt text
                    'content_structure': content_structure,
                    'original_json': json.dumps(structured_json) if isinstance(structured_json, dict) else text_content  # Store JSON for citation processing
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse content JSON: {e}")
                raise HTTPException(status_code=500, detail="Failed to process content")
            except Exception as e:
                logger.error(f"Error processing content: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to process content")
        else:
            # Non-structured content uses regular parameters
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
            logger.info(f"Converted file type from {source_file.file_type} to {file_type}")
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
        text_content: str
    ) -> None:
        """Create flashcards and their citations."""
        # Initialize appropriate citation processor based on file type
        if source_file.file_type == FileType.HTML.value:
            citation_processor = HTMLCitationProcessor()
            # Get processed HTML content for preview text generation
            processed_json = s3_get_processed_text(source_file.processed_text_s3_key, processing_type='html_structure')
            if processed_json:
                html_content = HTMLContent.from_json(processed_json)
                # No need to flatten - pass the JSON directly to the citation processor
                text_content = processed_json
        elif source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
            citation_processor = YouTubeCitationProcessor()
        elif source_file.file_type == FileType.TXT.value:
            citation_processor = TextCitationProcessor()
        elif source_file.file_type == FileType.PDF.value:
            citation_processor = PDFCitationProcessor()
            # Get processed PDF content for preview text generation
            processed_json = s3_get_processed_text(source_file.processed_text_s3_key, processing_type='pdf_structure')
            logger.info(f"Retrieved processed JSON from S3: {bool(processed_json)}")
            if processed_json:
                logger.info(f"Processing JSON content type: {type(processed_json)}")
                logger.info(f"Processing JSON preview (first 100 chars): {processed_json[:100]}")
                try:
                    # Use JSON directly for citation processing
                    text_content = processed_json
                    logger.info("Successfully loaded PDF JSON content for citations")
                    logger.info(f"Final text_content preview (first 100 chars): {text_content[:100]}")
                except Exception as e:
                    logger.error(f"Error processing PDF content: {str(e)}")
                    logger.error(f"Raw JSON preview: {processed_json[:200]}")
        elif source_file.file_type == FileType.IMAGE.value:
            citation_processor = ImageCitationProcessor()
            # The text_content should already be the structured JSON from process_content
            # No need to retrieve it again from S3
            logger.info(f"Using image JSON for citation processing")
            try:
                # Ensure we have valid JSON for citation processing
                if isinstance(text_content, str):
                    try:
                        structured_json = json.loads(text_content)
                        # Keep text_content as the JSON string
                    except json.JSONDecodeError:
                        logger.error("Failed to parse image JSON content")
                        raise HTTPException(status_code=500, detail="Failed to process image citations: invalid JSON")
                else:
                    # If it's already a dict, convert to JSON string for citation processor
                    structured_json = text_content
                    text_content = json.dumps(structured_json)
                
                logger.info("Successfully prepared image JSON content for citations")
                logger.info(f"JSON content preview (first 100 chars): {text_content[:100]}")
            except Exception as e:
                logger.error(f"Error processing image content: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to process image citations: {str(e)}")
        else:
            citation_processor = CitationProcessor()
        
        for i, card in enumerate(generated_cards):
            flashcard = Flashcard(
                front=card["front"],
                back=card["back"],
                is_ai_generated=True,
                generation_model=model.value.lower(),
                prompt_template_id=db_template.id,
                prompt_parameters={"num_cards": len(generated_cards)},
                model_parameters=generation_request.model_params,
                answer_key_terms=card.get("answer_key_terms", []),
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
            logger.debug(f"Processing {len(citations)} citations for flashcard {flashcard.id} (card {i + 1} of {len(generated_cards)})")
            citation_count = 0
            
            for citation in citations:
                logger.debug(f"Raw citation data: {citation}")
                
                # For YouTube content, use the citation processor's parse method
                if source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
                    start_time, end_time, citation_type, context = citation_processor.parse_citation(citation)
                    if start_time is None or end_time is None:
                        logger.warning(f"Failed to parse YouTube citation: {citation}")
                        continue
                        
                    # Get preview text using timestamp values
                    preview_text = citation_processor.get_preview_text(
                        text_content=text_content,
                        start_time=start_time,
                        end_time=end_time,
                        citation_type=citation_type
                    )
                    
                    # Create citation record with float timestamps
                    db_citation = Citation(
                        flashcard_id=flashcard.id,
                        source_file_id=source_file.id,
                        citation_type=citation_type or CitationType.video_timestamp.value,
                        citation_data=[[float(start_time), float(end_time)]],
                        preview_text=preview_text
                    )
                    
                else:
                    # Original handling for non-YouTube content
                    citation_data = self._parse_citation(citation)
                    if not citation_data:
                        logger.warning(f"Failed to parse citation: {citation}")
                        continue
                        
                    start_num, end_num, citation_type, context = citation_data
                    preview_text = citation_processor.get_preview_text(
                        text_content=text_content,
                        start_num=start_num,
                        end_num=end_num,
                        citation_type=citation_type or (CitationType.sentence_range.value if use_sentences else CitationType.line_numbers.value)
                    )
                    
                    db_citation = Citation(
                        flashcard_id=flashcard.id,
                        source_file_id=source_file.id,
                        citation_type=citation_type or (CitationType.sentence_range.value if use_sentences else CitationType.line_numbers.value),
                        citation_data=[[start_num, end_num]],
                        preview_text=preview_text
                    )
                
                self.db.add(db_citation)
                self.db.flush()
                citation_count += 1
                logger.debug(f"Created citation record: id={db_citation.id}, data={db_citation.citation_data}")
            
            logger.debug(f"Created {citation_count} citations for flashcard {flashcard.id}")

        # Verify total citations created
        total_citations_created = self.db.query(Citation).join(Flashcard).filter(
            Flashcard.id.in_([f.id for f in flashcard_set.flashcards])
        ).count()
        logger.info(f"Total citations created for set {flashcard_set.id}: {total_citations_created}")

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
                    start_num, end_num = range_data
                    
                # Handle element-based citations
                elif 'id' in citation:
                    element_id = citation['id']
                    if not isinstance(element_id, int):
                        logger.warning(f"Invalid element ID: {element_id}")
                        return None
                    start_num = end_num = element_id
                    logger.info(f"Parsed element citation: {element_id}")
                    
                else:
                    logger.warning("Citation dict missing both range and id")
                    return None
                    
            elif isinstance(citation, (list, tuple)):
                if len(citation) != 2:
                    logger.warning(f"Invalid citation list length: {len(citation)}")
                    return None
                start_num, end_num = citation
                citation_type = None
                context = None
                logger.info(f"Parsed legacy citation format: {start_num}-{end_num}")
                
            else:
                logger.warning(f"Unexpected citation format: {type(citation)}")
                return None
                
            return start_num, end_num, citation_type, context
            
        except Exception as e:
            logger.error(f"Error parsing citation: {str(e)}", exc_info=True)
            return None 