"""Module for fetching and cleaning HTML content from URLs."""

import httpx
from bs4 import BeautifulSoup, Comment
from typing import Optional, Tuple
from urllib.parse import urlparse, urljoin
import re
import logging
import os
from datetime import datetime
import pathlib
from ..prompt_handling.image_prompts import analyze_image
from fastapi import HTTPException
import asyncio

# Get logger for this module
logger = logging.getLogger(__name__)

# Constants for image processing
MAX_CONCURRENT_IMAGES = 10  # Maximum number of images to process in parallel
MAX_TOTAL_IMAGES = 50     # Maximum total images to process per page

def save_cleaned_text(text: str, title: str) -> str:
    """Save cleaned text to a file in the output_files directory.
    
    Args:
        text: The cleaned text to save
        title: The webpage title
        
    Returns:
        Path to the saved file
    """
    # Get the path to the backend directory (2 levels up from this module)
    current_dir = pathlib.Path(__file__).resolve().parent
    backend_dir = current_dir.parent.parent
    output_dir = backend_dir / 'output_files'
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean title for filename
    clean_title = re.sub(r'[^\w\s-]', '', title)
    clean_title = re.sub(r'[-\s]+', '_', clean_title)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{clean_title}_{timestamp}.out.txt"
    
    # Save the file
    filepath = output_dir / filename
    logger.info(f"Saving cleaned text to: {filepath}")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    
    return str(filepath)

