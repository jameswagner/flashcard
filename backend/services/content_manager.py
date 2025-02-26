from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
import logging
from typing import Optional, Tuple, Dict, Any, List, Protocol
from datetime import datetime, UTC
import json
from io import BytesIO
import tempfile
import os
from dataclasses import dataclass
from pydantic import HttpUrl

from models.source import SourceFile
from models.enums import FileType
from utils.s3 import (
    upload_file,
    generate_s3_key,
    get_s3_body,
    store_processed_text,
    store_html_content,
)
from utils.html_processing import scrape_url, process_html, HTMLContent, HTMLProcessor
from utils.youtube_processing import fetch_transcript, YouTubeContent, YouTubeProcessor, get_video_info
from utils.pdf_processing.processor import PDFProcessor
from utils.plaintext_processing.processor import PlainTextProcessor
from utils.image_processing.processor import ImageProcessor
from utils.citation_processing.image_citation_processor import ImageCitationProcessor
from utils.citation_processing.text_citation_processor import TextCitationProcessor
from utils.citation_processing.html_citation_processor import HTMLCitationProcessor
from utils.citation_processing.pdf_citation_processor import PDFCitationProcessor
from utils.citation_processing.youtube_citation_processor import YouTubeCitationProcessor

logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    raw_content: Any
    processed_content: Any
    raw_key: str
    processed_key: str
    processing_type: str

