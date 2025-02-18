import os
from typing import List, Dict, Any, Optional
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from models.enums import AIModel
from models.prompt import PromptTemplate as DBPromptTemplate
from sqlalchemy.orm import Session
from utils.text_processing import add_line_markers
from utils.sentence_processing import add_sentence_markers
from utils.text_chunking import chunk_text, merge_flashcard_results, count_tokens, chunk_html_content, chunk_youtube_transcript
import traceback
import re
import asyncio
import time
import sys
import logging
from concurrent.futures import ThreadPoolExecutor
from utils.html_processing import HTMLContent
from models.enums import FileType
import json

# Get logger for this module
logger = logging.getLogger(__name__)

# Rate limiting configuration
TOKENS_PER_MINUTE = 200_000  # OpenAI's rate limit
SAFETY_FACTOR = 0.9  # Reduce token usage to provide a safety margin
MAX_PARALLEL_REQUESTS = 4  # Maximum number of parallel requests to maintain

class TokenBucket:
    """Token bucket for rate limiting."""
    def __init__(self, tokens_per_minute: int):
        self.max_tokens = tokens_per_minute
        self.tokens = tokens_per_minute
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def get_delay_for_tokens(self, requested_tokens: int) -> float:
        """Calculate delay needed before processing requested tokens."""
        async with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            
            # Replenish tokens based on time passed
            self.tokens = min(
                self.max_tokens,
                self.tokens + (TOKENS_PER_MINUTE * (time_passed / 60))
            )
            
            if self.tokens >= requested_tokens:
                self.tokens -= requested_tokens
                self.last_update = now
                return 0
            
            # Calculate delay needed
            tokens_needed = requested_tokens - self.tokens
            minutes_needed = tokens_needed / TOKENS_PER_MINUTE
            return max(0, minutes_needed * 60)
    
    async def consume(self, tokens: int):
        """Consume tokens from the bucket."""
        async with self.lock:
            self.tokens = max(0, self.tokens - tokens)
            self.last_update = time.time()

# Global token bucket for rate limiting
token_bucket = TokenBucket(int(TOKENS_PER_MINUTE * SAFETY_FACTOR))

def get_latest_prompt_template(db: Session, model: AIModel = None) -> DBPromptTemplate:
    """Get the latest active prompt template for the given model."""
    query = db.query(DBPromptTemplate).filter(DBPromptTemplate.is_active == True)
    if model:
        query = query.filter(
            (DBPromptTemplate.model_id == model.value) | 
            (DBPromptTemplate.model_id == None)
        )
    return query.order_by(DBPromptTemplate.version.desc()).first()

