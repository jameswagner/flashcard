from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging
import json
from typing import Optional, Tuple

from models.source import SourceFile
from models.enums import FileType
from utils.s3 import (
    get_file_content,
    store_processed_text as s3_store_processed_text,
    get_processed_text as s3_get_processed_text,
)
from utils.html_processing import process_html, HTMLContent
from utils.youtube_processing import YouTubeContent
from utils.plaintext_processing.processor import process_text

logger = logging.getLogger(__name__)

class ContentProcessingService:
    def __init__(self, db: Session):
        self.db = db
        self._youtube_content_cache = {}

    async def process_content(self, source_file: SourceFile) -> Tuple[str, str]:
        """Process source content based on file type."""
        logger.info(f"Processing source content of type: {source_file.file_type}")
        
        if source_file.file_type == FileType.HTML.value:
            logger.info("Processing HTML content...")
            html_content = await self.process_html_content(source_file)
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
            youtube_content = await self.process_youtube_content(source_file)
            text_content = youtube_content.transcript_text
            content_structure = (
                "The text is a YouTube video transcript with timestamps in seconds. "
                "Citations use video_timestamp type to reference specific moments in the video. "
                "Each citation includes a 20-second chunk of content and its chapter context."
            )
            
        else:  # TXT files
            logger.info("Processing plain text file...")
            text_content = get_file_content(source_file.s3_key)
            
            if not source_file.processed_text_s3_key:
                logger.debug("No processed text found, processing now...")
                processed_text = process_text(text_content)
                processed_key = s3_store_processed_text(processed_text, source_file.s3_key)
                source_file.processed_text_s3_key = processed_key
                source_file.processed_text_type = 'sentences'
                self.db.commit()
            else:
                processed_text = s3_get_processed_text(source_file.processed_text_s3_key)
            
            text_content = processed_text
            content_structure = (
                "The text has been pre-processed to identify sentence boundaries. "
                "Each sentence is numbered starting from 1."
            )
        
        logger.info(f"Processed content length: {len(text_content)} characters")
        return text_content, content_structure

    async def process_html_content(self, source_file: SourceFile) -> HTMLContent:
        """Process HTML content and ensure it's stored properly."""
        logger.info(f"Processing HTML content for source file: {source_file.filename}")
        
        # Get raw HTML and processed content
        raw_html = get_file_content(source_file.s3_key)
        processed_json = s3_get_processed_text(source_file.s3_key, processing_type='html_structure')
        
        if processed_json is None:
            try:
                processed_content = process_html(raw_html, source_file.filename)
                processed_json = processed_content.to_json()
                s3_store_processed_text(processed_json, source_file.s3_key, processing_type='html_structure')
            except Exception as e:
                logger.error(f"Error processing HTML: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        return HTMLContent.from_json(processed_json)

    async def process_youtube_content(self, source_file: SourceFile) -> YouTubeContent:
        """Process YouTube transcript content and ensure it's stored properly."""
        # Check cache first
        if source_file.id in self._youtube_content_cache:
            return self._youtube_content_cache[source_file.id]
        
        try:
            # Get processed content
            processed_json = s3_get_processed_text(source_file.s3_key, processing_type='youtube_transcript')
            
            if not processed_json:
                raise HTTPException(status_code=500, detail="No processed content found")
            
            if isinstance(processed_json, str):
                try:
                    processed_json = json.loads(processed_json)
                except json.JSONDecodeError as e:
                    raise HTTPException(status_code=500, detail="Invalid JSON format")
            
            content = YouTubeContent.from_dict(processed_json)
            
            # Cache the content
            self._youtube_content_cache[source_file.id] = content
            return content
            
        except Exception as e:
            logger.error(f"Error processing YouTube content: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    def clear_youtube_cache(self):
        """Clear the YouTube content cache."""
        self._youtube_content_cache.clear()
        logger.info("Cleared YouTube content cache") 