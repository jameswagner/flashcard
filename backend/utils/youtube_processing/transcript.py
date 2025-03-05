"""YouTube transcript processing for flashcard generation."""

from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, Dict, Optional, TypedDict, Any, Union
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import logging
import sys
import requests
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
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
class Segment:
    """A segment of transcript text with timing information."""
    text: str
    start_time: float
    end_time: float
    chapter: Optional[str] = None

@dataclass
class Chapter:
    """A chapter containing segments."""
    title: str
    start_seconds: float
    segments: List[Segment] = field(default_factory=list)

@dataclass
class YouTubeContent:
    """Structured content from a YouTube video."""
    video_id: str
    title: str
    description: str
    transcript_text: str
    chapters: List[Dict[str, any]]
    segments: List[Dict[str, any]]
    structured_content: dict
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
            "structured_content": self.structured_content,
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
            structured_content=data.get('structured_content', {}),
            channel=data.get('channel'),
            published_at=data.get('published_at'),
            duration=data.get('duration'),
            statistics=data.get('statistics')
        )

def format_duration(duration: str) -> str:
    """
    Convert YouTube duration format (PT1H2M10S) to readable format (1:02:10)
    """
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return duration
    
    hours, minutes, seconds = match.groups()
    time_str = ""
    
    if hours:
        time_str += f"{hours}:"
        time_str += f"{int(minutes or 0):02d}:"
    else:
        time_str += f"{int(minutes or 0)}:"
    
    time_str += f"{int(seconds or 0):02d}"
    return time_str

