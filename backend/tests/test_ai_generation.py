import os
import pytest
from fastapi import UploadFile
from io import BytesIO
from models.enums import AIModel, FileType, CitationType
from models.source import SourceFile
from models.set import FlashcardSet
from models.flashcard import Flashcard
from models.prompt import PromptTemplate
import json

def test_upload_source_file(client, test_db, mock_s3):
    """Test uploading a source file."""
    # Create a test file
    content = b"This is a test file content"
    file = BytesIO(content)
    file.name = "test.txt"

    # Upload the file
    response = client.post(
        "/api/ai/upload",
        files={"file": ("test.txt", file, "text/plain")},
        data={"user_id": "test_user"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["filename"] == "test.txt"

    # Verify database record
    source_file = test_db.get(SourceFile, data["id"])
    assert source_file is not None
    assert source_file.filename == "test.txt"
    assert source_file.file_type == FileType.TXT.value

    # Verify S3 upload was called
    mock_s3["upload"].assert_called_once()

def test_upload_invalid_file_type(client):
    """Test uploading a file with unsupported extension."""
    file = BytesIO(b"test content")
    file.name = "test.xyz"

    response = client.post(
        "/api/ai/upload",
        files={"file": ("test.xyz", file, "text/plain")}
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_generate_flashcards(client, test_db, mock_services):
    """Test generating flashcards from a source file."""
    # First upload a file
    content = b"This is a test file content for generating flashcards."
    file = BytesIO(content)
    file.name = "test.txt"

    upload_response = client.post(
        "/api/ai/upload",
        files={"file": ("test.txt", file, "text/plain")}
    )
    source_file_id = upload_response.json()["id"]

    # Create a test prompt template
    template = PromptTemplate(
        name="Test Template",
        version=1,
        template="Test template text",
        parameter_schema={},
        model_parameter_schema={},
        is_active=True
    )
    test_db.add(template)
    test_db.commit()

    # Generate flashcards
    response = client.post(
        f"/api/ai/generate/{source_file_id}",
        data={
            "model": AIModel.GPT_35_TURBO.value,
            "num_cards": 5,
            "user_id": "test_user",
            "title": "Test Set",
            "description": "Test Description"
        }
    )
    if response.status_code != 200:
        print("\nError response:", response.json())
    assert response.status_code == 200
    data = response.json()
    assert "set_id" in data
    assert "num_cards" in data

    # Verify flashcard set was created
    flashcard_set = test_db.get(FlashcardSet, data["set_id"])
    assert flashcard_set is not None
    assert flashcard_set.title == "Test Set"
    assert flashcard_set.description.startswith("Test Description")
    assert flashcard_set.initial_generation_model == AIModel.GPT_35_TURBO.value.lower()
    assert len(flashcard_set.flashcards) == 2  # From mock data

    # Verify AI service was called
    mock_services["ai"].assert_called_once()

    # Verify citations were created
    for card in flashcard_set.flashcards:
        assert len(card.citations) == 1
        citation = card.citations[0]
        assert citation.citation_type == CitationType.line_numbers.value
        assert len(citation.citation_data) == 1

def test_generate_nonexistent_source(client):
    """Test generating flashcards from a nonexistent source file."""
    response = client.post(
        "/api/ai/generate/99999",
        data={
            "model": AIModel.GPT_35_TURBO.value,
            "num_cards": 5
        }
    )
    assert response.status_code == 404
    assert "Source file not found" in response.json()["detail"]

def test_generate_unsupported_model(client, test_db):
    """Test generating flashcards with an unsupported model."""
    # First upload a file
    content = b"This is a test file content."
    file = BytesIO(content)
    file.name = "test.txt"

    upload_response = client.post(
        "/api/ai/upload",
        files={"file": ("test.txt", file, "text/plain")}
    )
    source_file_id = upload_response.json()["id"]

    response = client.post(
        f"/api/ai/generate/{source_file_id}",
        data={
            "model": "unsupported_model",
            "num_cards": 5
        }
    )
    assert response.status_code == 400
    assert "Unsupported model" in response.json()["detail"]

def test_generate_with_model_params(client, test_db, mock_services):
    """Test generating flashcards with custom model parameters."""
    try:
        # Upload a file
        content = b"This is a test file content."
        file = BytesIO(content)
        file.name = "test.txt"

        print("\n=== DEBUG: Starting file upload ===")
        upload_response = client.post(
            "/api/ai/upload",
            files={"file": ("test.txt", file, "text/plain")}
        )
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.json()}"
        source_file_id = upload_response.json()["id"]
        print(f"Upload successful, got source_file_id: {source_file_id}")

        # Create a test prompt template
        print("\n=== DEBUG: Creating prompt template ===")
        template = PromptTemplate(
            name="Test Template",
            version=1,
            template="Test template text",
            parameter_schema={},
            model_parameter_schema={},
            is_active=True
        )
        test_db.add(template)
        test_db.commit()
        test_db.refresh(template)
        print(f"Created template with ID: {template.id}")

        # Generate with custom parameters
        print("\n=== DEBUG: Generating flashcards ===")
        model_params = {"temperature": 0.8}
        response = client.post(
            f"/api/ai/generate/{source_file_id}",
            data={
                "model": AIModel.GPT_35_TURBO.value,
                "num_cards": 5,
                "model_params": json.dumps(model_params),
                "title": "Test Set",
                "description": "Test Description"
            }
        )
        
        if response.status_code != 200:
            print("\nError response:", response.json())
            print("\nTemplate ID:", template.id)
            print("Template active:", template.is_active)
            print("\nModel params sent:", json.dumps(model_params))
            print("Response headers:", response.headers)
            print("\nMock services state:")
            print("AI mock called:", mock_services["ai"].called)
            print("AI mock call args:", mock_services["ai"].call_args if mock_services["ai"].called else None)
            print("S3 mock get_content called:", mock_services["s3"]["get_content"].called)
            print("Text processing add_markers called:", mock_services["text"]["add_markers"].called)
        assert response.status_code == 200

        data = response.json()
        print("\n=== DEBUG: Generation response ===")
        print(f"Response data: {data}")
        
        assert "set_id" in data
        assert "num_cards" in data

        # Verify parameters were saved
        flashcard_set = test_db.get(FlashcardSet, data["set_id"])
        assert flashcard_set is not None
        assert flashcard_set.model_parameters == model_params
        assert flashcard_set.prompt_template_id == template.id

        # Verify AI service was called with correct parameters
        mock_services["ai"].assert_called_once()
        call_args = mock_services["ai"].call_args[1]
        assert call_args["params"]["model_params"] == model_params
    except Exception as e:
        print("\nTest failed with exception:", str(e))
        print("\nMock services state:")
        print("AI mock called:", mock_services["ai"].called)
        print("AI mock call args:", mock_services["ai"].call_args if mock_services["ai"].called else None)
        print("S3 mock get_content called:", mock_services["s3"]["get_content"].called)
        print("Text processing add_markers called:", mock_services["text"]["add_markers"].called)
        raise 