async def scrape_url(url: str) -> Tuple[str, str]:
    """Scrape HTML content from a URL.
    
    Args:
        url: URL to scrape
        
    Returns:
        Tuple of (raw_html, title)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # Log response headers and encoding info
            logger.info(f"Response headers: {dict(response.headers)}")
            logger.info(f"Response apparent encoding: {response.encoding}")
            
            # Get document encoding from Content-Type header
            content_type = response.headers.get('content-type', '').lower()
            declared_encoding = None
            if 'charset=' in content_type:
                declared_encoding = content_type.split('charset=')[-1].strip()
            logger.info(f"Declared charset in Content-Type: {declared_encoding}")
            
            # Use UTF-8 as primary encoding, with fallbacks
            encodings_to_try = ['utf-8']
            if declared_encoding and declared_encoding.lower() != 'utf-8':
                encodings_to_try.append(declared_encoding)
            encodings_to_try.extend(['latin1', 'cp1252', 'iso-8859-1'])
            
            # Try each encoding
            text = None
            used_encoding = None
            for encoding in encodings_to_try:
                try:
                    text = response.content.decode(encoding)
                    used_encoding = encoding
                    logger.info(f"Successfully decoded content using {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                logger.warning("Failed to decode with all encodings, using UTF-8 with error handling")
                text = response.content.decode('utf-8', errors='replace')
                used_encoding = 'utf-8 (with replacements)'
            
            # Parse HTML with explicit encoding
            soup = BeautifulSoup(text, 'html.parser', from_encoding=used_encoding)
            
            # Check meta charset
            meta_charset = None
            charset_tag = soup.find('meta', charset=True)
            if charset_tag:
                meta_charset = charset_tag.get('charset')
            elif soup.find('meta', {'http-equiv': 'Content-Type'}):
                meta_content = soup.find('meta', {'http-equiv': 'Content-Type'}).get('content', '')
                if 'charset=' in meta_content:
                    meta_charset = meta_content.split('charset=')[-1].strip()
            
            logger.info(f"Meta charset declaration: {meta_charset}")
            logger.info(f"Final encoding used: {used_encoding}")
            
            # Get title
            title = soup.title.string if soup.title else url.split('/')[-1]
            title = title.strip()
            
            # Clean HTML
            cleaned_html = await clean_html(text, url)
            
            return cleaned_html, title
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {url}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing URL: {str(e)}")

async def process_image(img_tag, base_url: str) -> str:
    """Process an image tag and return a text description.
    
    Args:
        img_tag: BeautifulSoup tag for the image
        base_url: Base URL for resolving relative image URLs
        
    Returns:
        Text description of the image or empty string if processing fails
    """
    # Get image URL from src or data-src attributes
    src = img_tag.get('src', '') or img_tag.get('data-src', '')
    if not src:
        return ''
    
    # Handle data URLs
    if src.startswith('data:image/'):
        logger.debug("Skipping data URL image")
        return ''
        
    # Handle various URL formats
    if src.startswith('//'):
        # Protocol-relative URL
        img_url = f"https:{src}"
    elif src.startswith('http://') or src.startswith('https://'):
        # Already absolute
        img_url = src
    elif src.startswith('/'):
        # Root-relative URL
        parsed_base = urlparse(base_url)
        img_url = f"{parsed_base.scheme}://{parsed_base.netloc}{src}"
    else:
        # Relative URL
        img_url = urljoin(base_url, src)
    
    # Validate URL
    try:
        parsed = urlparse(img_url)
        if not all([parsed.scheme, parsed.netloc]):
            logger.warning(f"Invalid image URL: {img_url}")
            return ''
    except Exception as e:
        logger.warning(f"Error parsing image URL {img_url}: {str(e)}")
        return ''
    
    # Get alt text
    alt_text = img_tag.get('alt', '').strip() or img_tag.get('title', '').strip()
    
    try:
        # Get image description from GPT-4 Vision
        description = await analyze_image(img_url)
        if description:
            return f"[IMG: desc: {description}]"
            
        # If analysis failed but we have alt text, use that
        if alt_text:
            return f"[IMG: alt: {alt_text}]"
            
        # Otherwise skip this image
        return ''
            
    except Exception as e:
        logger.error(f"Error processing image {img_url}: {str(e)}")
        # If we have alt text, use it, otherwise skip the image
        return f"[IMG: alt: {alt_text}]" if alt_text else ''

async def process_image_with_url(img_tag, base_url: str) -> str:
    """Process an image tag and return a text description with URL.
    
    Args:
        img_tag: BeautifulSoup tag for the image
        base_url: Base URL for resolving relative image URLs
        
    Returns:
        Text description of the image with URL or empty string if processing fails
    """
    # Get image URL from src or data-src attributes
    src = img_tag.get('src', '') or img_tag.get('data-src', '')
    if not src:
        return ''
    
    # Handle data URLs
    if src.startswith('data:image/'):
        logger.debug("Skipping data URL image")
        return ''
        
    # Handle various URL formats
    if src.startswith('//'):
        # Protocol-relative URL
        img_url = f"https:{src}"
    elif src.startswith('http://') or src.startswith('https://'):
        # Already absolute
        img_url = src
    elif src.startswith('/'):
        # Root-relative URL
        parsed_base = urlparse(base_url)
        img_url = f"{parsed_base.scheme}://{parsed_base.netloc}{src}"
    else:
        # Relative URL
        img_url = urljoin(base_url, src)
    
    # Validate URL
    try:
        parsed = urlparse(img_url)
        if not all([parsed.scheme, parsed.netloc]):
            logger.warning(f"Invalid image URL: {img_url}")
            return ''
    except Exception as e:
        logger.warning(f"Error parsing image URL {img_url}: {str(e)}")
        return ''
    
    # Get alt text
    alt_text = img_tag.get('alt', '').strip() or img_tag.get('title', '').strip()
    
    # Return formatted text with URL and alt text if available
    if alt_text:
        return f"[IMG: alt: {alt_text} URL: {img_url}]"
    else:
        return f"[IMG: URL: {img_url}]"

def get_ref_container(ref_content, soup):
    """Extract meaningful reference container.
    
    Args:
        ref_content: The reference content element
        soup: The BeautifulSoup object containing the full document
        
    Returns:
        The container element or None if no valid container found
    """
    current = ref_content
    max_levels = 3
    
    logger.debug(f"\nExamining reference container:")
    logger.debug(f"Initial element: {current.name} (id={current.get('id', 'None')})")
    
    for level in range(max_levels):
        if not current:
            logger.debug(f"Level {level}: No current element, breaking")
            break
            
        # Get text of current element
        text = current.get_text(strip=True)
        logger.debug(f"Level {level}: Examining {current.name} element")
        logger.debug(f"Text content: {text[:100]}...")
        
        # Skip if it's just a number or empty
        if text and not text.strip('[](){}.').isdigit():
            # Size check - container should be less than 20% of total document
            container_length = len(str(current))
            total_length = len(str(soup))
            size_ratio = container_length / total_length
            logger.debug(f"Container size ratio: {size_ratio:.2%}")
            
            if size_ratio > 0.2:
                logger.debug("Container too large (>20% of document), breaking")
                break
            
            # Structure check - should not contain any subheadings
            headings = current.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if headings:
                logger.debug(f"Found {len(headings)} headings in container, breaking")
                break
            
            logger.debug(f"Found valid reference container at level {level}")
            return current
            
        logger.debug("Text empty or just numbers, moving to parent")
        current = current.parent
        if current:
            logger.debug(f"New parent: {current.name} (id={current.get('id', 'None')})")
    
    logger.debug("No valid reference container found")
    return None

async def remove_unwanted_elements(soup: BeautifulSoup) -> None:
    """Remove unwanted elements like scripts, styles, iframes etc."""
    # Remove common unwanted elements
    for tag in ['script', 'style', 'iframe', 'nav', 'footer', 'aside']:
        elements = soup.find_all(tag)
        logger.debug(f"Removing {len(elements)} {tag} elements")
        for element in elements:
            element.decompose()
        logger.debug(f"Length after removing {tag} elements: {len(str(soup))}")
        logger.debug(f"Paragraphs after removing {tag} elements: {len(soup.find_all('p'))}")
    
    # Remove elements with inline CSS that hides them
    hidden_elements = soup.find_all(
        lambda tag: tag.get('style') and (
            'display: none' in tag['style'].lower() or
            'display:none' in tag['style'].lower() or
            'visibility: hidden' in tag['style'].lower() or
            'visibility:hidden' in tag['style'].lower() or
            'opacity: 0' in tag['style'].lower() or
            'opacity:0' in tag['style'].lower()
        )
    )
    logger.info(f"Removing {len(hidden_elements)} elements hidden by inline CSS")
    for element in hidden_elements:
        element.decompose()
    
    # Remove elements with hidden attribute
    hidden_attr_elements = soup.find_all(attrs={'hidden': True})
    logger.info(f"Removing {len(hidden_attr_elements)} elements with hidden attribute")
    for element in hidden_attr_elements:
        element.decompose()
    
    # Remove elements with aria-hidden="true"
    aria_hidden_elements = soup.find_all(attrs={'aria-hidden': 'true'})
    logger.info(f"Removing {len(aria_hidden_elements)} elements with aria-hidden=true")
    for element in aria_hidden_elements:
        element.decompose()

async def remove_navigation_elements(soup: BeautifulSoup) -> None:
    """Remove navigation-related elements from the soup."""
    # Remove site headers
    headers = soup.find_all('header')
    for header in headers:
        classes = header.get('class', [])
        if any(cls in classes for cls in ['site-header', 'main-header', 'navbar', 'top-header', 'global-header']):
            header.decompose()

    # Remove navigation elements by class and role
    nav_classes = ['navigation', 'nav', 'navbar', 'menu', 'navbox']
    nav_roles = ['navigation', 'menubar', 'menu']
    
    # Remove by role
    for elem in soup.find_all(attrs={"role": "navigation"}):
        elem.decompose()
    
    # Remove by class
    for nav_class in nav_classes:
        for element in soup.find_all(class_=nav_class):
            element.decompose()
    
    # Remove by role
    for role in nav_roles:
        for element in soup.find_all(attrs={"role": role}):
            element.decompose()
    
    # Remove Wikipedia-style navboxes
    for navbox in soup.find_all(class_=re.compile(r'.*navbox.*')):
        navbox.decompose()

def extract_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Extract and return the main content section of the document."""
    # Try finding elements that are definitely main content
    for selector in ['[role="main"]', '#main-content', '#content', '.main-content']:
        main_content = soup.select_one(selector)
        if main_content and len(str(main_content)) > 1000:
            return BeautifulSoup(str(main_content), 'html.parser')
    
    # Try article or main tags
    for tag in ['main', 'article']:
        element = soup.find(tag)
        if element and len(str(element)) > len(str(soup)) * 0.5:
            main_paragraphs = len(element.find_all('p'))
            total_paragraphs = len(soup.find_all('p'))
            
            if main_paragraphs > total_paragraphs * 0.7:
                return BeautifulSoup(str(element), 'html.parser')
    
    return soup