def get_video_info(video_id: str) -> dict:
    """
    Get structured video information including chapters from YouTube API
    Returns a dictionary with all video metadata
    """
    logger.info(f"Getting info for video {video_id}")
    
    # Path to service account file - check multiple locations
    service_account_paths = [
        os.path.join(os.path.dirname(__file__), 'service_account.json'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'service_account.json'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'service_account.json')
    ]
    
    service_account_path = None
    for path in service_account_paths:
        if os.path.exists(path):
            service_account_path = path
            logger.info(f"Found service account file at: {path}")
            break
    
    try:
        if service_account_path:
            logger.info(f"Using YouTube API with service account from: {service_account_path}")
            # Use the YouTube API with service account
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=['https://www.googleapis.com/auth/youtube.readonly']
            )
            youtube = build('youtube', 'v3', credentials=credentials)  # type: Any
            
            # Get video details with chapters
            logger.info(f"Requesting video details for ID: {video_id}")
            request = youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            )
            response = request.execute()
            
            if not response['items']:
                logger.warning(f"No video found with ID: {video_id}")
                return {"error": f"No video found with ID: {video_id}"}
            
            video = response['items'][0]
            logger.info(f"Successfully retrieved video data for: {video['snippet']['title']}")
            
            # Extract chapters from description as YouTube API doesn't directly expose chapters
            description = video['snippet']['description']
            timestamp_pattern = r'(\d{1,2}:?\d{2}:\d{2}|\d{1,2}:\d{2})\s*-\s*(.+)'
            chapters = []
            
            logger.info("Extracting chapters from video description")
            for line in description.split('\n'):
                match = re.match(timestamp_pattern, line.strip())
                if match:
                    time, title = match.groups()
                    # Convert timestamp to seconds for easier processing
                    time_parts = time.split(':')
                    seconds = 0
                    if len(time_parts) == 2:  # MM:SS
                        seconds = int(time_parts[0]) * 60 + int(time_parts[1])
                    elif len(time_parts) == 3:  # HH:MM:SS
                        seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
                    
                    chapters.append({
                        "title": title.strip(),
                        "time": time,
                        "seconds": seconds
                    })
            
            logger.info(f"Found {len(chapters)} chapters in video description")
            
            # Create structured output
            result = {
                "id": video_id,
                "title": video['snippet']['title'],
                "description": video['snippet']['description'],
                "channel": video['snippet']['channelTitle'],
                "published_at": video['snippet']['publishedAt'],
                "duration": {
                    "raw": video['contentDetails']['duration'],
                    "formatted": format_duration(video['contentDetails']['duration'])
                },
                "statistics": {
                    "views": int(video['statistics'].get('viewCount', 0)),
                    "likes": int(video['statistics'].get('likeCount', 0)),
                    "comments": int(video['statistics'].get('commentCount', 0))
                },
                "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "chapters": chapters
            }
            logger.info(f"Returning structured video info with {len(result)} fields")
            return result
        else:
            # Fallback to oEmbed API if service account file not found
            logger.warning("Service account file not found, falling back to oEmbed API")
            url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            logger.info(f"Requesting oEmbed data from: {url}")
            response = requests.get(url)
            
            if response.status_code != 200:
                logger.error(f"Failed to get video info: HTTP {response.status_code}")
                return {"error": f"HTTP error {response.status_code}"}
            
            oembed_data = response.json()
            logger.info(f"Successfully retrieved oEmbed data for: {oembed_data.get('title', 'Unknown title')}")
            
            # Get additional metadata from YouTube page
            page_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"Requesting YouTube page data from: {page_url}")
            page_response = requests.get(page_url)
            
            # Extract description and other metadata using regex
            description = ""
            duration_seconds = 0
            duration_raw = ""
            views = 0
            
            if page_response.status_code == 200:
                logger.info("Successfully retrieved YouTube page data")
                # Try to extract description
                desc_match = re.search(r'"description":{"simpleText":"(.*?)"}', page_response.text)
                if desc_match:
                    description = desc_match.group(1).replace('\\n', '\n')
                    logger.info(f"Extracted description of length: {len(description)}")
                
                # Try to extract duration
                duration_match = re.search(r'"lengthSeconds":"(\d+)"', page_response.text)
                if duration_match:
                    duration_seconds = int(duration_match.group(1))
                    logger.info(f"Extracted duration: {duration_seconds} seconds")
                    
                # Try to extract duration in ISO format
                duration_iso_match = re.search(r'"duration":"([^"]+)"', page_response.text)
                if duration_iso_match:
                    duration_raw = duration_iso_match.group(1)
                    logger.info(f"Extracted ISO duration: {duration_raw}")
                
                # Try to extract view count
                views_match = re.search(r'"viewCount":"(\d+)"', page_response.text)
                if views_match:
                    views = int(views_match.group(1))
                    logger.info(f"Extracted view count: {views}")
            else:
                logger.warning(f"Failed to get YouTube page data: HTTP {page_response.status_code}")
            
            # Extract chapters from description
            chapters = []
            timestamp_pattern = r'(\d{1,2}:?\d{2}:\d{2}|\d{1,2}:\d{2})\s*-\s*(.+)'
            
            logger.info("Extracting chapters from video description")
            for line in description.split('\n'):
                match = re.match(timestamp_pattern, line.strip())
                if match:
                    time, title = match.groups()
                    # Convert timestamp to seconds for easier processing
                    time_parts = time.split(':')
                    seconds = 0
                    if len(time_parts) == 2:  # MM:SS
                        seconds = int(time_parts[0]) * 60 + int(time_parts[1])
                    elif len(time_parts) == 3:  # HH:MM:SS
                        seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
                    
                    chapters.append({
                        "title": title.strip(),
                        "time": time,
                        "seconds": seconds
                    })
            
            logger.info(f"Found {len(chapters)} chapters in video description")
            
            # Format the duration
            formatted_duration = format_duration(duration_raw) if duration_raw else f"{duration_seconds // 60}:{duration_seconds % 60:02d}"
            
            # Return structured data
            result = {
                "id": video_id,
                "title": oembed_data.get("title", f"YouTube Video {video_id}"),
                "description": description,
                "channel": oembed_data.get("author_name", "Unknown Channel"),
                "published_at": None,  # Not easily available without API key
                "duration": {
                    "raw": duration_raw,
                    "seconds": duration_seconds,
                    "formatted": formatted_duration
                },
                "statistics": {
                    "views": views,
                    "likes": None,  # Not easily available without API key
                    "comments": None  # Not easily available without API key
                },
                "thumbnail_url": oembed_data.get("thumbnail_url"),
                "chapters": chapters
            }
            logger.info(f"Returning structured video info with {len(result)} fields")
            return result
            
    except Exception as e:
        logger.error(f"Error getting video info for {video_id}: {str(e)}", exc_info=True)
        return {"error": str(e)}

