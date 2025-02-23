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

def split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs based on double newlines or first line indentation.
    
    Args:
        text: Text to split into paragraphs
    
    Returns:
        List of paragraphs
    """
    # First split by double newlines
    paragraphs = re.split(r'\n\s*\n', text)
    
    # Further split by indented first lines (if not already split by newlines)
    result = []
    for p in paragraphs:
        # Check if paragraph starts with indentation
        lines = p.split('\n')
        current_para = []
        for line in lines:
            if line.startswith('    ') or line.startswith('\t'):
                # If we have accumulated lines, add them as a paragraph
                if current_para:
                    result.append('\n'.join(current_para))
                current_para = [line]
            else:
                current_para.append(line)
        # Add the last paragraph
        if current_para:
            result.append('\n'.join(current_para))
    
    # Clean up paragraphs
    result = [p.strip() for p in result]
    result = [p for p in result if p]
    
    return result

def process_paragraph(text: str, paragraph_number: int, start_sentence_number: int = 1) -> List[Tuple[str, int]]:
    """Process a single paragraph, splitting into chunks if too long.
    Each chunk becomes a new paragraph.
    
    Args:
        text: Paragraph text to process
        paragraph_number: The number of this paragraph (unused, as we handle numbering in process_text)
        start_sentence_number: The number to start counting sentences from
    
    Returns:
        List of paragraph texts with their sentence counts
    """
    sentences = split_into_sentences(text)
    current_sentence = start_sentence_number
    result = []
    
    # If more than 15 sentences, split into chunks of 8
    if len(sentences) > 15:
        for i in range(0, len(sentences), 8):
            chunk = sentences[i:i+8]
            marked_sentences = [
                f"[SENTENCE {current_sentence + j}] {sentence}"
                for j, sentence in enumerate(chunk)
            ]
            result.append(("\n".join(marked_sentences), len(chunk)))
            current_sentence += len(chunk)
    else:
        marked_sentences = [
            f"[SENTENCE {current_sentence + i}] {sentence}"
            for i, sentence in enumerate(sentences)
        ]
        result.append(("\n".join(marked_sentences), len(sentences)))
    
    return result

def process_text(text: str) -> str:
    """Process text by splitting into paragraphs and adding markers.
    
    Args:
        text: Raw input text
    
    Returns:
        Text with [PARAGRAPH X] and [SENTENCE Y] markers added
    """
    paragraphs = split_into_paragraphs(text)
    
    processed_paragraphs = []
    current_sentence = 1
    current_paragraph = 1
    
    for paragraph in paragraphs:
        # Process paragraph and get chunks (if any)
        chunks = process_paragraph(paragraph, current_paragraph, current_sentence)
        
        # Add each chunk as a new paragraph
        for chunk_text, sentence_count in chunks:
            processed_paragraphs.append(f"[PARAGRAPH {current_paragraph}]\n{chunk_text}")
            current_sentence += sentence_count
            current_paragraph += 1
    
    return "\n\n".join(processed_paragraphs)

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

def extract_paragraph_numbers(text: str) -> List[int]:
    """Extract all paragraph numbers from a text with [PARAGRAPH X] markers.
    
    Args:
        text: Text containing [PARAGRAPH X] markers
    
    Returns:
        List of paragraph numbers found in the text
    """
    pattern = r"\[PARAGRAPH (\d+)\]"
    matches = re.finditer(pattern, text)
    return [int(match.group(1)) for match in matches]

if __name__ == "__main__":
    import os
    
    # Get the directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "barnaby.txt")
    
    print("Processing Barnaby.txt...\n")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print("Original paragraphs:")
    paragraphs = split_into_paragraphs(text)
    print(f"Found {len(paragraphs)} paragraphs")
    for i, p in enumerate(paragraphs, 1):
        sentences = split_into_sentences(p)
        print(f"Paragraph {i}: {len(sentences)} sentences")
    print("\n" + "="*80 + "\n")
    
    print("Processed text:")
    processed = process_text(text)
    print(processed) 