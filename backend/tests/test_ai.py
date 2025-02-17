import pytest
from unittest.mock import patch, MagicMock
from backend.utils.ai_flashcard_creation import get_latest_prompt_template, create_flashcards_from_text
from models.enums import AIModel
from models.prompt import PromptTemplate

def test_get_latest_prompt_template_model_specific(test_db):
    """Test getting a model-specific prompt template."""
    # Create test templates
    template1 = PromptTemplate(
        name="General Template",
        version=1,
        template="General template text",
        parameter_schema={},
        model_parameter_schema={},
        is_active=True
    )
    template2 = PromptTemplate(
        name="GPT-4 Template",
        version=1,
        template="GPT-4 specific template",
        parameter_schema={},
        model_parameter_schema={},
        model_id=AIModel.GPT_4.value,
        is_active=True
    )
    test_db.add(template1)
    test_db.add(template2)
    test_db.commit()

    # Test getting model-specific template
    result = get_latest_prompt_template(test_db, AIModel.GPT_4)
    assert result.name == "GPT-4 Template"
    assert result.model_id == AIModel.GPT_4.value

def test_get_latest_prompt_template_fallback(test_db):
    """Test fallback to general template when no model-specific template exists."""
    template = PromptTemplate(
        name="General Template",
        version=1,
        template="General template text",
        parameter_schema={},
        model_parameter_schema={},
        is_active=True
    )
    test_db.add(template)
    test_db.commit()

    result = get_latest_prompt_template(test_db, AIModel.GPT_4)
    assert result.name == "General Template"
    assert result.model_id is None

def test_get_latest_prompt_template_version(test_db):
    """Test getting the latest version of a template."""
    template1 = PromptTemplate(
        name="Template v1",
        version=1,
        template="Version 1",
        parameter_schema={},
        model_parameter_schema={},
        is_active=True
    )
    template2 = PromptTemplate(
        name="Template v2",
        version=2,
        template="Version 2",
        parameter_schema={},
        model_parameter_schema={},
        is_active=True
    )
    test_db.add(template1)
    test_db.add(template2)
    test_db.commit()

    result = get_latest_prompt_template(test_db)
    assert result.version == 2
    assert result.template == "Version 2"

@patch('utils.ai.ChatOpenAI')
@patch('utils.ai.add_line_markers')
def test_create_flashcards_from_text_gpt(mock_add_markers, mock_chat, test_db):
    """Test creating flashcards using GPT model."""
    # Create test template
    template = PromptTemplate(
        name="Test Template",
        version=1,
        template="Create flashcards from: {source_text}",
        parameter_schema={},
        model_parameter_schema={},
        is_active=True
    )
    test_db.add(template)
    test_db.commit()

    # Mock the line markers
    mock_add_markers.return_value = "Marked text"

    # Mock the AI response
    mock_response = MagicMock()
    mock_response.content = '''[
        {
            "front": "Test Question",
            "back": "Test Answer",
            "citations": [[1, 2]]
        }
    ]'''
    mock_chat.return_value.invoke.return_value = mock_response

    # Test flashcard creation
    result = create_flashcards_from_text(
        text="Test text",
        model=AIModel.GPT_4,
        db=test_db,
        num_cards=1
    )

    assert len(result) == 1
    assert result[0]["front"] == "Test Question"
    assert result[0]["back"] == "Test Answer"
    assert result[0]["citations"] == [[1, 2]]

@patch('utils.ai.ChatOpenAI')
def test_create_flashcards_invalid_response(mock_chat, test_db):
    """Test handling of invalid AI response."""
    # Create test template
    template = PromptTemplate(
        name="Test Template",
        version=1,
        template="Test template",
        parameter_schema={},
        model_parameter_schema={},
        is_active=True
    )
    test_db.add(template)
    test_db.commit()

    # Mock invalid AI response
    mock_response = MagicMock()
    mock_response.content = "Invalid JSON"
    mock_chat.return_value.invoke.return_value = mock_response

    with pytest.raises(ValueError, match="Failed to parse AI response"):
        create_flashcards_from_text(
            text="Test text",
            model=AIModel.GPT_4,
            db=test_db,
            num_cards=1
        )

def test_create_flashcards_no_template(test_db):
    """Test error when no template is available."""
    with pytest.raises(ValueError, match="No suitable prompt template found"):
        create_flashcards_from_text(
            text="Test text",
            model=AIModel.GPT_4,
            db=test_db,
            num_cards=1
        ) 