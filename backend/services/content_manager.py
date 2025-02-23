from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, UTC
import json
from io import BytesIO
import tempfile
import os

from models.source import SourceFile
from models.enums import FileType
from utils.s3 import (
    upload_file,
    generate_s3_key,
    get_s3_body,
    store_processed_text,
    store_html_content,
)
from utils.html_processing import scrape_url, process_html, HTMLContent
from utils.youtube_processing import fetch_transcript, YouTubeContent
from utils.pdf_processing.processor import process_pdf
from scripts.get_video_info import get_video_info
from utils.plaintext_processing.processor import process_text

logger = logging.getLogger(__name__)

class ContentManager:
    """Unified service for handling content upload, processing, and retrieval."""
    
    def __init__(self, db: Session):
        self.db = db
        self._youtube_content_cache = {}  # Add cache for YouTube content
        self._processors = {
            FileType.HTML: self._process_html,
            FileType.YOUTUBE_TRANSCRIPT: self._process_youtube,
            FileType.TXT: self._process_text,
            FileType.PDF: self._process_pdf,  # Add PDF processor
        }
        self._content_structure_descriptions = {
            FileType.HTML: (
                "The text is structured HTML content with sections, paragraphs, tables, and lists. "
                "Each section begins with [Section: heading]. "
                "Content is organized hierarchically with sections containing paragraphs and other elements. "
                "Valid citation types:\n"
                "- section: For citing entire sections with their headings\n"
                "- paragraph: For citing specific paragraphs\n"
                "- table: For citing tables\n"
                "- list: For citing ordered or unordered lists\n"
            ),
            FileType.YOUTUBE_TRANSCRIPT: (
                "The text is a YouTube video transcript with timestamps in seconds. "
                "Valid citation types:\n"
                "- video_timestamp: For citing specific moments (use range for time spans)\n"
                "- video_chapter: For citing entire chapters or sections\n"
                "Each citation should include relevant context like chapter names or topics."
            ),
            FileType.TXT: (
                "The text has been pre-processed to identify paragraph sentence boundaries. "
                "Each sentence and paragraph is numbered starting from 1."
                "Valid citation types:\n"
                "- sentence_range: For citing one or more sentences by their numbers. Use this if a concept does not span 1 or more paragraphs."
                "- paragraph: For citing one or more paragraphs by their numbers. Use this if a concept spans 1 or more paragraphs."
            ),
            FileType.PDF: (
                "The text is extracted from a PDF document with special processing to maintain structure. "
                "IMPORTANT: Only use citation types that match the document's structure. The available types depend on what was successfully extracted:\n"
                "- If sections were found: Sections are marked with [Section X] headers\n"
                "- If paragraphs were found: Paragraphs are marked with [Paragraph X]\n"
                "- All documents have sentence markers: [SENTENCE X]\n\n"
                "Valid citation types (use ONLY if corresponding markers exist in the text):\n"
                "- section: For citing sections (only if [Section X] markers exist)\n"
                "- paragraph: For citing paragraphs (only if [Paragraph X] markers exist)\n"
                "- list: For citing lists (only if [List X] markers exist)\n"
                "- sentence_range: For citing specific sentences \n"
                "- pdf_bbox: For citing specific regions by their bounding box coordinates (advanced use)\n\n"
                "CRITICAL: Check the processed text first and only use citation types that match existing markers. "
                "Using non-existent markers will result in failed citations."
            )
        }

    async def upload_and_process(
        self, 
        file: Optional[UploadFile] = None,
        url: Optional[str] = None,
        video_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> SourceFile:
        """Unified method for uploading and processing content from any source."""
        try:
            if url:
                return await self._handle_url_upload(url, user_id)
            elif video_id:
                return await self._handle_youtube_upload(video_id, user_id)
            elif file:
                return await self._handle_file_upload(file, user_id)
            else:
                raise HTTPException(status_code=400, detail="No content provided")
                
        except Exception as e:
            logger.error(f"Error in upload_and_process: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _handle_url_upload(self, url: str, user_id: Optional[str]) -> SourceFile:
        """Handle URL content upload and processing."""
        raw_html, title = await scrape_url(url)
        
        # Create source file record
        source_file = SourceFile(
            filename=title or url.split('/')[-1] or 'index.html',
            url=url,
            file_type=FileType.HTML.value
        )
        
        # Process and store content
        await self._store_content(source_file, raw_html, user_id)
        return source_file

    async def _handle_youtube_upload(
        self, 
        video_id: str, 
        user_id: Optional[str],
        video_title: Optional[str] = None
    ) -> SourceFile:
        """Handle YouTube video upload and processing."""
        # Fetch video info and transcript
        video_info = get_video_info(video_id)
        if 'error' in video_info:
            raise HTTPException(status_code=404, detail=f"Could not fetch video info: {video_info['error']}")
            
        title = video_title or video_info['title']
        content = fetch_transcript(video_id, title, video_info['description'])
        
        if not content:
            raise HTTPException(status_code=404, detail=f"Could not fetch transcript for video {video_id}")
            
        # Create source file record
        source_file = SourceFile(
            filename=f"{title} ({video_id})",
            url=f"https://www.youtube.com/watch?v={video_id}",
            file_type=FileType.YOUTUBE_TRANSCRIPT.value
        )
        
        # Process and store content
        await self._store_content(source_file, content, user_id)
        return source_file

    async def _handle_file_upload(self, file: UploadFile, user_id: Optional[str]) -> SourceFile:
        """Handle file upload and processing."""
        # Validate file type
        extension = file.filename.lower().split('.')[-1]
        try:
            file_type = FileType(extension)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")
            
        # Create source file record
        source_file = SourceFile(
            filename=file.filename,
            file_type=extension
        )
        
        # Process and store content
        await self._store_content(source_file, file.file, user_id)
        return source_file

    async def _process_text_upload(self, content: Any) -> Tuple[str, str]:
        """Process and store text content.
        
        Args:
            content: File-like object containing text content
            
        Returns:
            Tuple of (raw_key, processed_key)
        """
        if not hasattr(content, 'read'):
            raise HTTPException(status_code=400, detail="Invalid content type for text file upload")
            
        # Read content
        text_content = content.read()
        if isinstance(text_content, bytes):
            text_content = text_content.decode('utf-8')
            
        # Process with sentence markers
        processed_text = process_text(text_content)
        
        return text_content, processed_text

    async def _store_content(
        self, 
        source_file: SourceFile, 
        content: Any,
        user_id: Optional[str]
    ) -> None:
        """Store both raw and processed content."""
        # Generate S3 key for raw content
        source_file.s3_key = generate_s3_key(source_file.filename, user_id)
        
        if source_file.file_type == FileType.HTML.value:
            # Process and store HTML content
            title = source_file.filename.rsplit('.', 1)[0]  # Extract title from filename without extension
            processed_content = process_html(content, title)
            raw_key, processed_key = store_html_content(
                raw_html=content,
                processed_json=processed_content.to_json(),
                url=source_file.url,
                user_id=user_id
            )
            source_file.s3_key = raw_key
            source_file.processed_text_s3_key = processed_key
            source_file.processed_text_type = 'html_structure'
            
        elif source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
            # Store YouTube content
            processed_key = store_processed_text(
                json.dumps(content.to_dict()),
                source_file.s3_key,
                processing_type='youtube_transcript'
            )
            source_file.processed_text_s3_key = processed_key
            source_file.processed_text_type = 'youtube_transcript'
            
        elif source_file.file_type == FileType.TXT.value:
            # Process text content
            raw_text, processed_text = await self._process_text_upload(content)
            
            # Store both versions
            upload_file(BytesIO(raw_text.encode('utf-8')), source_file.s3_key)
            processed_key = store_processed_text(
                processed_text,
                source_file.s3_key,
                processing_type='sentences'
            )
            source_file.processed_text_s3_key = processed_key
            source_file.processed_text_type = 'sentences'
            
        elif source_file.file_type == FileType.PDF.value:
            # For PDFs, we need to save the file temporarily to process it
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                # Read content if it's a file-like object
                if hasattr(content, 'read'):
                    pdf_content = content.read()
                else:
                    pdf_content = content
                
                # Write to temp file
                if isinstance(pdf_content, str):
                    tmp_file.write(pdf_content.encode('utf-8'))
                else:
                    tmp_file.write(pdf_content)
                tmp_file.flush()
                tmp_path = tmp_file.name
            
            try:
                # Process the PDF after the file is closed
                processed_content = process_pdf(tmp_path, source_file.filename)
                
                # Store both versions
                upload_file(BytesIO(pdf_content), source_file.s3_key)
                processed_key = store_processed_text(
                    processed_content.to_json(),
                    source_file.s3_key,
                    processing_type='pdf_structure'
                )
                source_file.processed_text_s3_key = processed_key
                source_file.processed_text_type = 'pdf_structure'
            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {tmp_path}: {e}")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {source_file.file_type}")
        
        # Save to database
        self.db.add(source_file)
        self.db.commit()
        self.db.refresh(source_file)

    async def _process_html(self, content: str) -> str:
        """Process HTML content."""
        processed_content = process_html(content)
        return processed_content.to_json()

    async def _process_youtube(self, content: YouTubeContent) -> str:
        """Process YouTube content."""
        return content.to_json()

    async def _process_text(self, content: str) -> str:
        """Process text content."""
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        return process_text(content)

    async def _process_pdf(self, content: bytes) -> str:
        """Process PDF content."""
        # Create a temporary file to process the PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            tmp_path = tmp_file.name
        
        try:
            # Process the PDF after the file is closed
            processed_content = process_pdf(tmp_path, "document.pdf")
            return processed_content.to_json()
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {tmp_path}: {e}")

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
            
        # Get the structure description
        structure_description = self._content_structure_descriptions.get(
            FileType(source_file.file_type),
            "Plain text content with no specific structure."
        )
        
        return processed_content, structure_description

    async def process_and_store(self, source_file: SourceFile) -> None:
        """Process content and store it in S3 if not already processed."""
        if source_file.processed_text_s3_key:
            return  # Already processed
            
        # Get raw content
        raw_content = get_s3_body(source_file.s3_key)
        if not raw_content:
            raise HTTPException(status_code=404, detail="Source content not found")
            
        # Process the content
        processor = self._processors.get(FileType(source_file.file_type))
        if not processor:
            raise HTTPException(status_code=400, detail=f"No processor for file type: {source_file.file_type}")
            
        processed_content = await processor(raw_content)
        
        # Store processed content
        source_file.processed_text_s3_key = store_processed_text(
            processed_content,
            source_file.s3_key,
            processing_type=source_file.file_type
        )
        source_file.processed_text_type = source_file.file_type
        self.db.commit()

    def clear_youtube_cache(self):
        """Clear the YouTube content cache."""
        self._youtube_content_cache.clear()
        logger.info("Cleared YouTube content cache") 