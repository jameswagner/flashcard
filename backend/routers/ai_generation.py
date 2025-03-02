from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple, Literal
import json
import logging
import traceback
from datetime import datetime, UTC
from pydantic import BaseModel, HttpUrl, Field

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

# Initialize router
router = APIRouter()

# New request models for unified upload
class SourceUpload(BaseModel):
    source_type: Literal["file", "url", "youtube"] = Field(..., description="Type of source being uploaded")
    url: Optional[HttpUrl] = None
    video_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

class UnifiedUploadRequest(BaseModel):
    sources: List[SourceUpload]
    user_id: Optional[str] = None

# Dependency injection for services
def get_content_manager(db: Session = Depends(get_db)) -> ContentManager:
    return ContentManager(db)

def get_ai_flashcard_service(
    content_manager: ContentManager = Depends(get_content_manager),
    db: Session = Depends(get_db)
) -> AIFlashcardService:
    return AIFlashcardService(db, content_manager)

@router.post("/upload", response_model=List[SourceFileUploadResponse])
async def unified_upload(
    request: str = Form(..., description="JSON string of UnifiedUploadRequest"),
    files: List[UploadFile] = File(None),
    content_manager: ContentManager = Depends(get_content_manager),
    db: Session = Depends(get_db)
):
    """Unified upload endpoint supporting multiple sources."""
    try:
        # Parse the request JSON string
        request_data = UnifiedUploadRequest.parse_raw(request)
        logger.info(f"Received upload request with {len(request_data.sources)} sources")
    except Exception as e:
        logger.error(f"Failed to parse request data: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid request format")
    
    try:
        uploaded_sources = []
        
        for source in request_data.sources:
            file = None
            if source.source_type == "file":
                # For now, since we're only handling single file uploads from FE,
                # we can assume files[0]. In the future, we'll need to match files
                # to their corresponding source entries
                if not files or not files[0]:
                    raise HTTPException(
                        status_code=400,
                        detail="File upload requested but no file provided"
                    )
                file = files[0]
            
            source_file = await content_manager.upload_and_process(
                file=file,
                url=str(source.url) if source.url else None,
                video_id=source.video_id,
                user_id=request_data.user_id,
                title=source.title,
                description=source.description
            )
            
            uploaded_sources.append({
                "id": source_file.id,
                "filename": source_file.filename,
                "source_type": source.source_type
            })
            
        logger.info(f"Successfully processed {len(uploaded_sources)} uploads")
        return uploaded_sources
        
    except Exception as e:
        logger.error(f"Error processing uploads: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process uploads: {str(e)}"
        )

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
    selected_content: Optional[str] = Form(None),
    ai_flashcard_service: AIFlashcardService = Depends(get_ai_flashcard_service)
):
    """Generate flashcards from a source file using AI."""
    # Parse model parameters if provided
    parsed_model_params = None
    if model_params:
        try:
            parsed_model_params = json.loads(model_params)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid model parameters JSON")
    
    # Parse selected content if provided
    parsed_selected_content = None
    if selected_content:
        try:
            parsed_selected_content = json.loads(selected_content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid selected content JSON")
    
    # Create request model
    generation_request = FlashcardGenerationRequest(
        model=model,
        num_cards=num_cards,
        user_id=user_id,
        model_params=parsed_model_params,
        title=title,
        description=description,
        use_sentences=use_sentences,
        selected_content=parsed_selected_content
    )
    
    return await ai_flashcard_service.generate_flashcards(source_file_id, generation_request) 