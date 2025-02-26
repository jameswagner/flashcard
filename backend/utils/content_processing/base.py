from typing import Dict, Protocol
from abc import ABC, abstractmethod

class ContentProcessor(ABC):
    """Base class for all content type processors.
    
    Each processor should implement:
    1. to_structured_json: Convert raw content to a structured JSON format
    2. to_prompt_text: Convert structured JSON to text with appropriate markers
    """
    
    @abstractmethod
    def to_structured_json(self, raw_content: str) -> Dict:
        """Convert raw content to structured JSON format.
        
        The JSON structure should capture the hierarchical nature of the content
        (sections, paragraphs, sentences, etc.) in a way that:
        1. Preserves the original structure
        2. Makes it easy to generate different types of prompt text
        3. Supports citation generation
        
        Args:
            raw_content: Raw content string
            
        Returns:
            Dict containing structured representation of the content
        """
        pass
    
    @abstractmethod
    def to_prompt_text(self, structured_json: Dict) -> str:
        """Convert structured JSON to prompt text with appropriate markers.
        
        The prompt text should include markers that:
        1. Make the structure clear to the LLM
        2. Support accurate citation generation
        3. Preserve the hierarchical nature of the content
        
        Args:
            structured_json: Structured content from to_structured_json()
            
        Returns:
            String containing content with appropriate markers for citations
        """
        pass 