async def process_images_in_content(soup: BeautifulSoup, url: str) -> None:
    """Process all images in the content, replacing them with text descriptions."""
    images = soup.find_all('img')
    logger.info(f"Found {len(images)} images")
    
    # Limit total number of images
    if len(images) > MAX_TOTAL_IMAGES:
        logger.warning(f"Too many images ({len(images)}), processing only first {MAX_TOTAL_IMAGES}")
        images = images[:MAX_TOTAL_IMAGES]
    
    # Collect all image URLs and their tags
    img_data = []
    for img in images:
        try:
            # Get raw image URL
            src = img.get('src', '') or img.get('data-src', '')
            if not src:
                continue

            # Handle various URL formats
            if src.startswith('//'):
                img_url = f"https:{src}"
            elif src.startswith('http://') or src.startswith('https://'):
                img_url = src
            elif src.startswith('/'):
                parsed_base = urlparse(url)
                img_url = f"{parsed_base.scheme}://{parsed_base.netloc}{src}"
            else:
                img_url = urljoin(url, src)

            # Skip data URLs
            if img_url.startswith('data:image/'):
                continue

            # Validate URL
            try:
                parsed = urlparse(img_url)
                if not all([parsed.scheme, parsed.netloc]):
                    continue
                img_data.append((img, img_url))
            except Exception as e:
                logger.warning(f"Error parsing image URL {img_url}: {str(e)}")
                continue

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
    
    if not img_data:
        return

    # Process images in batches
    for i in range(0, len(img_data), MAX_CONCURRENT_IMAGES):
        batch = img_data[i:i + MAX_CONCURRENT_IMAGES]
        batch_urls = [url for _, url in batch]
        
        logger.info(f"Processing batch of {len(batch)} images ({i + 1}-{i + len(batch)} of {len(img_data)})")
        descriptions = await asyncio.gather(*[analyze_image(url) for url in batch_urls])

        # Replace images with their descriptions
        for (img, _), description in zip(batch, descriptions):
            try:
                if description:
                    img.replace_with(soup.new_string(f"[IMG: desc: {description}]"))
                else:
                    alt_text = img.get('alt', '').strip() or img.get('title', '').strip()
                    if alt_text:
                        img.replace_with(soup.new_string(f"[IMG: alt: {alt_text}]"))
                    else:
                        img.decompose()
            except Exception as e:
                logger.error(f"Error replacing image with description: {str(e)}")
                img.decompose()