def parse_chapters(description: str, existing_chapters: List[Dict[str, any]] = None) -> List[Dict[str, any]]:
    """Extract chapters from video description or use existing chapters if provided."""
    logger.info("Parsing chapters from description or using existing chapters")
    
    # If we already have chapters from video_info, use those
    if existing_chapters and len(existing_chapters) > 0:
        logger.info(f"[+] Using {len(existing_chapters)} existing chapters")
        # Log the first few chapters for debugging
        for i, chapter in enumerate(existing_chapters[:3]):
            logger.info(f"Chapter {i+1}: {chapter['title']} at {chapter['time']}")
        if len(existing_chapters) > 3:
            logger.info(f"... and {len(existing_chapters) - 3} more chapters")
            
        # Convert to the format expected by the rest of the code
        return [
            {
                "title": chapter["title"],
                "time": chapter["time"],
                "start_seconds": chapter["seconds"]
            }
            for chapter in existing_chapters
        ]
    
    # Otherwise, try to extract from description
    logger.info("No existing chapters provided, extracting from description")
    
    # Single pattern to match both formats:
    # - Title followed by timestamp: "Title 00:00" or "Title - 00:00" or "Title: 00:00"
    # - Timestamp followed by title: "00:00 Title" or "00:00 - Title" or "00:00: Title"
    timestamp_pattern = r'^(?:(.+?)(?:[-:\s]+)|)(\d{1,2}:(?:\d{1,2}:)?\d{2})(?:(?:[-:\s]+)(.+)|)$'
    chapters = []
    
    # Process each line
    for line in description.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        match = re.match(timestamp_pattern, line)
        if match:
            before, timestamp, after = match.groups()
            title = (before or after).strip()
            time = timestamp.strip()
            
            # Convert timestamp to seconds
            time_parts = time.split(':')
            try:
                if len(time_parts) == 2:  # MM:SS
                    minutes, seconds = map(int, time_parts)
                    total_seconds = minutes * 60 + seconds
                elif len(time_parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, time_parts)
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                else:
                    logger.error(f"[x] Invalid time format: {time}")
                    continue
                
                chapters.append({
                    "title": title,
                    "time": time,
                    "start_seconds": total_seconds
                })
                logger.info(f"Found chapter: {title} at {time} ({total_seconds}s)")
            except ValueError as e:
                logger.error(f"[x] Error parsing time parts {time_parts}: {str(e)}")
    
    # Sort chapters by start time
    chapters.sort(key=lambda x: x['start_seconds'])
    
    logger.info(f"[+] Found {len(chapters)} chapters in description")
    return chapters

def fetch_transcript(video_id: str, video_title: str, description: str = "", existing_chapters: List[Dict[str, any]] = None) -> Optional[YouTubeContent]:
    """Fetch and process transcript for a YouTube video."""
    logger.info(f"Fetching transcript for video {video_id}: {video_title}")
    
    try:
        # Fetch raw transcript
        logger.info(f"Requesting transcript from YouTube API for video {video_id}")
        micro_segments = YouTubeTranscriptApi.get_transcript(video_id)
        logger.info(f"Retrieved {len(micro_segments)} micro-segments from API")
        
        # Get chapters
        chapters = parse_chapters(description, existing_chapters)
        logger.info(f"Found {len(chapters)} chapters")
        
        # If no chapters found, create a default chapter
        if not chapters:
            chapters = [{
                "title": "Video Transcript",
                "time": "00:00",
                "start_seconds": 0
            }]
            logger.info("No chapters found, using default chapter")
        
        # Initialize chapter objects
        chapter_objects: List[Chapter] = []
        for i, chapter in enumerate(chapters):
            next_chapter_start = chapters[i + 1]["start_seconds"] if i < len(chapters) - 1 else float('inf')
            current_chapter = Chapter(
                title=chapter["title"],
                start_seconds=chapter["start_seconds"]
            )
            chapter_objects.append(current_chapter)
            
            # Initialize variables for building larger segments from micro-segments
            current_segment_start = chapter["start_seconds"]
            current_segment_text = []
            
            # Process micro-segments for this chapter
            for micro_segment in micro_segments:
                micro_start = float(micro_segment["start"])
                micro_end = micro_start + float(micro_segment["duration"])
                
                # Skip micro-segments before this chapter
                if micro_end <= chapter["start_seconds"]:
                    continue
                    
                # If micro-segment starts in next chapter, it belongs there
                if micro_start >= next_chapter_start:
                    break
                
                # If micro-segment crosses chapter boundary, trim it to end at chapter boundary
                if micro_end > next_chapter_start:
                    micro_end = next_chapter_start
                
                # Calculate how long this segment would be if we add this micro-segment
                potential_segment_duration = micro_end - current_segment_start
                
                # If adding this micro-segment would make our segment too long,
                # create a new segment with what we have so far
                if potential_segment_duration > SEGMENT_SIZE_SECONDS and current_segment_text:
                    # Create new segment with accumulated text
                    current_chapter.segments.append(Segment(
                        text=" ".join(current_segment_text),
                        start_time=current_segment_start,
                        end_time=micro_start,  # End at start of current micro-segment
                        chapter=current_chapter.title
                    ))
                    
                    # Start new segment
                    current_segment_text = []
                    current_segment_start = micro_start
                
                # Add current micro-segment to accumulating text
                current_segment_text.append(micro_segment["text"])
                
                # If we've reached the chapter boundary, create final segment
                if micro_end >= next_chapter_start:
                    current_chapter.segments.append(Segment(
                        text=" ".join(current_segment_text),
                        start_time=current_segment_start,
                        end_time=next_chapter_start,
                        chapter=current_chapter.title
                    ))
                    current_segment_text = []
            
            # Handle any remaining text in the current chapter
            if current_segment_text:
                current_chapter.segments.append(Segment(
                    text=" ".join(current_segment_text),
                    start_time=current_segment_start,
                    end_time=min(current_segment_start + SEGMENT_SIZE_SECONDS, next_chapter_start),
                    chapter=current_chapter.title
                ))
        
        # Create YouTubeContent object
        content = YouTubeContent(
            video_id=video_id,
            title=video_title,
            description=description,
            transcript_text="",  # We don't need this anymore as we have structured content
            chapters=chapters,
            segments=[],  # Raw segments not needed as we have structured content
            structured_content={
                "title": video_title,
                "sections": [
                    {
                        "header": chapter.title,
                        "content": [
                            {
                                "type": "transcript_segment",
                                "text": segment.text,
                                "start_time": segment.start_time,
                                "end_time": segment.end_time
                            }
                            for segment in chapter.segments
                        ],
                        "level": 1
                    }
                    for chapter in chapter_objects
                ]
            }
        )
        
        return content
        
    except Exception as e:
        logger.error(f"Error processing transcript for video {video_id}: {str(e)}", exc_info=True)
        return None

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

