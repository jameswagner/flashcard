"""YouTube-specific citation processing."""

import re
import logging
from typing import Optional, Tuple, Dict, Any, List
from .citation_processor import CitationProcessor
from models.enums import CitationType
import json

logger = logging.getLogger(__name__)

class YouTubeCitationProcessor(CitationProcessor):
    """Processor for YouTube transcript citations with timestamp support."""
    
    def parse_citation(self, citation: Any) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        """Parse citation data into timestamp components.
        
        Args:
            citation: Raw citation data in either dict or list format
            
        Returns:
            Tuple of (start_time, end_time, citation_type, context)
            Times are in seconds
        """
        if isinstance(citation, dict):
            citation_type = citation.get('citation_type', CitationType.video_timestamp.value)
            context = citation.get('context')
            
            # Handle timestamp range
            if 'range' in citation:
                range_data = citation['range']
                if not isinstance(range_data, (list, tuple)) or len(range_data) != 2:
                    logger.warning(f"Invalid range format: {range_data}")
                    return None, None, None, None
                start_time, end_time = map(float, range_data)
                
            else:
                logger.warning(f"Citation missing range: {citation}")
                return None, None, None, None
                
        # Handle legacy format [[start, end]]
        elif isinstance(citation, (list, tuple)):
            if len(citation) != 2:
                logger.warning(f"Invalid citation list length: {len(citation)}")
                return None, None, None, None
            start_time, end_time = map(float, citation)
            citation_type = CitationType.video_timestamp.value
            context = None
            
        else:
            logger.warning(f"Unexpected citation format: {type(citation)}")
            return None, None, None, None
        
        return start_time, end_time, citation_type, context

    def format_timestamp(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string HH:MM:SS
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
        return f"{minutes:02d}:{seconds:05.2f}"

    def get_preview_text(
        self, 
        text_content: str, 
        start_time: float, 
        end_time: float, 
        citation_type: Optional[str] = None
    ) -> str:
        """Get preview text for a timestamp range.
        
        Args:
            text_content: The structured JSON content
            start_time: Starting timestamp in seconds
            end_time: Ending timestamp in seconds
            citation_type: Optional type of citation (ignored for YouTube)
            
        Returns:
            Preview text for the timestamp range
        """
        try:
            if isinstance(text_content, str):
                content = json.loads(text_content)
            else:
                content = text_content
        except json.JSONDecodeError:
            logger.error("Failed to parse text_content as JSON")
            return ""
            
        relevant_text = []
        current_section = None
        actual_start = None
        actual_end = None
        
        # Process each section
        for section in content.get('sections', []):
            # Track current section header for context
            current_section = section.get('header')
            
            # Process transcript segments in this section
            for item in section.get('content', []):
                if item.get('type') == 'transcript_segment':
                    chunk_start = item['start_time']
                    chunk_end = item['end_time']
                    
                    # Check if this segment overlaps with our target range
                    if (chunk_start <= end_time and chunk_end >= start_time):
                        # Update actual start/end times
                        if actual_start is None or chunk_start < actual_start:
                            actual_start = chunk_start
                        if actual_end is None or chunk_end > actual_end:
                            actual_end = chunk_end
                        
                        # Add section context if not already added
                        if current_section and not any(text.startswith(f"[Chapter: {current_section}]") for text in relevant_text):
                            relevant_text.append(f"[Chapter: {current_section}] ")
                        
                        # Add the segment text
                        if item['text']:
                            relevant_text.append(item['text'])
        
        if not relevant_text or actual_start is None or actual_end is None:
            return ""
        
        # Join all text, ensuring proper spacing
        result = " ".join(text.strip() for text in relevant_text if text.strip())
        
        # Add actual timestamp range in HH:MM:SS format
        timestamp_display = f"[{self.format_timestamp(actual_start)}-{self.format_timestamp(actual_end)}]"
        return f"{timestamp_display} {result}"

    def format_citation_data(self, start_time: float, end_time: float) -> List[List[float]]:
        """Format citation data as a list of timestamp ranges.
        
        Args:
            start_time: Starting timestamp in seconds
            end_time: Ending timestamp in seconds
            
        Returns:
            List containing a single two-element list with start and end timestamps
        """
        return [[start_time, end_time]] 