from typing import List, Dict, Any
import tiktoken
from models.enums import AIModel
from utils.html_processing import HTMLContent
from config.env import settings
import re

def count_tokens(text: str, model: AIModel = AIModel.GPT4O_MINI) -> int:
    """Count tokens for a given text using the appropriate tokenizer.
    
    Args:
        text: The text to count tokens for
        model: The AI model to use for token counting
        
    Returns:
        Number of tokens in the text
    """
    # For GPT-4-Turbo and similar models
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(text))

def chunk_text(
    text: str,
    max_tokens: int = None,
    overlap_tokens: int = None,
    model: AIModel = AIModel.GPT4O_MINI
) -> List[str]:
    """Split text into chunks while respecting sentence markers.
    
    Args:
        text: The text to chunk (with [SENTENCE X] markers)
        max_tokens: Maximum tokens per chunk (defaults to config value)
        overlap_tokens: Number of tokens to overlap between chunks (defaults to config value)
        model: The AI model to use for token counting
        
    Returns:
        List of text chunks, each preserving sentence markers
    """
    # Use config values if not specified
    if max_tokens is None:
        max_tokens = settings.text_processing.max_tokens_per_chunk
    if overlap_tokens is None:
        overlap_tokens = settings.text_processing.overlap_tokens
    
    # Initialize chunks list
    chunks = []
    
    # Get encoding for token counting
    encoding = tiktoken.encoding_for_model("gpt-4")
    
    # Split text into marked sentences
    sentences = [s.strip() for s in text.split('\n') if s.strip()]
    
    # Initialize first chunk
    current_chunk = []
    current_tokens = 0
    
    for i, sentence in enumerate(sentences):
        # Skip empty sentences
        if not sentence:
            continue
            
        # Count tokens in this sentence
        sentence_tokens = len(encoding.encode(sentence))
        
        # If this single sentence is too long, we have to split it
        # (this should be rare since we're using sentence markers)
        if sentence_tokens > max_tokens:
            print(f"WARNING: Found very long sentence ({sentence_tokens} tokens)")
            if current_chunk:  # Save current chunk first
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_tokens = 0
            chunks.append(sentence)  # Add long sentence as its own chunk
            continue
            
        # If adding this sentence would exceed max tokens, save current chunk
        if current_tokens + sentence_tokens > max_tokens and current_chunk:
            # Join current chunk sentences with newlines
            chunks.append('\n'.join(current_chunk))
            
            # Start new chunk with overlap
            # Take the last few sentences that fit within overlap_tokens
            overlap_chunk = []
            overlap_tokens_count = 0
            
            # Work backwards through current chunk to build overlap
            for prev_sentence in reversed(current_chunk):
                prev_tokens = len(encoding.encode(prev_sentence))
                if overlap_tokens_count + prev_tokens <= overlap_tokens:
                    overlap_chunk.insert(0, prev_sentence)
                    overlap_tokens_count += prev_tokens
                else:
                    break
            
            # Start new chunk with overlap sentences
            current_chunk = overlap_chunk
            current_tokens = overlap_tokens_count
        
        # Add sentence to current chunk
        current_chunk.append(sentence)
        current_tokens += sentence_tokens
        
        # Print progress for long texts
        if i % 100 == 0:
            print(f"Processed {i}/{len(sentences)} sentences...")
    
    # Add the last chunk if there's anything left
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    # Print chunk statistics
    total_tokens = sum(len(encoding.encode(chunk)) for chunk in chunks)
    print(f"\nChunking Statistics:")
    print(f"Total sentences: {len(sentences)}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Total tokens: {total_tokens}")
    print(f"Average tokens per chunk: {total_tokens / len(chunks):.0f}")
    
    return chunks

