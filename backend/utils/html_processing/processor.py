"""Module for processing HTML into structured content for flashcard generation."""

from dataclasses import dataclass
from typing import List, Optional
from bs4 import BeautifulSoup, NavigableString, Tag
import json

@dataclass
class HTMLSection:
    """Represents a section of HTML content with its heading."""
    level: int  # h1 = 1, h2 = 2, etc.
    heading: str
    paragraphs: List[str]

@dataclass
class HTMLContent:
    """Represents processed HTML content with sections and paragraphs."""
    title: str
    sections: List[HTMLSection]
    
    def to_json(self) -> str:
        """Convert to JSON format for storage."""
        return json.dumps({
            'title': self.title,
            'sections': [{
                'level': s.level,
                'heading': s.heading,
                'paragraphs': s.paragraphs
            } for s in self.sections]
        })
    
    @staticmethod
    def from_json(json_str: str) -> 'HTMLContent':
        """Create HTMLContent from JSON string."""
        data = json.loads(json_str)
        return HTMLContent(
            title=data['title'],
            sections=[HTMLSection(
                level=s['level'],
                heading=s['heading'],
                paragraphs=s['paragraphs']
            ) for s in data['sections']]
        )

def is_text_container(tag) -> bool:
    """Check if a tag directly contains text (is a leaf node for text content)."""
    # Check if tag has any nested block elements
    block_elements = ['p', 'div', 'section', 'article', 'header', 'footer', 'nav']
    has_block_children = any(child.name in block_elements for child in tag.children if child.name)
    
    # Get direct text content (excluding nested tags)
    text = ''.join(child for child in tag.children 
                  if isinstance(child, NavigableString)).strip()
    
    return bool(text) and not has_block_children

def process_table(table: Tag) -> List[str]:
    """Convert a table into a list of text strings.
    
    Each row is converted to a structured format:
    Column1: value1 | Column2: value2 | ...
    """
    rows = []
    
    # Get headers if they exist
    headers = []
    header_row = table.find('thead')
    if header_row:
        headers = [th.get_text().strip() for th in header_row.find_all('th')]
    
    # Process each row
    for row in table.find_all('tr'):
        # Skip header row if we already processed it
        if row.find_parent('thead'):
            continue
            
        cells = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
        if cells:
            if headers and len(headers) == len(cells):
                # Use headers if available
                row_text = " | ".join(f"{h}: {c}" for h, c in zip(headers, cells))
            else:
                # Just use cell values
                row_text = " | ".join(cells)
            if row_text.strip():
                rows.append(row_text)
    
    return rows

def process_list(list_tag: Tag) -> List[str]:
    """Convert a list into a sequence of text strings with appropriate markers."""
    items = []
    is_ordered = list_tag.name == 'ol'
    
    for i, item in enumerate(list_tag.find_all('li', recursive=False)):
        text = ' '.join(item.get_text().split())
        if text:
            marker = f"{i+1}." if is_ordered else "•"
            items.append(f"{marker} {text}")
    
    return items

def process_html(html: str, title: str) -> HTMLContent:
    """Process HTML content into structured format for flashcard generation.
    
    Args:
        html: The HTML content to process
        title: The title of the content
        
    Returns:
        HTMLContent object with structured content
    """
    soup = BeautifulSoup(html, 'html.parser')
    sections: List[HTMLSection] = []
    current_section = None
    
    # Counters for different elements
    section_counters = [0] * 6  # One counter for each heading level (h1-h6)
    paragraph_count = 0
    table_count = 0
    list_count = 0
    
    def extract_text(tag) -> str:
        """Extract clean text from a tag."""
        return ' '.join(tag.get_text().split())
    
    def get_section_number(level: int) -> str:
        """Generate hierarchical section number."""
        # Reset all counters below the current level
        for i in range(level, len(section_counters)):
            section_counters[i] = 0
        # Increment current level counter
        section_counters[level - 1] += 1
        # Build section number using all relevant levels
        return '.'.join(str(count) for count in section_counters[:level] if count > 0)
    
    # Start with a default section if there's content before any heading
    section_counters[0] += 1
    current_section = HTMLSection(level=1, heading=f"[Section 1] {title}", paragraphs=[])
    sections.append(current_section)
    
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'span', 'table', 'ul', 'ol']):
        # Handle headings
        if tag.name.startswith('h'):
            level = int(tag.name[1])
            heading_text = extract_text(tag)
            if heading_text:
                section_num = get_section_number(level)
                current_section = HTMLSection(level=level, heading=f"[Section {section_num}] {heading_text}", paragraphs=[])
                sections.append(current_section)
        
        # Handle tables
        elif tag.name == 'table':
            if current_section:
                table_count += 1
                table_rows = process_table(tag)
                if table_rows:
                    current_section.paragraphs.append(f"[Table {table_count}]")
                    current_section.paragraphs.extend(table_rows)
        
        # Handle lists
        elif tag.name in ['ul', 'ol']:
            if current_section:
                list_count += 1
                list_items = process_list(tag)
                if list_items:
                    current_section.paragraphs.append(f"[List {list_count}]")
                    current_section.paragraphs.extend(list_items)
        
        # Handle paragraphs and text containers
        elif tag.name == 'p' or (tag.name in ['div', 'span'] and is_text_container(tag)):
            text = extract_text(tag)
            if text and current_section and len(text.split()) > 3:  # Only include if it has more than 3 words
                paragraph_count += 1
                current_section.paragraphs.append(f"[Paragraph {paragraph_count}] {text}")
    
    # Remove sections with no paragraphs
    sections = [s for s in sections if s.paragraphs]
    
    return HTMLContent(title=title, sections=sections) 