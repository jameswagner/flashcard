from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
import logging
from typing import Optional
from datetime import datetime, UTC
import json

from models.source import SourceFile
from models.enums import FileType
from utils.s3 import (
    upload_file,
    generate_s3_key,
    store_html_content,
    store_processed_text as s3_store_processed_text,
)
from utils.html_processing import scrape_url, process_html
from utils.youtube_processing import fetch_transcript
from scripts.get_video_info import get_video_info

logger = logging.getLogger(__name__)

class ContentUploadService:
    def __init__(self, db: Session):
        self.db = db

    async def upload_url(self, url: str, user_id: Optional[str] = None) -> dict:
        """Upload HTML content from a URL and create a database record."""
        logger.info(f"Uploading URL content: {url}")
        
        try:
            # Fetch and process HTML content
            raw_html, title = await scrape_url(url)
            processed_content = process_html(raw_html, title)
            
            # Store both raw and processed content
            raw_key, processed_key = store_html_content(
                raw_html=raw_html,
                processed_json=processed_content.to_json(),
                url=url,
                user_id=user_id
            )
            
            # Create database record
            filename = title or url.split('/')[-1] or 'index.html'
            source_file = SourceFile(
                filename=filename,
                s3_key=raw_key,
                url=url,
                file_type=FileType.HTML.value,
                processed_text_s3_key=processed_key,
                processed_text_type='html_structure'
            )
            self.db.add(source_file)
            self.db.commit()
            self.db.refresh(source_file)
            
            return {"id": source_file.id, "filename": filename}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing URL {url}: {str(e)}", exc_info=True)
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
            file_type=extension,
            processed_text_s3_key=None,  # Initialize as None, will be set during processing
            processed_text_type=None  # Initialize as None, will be set during processing
        )
        self.db.add(source_file)
        self.db.commit()
        self.db.refresh(source_file)
        
        return {"id": source_file.id, "filename": source_file.filename}

    async def upload_youtube_video(
        self, 
        video_id: str, 
        video_title: str = None, 
        description: str = None, 
        user_id: Optional[str] = None
    ) -> dict:
        """Upload YouTube video transcript and create a database record."""
        logger.info(f"Uploading YouTube video transcript: {video_id}")
        
        try:
            # Fetch video metadata from YouTube API
            video_info = get_video_info(video_id)
            if 'error' in video_info:
                logger.error(f"Failed to fetch video info: {video_info['error']}")
                raise HTTPException(status_code=404, detail=f"Could not fetch video info: {video_info['error']}")
            
            # Use provided title/description or ones from API
            actual_title = video_title or video_info['title']
            actual_description = description or video_info['description']
            
            # Fetch transcript - removed await since it's not async
            content = fetch_transcript(video_id, actual_title, actual_description)
            if not content:
                raise HTTPException(status_code=404, detail=f"Could not fetch transcript for video {video_id}")
            
            # Add additional metadata from video_info
            content.channel = video_info['channel']
            content.published_at = video_info['published_at']
            content.duration = video_info['duration']['formatted']
            content.statistics = video_info['statistics']
            
            # Generate S3 key and store content
            s3_key = generate_s3_key(f"{video_id}.json", user_id)
            processed_key = s3_store_processed_text(
                json.dumps(content.to_dict()),
                s3_key,
                processing_type='youtube_transcript'
            )
            
            # Create database record
            source_file = SourceFile(
                filename=f"{actual_title} ({video_id})",
                s3_key=s3_key,
                url=f"https://www.youtube.com/watch?v={video_id}",
                file_type=FileType.YOUTUBE_TRANSCRIPT.value,
                processed_text_s3_key=processed_key,
                processed_text_type='youtube_transcript'
            )
            self.db.add(source_file)
            self.db.commit()
            self.db.refresh(source_file)
            
            return {"id": source_file.id, "filename": source_file.filename}
            
        except Exception as e:
            logger.error(f"Error uploading YouTube video: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error uploading YouTube video: {str(e)}") 