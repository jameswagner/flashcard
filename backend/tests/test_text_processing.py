import pytest
from utils.text_processing import add_line_markers, extract_line_numbers, get_text_from_line_numbers

def test_add_line_markers_basic():
    """Test basic line marking functionality."""
    text = "This is a test."
    result = add_line_markers(text)
    assert result == "[LINE 1] This is a test."

def test_add_line_markers_multiple_lines():
    """Test line wrapping and marking with multiple lines."""
    text = "This is a longer text that should be wrapped into multiple lines based on the length limit."
    result = add_line_markers(text, max_line_length=20)
    lines = result.split('\n')
    assert len(lines) > 1
    assert all(line.startswith("[LINE") for line in lines)

def test_add_line_markers_long_word():
    """Test handling of words longer than max_line_length."""
    text = "This is a supercalifragilisticexpialidocious word."
    result = add_line_markers(text, max_line_length=20)
    assert "supercalifragilisticexpialidocious" in result

def test_add_line_markers_empty():
    """Test handling of empty text."""
    text = ""
    result = add_line_markers(text)
    assert result == ""

def test_extract_line_numbers_basic():
    """Test basic line number extraction."""
    text = "[LINE 1] First line\n[LINE 2] Second line"
    numbers = extract_line_numbers(text)
    assert numbers == [1, 2]

def test_extract_line_numbers_empty():
    """Test line number extraction from text without markers."""
    text = "No line markers here"
    numbers = extract_line_numbers(text)
    assert numbers == []

def test_get_text_from_line_numbers_basic():
    """Test basic text extraction from line numbers."""
    # Create a text that will be wrapped into multiple lines by add_line_markers
    text = "This is a long line that should be wrapped. This is another long line that should also be wrapped."
    max_line_length = 30
    
    # First verify the text is properly marked and wrapped with a small max_line_length
    marked = add_line_markers(text, max_line_length=max_line_length)
    marked_lines = marked.split('\n')
    assert len(marked_lines) >= 3, "Text should be wrapped into multiple lines"
    
    # Now test get_text_from_line_numbers with the same max_line_length
    result = get_text_from_line_numbers(text, 1, 2, max_line_length=max_line_length)
    
    # Get the expected text from the first two marked lines
    expected = ' '.join(
        line.replace("[LINE 1] ", "").replace("[LINE 2] ", "")
        for line in marked_lines[:2]
    )
    
    assert result.strip() == expected.strip()

def test_get_text_from_line_numbers_invalid_range():
    """Test text extraction with invalid line numbers."""
    text = "First line.\nSecond line."
    # Test with line numbers out of range
    result = get_text_from_line_numbers(text, 0, 5)
    # Should return all available text
    assert "First line" in result
    assert "Second line" in result
    
def test_get_text_from_line_numbers_single_line():
    """Test extracting a single line."""
    text = "First line.\nSecond line.\nThird line."
    # When requesting line 2, should only get second line
    result = get_text_from_line_numbers(text, 2, 3)
    # The text should be wrapped and marked, then we extract just line 2
    marked = add_line_markers(text)
    marked_lines = marked.split('\n')
    expected = marked_lines[1].replace("[LINE 2] ", "") if len(marked_lines) > 1 else ""
    assert result.strip() == expected.strip() 