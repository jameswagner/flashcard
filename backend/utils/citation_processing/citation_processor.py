"""Base class for processing citations across different content types."""

from typing import Optional, Tuple, Dict, Any, List
import logging
from models.enums import CitationType

logger = logging.getLogger(__name__)

class CitationProcessor:
    """Base class for processing citations."""
    
    def parse_citation(self, citation: Any) -> Tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
        """Parse citation data into components.
        
        Args:
            citation: Raw citation data in either dict or list format
            
        Returns:
            Tuple of (start_num, end_num, citation_type, context)
            For element-based citations, start_num and end_num will be the same element ID
        """
        if isinstance(citation, dict):
            citation_type = citation.get('citation_type')
            if not citation_type:
                logger.warning(f"Citation missing citation_type: {citation}")
                return None, None, None, None
                
            context = citation.get('context')
            
            # Handle range-based citations (sentences, paragraphs)
            if 'range' in citation:
                range_data = citation['range']
                if not isinstance(range_data, (list, tuple)) or len(range_data) != 2:
                    logger.warning(f"Invalid range format: {range_data}")
                    return None, None, None, None
                start_num, end_num = range_data
                
            # Handle element-based citations (tables, lists, sections)
            elif 'id' in citation:
                element_id = citation['id']
                if not isinstance(element_id, int):
                    logger.warning(f"Invalid element ID: {element_id}")
                    return None, None, None, None
                # Use element ID for both start and end
                start_num = end_num = element_id
                
            else:
                logger.warning(f"Citation missing range or id: {citation}")
                return None, None, None, None
                
        # Handle legacy format [[start, end]]
        elif isinstance(citation, (list, tuple)):
            if len(citation) != 2:
                logger.warning(f"Invalid citation list length: {len(citation)} - {citation}")
                return None, None, None, None
            start_num, end_num = citation
            citation_type = None
            context = None
            
        else:
            logger.warning(f"Unexpected citation format: {type(citation)} - {citation}")
            return None, None, None, None
        
        # Validate numbers
        if not isinstance(start_num, int) or not isinstance(end_num, int):
            logger.warning(f"Invalid citation numbers: start={start_num} ({type(start_num)}), end={end_num} ({type(end_num)})")
            return None, None, None, None
        
        return start_num, end_num, citation_type, context

    def format_citation_data(self, start_num: int, end_num: int) -> List[List[int]]:
        """Format citation data as a simple list of ranges.
        
        Args:
            start_num: Starting number/ID
            end_num: Ending number/ID
            
        Returns:
            List containing a single two-element list with start and end numbers
        """
        return [[start_num, end_num]]

    def get_preview_text(self, text_content: str, start_num: int, end_num: int, citation_type: Optional[str] = None) -> str:
        """Get preview text for a citation. Should be overridden by subclasses.
        
        Args:
            text_content: The source text content
            start_num: Starting number/ID
            end_num: Ending number/ID
            citation_type: Optional type of citation
            
        Returns:
            Preview text for the citation
        """
        # Default implementation for simple line-based content
        lines = text_content.split('\n')
        return "\n".join(line.strip() for line in lines[max(0, start_num - 1):min(len(lines), end_num)]) 