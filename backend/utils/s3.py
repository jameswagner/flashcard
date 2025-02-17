import os
import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
from datetime import datetime
from typing import Optional, BinaryIO, Tuple, Union
import json

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE_MB', '10')) * 1024 * 1024  # Convert MB to bytes

def upload_file(file: BinaryIO, object_key: str) -> str:
    """Upload a file to S3 and return its key."""
    try:
        s3_client.upload_fileobj(file, BUCKET_NAME, object_key)
        return object_key
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file to S3: {str(e)}")

def delete_file(object_key: str) -> None:
    """Delete a file from S3."""
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=object_key)
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file from S3: {str(e)}")

def get_file_content(object_key: str) -> str:
    """Get the content of a text file from S3."""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=object_key)
        return response['Body'].read().decode('utf-8')
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error reading file from S3: {str(e)}")

def generate_s3_key(filename: str, user_id: Optional[str] = None, is_processed: bool = False) -> str:
    """Generate a unique S3 key for a file.
    
    Args:
        filename: Original filename
        user_id: Optional user ID for namespacing
        is_processed: Whether this is a processed version of the file
    
    Returns:
        S3 key for the file
    """
    import uuid
    extension = os.path.splitext(filename)[1]
    unique_id = str(uuid.uuid4())
    prefix = f"users/{user_id}" if user_id else "public"
    file_type = "processed" if is_processed else "original"
    
    # Determine extension for processed files based on content type
    if is_processed:
        if extension.lower() in ['.html', '.htm']:
            processed_ext = '.json'
        else:
            processed_ext = '.sentences'
    else:
        processed_ext = ''
        
    return f"{prefix}/{file_type}/{unique_id}{extension}{processed_ext}"

def store_processed_text(text: Union[str, dict], original_s3_key: str, processing_type: str = "sentences") -> str:
    """Store processed text in S3.
    
    Args:
        text: Text to store (string or dictionary that will be converted to JSON)
        original_s3_key: S3 key of the original file
        processing_type: Type of processing ("sentences", "html_structure", "youtube_transcript")
    
    Returns:
        S3 key where processed text was stored
    """
    prefix = os.path.dirname(os.path.dirname(original_s3_key))
    filename = os.path.basename(original_s3_key)
    processed_key = f"{prefix}/processed/{filename}.{processing_type}"
    
    try:
        content_type = "application/json" if isinstance(text, dict) or processing_type in ["html_structure", "youtube_transcript"] else "text/plain"
        
        # Convert dict to JSON string if needed
        if isinstance(text, dict):
            text = json.dumps(text, ensure_ascii=False, indent=2)
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=processed_key,
            Body=text.encode('utf-8') if isinstance(text, str) else json.dumps(text, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType=content_type
        )
        return processed_key
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error storing processed text in S3: {str(e)}")

def get_processed_text(original_s3_key: str, processing_type: str = "sentences") -> Optional[str]:
    """Get processed text from S3 if it exists.
    
    Args:
        original_s3_key: S3 key of the original file
        processing_type: Type of processing to retrieve ("sentences", "html_structure")
    
    Returns:
        Processed text if it exists, None otherwise
    """
    prefix = os.path.dirname(os.path.dirname(original_s3_key))
    filename = os.path.basename(original_s3_key)
    processed_key = f"{prefix}/processed/{filename}.{processing_type}"
    
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=processed_key)
        return response['Body'].read().decode('utf-8')
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise HTTPException(status_code=500, detail=f"Error reading processed text from S3: {str(e)}")

def store_html_content(raw_html: str, processed_json: str, url: str, user_id: Optional[str] = None) -> Tuple[str, str]:
    """Store both raw HTML and its processed JSON content in S3.
    
    Args:
        raw_html: Raw HTML content
        processed_json: JSON string of processed content
        url: Source URL
        user_id: Optional user ID for namespacing
    
    Returns:
        Tuple of (raw_html_key, processed_json_key)
    """
    # Generate keys for both raw and processed content
    filename = url.split('/')[-1] or 'index.html'
    raw_key = generate_s3_key(filename, user_id, is_processed=False)
    processed_key = generate_s3_key(filename, user_id, is_processed=True)
    
    try:
        # Store raw HTML
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=raw_key,
            Body=raw_html.encode('utf-8'),
            ContentType='text/html'
        )
        
        # Store processed content
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=processed_key,
            Body=processed_json.encode('utf-8'),
            ContentType='application/json'
        )
        
        return raw_key, processed_key
    
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error storing HTML content in S3: {str(e)}")

def get_html_content(raw_key: str, processed_key: str) -> Tuple[str, str]:
    """Retrieve both raw HTML and its processed content from S3.
    
    Args:
        raw_key: S3 key for raw HTML
        processed_key: S3 key for processed content
    
    Returns:
        Tuple of (raw_html, processed_json)
    
    Raises:
        HTTPException: If content cannot be retrieved
    """
    try:
        # Get raw HTML
        raw_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=raw_key)
        raw_html = raw_response['Body'].read().decode('utf-8')
        
        # Get processed content
        processed_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=processed_key)
        processed_json = processed_response['Body'].read().decode('utf-8')
        
        return raw_html, processed_json
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail="HTML content not found")
        raise HTTPException(status_code=500, detail=f"Error retrieving HTML content from S3: {str(e)}") 