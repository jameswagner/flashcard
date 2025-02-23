"""Text-specific citation processing."""

from typing import Optional
import logging
import re
from .citation_processor import CitationProcessor
from models.enums import CitationType

logger = logging.getLogger(__name__)

class TextCitationProcessor(CitationProcessor):
    """Processor for plain text citations with sentence and paragraph markers."""
    
    def get_preview_text(
        self, 
        text_content: str, 
        start_num: int, 
        end_num: int, 
        citation_type: Optional[str] = None
    ) -> str:
        """Get preview text for a citation, preserving sentence and paragraph markers.
        
        Args:
            text_content: The source text content with [SENTENCE X] and [PARAGRAPH X] markers
            start_num: Starting number
            end_num: Ending number
            citation_type: Type of citation (sentence_range or paragraph)
            
        Returns:
            Preview text for the citation with markers preserved
        """
        if not citation_type:
            citation_type = CitationType.sentence_range.value
            
        if citation_type == CitationType.sentence_range.value:
            # Split on sentence markers, keeping the markers
            sentences = re.split(r'(?=\[SENTENCE \d+\])', text_content)
            # Remove empty strings and leading/trailing whitespace
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # Filter sentences by their numbers
            selected_sentences = []
            for sentence in sentences:
                # Extract sentence number from marker
                match = re.match(r'\[SENTENCE (\d+)\]', sentence)
                if match:
                    sentence_num = int(match.group(1))
                    if start_num <= sentence_num <= end_num:
                        selected_sentences.append(sentence)
            
            return "\n".join(selected_sentences)
            
        elif citation_type == CitationType.paragraph.value:
            # Split on paragraph markers, keeping the markers
            paragraphs = re.split(r'(?=\[PARAGRAPH \d+\])', text_content)
            # Remove empty strings and leading/trailing whitespace
            paragraphs = [p.strip() for p in paragraphs if p.strip()]
            
            # Filter paragraphs by their numbers
            selected_paragraphs = []
            for paragraph in paragraphs:
                # Extract paragraph number from marker
                match = re.match(r'\[PARAGRAPH (\d+)\]', paragraph)
                if match:
                    paragraph_num = int(match.group(1))
                    if start_num <= paragraph_num <= end_num:
                        selected_paragraphs.append(paragraph)
            
            return "\n\n".join(selected_paragraphs)
            
        else:
            logger.warning(f"Unsupported citation type: {citation_type}")
            return "" 