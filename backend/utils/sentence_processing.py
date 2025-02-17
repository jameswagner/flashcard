from typing import List, Tuple
import re
import nltk
from nltk.tokenize import sent_tokenize

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using NLTK's sentence tokenizer.
    
    Args:
        text: Text to split into sentences
    
    Returns:
        List of sentences
    """    
    # Split into sentences
    sentences = sent_tokenize(text)
    
    # Clean up sentences
    sentences = [s.strip() for s in sentences]
    sentences = [s for s in sentences if s]  # Remove empty sentences
    
    return sentences

def add_sentence_markers(text: str) -> str:
    """Add sentence markers to text for AI processing.
    
    Args:
        text: Raw input text
    
    Returns:
        Text with [SENTENCE X] markers added at the start of each sentence
    """
    sentences = split_into_sentences(text)
    marked_sentences = [
        f"[SENTENCE {i + 1}] {sentence}"
        for i, sentence in enumerate(sentences)
    ]
    return "\n".join(marked_sentences)

def get_text_from_sentence_numbers(text: str, start_sentence: int, end_sentence: int) -> str:
    """Extract text from the specified sentence numbers (1-indexed).
    
    Args:
        text: Raw text (will be processed to identify sentences)
        start_sentence: Starting sentence number (1-indexed)
        end_sentence: Ending sentence number (1-indexed, inclusive)
    
    Returns:
        Text from the specified sentence range
    """
    sentences = split_into_sentences(text)
    
    # Convert to 0-based indexing for array access
    start_idx = start_sentence - 1
    end_idx = end_sentence  # end_sentence is inclusive
    
    # Validate indices
    if start_idx < 0:
        start_idx = 0
    if end_idx > len(sentences):
        end_idx = len(sentences)
    if end_idx <= start_idx:
        return ""
    
    # Extract and join the relevant sentences
    selected_sentences = sentences[start_idx:end_idx]
    return " ".join(selected_sentences)

def extract_sentence_numbers(text: str) -> List[int]:
    """Extract all sentence numbers from a text with [SENTENCE X] markers.
    
    Args:
        text: Text containing [SENTENCE X] markers
    
    Returns:
        List of sentence numbers found in the text
    """
    pattern = r"\[SENTENCE (\d+)\]"
    matches = re.finditer(pattern, text)
    return [int(match.group(1)) for match in matches] 