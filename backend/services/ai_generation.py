from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
import logging
import json
import traceback
from datetime import datetime, UTC
from typing import Optional, Dict, Any
import re

from models.source import SourceFile, Citation
from models.set import FlashcardSet
from models.flashcard import Flashcard, flashcard_set_association
from models.prompt import PromptTemplate
from models.enums import FileType, AIModel, CitationType

from utils.s3 import (
    upload_file,
    generate_s3_key,
    get_file_content,
    store_processed_text as s3_store_processed_text,
    get_processed_text as s3_get_processed_text,
    store_html_content,
    get_html_content
)
from utils.ai_flashcard_creation import create_flashcards_from_text, get_latest_prompt_template
from utils.text_processing import get_text_from_line_numbers, add_line_markers
from utils.sentence_processing import get_text_from_sentence_numbers, add_sentence_markers
from utils.html_processing import scrape_url, process_html, HTMLContent
from utils.youtube_processing import fetch_transcript, YouTubeContent, generate_citations

from api.models.requests.ai_generation import FlashcardGenerationRequest

logger = logging.getLogger(__name__)

class AIGenerationService:
    def __init__(self, db: Session):
        self.db = db
        self._youtube_content_cache = {}  # Cache for processed YouTube content

    async def upload_url(self, url: str, user_id: Optional[str] = None) -> dict:
        """Upload HTML content from a URL and create a database record.
        
        Args:
            url: The URL to scrape
            user_id: Optional user ID for namespacing
            
        Returns:
            Dict with source file ID and filename
        """
        print("\n=== UPLOADING URL CONTENT ===")
        print(f"URL: {url}")
        print(f"User ID: {user_id}")
        
        try:
            # Fetch and process HTML content
            print("\nFetching content from URL...")
            raw_html, title = await scrape_url(url)
            print(f"Retrieved content length: {len(raw_html)}")
            print(f"Title: {title}")
            
            print("\nProcessing HTML content...")
            processed_content = process_html(raw_html, title)
            print("HTML processed successfully")
            
            # Store both raw and processed content
            print("\nStoring content in S3...")
            raw_key, processed_key = store_html_content(
                raw_html=raw_html,
                processed_json=processed_content.to_json(),
                url=url,
                user_id=user_id
            )
            print(f"Raw content stored at: {raw_key}")
            print(f"Processed content stored at: {processed_key}")
            
            # Create database record
            print("\nCreating database record...")
            filename = title or url.split('/')[-1] or 'index.html'
            source_file = SourceFile(
                filename=filename,
                s3_key=raw_key,
                url=url,
                file_type=FileType.HTML.value,
                processed_text_type='html_structure'
            )
            self.db.add(source_file)
            self.db.commit()
            self.db.refresh(source_file)
            print(f"Created source file record with ID: {source_file.id}")
            
            return {"id": source_file.id, "filename": filename}
            
        except Exception as e:
            self.db.rollback()
            print(f"\nERROR processing URL {url}: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    def upload_source_file(self, file: UploadFile, user_id: Optional[str] = None) -> dict:
        """Upload a source file to S3 and create a database record."""
        # Validate file type
        extension = file.filename.lower().split('.')[-1]
        try:
            file_type = FileType(extension)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")
        
        # Generate S3 key and upload
        s3_key = generate_s3_key(file.filename, user_id)
        upload_file(file.file, s3_key)
        
        # Create database record
        source_file = SourceFile(
            filename=file.filename,
            s3_key=s3_key,
            file_type=extension
        )
        self.db.add(source_file)
        self.db.commit()
        self.db.refresh(source_file)
        
        return {"id": source_file.id, "filename": source_file.filename}

    async def _process_html_content(self, source_file: SourceFile) -> HTMLContent:
        """Process HTML content and ensure it's stored properly.
        
        Args:
            source_file: The source file record to process
            
        Returns:
            Processed HTML content structure
            
        Raises:
            HTTPException: If content cannot be processed or stored
        """
        print("\n=== PROCESSING HTML CONTENT ===")
        print(f"Source file: {source_file.filename} (ID: {source_file.id})")
        
        # Get raw HTML and processed content
        print("\nFetching raw HTML from S3...")
        raw_html = get_file_content(source_file.s3_key)
        print(f"Raw HTML length: {len(raw_html)}")
        print("First 500 chars of raw HTML:")
        print("-" * 80)
        print(raw_html[:500])
        print("-" * 80)
        
        print("\nChecking for existing processed content...")
        processed_json = s3_get_processed_text(source_file.s3_key, processing_type='html_structure')
        
        if processed_json is None:
            print("\nNo existing processed content found, processing HTML...")
            try:
                processed_content = process_html(raw_html, source_file.filename)
                processed_json = processed_content.to_json()
                print("\nStoring processed content in S3...")
                s3_store_processed_text(processed_json, source_file.s3_key, processing_type='html_structure')
                print("Successfully stored processed content")
            except Exception as e:
                print(f"\nERROR processing HTML: {str(e)}")
                print(traceback.format_exc())
                raise
        else:
            print("Found existing processed content")
        
        print("\nProcessed content structure:")
        content = HTMLContent.from_json(processed_json)
        print(f"Title: {content.title}")
        print(f"Number of sections: {len(content.sections)}")
        for i, section in enumerate(content.sections):
            print(f"\nSection {i+1}:")
            print(f"  Level: {section.level}")
            print(f"  Heading: {section.heading}")
            print(f"  Number of paragraphs: {len(section.paragraphs)}")
            if section.paragraphs:
                print(f"  First paragraph preview: {section.paragraphs[0][:100]}...")
        
        return content

    async def upload_youtube_video(self, video_id: str, video_title: str = None, description: str = None, user_id: Optional[str] = None) -> dict:
        """Upload YouTube video transcript and create a database record.
        
        Args:
            video_id: YouTube video ID
            video_title: Optional title override (will fetch from YouTube if not provided)
            description: Optional description override (will fetch from YouTube if not provided)
            user_id: Optional user ID for namespacing
            
        Returns:
            Dict with source file ID and filename
        """
        logger.info(f"=== UPLOADING YOUTUBE VIDEO TRANSCRIPT ===")
        logger.info(f"Video ID: {video_id}")
        
        try:
            # Fetch video metadata from YouTube API
            logger.info("Fetching video metadata from YouTube API...")
            from scripts.get_video_info import get_video_info
            video_info = get_video_info(video_id)
            if 'error' in video_info:
                logger.error(f"Failed to fetch video info: {video_info['error']}")
                raise HTTPException(status_code=404, detail=f"Could not fetch video info: {video_info['error']}")
            
            # Use provided title/description or ones from API
            actual_title = video_title or video_info['title']
            actual_description = description or video_info['description']
            
            logger.info(f"Title: {actual_title}")
            logger.debug(f"Description length: {len(actual_description)} chars")
            
            # Fetch and process transcript
            logger.info("Fetching and processing transcript...")
            processed_content = fetch_transcript(video_id, actual_title, actual_description)
            if not processed_content:
                logger.error(f"Failed to fetch transcript for video {video_id}")
                raise HTTPException(status_code=404, detail="Could not fetch video transcript")
            
            # Add video metadata to processed content
            processed_content.channel = video_info['channel']
            processed_content.published_at = video_info['published_at']
            processed_content.duration = video_info['duration']
            processed_content.statistics = video_info['statistics']
            
            logger.info(f"Retrieved transcript: {len(processed_content.transcript_text)} chars")
            logger.info(f"Found {len(processed_content.chapters)} chapters")
            logger.debug(f"First chapter: {processed_content.chapters[0] if processed_content.chapters else 'None'}")
            
            # Store processed content with complete metadata
            logger.info("Storing content in S3...")
            s3_key = generate_s3_key(f"{video_id}.json", user_id)
            s3_store_processed_text(processed_content.to_dict(), s3_key, processing_type='youtube_transcript')
            logger.debug(f"Content stored at: {s3_key}")
            
            # Create database record
            logger.info("Creating database record...")
            source_file = SourceFile(
                filename=f"{actual_title} ({video_id})",
                s3_key=s3_key,
                url=f"https://www.youtube.com/watch?v={video_id}",
                file_type=FileType.YOUTUBE_TRANSCRIPT.value,
                processed_text_type='youtube_transcript'
            )
            self.db.add(source_file)
            self.db.commit()
            self.db.refresh(source_file)
            logger.info(f"Created source file record with ID: {source_file.id}")
            
            return {"id": source_file.id, "filename": source_file.filename}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing YouTube video {video_id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    async def _process_youtube_content(self, source_file: SourceFile) -> YouTubeContent:
        """Process YouTube transcript content and ensure it's stored properly.
        
        Args:
            source_file: The source file record to process
            
        Returns:
            Processed YouTube content structure
            
        Raises:
            HTTPException: If content cannot be processed or stored
        """
        # Check cache first
        if source_file.id in self._youtube_content_cache:
            logger.debug(f"Using cached YouTube content for source file {source_file.id}")
            return self._youtube_content_cache[source_file.id]

      
        
        try:
            # Get processed content
            logger.info("Fetching processed content from S3...")
            processed_json = s3_get_processed_text(source_file.s3_key, processing_type='youtube_transcript')
            
            if not processed_json:
                logger.error(f"No processed content found for source file {source_file.id}")
                raise HTTPException(status_code=500, detail="No processed content found")
            
            logger.info("Creating YouTubeContent from processed JSON...")
            if isinstance(processed_json, str):
                try:
                    processed_json = json.loads(processed_json)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON: {str(e)}")
                    raise HTTPException(status_code=500, detail="Invalid JSON format")
            
            content = YouTubeContent.from_dict(processed_json)
            
            # Cache the content
            self._youtube_content_cache[source_file.id] = content
            
            # Log content details
            logger.info(f"Video ID: {content.video_id}")
            logger.info(f"Title: {content.title}")
            logger.info(f"Description length: {len(content.description)} chars")
            logger.info(f"Transcript length: {len(content.transcript_text)} characters")
            logger.info(f"Number of chapters: {len(content.chapters)}")
            logger.info(f"Number of segments: {len(content.segments)}")
            
            # Log chapter information
            if content.chapters:
                logger.debug("Chapter information:")
                for i, chapter in enumerate(content.chapters, 1):
                    logger.debug(f"  Chapter {i}: {chapter['title']} at {chapter['time']}")
            
            return content
            
        except Exception as e:
            logger.error(f"Error processing YouTube content: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    def clear_youtube_cache(self):
        """Clear the YouTube content cache."""
        self._youtube_content_cache.clear()
        logger.info("Cleared YouTube content cache")

    async def generate_flashcards(
        self,
        source_file_id: int,
        generation_request: FlashcardGenerationRequest
    ) -> dict:
        """Generate flashcards from a source file using AI."""
        print("\n=== STARTING FLASHCARD GENERATION ===")
        print(f"Source file ID: {source_file_id}")
        print(f"Generation request: {generation_request}")
        
        try:
            # Validate model and source file
            model = self._validate_model(generation_request.model)
            source_file = await self._validate_and_get_source(source_file_id)
            
            # Process content based on file type
            text_content, content_structure = await self._process_source_content(source_file)
            
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
            print(f"\nERROR during flashcard generation: {str(e)}")
            print(traceback.format_exc())
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
            logger.error(f"Source file not found: {source_file_id}")
            raise HTTPException(status_code=404, detail="Source file not found")
        
        if source_file.file_type not in [
            FileType.TXT.value,
            FileType.HTML.value,
            FileType.YOUTUBE_TRANSCRIPT.value
        ]:
            logger.error(f"Unsupported file type: {source_file.file_type}")
            raise HTTPException(
                status_code=400,
                detail="Only .txt, HTML, and YouTube transcripts are currently supported"
            )
        
        return source_file

    async def _process_source_content(self, source_file: SourceFile) -> tuple[str, str]:
        """Process source content based on file type."""
        logger.info(f"Processing source content of type: {source_file.file_type}")
        
        if source_file.file_type == FileType.HTML.value:
            logger.info("Processing HTML content...")
            html_content = await self._process_html_content(source_file)
            text_content = "\n\n".join(
                f"[Section: {section.heading}]\n" + 
                "\n".join(section.paragraphs)
                for section in html_content.sections
            )
            content_structure = (
                "The text is structured HTML content with sections, paragraphs, tables, and lists. "
                "Each section begins with [Section: heading]. "
                "Content is organized hierarchically with sections containing paragraphs and other elements. "
                "Citations should reference the appropriate HTML element type (paragraph, section, table, or list)."
            )
            
        elif source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
            logger.info("Processing YouTube transcript content...")
            youtube_content = await self._process_youtube_content(source_file)
            text_content = youtube_content.transcript_text
            content_structure = (
                "The text is a YouTube video transcript with timestamps in seconds. "
                "Citations use video_timestamp type to reference specific moments in the video. "
                "Each citation includes a 20-second chunk of content and its chapter context."
            )
            logger.debug(f"Content structure guidance: {content_structure}")
            
        else:  # TXT files
            logger.info("Processing plain text file...")
            text_content = get_file_content(source_file.s3_key)
            processed_text = s3_get_processed_text(source_file.s3_key)
            
            if processed_text is None:
                logger.debug("No existing processed text found, processing now...")
                processed_text = add_sentence_markers(text_content)
                s3_store_processed_text(processed_text, source_file.s3_key)
            
            text_content = processed_text
            content_structure = (
                "The text has been pre-processed to identify sentence boundaries. "
                "Each sentence is numbered starting from 1."
            )
        
        logger.info(f"Processed content length: {len(text_content)} characters")
        return text_content, content_structure

    async def _generate_and_save_flashcards(
        self,
        text_content: str,
        content_structure: str,
        source_file: SourceFile,
        model: AIModel,
        generation_request: FlashcardGenerationRequest
    ) -> dict:
        """Generate and save flashcards from text content."""
        print("\n=== GENERATING FLASHCARDS ===")
        
        # Get template and parameters
        print("\nPreparing generation parameters...")
        params = {
            'source_text': text_content,
            'content_structure': content_structure
        }
        print("Parameters prepared:")
        for k, v in params.items():
            if k != 'source_text':
                print(f"  {k}: {v}")
            else:
                print(f"  {k}: [length: {len(v)}]")
        
        db_template = get_latest_prompt_template(self.db, model)
        if not db_template:
            print("ERROR: No suitable prompt template found")
            raise HTTPException(status_code=500, detail="No suitable prompt template found")
        
        print(f"\nUsing prompt template: {db_template.name} (version {db_template.version})")
        
        # Generate flashcards
        print("\nCalling AI model for flashcard generation...")
        generated_cards = await create_flashcards_from_text(
            text=text_content,
            processed_text=text_content,
            model=model,
            db=self.db,
            params=params,
            use_sentences=True,  # Always use sentences for HTML content
            model_params=generation_request.model_params or {},
            file_type=source_file.file_type  # Pass the file type from source file
        )
        
        if not generated_cards:
            print("ERROR: No flashcards were generated")
            raise HTTPException(status_code=500, detail="No flashcards were generated")
        
        print(f"\nGenerated {len(generated_cards)} flashcards")
        
        # Create and populate flashcard set
        print("\nCreating flashcard set...")
        flashcard_set = await self._create_flashcard_set(
            generated_cards=generated_cards,
            source_file=source_file,
            model=model,
            db_template=db_template,
            generation_request=generation_request
        )
        self.db.add(flashcard_set)
        self.db.flush()
        print(f"Created flashcard set with ID: {flashcard_set.id}")
        
        # Add flashcards and citations
        print("\nCreating flashcards and citations...")
        await self._create_flashcards_and_citations(
            generated_cards=generated_cards,
            flashcard_set=flashcard_set,
            source_file=source_file,
            model=model,
            db_template=db_template,
            generation_request=generation_request,
            use_sentences=True,  # Always use sentences for HTML content
            text_content=text_content
        )
        
        self.db.commit()
        print("\n=== FLASHCARD GENERATION COMPLETE ===")
        
        return {"set_id": flashcard_set.id, "num_cards": len(generated_cards)}

    async def _create_flashcard_set(
        self,
        generated_cards: list,
        source_file: SourceFile,
        model: AIModel,
        db_template: PromptTemplate,
        generation_request: FlashcardGenerationRequest
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
        generation_request: FlashcardGenerationRequest,
        use_sentences: bool,
        text_content: str
    ) -> None:
        """Create flashcards and their citations."""
        for index, card_data in enumerate(generated_cards, start=1):
            logger.debug(f"Processing card {index} with data: {card_data}")
            flashcard = Flashcard(
                front=card_data["front"],
                back=card_data["back"],
                is_ai_generated=True,
                generation_model=model.value.lower(),
                prompt_template_id=db_template.id,
                prompt_parameters={"num_cards": len(generated_cards)},
                model_parameters=generation_request.model_params
            )
            self.db.add(flashcard)
            self.db.flush()
            
            # Create association with explicit card_index
            stmt = flashcard_set_association.insert().values(
                flashcard_id=flashcard.id,
                set_id=flashcard_set.id,
                card_index=index,
                created_at=datetime.now(UTC)
            )
            self.db.execute(stmt)
            
            await self._process_citations(
                card_data.get("citations", []),
                flashcard,
                source_file,
                use_sentences,
                text_content,
                index
            )

    def _parse_citation(self, citation) -> tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
        """Parse citation data into components.
        
        Returns:
            Tuple of (start_num, end_num, citation_type, context)
            For element-based citations (tables, lists), start_num will be the element ID
        """
        if isinstance(citation, dict):
            citation_type = citation.get('citation_type')
            if not citation_type:
                logger.warning(f"Citation missing citation_type: {citation}")
                return None, None, None, None
                
            context = citation.get('context')
            
            # Handle range-based citations (sentences, paragraphs)
            if 'range' in citation:
                range_data = citation['range']
                if not isinstance(range_data, (list, tuple)) or len(range_data) != 2:
                    logger.warning(f"Invalid range format: {range_data}")
                    return None, None, None, None
                start_num, end_num = range_data
                
            # Handle element-based citations (tables, lists, sections)
            elif 'id' in citation:
                element_id = citation['id']
                if not isinstance(element_id, int):
                    logger.warning(f"Invalid element ID: {element_id}")
                    return None, None, None, None
                start_num = end_num = element_id
                
            else:
                logger.warning(f"Citation missing range or id: {citation}")
                return None, None, None, None
                
        # Handle legacy format [[start, end]]
        elif isinstance(citation, (list, tuple)):
            if len(citation) != 2:
                logger.warning(f"Invalid citation list length: {len(citation)} - {citation}")
                return None, None, None, None
            start_num, end_num = citation
            citation_type = None
            context = None
            
        else:
            logger.warning(f"Unexpected citation format: {type(citation)} - {citation}")
            return None, None, None, None
        
        # Validate numbers
        if not isinstance(start_num, int) or not isinstance(end_num, int):
            logger.warning(f"Invalid citation numbers: start={start_num} ({type(start_num)}), end={end_num} ({type(end_num)})")
            return None, None, None, None
        
        return start_num, end_num, citation_type, context

    async def _process_citations(
        self,
        citations: list,
        flashcard: Flashcard,
        source_file: SourceFile,
        use_sentences: bool,
        text_content: str,
        card_index: int
    ) -> None:
        """Process citations for a flashcard."""
        logger.debug(f"Processing citations for card {card_index}: {citations}")
        
        for citation in citations:
            try:
                # Parse citation data
                start_num, end_num, citation_type, context = self._parse_citation(citation)
                if start_num is None:
                    continue
                
                # Determine citation type if not explicitly provided
                if citation_type is None:
                    citation_type = (
                        CitationType.sentence_range.value if use_sentences 
                        else CitationType.line_numbers.value
                    )

                # Get preview text based on citation type
                if source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
                    logger.info(f"Processing YouTube citation with range [{start_num}-{end_num}]")
                    
                    # Get the YouTubeContent object which already has the parsed segments
                    youtube_content = await self._process_youtube_content(source_file)
                    if not youtube_content or not youtube_content.segments:
                        logger.error("No segments found in YouTube content")
                        continue
                        
                    # Extract text from segments that overlap with our citation range
                    preview_text = []
                    matching_segments = 0
                    
                    for segment in youtube_content.segments:
                        segment_start = segment['start']
                        segment_end = segment_start + segment['duration']
                        
                        # If we've gone past our target range, we can stop
                        if segment_start > end_num:
                            logger.debug("[x] Past target range, breaking early")
                            break
                            
                        # Check if this segment overlaps with our citation range
                        if not (segment_end < start_num or segment_start > end_num):
                            preview_text.append(segment['text'])
                            matching_segments += 1
                            logger.debug(f"[+] Found matching segment [{segment_start:.2f}-{segment_end:.2f}]s")
                        else:
                            logger.debug(f"[x] Segment outside citation range [{segment_start:.2f}-{segment_end:.2f}]s")
                    
                    preview = ' '.join(preview_text)
                    logger.info(f"Found {matching_segments} matching segments")
                    logger.info(f"Generated preview text ({len(preview)} chars): {preview[:100]}...")
                elif source_file.file_type == FileType.HTML.value:
                    preview = self._get_html_preview(
                        text_content=text_content,
                        start_num=start_num,
                        end_num=end_num,
                        citation_type=citation_type,
                        context=context
                    )
                elif use_sentences:
                    preview = get_text_from_sentence_numbers(text_content, start_num, end_num)
                else:
                    preview = get_text_from_line_numbers(text_content, start_num, end_num)
                
                logger.debug(f"Creating citation: type={citation_type}, range={start_num}-{end_num}, context={context}")
                logger.debug(f"Preview text: {preview[:100]}...")
                    
                citation_obj = Citation(
                    flashcard=flashcard,
                    source_file=source_file,
                    citation_type=citation_type,
                    citation_data=[[start_num, end_num]],  # Store just the range array
                    preview_text=preview
                )
                self.db.add(citation_obj)
                
            except Exception as e:
                logger.error(f"Failed to process citation: {str(e)}")
                logger.error(f"Citation data: {citation}")
                logger.error(traceback.format_exc())
                continue

    def _get_html_preview(
        self, 
        text_content: str, 
        start_num: int, 
        end_num: int, 
        citation_type: str,
        context: Optional[str] = None
    ) -> str:
        """Extract preview text from HTML content based on citation type."""
        lines = text_content.split('\n')
        
        # For element-based citations (tables, lists), start_num is the element ID
        if citation_type in [CitationType.html_table.value, CitationType.html_list.value]:
            # Find the element with the matching ID
            marker = f"[{citation_type.split('_')[1].upper()} {start_num}]"
            for i, line in enumerate(lines):
                if marker in line:
                    # Extract until the next element or section
                    end_i = i + 1
                    while end_i < len(lines) and not any(
                        marker in lines[end_i] 
                        for marker in ['[SECTION:', '[TABLE', '[LIST', '[PARAGRAPH']
                    ):
                        end_i += 1
                    return "\n".join(lines[i:end_i])
        
        # For paragraph citations
        elif citation_type == CitationType.html_paragraph.value:
            paragraphs = []
            current_paragraph = 0
            
            for line in lines:
                if line.strip().startswith('[Paragraph '):
                    current_paragraph += 1
                    if start_num <= current_paragraph <= end_num:
                        paragraphs.append(line.strip())
            
            return "\n".join(paragraphs)
        
        # For section citations
        elif citation_type == CitationType.html_section.value:
            section_content = []
            in_target_section = False
            current_section = 0
            
            for line in lines:
                if line.strip().startswith('[Section '):
                    current_section += 1
                    if current_section == start_num:
                        in_target_section = True
                        section_content.append(line.strip())
                    elif current_section > end_num:
                        break
                elif in_target_section:
                    if line.strip().startswith('[Section '):
                        break
                    section_content.append(line.strip())
            
            return "\n".join(section_content)
        
        # Fallback for other citation types or if specific handling fails
        return "\n".join(line.strip() for line in lines[max(0, start_num - 1):min(len(lines), end_num)]) 