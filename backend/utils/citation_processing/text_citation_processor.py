"""Text-specific citation processing."""

from typing import Optional
import logging
import re
from .citation_processor import CitationProcessor
from models.enums import CitationType

logger = logging.getLogger(__name__)

class TextCitationProcessor(CitationProcessor):
    """Processor for plain text citations with sentence markers."""
    
    def get_preview_text(
        self, 
        text_content: str, 
        start_num: int, 
        end_num: int, 
        citation_type: Optional[str] = None
    ) -> str:
        """Get preview text for a citation, preserving sentence markers.
        
        Args:
            text_content: The source text content with [SENTENCE X] markers
            start_num: Starting sentence number
            end_num: Ending sentence number
            citation_type: Optional type of citation (ignored for plain text)
            
        Returns:
            Preview text for the citation with sentence markers preserved
        """
        # Split on sentence markers, keeping the markers
        # The (?=pattern) is a positive lookahead that keeps the marker with the sentence
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