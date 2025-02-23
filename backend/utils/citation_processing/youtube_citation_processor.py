"""YouTube-specific citation processing."""

import re
import logging
from typing import Optional, Tuple, Dict, Any, List
from .citation_processor import CitationProcessor
from models.enums import CitationType

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
            text_content: The transcript text with timestamp markers
            start_time: Starting timestamp in seconds
            end_time: Ending timestamp in seconds
            citation_type: Optional type of citation (ignored for YouTube)
            
        Returns:
            Preview text for the timestamp range
        """
        # Find all timestamp ranges and their text
        timestamp_pattern = r'\[(\d+(?:\.\d+)?)s-(\d+(?:\.\d+)?)s\](.*?)(?=\[\d+(?:\.\d+)?s-\d+(?:\.\d+)?s\]|$)'
        matches = re.finditer(timestamp_pattern, text_content, re.DOTALL)
        
        relevant_text = []
        current_chapter = None
        actual_start = None
        actual_end = None
        
        for match in matches:
            chunk_start = float(match.group(1))
            chunk_end = float(match.group(2))
            chunk_text = match.group(3).strip()
            
            # Check if this chunk overlaps with our target range
            if (chunk_start <= end_time and chunk_end >= start_time):
                # Update actual start/end times
                if actual_start is None or chunk_start < actual_start:
                    actual_start = chunk_start
                if actual_end is None or chunk_end > actual_end:
                    actual_end = chunk_end
                
                # Look for chapter headings
                chapter_match = re.search(r'##\s*([^#\n]+)', chunk_text)
                if chapter_match:
                    current_chapter = chapter_match.group(1).strip()
                    # Remove the chapter heading from the chunk text
                    chunk_text = re.sub(r'##\s*[^#\n]+', '', chunk_text).strip()
                
                # Add chapter context if available
                if current_chapter and not any(text.startswith(f"[Chapter: {current_chapter}]") for text in relevant_text):
                    relevant_text.append(f"[Chapter: {current_chapter}] ")
                
                # Add the chunk text
                if chunk_text:
                    relevant_text.append(chunk_text)
        
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