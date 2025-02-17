"""YouTube transcript processing for flashcard generation."""

from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, Dict, Optional, TypedDict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import logging
import sys
from ..text_processing import add_line_markers, extract_line_numbers, get_text_from_line_numbers

# Configure logging to handle Unicode characters
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Configuration
SEGMENT_SIZE_SECONDS = 20  # Default segment size in seconds

@dataclass
class YouTubeContent:
    """Structured content from a YouTube video."""
    video_id: str
    title: str
    description: str
    transcript_text: str
    chapters: List[Dict[str, any]]
    segments: List[Dict[str, any]]
    # Additional metadata fields
    channel: Optional[str] = None
    published_at: Optional[str] = None
    duration: Optional[str] = None
    statistics: Optional[Dict[str, any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "description": self.description,
            "transcript_text": self.transcript_text,
            "chapters": self.chapters,
            "segments": self.segments,
            "channel": self.channel,
            "published_at": self.published_at,
            "duration": self.duration,
            "statistics": self.statistics
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'YouTubeContent':
        """Create YouTubeContent from dictionary."""
        if isinstance(data, str):
            logger.error("Expected dictionary but got string")
            try:
                data = json.loads(data)
                logger.debug("Successfully parsed string as JSON")
            except json.JSONDecodeError as e:
                logger.error("Failed to parse string as JSON")
                raise ValueError("Invalid data format - expected dictionary or valid JSON string")
        
        logger.debug(f"Creating YouTubeContent from dict with video_id: {data.get('video_id')}")
        return cls(
            video_id=data.get('video_id', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            transcript_text=data.get('transcript_text', ''),
            chapters=data.get('chapters', []),
            segments=data.get('segments', []),
            channel=data.get('channel'),
            published_at=data.get('published_at'),
            duration=data.get('duration'),
            statistics=data.get('statistics')
        )

def parse_chapters(description: str) -> List[Dict[str, any]]:
    """Extract chapters from video description."""
    logger.debug("Parsing chapters from description")
    
    timestamp_pattern = r'(\d+:(?:\d{1,2}:)?\d{2})\s*([-\s]+)?\s*(.+)'
    chapters = []
    
    for line in description.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        match = re.match(timestamp_pattern, line)
        if match:
            time, separator, title = match.groups()
            logger.debug(f"[+] Found chapter: {time} - {title}")
            
            # Convert timestamp to seconds
            time_parts = time.split(':')
            try:
                if len(time_parts) == 2:  # MM:SS
                    minutes, seconds = map(int, time_parts)
                    seconds = minutes * 60 + seconds
                elif len(time_parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, time_parts)
                    seconds = hours * 3600 + minutes * 60 + seconds
                
                chapters.append({
                    "title": title.strip(),
                    "time": time,
                    "start_seconds": seconds
                })
            except ValueError as e:
                logger.error(f"[x] Error parsing time parts {time_parts}")
    
    logger.info(f"[+] Found {len(chapters)} chapters")
    return chapters

def fetch_transcript(video_id: str, video_title: str, description: str = "") -> Optional[YouTubeContent]:
    """Fetch and process transcript for a YouTube video.
    
    Args:
        video_id: YouTube video ID
        video_title: Title of the video
        description: Video description for chapter extraction
        
    Returns:
        YouTubeContent object with transcript and metadata
    """
    logger.info(f"Fetching transcript for video {video_id}: {video_title}")
    
    try:
        # Fetch raw transcript
        transcript_segments = YouTubeTranscriptApi.get_transcript(video_id)
        logger.info(f"Retrieved {len(transcript_segments)} transcript segments")
        
        # Extract chapters if description is provided
        chapters = parse_chapters(description) if description else []
        logger.debug(f"Found {len(chapters)} chapters")
        
        # Process transcript segments and add chapter information
        full_text = ""
        current_chapter = 0
        
        # Add first chapter marker if exists
        if chapters:
            full_text += f"\n## {chapters[0]['title']}\n\n"
        
        # Group segments into SEGMENT_SIZE_SECONDS chunks
        current_chunk = []
        chunk_start_time = 0
        chunk_text = ""
        
        for segment in transcript_segments:
            # Check if we've entered a new chapter
            if chapters and current_chapter < len(chapters) - 1:
                if segment['start'] >= chapters[current_chapter + 1]['start_seconds']:
                    current_chapter += 1
                    logger.debug(f"Entering chapter: {chapters[current_chapter]['title']}")
                    full_text += f"\n## {chapters[current_chapter]['title']}\n\n"
            
            # Add chapter information to segment
            segment['chapter'] = chapters[current_chapter]['title'] if chapters else None
            
            # If this is the first segment in a chunk, set the start time
            if not current_chunk:
                chunk_start_time = segment['start']
                
            # Add segment to current chunk
            current_chunk.append(segment)
            chunk_text += f"{segment['text']} "
            
            # If we've reached SEGMENT_SIZE_SECONDS from chunk start, or this is the last segment
            if (segment['start'] - chunk_start_time >= SEGMENT_SIZE_SECONDS) or (segment == transcript_segments[-1]):
                # Format timestamp as raw seconds and add text
                timestamp = f"[{chunk_start_time:.2f}s-{segment['start'] + segment['duration']:.2f}s]"
                full_text += f"{timestamp} {chunk_text.strip()}\n"
                
                # Reset chunk
                current_chunk = []
                chunk_text = ""
        
        logger.info(f"Successfully processed transcript into {len(full_text)} chars with {len(chapters)} chapters")
        return YouTubeContent(
            video_id=video_id,
            title=video_title,
            description=description,
            transcript_text=full_text.strip(),
            chapters=chapters,
            segments=transcript_segments
        )
        
    except Exception as e:
        logger.error(f"Error processing transcript for video {video_id}: {str(e)}", exc_info=True)
        return None

def generate_citations(content: YouTubeContent) -> List[Dict[str, any]]:
    """Generate timestamp-based citations for a YouTube transcript."""
    logger.info(f"Generating citations for video {content.video_id}")
    citations = []
    
    # Group segments into SEGMENT_SIZE_SECONDS chunks
    current_chunk = []
    chunk_start_time = 0
    
    for segment in content.segments:
        # If this is the first segment in a chunk, set the start time
        if not current_chunk:
            chunk_start_time = segment['start']
            
        # Add segment to current chunk
        current_chunk.append(segment)
        
        # If we've reached SEGMENT_SIZE_SECONDS from chunk start, or this is the last segment
        if (segment['start'] - chunk_start_time >= SEGMENT_SIZE_SECONDS) or (segment == content.segments[-1]):
            # Get the end time of the last segment in chunk
            chunk_end_time = segment['start'] + segment['duration']
            
            # Find the chapter for this chunk (using start time)
            chapter = None
            for i, ch in enumerate(content.chapters):
                if i < len(content.chapters) - 1:
                    if ch['start_seconds'] <= chunk_start_time < content.chapters[i + 1]['start_seconds']:
                        chapter = ch['title']
                        break
                else:
                    if ch['start_seconds'] <= chunk_start_time:
                        chapter = ch['title']
            
            # Combine all text from segments in this chunk
            preview_text = " ".join(seg['text'] for seg in current_chunk)
            
            citation = {
                "citation_type": "video_timestamp",
                "range": [int(chunk_start_time), int(chunk_end_time)],
                "context": chapter or "Unknown Chapter",
                "preview_text": preview_text
            }
            citations.append(citation)
            
            # Start a new chunk
            current_chunk = []
            chunk_start_time = chunk_end_time
    
    logger.info(f"Generated {len(citations)} timestamp-based citations")
    return citations

def save_transcript(content: YouTubeContent, output_file: str):
    """Save processed transcript to a JSON file."""
    logger.info(f"Saving transcript for video {content.video_id} to {output_file}")
    
    try:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(content.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info("Successfully saved transcript")
    except Exception as e:
        logger.error(f"Error saving transcript: {str(e)}", exc_info=True) 