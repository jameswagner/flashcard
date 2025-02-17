from pydantic_settings import BaseSettings
from pydantic import Field
from models.scoring_config import ScoringConfig
from typing import Optional
from sqlalchemy.orm import Session
from database import get_db

class TextProcessingConfig(BaseSettings):
    """Configuration for text processing and chunking."""
    max_tokens_per_chunk: int = Field(
        default=10000,
        description="Maximum number of tokens per chunk for text processing"
    )
    overlap_tokens: int = Field(
        default=1000,
        description="Number of tokens to overlap between chunks"
    )
    max_line_length: int = Field(
        default=100,
        description="Maximum line length for text wrapping"
    )

class Settings(BaseSettings):
    # Database settings
    database_url: str = Field(
        default="sqlite:///./flashcards.db",
        description="Database connection URL"
    )
    
    # API settings
    api_title: str = Field(
        default="Flashcards API",
        description="API title for documentation"
    )
    api_description: str = Field(
        default="API for managing flashcards and study sessions",
        description="API description for documentation"
    )
    api_version: str = Field(
        default="1.0.0",
        description="API version"
    )
    
    # Scoring settings
    active_scoring_config_id: Optional[int] = Field(
        default=None,
        description="ID of the active scoring configuration in the database"
    )
    scoring: ScoringConfig = Field(
        default_factory=ScoringConfig,
        description="Active scoring configuration"
    )
    
    # Text processing settings
    text_processing: TextProcessingConfig = Field(
        default_factory=TextProcessingConfig,
        description="Text processing configuration"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        extra = "ignore"  # Allow extra fields in environment without validation errors

settings = Settings()

def load_active_scoring_config():
    """
    Load the active scoring configuration from the database into environment settings.
    Should be called during application startup.
    """
    from models.scoring_config import DBScoringConfig
    
    db = next(get_db())
    try:
        # Get most recent active config
        active_config = db.query(DBScoringConfig)\
            .filter_by(is_active=True)\
            .order_by(DBScoringConfig.created_at.desc())\
            .first()
        
        if active_config:
            # Update settings
            settings.active_scoring_config_id = active_config.id
            settings.scoring = active_config.to_config()
            print(f"Loaded active scoring config {active_config.id} (version {active_config.version})")
        else:
            # Create initial config from default settings
            new_config = DBScoringConfig.from_config(
                settings.scoring,
                version="1.0.0",
                description="Initial configuration"
            )
            new_config.is_active = True
            db.add(new_config)
            db.commit()
            db.refresh(new_config)
            
            settings.active_scoring_config_id = new_config.id
            print(f"Created initial scoring config {new_config.id}")
    
    except Exception as e:
        print(f"Error loading scoring config: {str(e)}")
        # Continue with default settings
    finally:
        db.close() 