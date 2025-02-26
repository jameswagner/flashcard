"""YouTube transcript processing for flashcard generation."""

from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, Dict, Optional, TypedDict, Any
from dataclasses import dataclass
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
    timestamp_pattern = r'(\d+:(?:\d{1,2}:)?\d{2})\s*([-\s]+)?\s*(.+)'
    chapters = []
    
    # Log a sample of the description for debugging
    desc_sample = description[:100] + "..." if len(description) > 100 else description
    logger.info(f"Description sample: {desc_sample}")
    
    for line in description.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        match = re.match(timestamp_pattern, line)
        if match:
            time, separator, title = match.groups()
            logger.info(f"[+] Found chapter: {time} - {title}")
            
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
                logger.info(f"Converted time {time} to {seconds} seconds")
            except ValueError as e:
                logger.error(f"[x] Error parsing time parts {time_parts}: {str(e)}")
    
    logger.info(f"[+] Found {len(chapters)} chapters in description")
    # Log the first few extracted chapters
    for i, chapter in enumerate(chapters[:3]):
        logger.info(f"Extracted chapter {i+1}: {chapter['title']} at {chapter['time']} ({chapter['start_seconds']}s)")
    if len(chapters) > 3:
        logger.info(f"... and {len(chapters) - 3} more chapters")
        
    return chapters

def fetch_transcript(video_id: str, video_title: str, description: str = "", existing_chapters: List[Dict[str, any]] = None) -> Optional[YouTubeContent]:
    """Fetch and process transcript for a YouTube video.
    
    Args:
        video_id: YouTube video ID
        video_title: Title of the video
        description: Video description for chapter extraction
        existing_chapters: Optional list of chapters from get_video_info
        
    Returns:
        YouTubeContent object with transcript and metadata
    """
    logger.info(f"Fetching transcript for video {video_id}: {video_title}")
    
    try:
        # Fetch raw transcript
        logger.info(f"Requesting transcript from YouTube API for video {video_id}")
        transcript_segments = YouTubeTranscriptApi.get_transcript(video_id)
        logger.info(f"Retrieved {len(transcript_segments)} transcript segments")
        
        # Debug log a brief sample of the first segment
        if transcript_segments:
            first_seg = transcript_segments[0]
            logger.debug(f"First segment - Start: {first_seg['start']:.2f}s, Text: {first_seg['text']}")
        
        # Extract chapters if description is provided
        logger.info("Parsing chapters from description or using existing chapters")
        chapters = parse_chapters(description, existing_chapters)
        logger.info(f"Found {len(chapters)} chapters")
        
        # Process transcript segments and add chapter information
        logger.info("Processing transcript segments and adding chapter information")
        full_text = ""
        current_chapter = 0
        
        # Add first chapter marker if exists
        if chapters:
            full_text += f"\n## {chapters[0]['title']}\n\n"
            logger.debug(f"Starting with chapter: {chapters[0]['title']}")
        
        # Group segments into SEGMENT_SIZE_SECONDS chunks
        current_chunk = []
        chunk_start_time = 0
        chunk_text = ""
        chunk_count = 0
        
        logger.info(f"Grouping segments into {SEGMENT_SIZE_SECONDS}-second chunks")
        for segment in transcript_segments:
            # Check if we've entered a new chapter
            if chapters and current_chapter < len(chapters) - 1:
                if segment['start'] >= chapters[current_chapter + 1]['start_seconds']:
                    current_chapter += 1
                    logger.info(f"Entering chapter: {chapters[current_chapter]['title']} at {segment['start']:.2f}s")
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
                # For the end time, use the start of the next segment (or current segment's start + 2s if last)
                chunk_end_time = (
                    transcript_segments[transcript_segments.index(segment) + 1]['start']
                    if segment != transcript_segments[-1]
                    else segment['start'] + 2.0
                )
                
                # Format timestamp as raw seconds and add text
                timestamp = f"[{chunk_start_time:.2f}s-{chunk_end_time:.2f}s]"
                full_text += f"{timestamp} {chunk_text.strip()}\n"
                
                chunk_count += 1
                if chunk_count % 10 == 0:
                    logger.info(f"Processed {chunk_count} chunks so far")
                
                # Reset chunk and set next chunk start time
                current_chunk = []
                chunk_text = ""
                if segment != transcript_segments[-1]:
                    chunk_start_time = chunk_end_time
        
        logger.info(f"Processed transcript into {chunk_count} chunks, total length {len(full_text)} chars")
        
        # Create and return YouTubeContent object
        youtube_content = YouTubeContent(
            video_id=video_id,
            title=video_title,
            description=description,
            transcript_text=full_text.strip(),
            chapters=chapters,
            segments=transcript_segments
        )
        
        logger.info(f"Successfully created YouTubeContent object for video {video_id}")
        return youtube_content
        
    except Exception as e:
        logger.error(f"Error processing transcript for video {video_id}: {str(e)}", exc_info=True)
        return None