class ContentProcessor:
    """Internal processor for handling different content types."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._processors = {
            FileType.TXT.value: PlainTextProcessor(),
            FileType.HTML.value: HTMLProcessor(),
            FileType.PDF.value: PDFProcessor(),
            FileType.IMAGE.value: ImageProcessor(),
            FileType.YOUTUBE_TRANSCRIPT.value: YouTubeProcessor(),
        }
        
        self._citation_processors = {
            FileType.TXT.value: TextCitationProcessor(),
            FileType.HTML.value: HTMLCitationProcessor(),
            FileType.PDF.value: PDFCitationProcessor(),
            FileType.IMAGE.value: ImageCitationProcessor(),
            FileType.YOUTUBE_TRANSCRIPT.value: YouTubeCitationProcessor(),
        }
    
    def _get_processor(self, file_type: str):
        """Get the appropriate processor for a file type."""
        processor = self._processors.get(file_type)
        if not processor:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
        return processor

    async def process_and_store(
        self,
        content: Any,
        source_file: SourceFile,
        user_id: Optional[str]
    ) -> ProcessingResult:
        """Process and store content based on file type."""
        processor = self._get_processor(source_file.file_type)
        
        try:
            # Handle content based on type
            if source_file.file_type in [FileType.IMAGE.value, FileType.PDF.value]:
                # For binary content (images and PDFs), keep as bytes
                if hasattr(content, 'read'):
                    content = content.read()
            else:
                # For text-based content, convert to string
                if hasattr(content, 'read'):
                    content = content.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
            
            # For PDFs, we need to save to a temporary file since the processor expects a file path
            pdf_temp_path = None
            if source_file.file_type == FileType.PDF.value:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(content)
                    pdf_temp_path = tmp_file.name
                    content = pdf_temp_path  # Pass the temporary file path to the processor
            
            # Process content
            structured_json = processor.to_structured_json(content)
            
            # Store content
            source_file.s3_key = generate_s3_key(source_file.filename, user_id)
            
            # Store only the structured JSON (for citations and prompt text generation)
            json_key = store_processed_text(
                json.dumps(structured_json),
                source_file.s3_key,
                processing_type=f'{source_file.file_type}_structure'
            )
            
            # Don't store prompt text in S3, it will be generated on demand
            # Update the source file to point to the JSON structure
            return ProcessingResult(
                raw_content=content,
                processed_content=structured_json,
                raw_key=source_file.s3_key,
                processed_key=json_key,  # Use the JSON key as the primary processed key
                processing_type=f'{source_file.file_type}_structure'
            )
            
        finally:
            # Clean up temporary PDF file if it exists
            if pdf_temp_path and os.path.exists(pdf_temp_path):
                try:
                    os.unlink(pdf_temp_path)
                except Exception as e:
                    self.logger.warning(f"Failed to clean up temporary PDF file {pdf_temp_path}: {e}")

class ContentManager:
    """Unified service for handling content upload, processing, and retrieval."""
    
    def __init__(self, db: Session):
        self.db = db
        self._youtube_content_cache = {}
        self._processor = ContentProcessor()  # New processor instance

    async def upload_and_process(
        self, 
        file: Optional[UploadFile] = None,
        url: Optional[str] = None,
        video_id: Optional[str] = None,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> SourceFile:
        """Unified method for uploading and processing content from any source."""
        try:
            if url:
                return await self._handle_url_upload(url, user_id, title, description)
            elif video_id:
                return await self._handle_youtube_upload(video_id, user_id, title, description)
            elif file:
                return await self._handle_file_upload(file, user_id, title, description)
            else:
                raise HTTPException(status_code=400, detail="No content provided")
                
        except Exception as e:
            logger.error(f"Error in upload_and_process: {str(e)}")
            # Wrap internal errors in HTTPException if they aren't already
            if not isinstance(e, HTTPException):
                raise HTTPException(status_code=500, detail=str(e))
            raise

    async def _handle_url_upload(
        self, 
        url: str, 
        user_id: Optional[str],
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> SourceFile:
        """Handle URL content upload and processing."""
        raw_html, fetched_title = await scrape_url(url)
        
        # Create source file record
        source_file = SourceFile(
            filename=title or fetched_title or url.split('/')[-1] or 'index.html',
            url=url,
            file_type=FileType.HTML.value,
            description=description
        )
        
        # Process and store content
        await self._store_content(source_file, raw_html, user_id)
        return source_file

    async def _handle_youtube_upload(
        self, 
        video_id: str, 
        user_id: Optional[str],
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> SourceFile:
        """Handle YouTube video upload and processing."""
        logger.info(f"Handling YouTube upload for video ID: {video_id}")
        
        # Fetch video info and transcript
        logger.info(f"Fetching video info for {video_id}")
        video_info = get_video_info(video_id)
        if 'error' in video_info:
            logger.error(f"Error fetching video info: {video_info['error']}")
            raise HTTPException(status_code=404, detail=f"Could not fetch video info: {video_info['error']}")
            
        actual_title = title or video_info['title']
        actual_description = description or video_info['description']
        logger.info(f"Using title: '{actual_title}' and description length: {len(actual_description)} chars")
        
        # Fetch transcript and enhance it with video metadata
        logger.info(f"Fetching transcript for video {video_id}")
        content = fetch_transcript(
            video_id, 
            actual_title, 
            actual_description, 
            existing_chapters=video_info.get('chapters')
        )
        
        if not content:
            logger.error(f"Failed to fetch transcript for video {video_id}")
            raise HTTPException(status_code=404, detail=f"Could not fetch transcript for video {video_id}")
        
        # Enhance content with additional metadata from video_info
        logger.info("Enhancing content with additional metadata from video_info")
        if isinstance(content, YouTubeContent):
            content.channel = video_info.get('channel')
            content.published_at = video_info.get('published_at')
            # Get the formatted duration from the duration object
            content.duration = video_info.get('duration', {}).get('formatted')
            content.statistics = {
                'views': video_info.get('statistics', {}).get('views'),
                'likes': video_info.get('statistics', {}).get('likes'),
                'comments': video_info.get('statistics', {}).get('comments'),
                'duration_seconds': video_info.get('duration', {}).get('seconds'),
                'formatted_duration': video_info.get('duration', {}).get('formatted'),
                'chapters': video_info.get('chapters', [])
            }
            logger.info(f"Added metadata: channel={content.channel}, duration={content.duration}, views={content.statistics.get('views')}")
            
        # Create source file record
        logger.info(f"Creating source file record for video {video_id}")
        source_file = SourceFile(
            filename=f"{actual_title} ({video_id})",
            url=f"https://www.youtube.com/watch?v={video_id}",
            file_type=FileType.YOUTUBE_TRANSCRIPT.value,
            description=actual_description
        )
        
        # Process and store content
        logger.info(f"Processing and storing content for video {video_id}")
        await self._store_content(source_file, content, user_id)
        logger.info(f"Successfully processed YouTube video {video_id}")
        return source_file

    async def _handle_file_upload(
        self, 
        file: UploadFile, 
        user_id: Optional[str],
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> SourceFile:
        """Handle file upload and processing."""
        # Validate file type
        extension = file.filename.lower().split('.')[-1]
        
        # Map image extensions to FileType.IMAGE
        image_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
        if extension in image_extensions:
            file_type = FileType.IMAGE.value
        else:
            try:
                file_type = FileType(extension).value
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")
            
        # Create source file record
        source_file = SourceFile(
            filename=title or file.filename,
            file_type=file_type,
            description=description
        )
        
        # Process and store content
        await self._store_content(source_file, file.file, user_id)
        return source_file

    async def _store_content(
        self, 
        source_file: SourceFile, 
        content: Any,
        user_id: Optional[str]
    ) -> None:
        """Store both raw and processed content."""
        # Use the new processor
        result = await self._processor.process_and_store(content, source_file, user_id)
        
        # Update source file with results
        source_file.s3_key = result.raw_key
        source_file.processed_text_s3_key = result.processed_key
        source_file.processed_text_type = result.processing_type
        
        # Save to database
        self.db.add(source_file)
        self.db.commit()
        self.db.refresh(source_file)

    def get_processed_content(self, source_file: SourceFile) -> Optional[str]:
        """Retrieve processed content for a source file."""
        if not source_file.processed_text_s3_key:
            return None
        return get_s3_body(source_file.processed_text_s3_key)

    async def process_content(self, source_file: SourceFile) -> Tuple[str, str]:
        """Process source content and return both content and structure description.
        
        Args:
            source_file: The source file to process
            
        Returns:
            Tuple of (processed_content, content_structure_description)
        """
        # Get or process the content
        if not source_file.processed_text_s3_key:
            await self.process_and_store(source_file)
            
        processed_content = self.get_processed_content(source_file)
        if not processed_content:
            raise HTTPException(status_code=404, detail="Processed content not found")
            
        # Get the structure description from FileType enum
        file_type = FileType(source_file.file_type)
        structure_description = file_type.structure_description
        
        return processed_content, structure_description

    async def process_and_store(self, source_file: SourceFile) -> None:
        """Process content and store it in S3 if not already processed."""
        if source_file.processed_text_s3_key:
            return  # Already processed
            
        # Get raw content
        raw_content = get_s3_body(source_file.s3_key)
        if not raw_content:
            raise HTTPException(status_code=404, detail="Source content not found")
            
        # Process using the new processor
        result = await self._processor.process_and_store(raw_content, source_file, None)
        
        # Update source file with results
        source_file.processed_text_s3_key = result.processed_key
        source_file.processed_text_type = result.processing_type
        self.db.commit()

    def clear_youtube_cache(self):
        """Clear the YouTube content cache."""
        self._youtube_content_cache.clear()
        logger.info("Cleared YouTube content cache") 