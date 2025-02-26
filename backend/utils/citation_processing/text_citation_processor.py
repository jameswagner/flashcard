"""Text-specific citation processing."""

from typing import Optional
import logging
import json
from .citation_processor import CitationProcessor
from models.enums import CitationType

logger = logging.getLogger(__name__)

class TextCitationProcessor(CitationProcessor):
    """Processor for plain text citations using structured JSON format."""
    
    def get_preview_text(
        self, 
        text_content: str, 
        start_num: int, 
        end_num: int, 
        citation_type: Optional[str] = None
    ) -> str:
        """Get preview text for a citation from structured JSON.
        
        Args:
            text_content: JSON string containing structured content from PlainTextProcessor.to_structured_json()
            start_num: Starting number
            end_num: Ending number
            citation_type: Type of citation (sentence_range or paragraph)
            
        Returns:
            Preview text for the citation
        """
        if not citation_type:
            citation_type = CitationType.sentence_range.value

        try:
            # Parse the JSON content
            content = json.loads(text_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON content: {e}")
            return ""
            
        if citation_type == CitationType.sentence_range.value:
            # Find sentences by their numbers across all paragraphs
            selected_sentences = []
            for paragraph in content.get("paragraphs", []):
                for sentence, sentence_num in zip(paragraph["sentences"], paragraph["sentence_numbers"]):
                    if start_num <= sentence_num <= end_num:
                        selected_sentences.append(sentence)
            
            return " ".join(selected_sentences)
            
        elif citation_type == CitationType.paragraph.value:
            # Find paragraphs by their numbers
            selected_paragraphs = []
            for paragraph in content.get("paragraphs", []):
                if start_num <= paragraph["number"] <= end_num:
                    # Join sentences in this paragraph
                    paragraph_text = " ".join(paragraph["sentences"])
                    selected_paragraphs.append(paragraph_text)
            
            return "\n\n".join(selected_paragraphs)
            
        else:
            logger.warning(f"Unsupported citation type: {citation_type}")
            return "" 