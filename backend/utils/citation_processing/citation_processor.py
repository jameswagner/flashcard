"""Base class for processing citations across different content types."""

from typing import Optional, Tuple, Dict, Any, List
import logging
from models.enums import CitationType

logger = logging.getLogger(__name__)

class CitationProcessor:
    """Base class for processing citations."""
    
    def parse_citation(self, citation):
        """Parse citation data into components.
        
        Args:
            citation: Raw citation data in either dict or list format
            
        Returns:
            Tuple of (start, end, citation_type, context)
        """
        if isinstance(citation, dict):
            citation_type = citation.get('citation_type')
            if not citation_type:
                logger.warning(f"Citation missing citation_type: {citation}")
                return None
                
            context = citation.get('context')
            
            # Handle range-based citations (sentences, paragraphs)
            if 'range' in citation:
                range_data = citation['range']
                if not isinstance(range_data, (list, tuple)) or len(range_data) != 2:
                    logger.warning(f"Invalid range format: {range_data}")
                    return None
                start, end = range_data
                
            # Handle element-based citations (tables, lists, sections)
            elif 'id' in citation:
                element_id = citation['id']
                # Use element ID for both start and end
                start = end = element_id
                
            else:
                logger.warning(f"Citation missing range or id: {citation}")
                return None
                
        # Handle legacy format [[start, end]]
        elif isinstance(citation, (list, tuple)):
            if len(citation) != 2:
                logger.warning(f"Invalid citation list length: {len(citation)} - {citation}")
                return None
            start, end = citation
            citation_type = None
            context = None
            
        else:
            logger.warning(f"Unexpected citation format: {type(citation)} - {citation}")
            return None
        
        # Just return the values as-is, no validation, no raw copies
        return start, end, citation_type, context

    def format_citation_data(self, start, end):
        """Format citation data as a simple list of ranges.
        
        Args:
            start: Starting position/ID
            end: Ending position/ID
            
        Returns:
            List containing a single two-element list with start and end values
        """
        return [[start, end]]

    def get_preview_text(
        self, 
        text_content, 
        start=None,
        end=None,
        citation_type=None
    ):
        """Get preview text for a citation. Should be overridden by subclasses.
        
        Args:
            text_content: The source text content
            start: Starting position/index/timestamp
            end: Ending position/index/timestamp
            citation_type: Optional type of citation
            
        Returns:
            Preview text for the citation
        """
        if start is None or end is None:
            logger.warning("Missing start/end values in get_preview_text")
            return ""
        
        # Try to use values as line numbers if possible
        try:
            lines = text_content.split('\n')
            start_idx = int(start) if not isinstance(start, bool) else start
            end_idx = int(end) if not isinstance(end, bool) else end
            return "\n".join(line.strip() for line in lines[max(0, start_idx - 1):min(len(lines), end_idx)])
        except (TypeError, ValueError):
            # If conversion fails, just return a placeholder
            logger.warning(f"Unable to use values for text selection: {start}, {end}")
            return f"[Citation from {start} to {end}]" 