def clean_whitespace(soup: BeautifulSoup) -> None:
    """Clean excess whitespace from text nodes."""
    for tag in soup.find_all(True):
        if tag.string:
            original = tag.string
            cleaned = re.sub(r'\s+', ' ', tag.string.strip())
            if original != cleaned:
                tag.string.replace_with(cleaned)

async def process_references(soup: BeautifulSoup) -> None:
    """Process all references in the document."""
    reference_links = soup.find_all('a', href=lambda h: h and h.startswith('#'))
    elements_to_remove = []
    
    i = 0
    while i < len(reference_links):
        try:
            ref_link = reference_links[i]
            
            # Skip if already marked for removal
            if any(elem in ref_link.parents for elem in elements_to_remove) or ref_link in elements_to_remove:
                i += 1
                continue
            
            # Try to process as range if there are more links
            if i + 1 < len(reference_links):
                success, refs_processed, range_text, range_containers = process_reference_range(
                    ref_link,
                    reference_links[i+1:],
                    soup
                )
                
                if success:
                    new_text = soup.new_string(range_text)
                    ref_link.replace_with(new_text)
                    reference_links[i + 1].extract()
                    elements_to_remove.extend(range_containers)
                    i += refs_processed + 1
                    continue
            
            # Process single reference
            await process_single_reference(ref_link, soup, elements_to_remove)
            
        except Exception as e:
            logger.error(f"Error processing reference: {str(e)}")
        
        i += 1
    
    # Remove reference containers
    for elem in elements_to_remove:
        elem.decompose()

async def process_single_reference(ref_link: BeautifulSoup, soup: BeautifulSoup, elements_to_remove: list) -> None:
    """Process a single reference link."""
    target_id = ref_link['href'][1:]
    ref_content = soup.find(id=target_id) or soup.find('a', attrs={'name': target_id})
    
    if not ref_content:
        return
    
    ref_container = get_ref_container(ref_content, soup)
    if ref_container:
        ref_num = ref_link.get_text().strip('[](){} .')
        ref_marker = f"[REF {ref_num}: " if ref_num.isdigit() else "[REF: "
        ref_text = f" {ref_marker}{ref_container.get_text(strip=True)}] "
        
        new_text = soup.new_string(ref_text)
        ref_link.replace_with(new_text)
        
        if ref_link not in ref_container.find_all() and ref_container not in elements_to_remove:
            elements_to_remove.append(ref_container)

