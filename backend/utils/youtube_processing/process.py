import json
from typing import Dict
from aws_sdk_s3 import S3Client

async def process_youtube_video(video_id: str, s3_client: S3Client) -> Dict[str, any]:
    """Process a YouTube video and store its transcript in S3."""
    logger.info(f"Processing YouTube video {video_id}")
    
    # Fetch transcript and generate citations
    content = await fetch_transcript(video_id)
    if not content:
        raise ValueError(f"Could not fetch transcript for video {video_id}")
    
    # Store transcript JSON in S3
    transcript_key = f"transcripts/{video_id}.json"
    await s3_client.put_object(
        transcript_key,
        json.dumps({
            "video_id": video_id,
            "segments": content.segments,
            "chapters": content.chapters,
            "processed_type": "youtube_transcript"
        })
    )
    
    logger.info(f"Stored transcript at {transcript_key}")
    
    return {
        "video_id": video_id,
        "s3_key": transcript_key,
        "processed_type": "youtube_transcript"
    } 