def generate_citations(content: YouTubeContent) -> List[Dict[str, any]]:
    """Generate timestamp-based citations for a YouTube transcript."""
    logger.info(f"Generating citations for video {content.video_id}: {content.title}")
    
    # Log some basic information about the content
    logger.info(f"Content has {len(content.segments)} segments and {len(content.chapters)} chapters")
    
    citations = []
    
    # Group segments into SEGMENT_SIZE_SECONDS chunks
    current_chunk = []
    chunk_start_time = 0
    
    logger.info(f"Grouping segments into {SEGMENT_SIZE_SECONDS}-second chunks for citations")
    
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
            
            # Log every 10th citation or if we have few citations
            if len(citations) <= 5 or len(citations) % 10 == 0:
                logger.info(f"Created citation {len(citations)}: {int(chunk_start_time)}s-{int(chunk_end_time)}s in '{citation['context']}'")
            
            # Start a new chunk
            current_chunk = []
            chunk_start_time = chunk_end_time
    
    logger.info(f"Generated {len(citations)} timestamp-based citations")
    
    # Log a sample of the first few citations
    for i, citation in enumerate(citations[:3]):
        logger.info(f"Citation {i+1}: {citation['range'][0]}-{citation['range'][1]}s, Context: {citation['context']}")
        preview_sample = citation['preview_text'][:50] + "..." if len(citation['preview_text']) > 50 else citation['preview_text']
        logger.info(f"  Preview: {preview_sample}")
    
    if len(citations) > 3:
        logger.info(f"... and {len(citations) - 3} more citations")
    
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

class YouTubeProcessor:
    """Processor for YouTube content that maintains transcript structure."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def to_structured_json(self, raw_content: str, title: Optional[str] = None) -> Dict:
        """Convert raw YouTube content to structured JSON format.
        
        Args:
            raw_content: Raw YouTube content (YouTubeContent object)
            title: Optional title override
            
        Returns:
            Dictionary with structured content
        """
        self.logger.info("Converting YouTube content to structured JSON format")
        
        if isinstance(raw_content, str):
            try:
                self.logger.info("Parsing raw content from JSON string")
                content = YouTubeContent.from_dict(json.loads(raw_content))
                self.logger.info(f"Successfully parsed JSON for video {content.video_id}")
            except json.JSONDecodeError:
                self.logger.error("Failed to parse raw content as JSON")
                raise ValueError("Invalid raw content format")
        elif isinstance(raw_content, YouTubeContent):
            self.logger.info(f"Using provided YouTubeContent object for video {raw_content.video_id}")
            content = raw_content
        else:
            self.logger.error(f"Unexpected content type: {type(raw_content)}")
            raise ValueError("Invalid content type")
            
        # Structure the content with sections based on chapters
        self.logger.info("Structuring content with sections based on chapters")
        sections = []
        current_section = None
        
        # Split transcript into lines
        lines = content.transcript_text.split('\n')
        self.logger.info(f"Processing {len(lines)} lines of transcript text")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for chapter marker
            chapter_match = re.match(r'##\s*(.+)', line)
            if chapter_match:
                # If we have a current section, add it to sections
                if current_section:
                    sections.append(current_section)
                    self.logger.debug(f"Added section: {current_section['header']} with {len(current_section['content'])} items")
                
                # Start new section
                current_section = {
                    'header': chapter_match.group(1).strip(),
                    'content': [],
                    'level': 1  # All YouTube chapters are top-level
                }
                self.logger.debug(f"Started new section: {current_section['header']}")
            elif current_section is None:
                # Create default section if none exists
                current_section = {
                    'header': 'Video Transcript',
                    'content': [],
                    'level': 1
                }
                self.logger.debug("Created default 'Video Transcript' section")
            
            # Process transcript line with timestamp
            timestamp_match = re.match(r'\[(\d+(?:\.\d+)?s)-(\d+(?:\.\d+)?s)\](.*)', line)
            if timestamp_match:
                start_time, end_time, text = timestamp_match.groups()
                text = text.strip()
                if text:
                    current_section['content'].append({
                        'type': 'transcript_segment',
                        'text': text,
                        'start_time': float(start_time.rstrip('s')),
                        'end_time': float(end_time.rstrip('s'))
                    })
        
        # Add final section if exists
        if current_section:
            sections.append(current_section)
            self.logger.debug(f"Added final section: {current_section['header']} with {len(current_section['content'])} items")
            
        # Create metadata
        self.logger.info("Creating metadata for structured JSON")
        metadata = {
            'video_id': content.video_id,
            'title': title or content.title,
            'description': content.description,
            'channel': content.channel,
            'published_at': content.published_at,
            'duration': content.duration,
            'statistics': content.statistics,
            'total_sections': len(sections),
            'has_chapters': bool(content.chapters)
        }
        
        result = {
            'title': metadata['title'],
            'sections': sections,
            'metadata': metadata
        }
        
        self.logger.info(f"Successfully created structured JSON with {len(sections)} sections")
        return result
    
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