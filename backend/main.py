from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from config.logging import setup_logging
from config.env import settings, load_active_scoring_config
from routers import flashcard_sets, flashcards, ai_generation, study_sessions
from utils.ai_scoring.model_manager import ModelManager

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version
)

# Initialize AI models at startup
@app.on_event("startup")
async def startup_event():
    """Load configurations and initialize services on startup."""
    try:
        logger.info("Loading active scoring configuration...")
        load_active_scoring_config()
        
        logger.info("Initializing AI models...")
        model_manager = ModelManager()
        await model_manager.initialize()
        logger.info("AI models initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize server: {str(e)}")
        # Re-raise to prevent server from starting with uninitialized models
        raise

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(flashcard_sets.router, prefix="/api/flashcard-sets", tags=["flashcard-sets"])
app.include_router(flashcards.router, prefix="/api/flashcards", tags=["flashcards"])
app.include_router(ai_generation.router, prefix="/api/ai", tags=["ai"])
app.include_router(study_sessions.router, prefix="/api/study-sessions", tags=["study-sessions"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Flashcards API"}

if __name__ == "__main__":
    logger.info("Starting Flashcards API server")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 