async def clean_html(html: str, url: str = '') -> str:
    """Clean HTML content by removing unnecessary elements and formatting the content."""
    logger.debug("\n=== CLEANING HTML CONTENT ===")
    soup = BeautifulSoup(html, 'html.parser')
    
    try:
        # Preserve pre tags before cleaning
        pre_tags = {}
        for i, pre in enumerate(soup.find_all('pre')):
            placeholder = f"[PRE_TAG_{i}]"
            pre_tags[placeholder] = str(pre)
            pre.replace_with(soup.new_string(placeholder))
        
        # Remove unwanted and navigation elements
        await remove_unwanted_elements(soup)
        await remove_navigation_elements(soup)
        
        # Process references
        await process_references(soup)
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Extract main content
        soup = extract_main_content(soup)
        
        logger.info(f"Main content: {soup.get_text()[:100]}")
        
        # Process images
        await process_images_in_content(soup, url)
        
        # Clean whitespace
        clean_whitespace(soup)
        
        # Restore pre tags
        cleaned_html = str(soup)
        for placeholder, pre_content in pre_tags.items():
            cleaned_html = cleaned_html.replace(placeholder, pre_content)
        
        # Validate output
        if len(cleaned_html.strip()) == 0:
            logger.error("WARNING: Cleaning resulted in empty content!")
            return html
        
        return cleaned_html
        
    except Exception as e:
        logger.error(f"Error during HTML cleaning: {str(e)}")
        return html

def process_reference_range(start_link, next_links, soup):
    """Process a range of references (e.g., [2-4]) and return combined text.
    
    Args:
        start_link: The first link in the range
        next_links: List of subsequent links to check for range pattern
        soup: BeautifulSoup object containing the document
        
    Returns:
        tuple: (success, refs_processed, combined_text, containers_to_remove)
            success: Whether range was successfully processed
            refs_processed: Number of additional links consumed
            combined_text: The combined reference text with range marker
            containers_to_remove: List of reference containers to remove
    """
    # Check for range pattern (hyphen between links)
    if (len(next_links) < 1 or 
        not start_link.next_sibling or 
        not isinstance(start_link.next_sibling, str) or 
        '–' not in start_link.next_sibling):  # Handle both hyphen types
        return False, 0, None, []
            
    end_link = next_links[0]
    
    # Extract numbers and validate they match link text
    start_href = start_link['href'].lstrip('#')
    end_href = end_link['href'].lstrip('#')
    
    start_match = re.search(r'(\d+)$', start_href)
    end_match = re.search(r'(\d+)$', end_href)
    
    if not (start_match and end_match):
        return False, 0, None, []
            
    # Extract numbers and prefix
    start_num = int(start_match.group(1))
    end_num = int(end_match.group(1))
    
    # Get the prefix by removing the number from the start href
    prefix = start_href[:start_match.start()]
    
    # Validate both hrefs use same prefix
    if not end_href.startswith(prefix):
        return False, 0, None, []
    
    # Validate range
    if start_num >= end_num or (end_num - start_num) > 10:  # Limit range size for safety
        return False, 0, None, []
            
    logger.debug(f"Processing reference range: {start_num}-{end_num} with prefix {prefix}")
    
    # Collect all references in range
    range_refs = []
    containers_to_remove = []
    
    # Format number to match the same width as original
    num_width = len(start_match.group(1))
    
    for ref_num in range(start_num, end_num + 1):
        # Format the reference ID using the detected prefix and number format
        ref_id = f"{prefix}{ref_num:0{num_width}d}"
        ref_content = soup.find(id=ref_id)
        
        if not ref_content:
            logger.info(f"Missing reference {ref_num} in range")
            return False, 0, None, []
                
        ref_container = get_ref_container(ref_content, soup)
        if not ref_container:
            logger.debug(f"Could not extract container for reference {ref_num}")
            return False, 0, None, []
                
        range_refs.append(ref_container.get_text(strip=True))
        containers_to_remove.append(ref_container)
    
    # Create combined reference text
    combined_text = f"[REFS {start_num}-{end_num}: {'; '.join(range_refs)}] "
    logger.debug(f"Combined text: {combined_text}")
    
    return True, 1, combined_text, containers_to_remove 