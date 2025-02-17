from typing import List

# Constants
MAX_LINE_LENGTH = 100
LINE_MARKER_FORMAT = "[LINE {}]"

def add_line_markers(text: str, max_line_length: int = MAX_LINE_LENGTH) -> str:
    """Add line markers to text, wrapping lines at word boundaries near max_line_length.
    
    Args:
        text: The input text to process
        max_line_length: Maximum target length for each line (default: 100)
    
    Returns:
        Text with [LINE X] markers added at the start of each wrapped line
    """
    words = text.split()
    lines: List[str] = []
    current_line: List[str] = []
    current_length = 0
    
    for word in words:
        # Handle words longer than max_line_length
        if len(word) > max_line_length:
            # If we have a partial line, add it first
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []
                current_length = 0
            # Add the long word as its own line
            lines.append(word)
            continue
        
        # Calculate length with new word (including space)
        new_length = current_length + (1 if current_line else 0) + len(word)
        
        if new_length <= max_line_length:
            # Add word to current line
            current_line.append(word)
            current_length = new_length
        else:
            # Line would be too long, start a new one
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
    
    # Add any remaining line
    if current_line:
        lines.append(" ".join(current_line))
    
    # Add line markers
    marked_lines = [
        f"{LINE_MARKER_FORMAT.format(i + 1)} {line}"
        for i, line in enumerate(lines)
    ]
    
    return "\n".join(marked_lines)


def extract_line_numbers(text: str) -> List[int]:
    """Extract all line numbers from a text with [LINE X] markers.
    
    Args:
        text: Text containing [LINE X] markers
    
    Returns:
        List of line numbers found in the text
    """
    import re
    pattern = r"\[LINE (\d+)\]"
    matches = re.finditer(pattern, text)
    return [int(match.group(1)) for match in matches]


def get_text_from_line_numbers(text: str, start_line: int, end_line: int, max_line_length: int = MAX_LINE_LENGTH) -> str:
    """Extract text from the specified line numbers (1-indexed).
    
    Args:
        text: Raw text (will be processed to add line markers)
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed, inclusive)
        max_line_length: Maximum line length for wrapping (default: 100)
    
    Returns:
        Text from the specified line range
    """
    # First, add line markers the same way the AI saw the text
    marked_text = add_line_markers(text, max_line_length=max_line_length)
    
    # Split into lines
    lines = marked_text.split('\n')
    
    # Convert to 0-based indexing for array access
    start_idx = start_line - 1
    end_idx = end_line  # end_line is inclusive
    
    # Validate indices
    if start_idx < 0:
        start_idx = 0
    if end_idx > len(lines):
        end_idx = len(lines)
    if end_idx <= start_idx:
        return ""
    
    print(f"\nDEBUG - Extracting lines {start_idx + 1} to {end_idx}")
    
    # Extract the relevant lines
    selected_lines = lines[start_idx:end_idx]
    print("\nDEBUG - Selected lines before cleaning:")
    print('\n'.join(selected_lines))
    
    # Remove [LINE X] markers and join
    import re
    cleaned_lines = [re.sub(r'\[LINE \d+\] ?', '', line).strip() for line in selected_lines]
    result = ' '.join(line for line in cleaned_lines if line)
    
    print("\nDEBUG - Final cleaned result:")
    print(result)
    
    return result 