"""YouTube-specific citation processing."""

import re
import logging
from typing import Optional, Tuple, Dict, Any, List
from .citation_processor import CitationProcessor
from models.enums import CitationType
import json
import math

logger = logging.getLogger(__name__)

class YouTubeCitationProcessor(CitationProcessor):
    """Processor for YouTube transcript citations with timestamp support."""
    
    def parse_citation(self, citation):
        """Parse citation data into timestamp components.
        
        Args:
            citation: Raw citation data in either dict or list format
            
        Returns:
            Tuple of (start_time, end_time, citation_type, context)
            Times are in seconds
        """
        logger.info(f"YouTube citation processor parsing citation: {citation}")
        
        if isinstance(citation, dict):
            citation_type = citation.get('citation_type', CitationType.video_timestamp.value)
            context = citation.get('context')
            
            # Handle timestamp range
            if 'range' in citation:
                range_data = citation['range']
                if not isinstance(range_data, (list, tuple)) or len(range_data) != 2:
                    logger.warning(f"Invalid range format: {range_data}")
                    return None
                start_time, end_time = map(float, range_data)
                logger.info(f"Parsed YouTube range citation: start_time={start_time}, end_time={end_time}, type={citation_type}")
                
            else:
                logger.warning(f"Citation missing range: {citation}")
                return None
                
        # Handle legacy format [[start, end]]
        elif isinstance(citation, (list, tuple)):
            if len(citation) != 2:
                logger.warning(f"Invalid citation list length: {len(citation)}")
                return None
            start_time, end_time = map(float, citation)
            citation_type = CitationType.video_timestamp.value
            context = None
            logger.info(f"Parsed YouTube legacy citation format: start_time={start_time}, end_time={end_time}")
            
        else:
            logger.warning(f"Unexpected citation format: {type(citation)}")
            return None
        
        # Return the timestamp values directly - no integer conversion needed
        return start_time, end_time, citation_type, context

    def format_timestamp(self, seconds):
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
        text_content, 
        start_num=None,
        end_num=None,
        citation_type=None
    ):
        """Get preview text for a timestamp range.
        
        Args:
            text_content: The structured JSON content
            start_num: Starting position in seconds
            end_num: Ending position in seconds
            citation_type: Optional type of citation (ignored for YouTube)
            
        Returns:
            Preview text for the timestamp range
        """
        logger.debug(f"Getting preview text for YouTube timestamp range: {start_num} to {end_num}")
        
        try:
            if text_content is None:
                return ""
                
            # Parse the transcript JSON
            transcript_data = json.loads(text_content) if isinstance(text_content, str) else text_content
            
            if not isinstance(transcript_data, dict) or "transcript" not in transcript_data:
                logger.warning("Invalid transcript data format")
                return ""
                
            transcript = transcript_data.get("transcript", [])
            if not transcript:
                return ""
                
            # Find segments that overlap with the target range
            overlapping_segments = []
            
            for segment in transcript:
                seg_start = segment.get("start", 0)
                seg_end = seg_start + segment.get("duration", 0)
                
                # Check if segment overlaps with citation range
                if seg_end >= start_num and seg_start <= end_num:
                    overlapping_segments.append(segment)
            
            relevant_text = []
            current_section = None
            actual_start = None
            actual_end = None
            
            # Process each segment
            for segment in overlapping_segments:
                # Track current section header for context
                current_section = segment.get('header')
                
                # Add section context if not already added
                if current_section and not any(text.startswith(f"[Chapter: {current_section}]") for text in relevant_text):
                    relevant_text.append(f"[Chapter: {current_section}] ")
                
                # Add the segment text
                if segment['text']:
                    relevant_text.append(segment['text'])
                
                # Update actual start/end times
                if actual_start is None or seg_start < actual_start:
                    actual_start = seg_start
                if actual_end is None or seg_end > actual_end:
                    actual_end = seg_end
            
            segment_count = len(relevant_text) - (1 if current_section else 0)
            logger.debug(f"Found {segment_count} transcript segments in range {actual_start}-{actual_end}")
            
            if not relevant_text or actual_start is None or actual_end is None:
                logger.warning(f"No transcript segments found for time range {start_num}-{end_num}")
                return ""
            
            # Join the text and format with timestamp
            result = " ".join(relevant_text)
            timestamp_display = f"[{self.format_timestamp(actual_start)}-{self.format_timestamp(actual_end)}]"
            logger.debug(f"Created YouTube preview with timestamp display: {timestamp_display}")
            return f"{timestamp_display} {result}"
        except Exception as e:
            logger.error(f"Error in get_preview_text: {e}")
            return ""

    def format_citation_data(self, start_value, end_value):
        """Format citation data as a list of timestamp ranges.
        
        Args:
            start_value: Starting position (seconds for YouTube)
            end_value: Ending position (seconds for YouTube)
            
        Returns:
            List containing a single two-element list with start and end values
        """
        logger.info(f"Formatting YouTube citation data: {start_value}-{end_value}")
        return [[start_value, end_value]] 