async def create_flashcards_from_text(
    text: str,
    model: AIModel,
    db: Session,
    params: Dict[str, Any] = None,
    use_sentences: bool = True,
    processed_text: Optional[str] = None,
    model_params: Optional[Dict] = None,
    max_tokens_per_chunk: Optional[int] = None,
    overlap_tokens: Optional[int] = None,
    file_type: Optional[FileType] = None
) -> List[Dict[str, Any]]:
    """Generate flashcards from text using the specified AI model and Langchain.
    
    Args:
        text: Raw text content
        model: AI model to use
        db: Database session
        params: Optional parameters for generation
        use_sentences: Whether to use sentence-based citations
        processed_text: Optional pre-processed text with markers
        model_params: Optional parameters for the AI model
        max_tokens_per_chunk: Maximum tokens per chunk (defaults to config value)
        overlap_tokens: Number of tokens to overlap between chunks (defaults to config value)
        file_type: Type of the source file (HTML, TXT, etc.)
    
    Returns:
        List of generated flashcards
    """
    logger.info("\n=== FLASHCARD GENERATION DEBUG ===")
    logger.info(f"Model: {model}")
    logger.info(f"Use sentences: {use_sentences}")
    logger.info(f"Model params: {model_params}")
    logger.info(f"File type: {file_type}")
    
    # Get appropriate prompt template
    db_template = get_latest_prompt_template(db, model)
    if not db_template:
        logger.error("ERROR: No suitable prompt template found")
        raise ValueError("No suitable prompt template found")
    
    logger.info("\n=== PROMPT TEMPLATE ===")
    logger.info(f"Template ID: {db_template.id}")
    logger.info(f"Template Name: {db_template.name}")
    logger.info(f"Template Version: {db_template.version}")
    
    # Process text if needed
    if processed_text is None:
        logger.info("\n=== PROCESSING TEXT ===")
        if use_sentences:
            logger.info("Using sentence-based processing")
            marked_text = add_sentence_markers(text)
        else:
            logger.info("Using line-based processing")
            marked_text = add_line_markers(text)
    else:
        marked_text = processed_text
    
    # Determine content type and chunking strategy
    logger.info("\n=== DETERMINING CONTENT TYPE ===")
    is_html_content = False
    
    if file_type == FileType.HTML:
        logger.info("File type is HTML")
        is_html_content = True
    elif file_type is None:
        # Fallback to detection if file_type not provided
        logger.info("No file type provided, attempting content detection")
        is_html_content = "[Section:" in marked_text or "[SECTION:" in marked_text
        logger.info(f"Content detection result: {'HTML' if is_html_content else 'Plain text'}")
    else:
        logger.info(f"Using standard processing for file type: {file_type}")
    
    # Chunk the text appropriately
    logger.info("\n=== CHUNKING TEXT ===")
    if is_html_content:
        logger.info("Using HTML-aware chunking")
        try:
            html_content = HTMLContent.from_json(marked_text)
            chunks = chunk_html_content(
                html_content,
                max_tokens=max_tokens_per_chunk,
                overlap_tokens=overlap_tokens,
                model=model
            )
        except Exception as e:
            logger.info(f"Failed to parse HTML content: {e}, falling back to regular chunking")
            chunks = chunk_text(
                marked_text,
                max_tokens=max_tokens_per_chunk,
                overlap_tokens=overlap_tokens,
                model=model
            )
    elif file_type == FileType.YOUTUBE_TRANSCRIPT:
        logger.info("Using YouTube transcript chunking")
        chunks = chunk_youtube_transcript(
            marked_text,
            max_tokens=max_tokens_per_chunk,
            overlap_tokens=overlap_tokens,
            model=model
        )
    else:
        logger.info("Using standard text chunking")
        chunks = chunk_text(
            marked_text,
            max_tokens=max_tokens_per_chunk,
            overlap_tokens=overlap_tokens,
            model=model
        )
    
    logger.info(f"Split text into {len(chunks)} chunks")
    logger.info("\nChunk previews:")
    for i, chunk in enumerate(chunks):
        logger.info(f"\nChunk {i+1} ({len(chunk)} chars):")
        logger.info("-" * 40)
        logger.info(chunk[:200] + "..." if len(chunk) > 200 else chunk)
        logger.info("-" * 40)
    
    # Create base prompt template
    prompt = PromptTemplate.from_template(db_template.template)
    
    # Initialize model
    model_params = model_params or {}
    model_params.setdefault('temperature', 0.7)
    
    if model in [AIModel.GPT_4, AIModel.GPT_35_TURBO, AIModel.GPT4O_MINI]:
        llm = ChatOpenAI(
            model=model.value,
            temperature=model_params['temperature'],
            api_key=os.getenv('OPENAI_API_KEY')
        )
    elif model in [AIModel.CLAUDE_3_OPUS, AIModel.CLAUDE_3_SONNET]:
        llm = ChatAnthropic(
            model=model.value,
            temperature=model_params['temperature'],
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
    elif model == AIModel.GEMINI_PRO:
        llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            temperature=model_params['temperature'],
            api_key=os.getenv('GOOGLE_API_KEY')
        )
    else:
        raise ValueError(f"Unsupported model: {model}")
    
    async def process_chunk(chunk: str, chunk_index: int) -> List[Dict[str, Any]]:
        """Process a single chunk of text."""
        logger.info(f"\n=== PROCESSING CHUNK {chunk_index + 1}/{len(chunks)} ===")
        
        # Prepare prompt parameters for this chunk
        chunk_params = params.copy() if params else {}  # Start with a copy of the base params
        chunk_params['source_text'] = chunk  # Override source_text with the chunk
        
        try:
            formatted_prompt = prompt.format(**chunk_params)
            
            # Estimate tokens for this request (prompt + expected response)
            estimated_tokens = count_tokens(formatted_prompt) * 1.2  # Multiple by 1.2 to account for response
            
            # Get required delay based on token usage
            delay = await token_bucket.get_delay_for_tokens(estimated_tokens)
            if delay > 0:
                logger.info(f"\nRate limit delay: Sleeping for {delay:.1f} seconds...")
                await asyncio.sleep(delay)
            
            # Only show the source text part of the prompt for clarity
            logger.info(f"\nChunk {chunk_index + 1} source text:")
            logger.info("-" * 80)
            # Safely encode the preview text
            preview_text = chunk[:1000] + "..." if len(chunk) > 1000 else chunk
            try:
                logger.info(preview_text)
            except UnicodeEncodeError:
                logger.info("(Preview text contains Unicode characters that cannot be displayed)")
            logger.info("-" * 80)
            logger.info(f"\nSending chunk {chunk_index + 1} to AI model")
            
            # Use asyncio.to_thread for CPU-bound tasks
            response = await asyncio.to_thread(llm.invoke, formatted_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Record actual token usage
            await token_bucket.consume(estimated_tokens)
            
            # Parse and validate the response
            chunk_cards = parse_ai_response(content)
            logger.info(f"Generated {len(chunk_cards)} cards from chunk {chunk_index + 1}")
            return chunk_cards

        except Exception as e:
                logger.error(f"Error processing chunk {chunk_index + 1}: {str(e)}")
                logger.error(traceback.format_exc())
                return []

    # Process chunks with controlled parallelism
    logger.info("\n=== PROCESSING ALL CHUNKS ===")
    semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
    
    async def process_with_semaphore(chunk: str, index: int) -> List[Dict[str, Any]]:
        async with semaphore:
            return await process_chunk(chunk, index)
    
    tasks = [process_with_semaphore(chunk, i) for i, chunk in enumerate(chunks)]
    chunk_results = await asyncio.gather(*tasks)
    
    # Merge results from all chunks
    logger.info("\n=== MERGING RESULTS ===")
    all_flashcards = merge_flashcard_results(chunk_results)
    logger.info(f"Generated {len(all_flashcards)} total flashcards")
    
    return all_flashcards 

def parse_ai_response(content: str) -> List[Dict[str, Any]]:
    """Parse and validate the AI model's response into a list of flashcards."""
    logger.info("\n=== PARSING AI RESPONSE ===")
    
    # Clean up the response if it's not valid JSON
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    # Clean special characters
    content = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', content)
    content = content.replace('•', '-')
    content = content.replace('·', '-')
    content = content.replace('‣', '-')
    content = content.replace('—', '-')
    content = content.replace('–', '-')
    content = content.replace('"', '"').replace('"', '"')
    content = content.replace(''', "'").replace(''', "'")
    
    # Check if response appears to be truncated
    if content.count('{') != content.count('}') or content.count('[') != content.count(']'):
        raise ValueError("Response appears to be truncated - unmatched braces detected")
    
    try:
        # First try direct JSON parsing
        flashcards = json.loads(content)
        logger.info(f"Successfully parsed JSON response. Raw content type: {type(flashcards)}")
    except json.JSONDecodeError:
        # If that fails, try to extract JSON from markdown code blocks
        logger.info("Initial JSON parsing failed, attempting to extract from markdown blocks")
        if '```json' in content:
            content = content.split('```json', 1)[1]
        elif '```' in content:
            content = content.split('```', 1)[1]
        if '```' in content:
            content = content.split('```', 1)[0]
        content = content.strip()
        try:
            flashcards = json.loads(content)
            logger.info("Successfully parsed JSON from markdown block")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
            logger.error(f"Content causing error: {content[:500]}...")
            raise ValueError(f"Failed to parse AI response: {str(e)}")
            
    # Extract flashcards array if wrapped in object
    if isinstance(flashcards, dict) and 'flashcards' in flashcards:
        logger.info("Found flashcards wrapped in object, extracting array")
        flashcards = flashcards['flashcards']
    elif not isinstance(flashcards, list):
        logger.error(f"Unexpected response format. Expected list or dict with 'flashcards' key, got: {type(flashcards)}")
        raise ValueError(f"Expected list or dict with 'flashcards' key, got: {type(flashcards)}")
    
    logger.info(f"Processing {len(flashcards)} flashcards")
    
    # Validate flashcard format
    for i, card in enumerate(flashcards):
        if not isinstance(card, dict):
            logger.error(f"Card {i+1} is not a dict: {type(card)}")
            raise ValueError(f"Expected dict for card, got: {type(card)}")
        
        # Log card structure before validation
        logger.info(f"Card {i+1} content preview: {str(card)[:200]}...")
            
        # Check required fields
        for field in ['front', 'back']:
            if field not in card:
                logger.error(f"Card {i+1} missing required field: {field}")
                raise ValueError(f"Card missing required field: {field}")
            
        # Check citations
        citations = card.get('citations', [])
        if citations:
            for j, citation in enumerate(citations):                # Validate citation format
                if isinstance(citation, (list, tuple)):
                    if len(citation) != 2:
                        logger.warning(f"Skipping invalid citation tuple length: {len(citation)}")
                        continue
                    if not all(isinstance(x, int) for x in citation):
                        logger.warning("Skipping citation with non-integer values")
                        continue
                elif isinstance(citation, dict):
                    if 'citation_type' not in citation:
                        logger.warning("Skipping citation missing citation_type")
                        continue
                    if 'range' not in citation and 'id' not in citation:
                        logger.warning("Skipping citation missing range or id")
                        continue
                        
        # Validate key terms and concepts
        key_terms = card.get('key_terms', [])
        if key_terms and not isinstance(key_terms, list):
            logger.warning(f"Card {i+1} has invalid key_terms type: {type(key_terms)}, setting to empty list")
            card['key_terms'] = []
        elif key_terms:
            card['key_terms'] = [str(term) for term in key_terms if term]
            
        key_concepts = card.get('key_concepts', [])
        if key_concepts and not isinstance(key_concepts, list):
            logger.warning(f"Card {i+1} has invalid key_concepts type: {type(key_concepts)}, setting to empty list")
            card['key_concepts'] = []
        elif key_concepts:
            card['key_concepts'] = [str(concept) for concept in key_concepts if concept]
            
        # Validate abbreviations
        abbreviations = card.get('abbreviations', [])
        if abbreviations:
            if not isinstance(abbreviations, list):
                logger.warning(f"Card {i+1} has invalid abbreviations type: {type(abbreviations)}, setting to empty list")
                card['abbreviations'] = []
            else:
                valid_abbreviations = []
                for abbr in abbreviations:
                    # Handle both old dict format and new list format
                    if isinstance(abbr, dict) and 'short' in abbr and 'long' in abbr:
                        valid_abbreviations.append([str(abbr['long']), str(abbr['short'])])
                    elif isinstance(abbr, (list, tuple)) and len(abbr) == 2:
                        valid_abbreviations.append([str(abbr[0]), str(abbr[1])])
                card['abbreviations'] = valid_abbreviations
    
    logger.info("\n=== FINISHED PARSING AI RESPONSE ===")
    return flashcards