from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
import json
import logging
import traceback
from datetime import datetime, UTC
from pydantic import BaseModel, HttpUrl

from database import get_db
from services.content_manager import ContentManager
from services.ai_flashcard import AIFlashcardService
from api.models.requests.ai_generation import (
    FlashcardGenerationRequest,
    URLUploadRequest,
    SourceFileUploadRequest,
    YouTubeUploadRequest
)
from api.models.responses.ai_generation import SourceFileUploadResponse, FlashcardGenerationResponse

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter()

@router.post("/upload/youtube", response_model=SourceFileUploadResponse)
async def upload_youtube_video(
    request: YouTubeUploadRequest,
    db: Session = Depends(get_db)
):
    """Upload a YouTube video transcript and create a database record."""
    logger.info(f"Received YouTube upload request for video: {request.video_id}")
    
    try:
        content_manager = ContentManager(db)
        source_file = await content_manager.upload_and_process(
            video_id=request.video_id,
            user_id=request.user_id
        )
        
        logger.info(f"Successfully processed YouTube video {request.video_id}")
        return {"id": source_file.id, "filename": source_file.filename}
        
    except Exception as e:
        logger.error(f"Error processing YouTube video {request.video_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process YouTube video: {str(e)}"
        )

@router.post("/upload", response_model=SourceFileUploadResponse)
async def upload_source_file(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a source file to S3 and create a database record."""
    content_manager = ContentManager(db)
    source_file = await content_manager.upload_and_process(file=file, user_id=user_id)
    return {"id": source_file.id, "filename": source_file.filename}

@router.post("/upload/url", response_model=SourceFileUploadResponse)
async def upload_url(
    request: URLUploadRequest,
    db: Session = Depends(get_db)
):
    """Upload content from a URL and create a database record."""
    content_manager = ContentManager(db)
    source_file = await content_manager.upload_and_process(url=str(request.url), user_id=request.user_id)
    return {"id": source_file.id, "filename": source_file.filename}

@router.post("/generate/{source_file_id}", response_model=FlashcardGenerationResponse)
async def generate_flashcards(
    source_file_id: int,
    model: str = Form(...),
    num_cards: int = Form(10),
    user_id: Optional[str] = Form(None),
    model_params: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    use_sentences: bool = Form(True),
    db: Session = Depends(get_db)
):
    """Generate flashcards from a source file using AI."""
    # Parse model parameters if provided
    parsed_model_params = None
    if model_params:
        try:
            parsed_model_params = json.loads(model_params)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid model parameters JSON")
    
    # Create request model
    generation_request = FlashcardGenerationRequest(
        model=model,
        num_cards=num_cards,
        user_id=user_id,
        model_params=parsed_model_params,
        title=title,
        description=description,
        use_sentences=use_sentences
    )
    
    # Initialize services
    content_manager = ContentManager(db)
    ai_flashcard_service = AIFlashcardService(db, content_manager)
    
    return await ai_flashcard_service.generate_flashcards(source_file_id, generation_request) 