def merge_flashcard_results(chunk_results: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Merge flashcards generated from different chunks.
    
    Args:
        chunk_results: List of flashcard lists, one per chunk
        
    Returns:
        Merged list of flashcards
    """
    # For now, simply concatenate all results
    # Deduplication logic can be added later
    merged_results = []
    for chunk_cards in chunk_results:
        merged_results.extend(chunk_cards)
    
    return merged_results

def chunk_html_content(
    content: HTMLContent,
    max_tokens: int = None,
    overlap_tokens: int = None,
    model: AIModel = AIModel.GPT4O_MINI
) -> List[str]:
    """Split HTML content into chunks while respecting section and element boundaries.
    
    Args:
        content: HTMLContent object containing structured content
        max_tokens: Maximum tokens per chunk (defaults to config value)
        overlap_tokens: Number of tokens to overlap between chunks (defaults to config value)
        model: The AI model to use for token counting
        
    Returns:
        List of text chunks, each preserving HTML structure
    """
    # Use config values if not specified
    if max_tokens is None:
        max_tokens = settings.text_processing.max_tokens_per_chunk
    if overlap_tokens is None:
        overlap_tokens = settings.text_processing.overlap_tokens
    
    chunks = []
    encoding = tiktoken.encoding_for_model("gpt-4")
    
    current_chunk = []
    current_tokens = 0
    current_section_idx = 0
    
    while current_section_idx < len(content.sections):
        section = content.sections[current_section_idx]
        section_text = f"[Section: {section.heading}]\n" + "\n".join(section.paragraphs)
        section_tokens = len(encoding.encode(section_text))
        
        # If a single section is too big, we need to split its paragraphs
        if section_tokens > max_tokens:
            # First, add any complete sections we have
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_tokens = 0
            
            # Now split this large section
            section_chunk = []
            section_chunk_tokens = len(encoding.encode(f"[Section: {section.heading}]\n"))
            
            for para in section.paragraphs:
                para_tokens = len(encoding.encode(para))
                if section_chunk_tokens + para_tokens > max_tokens and section_chunk:
                    # Complete this chunk
                    chunks.append(f"[Section: {section.heading}]\n" + "\n".join(section_chunk))
                    section_chunk = []
                    section_chunk_tokens = len(encoding.encode(f"[Section: {section.heading}]\n"))
                
                section_chunk.append(para)
                section_chunk_tokens += para_tokens
            
            # Add any remaining paragraphs
            if section_chunk:
                chunks.append(f"[Section: {section.heading}]\n" + "\n".join(section_chunk))
            
            current_section_idx += 1
            continue
        
        # If adding this section would exceed max tokens, save current chunk
        if current_tokens + section_tokens > max_tokens and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            
            # Start new chunk with overlap - take the last section if it fits
            if current_tokens <= overlap_tokens:
                current_chunk = [current_chunk[-1]]
                current_tokens = len(encoding.encode(current_chunk[-1]))
            else:
                current_chunk = []
                current_tokens = 0
        
        # Add section to current chunk
        current_chunk.append(section_text)
        current_tokens += section_tokens
        current_section_idx += 1
    
    # Add the last chunk if there's anything left
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    
    # Print chunk statistics
    total_tokens = sum(len(encoding.encode(chunk)) for chunk in chunks)
    print(f"\nHTML Chunking Statistics:")
    print(f"Total sections: {len(content.sections)}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Total tokens: {total_tokens}")
    print(f"Average tokens per chunk: {total_tokens / len(chunks):.0f}")
    
    return chunks

def chunk_youtube_transcript(
    text: str,
    max_tokens: int = None,
    overlap_tokens: int = None,
    model: AIModel = AIModel.GPT4O_MINI
) -> List[str]:
    """Split YouTube transcript into chunks while respecting timestamp markers.
    
    Args:
        text: The transcript text with [start_time-end_time] markers
        max_tokens: Maximum tokens per chunk (defaults to config value)
        overlap_tokens: Number of tokens to overlap between chunks (defaults to config value)
        model: The AI model to use for token counting
        
    Returns:
        List of text chunks, each preserving timestamp markers
    """
    # Use config values if not specified
    if max_tokens is None:
        max_tokens = settings.text_processing.max_tokens_per_chunk
    if overlap_tokens is None:
        overlap_tokens = settings.text_processing.overlap_tokens
    
    # Initialize chunks list
    chunks = []
    
    # Get encoding for token counting
    encoding = tiktoken.encoding_for_model("gpt-4")
    
    # Split text into segments (each starting with a timestamp)
    # Use positive lookbehind to ensure we don't split within timestamp markers
    segments = re.split(r'(?<=\])\s*(?=\[\d+\.\d+s-\d+\.\d+s\])', text)
    segments = [s.strip() for s in segments if s.strip()]
    
    # Initialize first chunk
    current_chunk = []
    current_tokens = 0
    
    for i, segment in enumerate(segments):
        # Skip empty segments
        if not segment:
            continue
            
        # Ensure segment starts with a timestamp
        if not segment.startswith('['):
            print(f"WARNING: Segment {i} missing timestamp, skipping: {segment[:100]}...")
            continue
            
        # Count tokens in this segment
        segment_tokens = len(encoding.encode(segment))
        
        # If this single segment is too long, we have to split it
        # (this should be rare since segments are usually short)
        if segment_tokens > max_tokens:
            print(f"WARNING: Found very long segment ({segment_tokens} tokens)")
            if current_chunk:  # Save current chunk first
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_tokens = 0
            chunks.append(segment)  # Add long segment as its own chunk
            continue
            
        # If adding this segment would exceed max tokens, save current chunk
        if current_tokens + segment_tokens > max_tokens and current_chunk:
            # Join current chunk segments with newlines
            chunks.append('\n'.join(current_chunk))
            
            # Start new chunk with overlap
            # Take the last few segments that fit within overlap_tokens
            overlap_chunk = []
            overlap_tokens_count = 0
            
            # Work backwards through current chunk to build overlap
            for prev_segment in reversed(current_chunk):
                prev_tokens = len(encoding.encode(prev_segment))
                if overlap_tokens_count + prev_tokens <= overlap_tokens:
                    overlap_chunk.insert(0, prev_segment)
                    overlap_tokens_count += prev_tokens
                else:
                    break
            
            # Start new chunk with overlap segments
            current_chunk = overlap_chunk
            current_tokens = overlap_tokens_count
        
        # Add segment to current chunk
        current_chunk.append(segment)
        current_tokens += segment_tokens
        
        # Print progress for long transcripts
        if i % 20 == 0:
            print(f"Processed {i}/{len(segments)} segments...")
            if current_chunk:
                print(f"Current chunk preview: {current_chunk[-1][:100]}...")
    
    # Add the last chunk if there's anything left
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    # Print chunk statistics and previews
    total_tokens = sum(len(encoding.encode(chunk)) for chunk in chunks)
    print(f"\nYouTube Chunking Statistics:")
    print(f"Total segments: {len(segments)}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Total tokens: {total_tokens}")
    print(f"Average tokens per chunk: {total_tokens / len(chunks):.0f}")
    
    # Print chunk boundaries for verification
    print("\nChunk Boundary Verification:")
    for i, chunk in enumerate(chunks):
        first_timestamp = re.search(r'\[\d+\.\d+s-\d+\.\d+s\]', chunk)
        last_timestamp = list(re.finditer(r'\[\d+\.\d+s-\d+\.\d+s\]', chunk))[-1] if chunk else None
        if first_timestamp and last_timestamp:
            print(f"Chunk {i+1}: {first_timestamp.group(0)} to {last_timestamp.group(0)}")
    
    return chunks 