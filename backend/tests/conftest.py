import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sqlalchemy import text
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from database import get_db
from models.base import Base
from main import app

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def test_db():
    # Create engine with special configuration for in-memory SQLite
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create a new session for each test
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop all tables after tests
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(test_db):
    # Override the get_db dependency
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    
    # Create test client
    with TestClient(app) as test_client:
        yield test_client
    
    # Clear dependency override after test
    app.dependency_overrides.clear()

@pytest.fixture
def mock_text_processing():
    """Mock text processing utilities."""
    with patch("routers.ai_generation.get_text_from_line_numbers") as mock_get_text:
        mock_get_text.return_value = "Test citation text"
        yield {
            "get_text": mock_get_text
        }

@pytest.fixture
def mock_s3():
    """Mock S3 operations."""
    with patch("routers.ai_generation.upload_file") as mock_upload, \
         patch("routers.ai_generation.get_file_content") as mock_get_content, \
         patch("routers.ai_generation.generate_s3_key") as mock_generate_key:
        
        mock_upload.return_value = "test_s3_key"
        mock_get_content.return_value = "This is test file content"
        mock_generate_key.return_value = "test_s3_key"
        yield {
            "upload": mock_upload,
            "get_content": mock_get_content,
            "generate_key": mock_generate_key
        }

@pytest.fixture
def mock_ai():
    """Mock AI operations."""
    with patch("routers.ai_generation.create_flashcards_from_text") as mock_create, \
         patch("routers.ai_generation.get_latest_prompt_template") as mock_get_template:
        
        # Set up the create_flashcards_from_text mock
        mock_create.return_value = [
            {
                "front": "Test Front 1",
                "back": "Test Back 1",
                "citations": [[1, 2]]
            },
            {
                "front": "Test Front 2",
                "back": "Test Back 2",
                "citations": [[3, 4]]
            }
        ]
        
        # Create a mock template that matches what we create in the test
        class MockTemplate:
            def __init__(self):
                self.id = 1
                self.name = "Test Template"
                self.version = 1
                self.template = "Test template text"
                self.parameter_schema = {}
                self.model_parameter_schema = {}
                self.is_active = True
                
            def __str__(self):
                return f"MockTemplate(id={self.id}, name={self.name}, active={self.is_active})"
        
        template = MockTemplate()
        print(f"\n=== DEBUG: Created mock template: {template}")
        mock_get_template.return_value = template
        
        yield mock_create

@pytest.fixture
def mock_services(mock_s3, mock_ai, mock_text_processing):
    """Combine all service mocks."""
    return {
        "s3": mock_s3,
        "ai": mock_ai,
        "text": mock_text_processing
    } 