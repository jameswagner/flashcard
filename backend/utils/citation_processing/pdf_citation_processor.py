"""PDF-specific citation processing."""

from typing import Optional
import logging
import json
from .citation_processor import CitationProcessor
from models.enums import CitationType

logger = logging.getLogger(__name__)

class PDFCitationProcessor(CitationProcessor):
    """Processor for PDF citations with support for both structured and unstructured content."""
    
    def get_preview_text(
        self, 
        text_content: str, 
        start_num: int, 
        end_num: int, 
        citation_type: Optional[str] = None
    ) -> str:
        """Get preview text for a citation.
        
        Args:
            text_content: The source text content with section and paragraph markers
            start_num: Starting number (section or paragraph)
            end_num: Ending number (section or paragraph)
            citation_type: Type of citation (section, paragraph, or sentence_range)
            
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

        def extract_text_from_content(content_item):
            """Extract text from a content item (paragraph or list item)."""
            if isinstance(content_item, dict):
                if 'sentences' in content_item:  # Paragraph
                    text = ' '.join(content_item['sentences'])
                    # Sanitize text - remove NUL characters and normalize whitespace
                    text = text.replace('\x00', '').strip()
                    return ' '.join(text.split())
                elif 'text' in content_item:  # List item
                    text = content_item['text']
                    if 'continuation_texts' in content_item:
                        text += ' ' + ' '.join(content_item['continuation_texts'])
                    # Sanitize text
                    text = text.replace('\x00', '').strip()
                    return ' '.join(text.split())
            return ""

        if citation_type == CitationType.section.value:
            # Find the specified section
            if start_num <= len(content.get('sections', [])):
                section = content['sections'][start_num - 1]
                texts = []
                if section.get('header'):
                    texts.append(section['header'])
                for item in section.get('content', []):
                    texts.append(extract_text_from_content(item))
                return '\n'.join(texts)
            return ""
            
        elif citation_type == CitationType.paragraph.value:
            # Find paragraphs across all sections
            paragraphs = []
            current_paragraph = 0
            
            for section in content.get('sections', []):
                for item in section.get('content', []):
                    if isinstance(item, dict) and 'sentences' in item:  # It's a paragraph
                        current_paragraph += 1
                        if start_num <= current_paragraph <= end_num:
                            paragraphs.append(extract_text_from_content(item))
            
            return '\n'.join(paragraphs)
            
        elif citation_type == CitationType.sentence_range.value:
            # Extract sentences from all paragraphs
            sentences = []
            current_sentence = 0
            
            for section in content.get('sections', []):
                for item in section.get('content', []):
                    if isinstance(item, dict) and 'sentences' in item:  # It's a paragraph
                        for sentence in item['sentences']:
                            current_sentence += 1
                            if start_num <= current_sentence <= end_num:
                                sentences.append(sentence)
            
            return ' '.join(sentences)
        
        elif citation_type == CitationType.list.value:
            # Find the specified list
            current_list = 0
            for section in content.get('sections', []):
                for i, item in enumerate(section.get('content', [])):
                    # Check if this is a list by looking at the next item
                    if isinstance(item, dict) and 'text' in item:
                        current_list += 1
                        if start_num <= current_list <= end_num:
                            # Get the list item text and any continuation texts
                            text = item['text']
                            if 'continuation_texts' in item and item['continuation_texts']:
                                text += '\n' + '\n'.join(item['continuation_texts'])
                            return text
            return ""
            
        else:
            logger.warning(f"Unsupported citation type: {citation_type}")
            return "" 