class YouTubeProcessor:
    """Processor for YouTube content that maintains transcript structure."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def to_structured_json(self, raw_content: Any) -> Dict:
        """Convert YouTube content to structured JSON format.
        
        Args:
            raw_content: YouTubeContent object
            
        Returns:
            Dictionary with structured content
        """
        try:
            if not isinstance(raw_content, YouTubeContent):
                raise ValueError("Expected YouTubeContent object")
            
            # Return the structured content directly
            result = {
                "title": raw_content.title,
                "sections": raw_content.structured_content["sections"],
                "metadata": {
                    "video_id": raw_content.video_id,
                    "title": raw_content.title,
                    "description": raw_content.description,
                    "channel": raw_content.channel,
                    "published_at": raw_content.published_at,
                    "duration": raw_content.duration,
                    "statistics": raw_content.statistics,
                    "total_sections": len(raw_content.structured_content["sections"]),
                    "has_chapters": len(raw_content.chapters) > 1  # More than just default chapter
                }
            }
            
            return result
        except Exception as e:
            logger.error(f"Error converting content to structured JSON: {str(e)}", exc_info=True)
            raise
    
    def to_prompt_text(self, structured_json: Dict) -> str:
        """Convert structured JSON to prompt text with markers.
        
        Args:
            structured_json: Output from to_structured_json()
            
        Returns:
            Text with [Section X], [Timestamp seconds], etc. markers
        """
        self.logger.info("Converting structured JSON to prompt text with markers")
        lines = []
        
        # Add title
        if structured_json.get('title'):
            lines.append(f"[Title] {structured_json['title']}\n")
            self.logger.debug(f"Added title: {structured_json['title']}")
        
        # Process sections
        self.logger.info(f"Processing {len(structured_json.get('sections', []))} sections")
        for i, section in enumerate(structured_json.get('sections', []), 1):
            # Add section header
            if section.get('header'):
                lines.append(f"[Section {i}] {section['header']}")
                self.logger.debug(f"Added section header: {section['header']}")
            
            # Process content
            content_count = len(section.get('content', []))
            self.logger.debug(f"Processing {content_count} content items in section {i}")
            for item in section.get('content', []):
                if item.get('type') == 'transcript_segment':
                    # Only include raw seconds timestamps
                    start_time = item['start_time']
                    end_time = item['end_time']
                    
                    # Format with raw seconds only
                    lines.append(f"[{start_time:.2f}s-{end_time:.2f}s] {item['text']}")
                    self.logger.debug(f"Added transcript segment: {start_time:.2f}s-{end_time:.2f}s")
            
            lines.append("")  # Add blank line between sections
        
        return "\n".join(lines).strip()
    
    def _format_timestamp(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
        return f"{minutes:02d}:{seconds:05.2f}" 