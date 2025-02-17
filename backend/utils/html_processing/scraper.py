"""Module for fetching and cleaning HTML content from URLs."""

import httpx
from bs4 import BeautifulSoup
from typing import Optional, Tuple
from urllib.parse import urlparse
import re

async def scrape_url(url: str) -> Tuple[str, str]:
    """Fetch and clean HTML content from a URL.
    
    Args:
        url: The URL to scrape
        
    Returns:
        Tuple of (raw_html, title)
        
    Raises:
        HTTPException: If the URL is invalid or content cannot be fetched
    """
    # Validate URL
    parsed = urlparse(url)
    if not all([parsed.scheme, parsed.netloc]):
        raise ValueError("Invalid URL format")
    
    # Fetch content
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        raw_html = response.text
    
    # Extract title
    soup = BeautifulSoup(raw_html, 'html.parser')
    title = soup.title.string if soup.title else ''
    title = re.sub(r'\s+', ' ', title).strip()
    
    return raw_html, title

def clean_html(html: str) -> str:
    """Clean HTML content by removing scripts, styles, and unnecessary elements.
    
    Args:
        html: Raw HTML content
        
    Returns:
        Cleaned HTML content
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove unwanted elements
    for element in soup.find_all(['script', 'style', 'iframe', 'nav', 'footer']):
        element.decompose()
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Clean whitespace
    for tag in soup.find_all(True):
        if tag.string:
            tag.string = re.sub(r'\s+', ' ', tag.string.strip())
    
    return str(soup) 