"""Module for processing HTML into structured content for flashcard generation."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
import json
import logging
from utils.content_processing.base import ContentProcessor

logger = logging.getLogger(__name__)

@dataclass
class HTMLSection:
    """Represents a section of HTML content with its heading."""
    level: int  # h1 = 1, h2 = 2, etc.
    heading: str
    paragraphs: List[str]

@dataclass
class HTMLContent:
    """Represents processed HTML content with sections, paragraphs, and other elements."""
    title: str
    sections: List[Dict]
    metadata: Dict

    def to_json(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'title': self.title,
            'sections': self.sections,
            'metadata': self.metadata
        }

    @classmethod
    def from_json(cls, json_data: Dict) -> 'HTMLContent':
        """Create HTMLContent from JSON data."""
        return cls(
            title=json_data.get('title', ''),
            sections=json_data.get('sections', []),
            metadata=json_data.get('metadata', {})
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
    """Convert a table into a list of text strings."""
    logger.info(f"Processing table: {table.prettify()[:200]}...")  # Log first 200 chars
    rows = []
    
    # Get headers if they exist
    headers = []
    header_row = table.find('thead')
    if header_row:
        headers = [th.get_text().strip() for th in header_row.find_all('th')]
        logger.info(f"Found table headers: {headers}")
    
    # Process each row
    for row in table.find_all('tr'):
        if row.find_parent('thead'):
            continue
            
        cells = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
        if cells:
            if headers and len(headers) == len(cells):
                row_text = " | ".join(f"{h}: {c}" for h, c in zip(headers, cells))
            else:
                row_text = " | ".join(cells)
            if row_text.strip():
                rows.append(row_text)
                logger.info(f"Processed row: {row_text}")
    
    logger.info(f"Table processing complete. Generated {len(rows)} rows")
    return rows

def process_list(list_tag: Tag) -> List[str]:
    """Convert a list into a sequence of text strings with appropriate markers."""
    logger.info(f"Processing list: {list_tag.prettify()[:200]}...")
    items = []
    is_ordered = list_tag.name == 'ol'
    
    for i, item in enumerate(list_tag.find_all('li', recursive=False)):
        text = ' '.join(item.get_text().split())
        if text:
            marker = f"{i+1}." if is_ordered else "•"
            items.append(f"{marker} {text}")
            logger.info(f"Processed list item: {items[-1]}")
    
    logger.info(f"List processing complete. Generated {len(items)} items")
    return items

class HTMLProcessor(ContentProcessor):
    """Processor for HTML content that maintains document structure."""
    
    def to_structured_json(self, raw_content: str, title: Optional[str] = None) -> Dict:
        """Convert raw HTML to structured JSON format."""
        logger.info(f"Starting HTML processing. Content length: {len(raw_content)}")
        logger.info(f"Raw content preview: {raw_content[:500]}...")
        
        if not raw_content.strip():
            logger.error("Received empty or whitespace-only content!")
            return {
                'title': title or "Empty Document",
                'sections': [],
                'metadata': {'error': 'Empty content received'}
            }
        
        try:
            soup = BeautifulSoup(raw_content, 'html.parser')
            logger.info(f"BeautifulSoup parsed content. Found {len(soup.find_all())} tags")
        except Exception as e:
            logger.error(f"Failed to parse HTML with BeautifulSoup: {str(e)}")
            raise
        
        # Extract title
        doc_title = title or self._extract_title(soup)
        logger.info(f"Extracted title: {doc_title}")
        
        # Process content into sections
        try:
            sections = self._process_sections(soup)
            logger.info(f"Processed {len(sections)} sections")
            for i, section in enumerate(sections):
                logger.info(f"Section {i+1}: {len(section.get('content', []))} content items")
                logger.info(f"Section {i+1} header: {section.get('header', 'No header')}")
        except Exception as e:
            logger.error(f"Error processing sections: {str(e)}", exc_info=True)
            raise
        
        # Create metadata
        metadata = {
            'total_sections': len(sections),
            'total_paragraphs': sum(len(section.get('content', [])) for section in sections),
            'has_tables': any('table' in str(item) for section in sections for item in section.get('content', [])),
            'has_lists': any('list' in str(item) for section in sections for item in section.get('content', []))
        }
        logger.info(f"Generated metadata: {metadata}")
        
        result = {
            'title': doc_title,
            'sections': sections,
            'metadata': metadata
        }
        
        logger.info("Final JSON structure:")
        logger.info(f"Title: {result['title']}")
        logger.info(f"Number of sections: {len(result['sections'])}")
        for i, section in enumerate(result['sections']):
            logger.info(f"Section {i+1} content count: {len(section.get('content', []))}")
        
        return result
    
    def _format_content_item(self, item: Dict, paragraph_num: int) -> Tuple[List[str], int]:
        """Format a single content item into a list of marked text lines.
    
    Args:
            item: Content item to format
            paragraph_num: Current paragraph number
            
        Returns:
            Tuple of (formatted lines, next paragraph number)
        """
        lines = []
        if isinstance(item, dict):
            if item.get('type') == 'paragraph':
                if 'paragraph_number' not in item or 'text' not in item:
                    logger.warning(f"Malformed paragraph item: {item}")
                    return lines, paragraph_num
                lines.append(f"[Paragraph {item['paragraph_number']}] {item['text']}")
                paragraph_num += 1
            elif item.get('type') == 'table':
                if 'table_id' not in item or 'content' not in item:
                    logger.warning(f"Malformed table item: {item}")
                    return lines, paragraph_num
                lines.append(f"[Table {item['table_id']}]")
                lines.extend(item['content'])
            elif item.get('type') == 'list':
                if 'list_id' not in item or 'items' not in item:
                    logger.warning(f"Malformed list item: {item}")
                    return lines, paragraph_num
                list_type = item.get('list_type', 'unordered')
                lines.append(f"[List {item['list_id']} Type: {list_type}]")
                # Use numbers for ordered lists, bullets for unordered
                if list_type == 'ordered':
                    lines.extend(f"{i+1}. {list_item}" for i, list_item in enumerate(item['items']))
                else:
                    lines.extend(f"• {list_item}" for list_item in item['items'])
        return lines, paragraph_num

    def to_prompt_text(self, structured_json: Dict) -> str:
        """Convert structured JSON to prompt text with nested section markers.
        
        Args:
            structured_json: Output from to_structured_json()
        
    Returns:
            Text with [Section X.Y.Z], [Paragraph N], etc. markers
        """
        lines = []
        current_paragraph = 1
        
        # Add title if present
        if structured_json.get('title'):
            lines.append(f"[Title] {structured_json['title']}\n")
        
        # Process sections with their full numbering
        for section in structured_json.get('sections', []):
            # Validate section has required fields
            if 'section_number' not in section:
                logger.warning(f"Section missing section_number: {section}")
                continue
                
            # Add section header with full path (e.g., "1.2.3")
            section_num = ".".join(str(n) for n in section['section_number'])
            if section.get('header'):
                lines.append(f"[Section {section_num}] {section['header']}")
            else:
                lines.append(f"[Section {section_num}]")
            
            # Process section content
            if 'content' not in section:
                logger.warning(f"Section {section_num} missing content")
                continue
                
            for item in section['content']:
                formatted_lines, current_paragraph = self._format_content_item(item, current_paragraph)
                lines.extend(formatted_lines)
            
            lines.append("")  # Add blank line between sections
        
        return "\n".join(lines).strip()
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title from HTML content."""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.text.strip()
        
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.text.strip()
        
        return "Untitled Document"
    
    def _process_sections(self, soup: BeautifulSoup) -> List[Dict]:
        """Process HTML content into sections with proper nesting based on header levels."""
        logger.info("Starting section processing")
        sections = []
        section_stack = []  # Stack to track current section hierarchy
        global_paragraph_counter = 0  # Global counter for paragraphs
        
        def get_header_level(tag_name: str) -> int:
            """Get numeric level from header tag name (h1 -> 1, h2 -> 2, etc.)"""
            return int(tag_name[1]) if tag_name[1:].isdigit() else 0
        
        def process_element(element: Tag) -> None:
            """Process a single element and its children."""
            nonlocal section_stack, global_paragraph_counter
            
            # Skip script, style, and other non-content tags
            if element.name in ['script', 'style', 'meta', 'link', 'noscript']:
                return
                
            logger.info(f"Processing element: <{element.name}> with {len(element.get_text().strip())} chars of text")
            
            # Handle header tags (h1 through h6)
            if element.name and element.name.startswith('h') and element.name[1:].isdigit():
                current_level = get_header_level(element.name)
                header_text = element.get_text().strip()
                
                # Pop sections from stack until we find appropriate parent level
                while section_stack and section_stack[-1]['level'] >= current_level:
                    section_stack.pop()
                
                # Create new section
                new_section = {
                    'level': current_level,
                    'header': header_text,
                    'content': [],
                    'subsections': []
                }
                
                # Add to parent section or top level
                if section_stack:
                    section_stack[-1]['subsections'].append(new_section)
                else:
                    sections.append(new_section)
                
                # Push new section onto stack
                section_stack.append(new_section)
                logger.info(f"Created new section level {current_level}: {header_text}")
                
            elif not section_stack:
                # Create default section if none exists
                default_section = {
                    'level': 1,
                    'header': '',
                    'content': [],
                    'subsections': []
                }
                sections.append(default_section)
                section_stack.append(default_section)
                logger.info("Created default section")
            
            # Process content based on type
            try:
                current_section = section_stack[-1]
                if element.name == 'p':
                    text = element.get_text().strip()
                    if text:  # Only add non-empty paragraphs
                        # Increment global paragraph counter
                        global_paragraph_counter += 1
                        current_section['content'].append({
                            'type': 'paragraph',
                            'text': text,
                            'paragraph_number': global_paragraph_counter
                        })
                        logger.info(f"Added paragraph {global_paragraph_counter} to section level {current_section['level']}: {text[:100]}...")
                elif element.name == 'table':
                    table_content = process_table(element)
                    if table_content:  # Only add non-empty tables
                        table_id = len([x for x in current_section['content'] if isinstance(x, dict) and x.get('type') == 'table']) + 1
                        current_section['content'].append({
                            'type': 'table',
                            'table_id': table_id,
                            'content': table_content
                        })
                        logger.info(f"Added table {table_id} to section level {current_section['level']}")
                elif element.name in ['ul', 'ol']:
                    list_content = process_list(element)
                    if list_content:  # Only add non-empty lists
                        list_id = len([x for x in current_section['content'] if isinstance(x, dict) and x.get('type') == 'list']) + 1
                        current_section['content'].append({
                            'type': 'list',
                            'list_id': list_id,
                            'items': list_content,
                            'list_type': 'ordered' if element.name == 'ol' else 'unordered'
                        })
                        logger.info(f"Added {element.name} list {list_id} to section level {current_section['level']}")
                elif element.name in ['div', 'article', 'section', 'main']:
                    # For container elements, process their children
                    for child in element.children:
                        if isinstance(child, Tag):
                            process_element(child)
                elif element.name and is_text_container(element):
                    # Handle other elements that directly contain text
                    text = element.get_text().strip()
                    if text:
                        # Increment global paragraph counter
                        global_paragraph_counter += 1
                        current_section['content'].append({
                            'type': 'paragraph',
                            'text': text,
                            'paragraph_number': global_paragraph_counter
                        })
                        logger.info(f"Added paragraph {global_paragraph_counter} from <{element.name}> to section level {current_section['level']}: {text[:100]}...")
            except Exception as e:
                logger.error(f"Error processing element <{element.name}>: {str(e)}", exc_info=True)
        
        # Get the main content area (body or main content div)
        content_area = soup.body or soup
        logger.info(f"Content area contains {len(content_area.find_all())} total tags")
        
        # Process all elements
        for element in content_area.children:
            if isinstance(element, Tag):
                process_element(element)
        
        def flatten_sections(sections_list: List[Dict]) -> List[Dict]:
            """Convert nested section structure to flat list with proper numbering."""
            flat_sections = []
            level_counters = {}  # Track counters for each level
            
            def process_section(section: Dict, parent_nums: List[int]) -> None:
                level = len(parent_nums) + 1  # Current level (1-based)
                
                # Reset counters for all deeper levels
                deeper_levels = [l for l in level_counters if l > level]
                for l in deeper_levels:
                    del level_counters[l]
                
                # Initialize or increment counter for current level
                if level not in level_counters:
                    level_counters[level] = 0
                level_counters[level] += 1
                
                # Build section number using parent numbers + current level counter
                section_num = parent_nums + [level_counters[level]]
                
                # Create flat section
                flat_section = {
                    'header': section['header'],
                    'content': section['content'],
                    'section_number': section_num
                }
                flat_sections.append(flat_section)
                
                # Process subsections
                for subsection in section.get('subsections', []):
                    process_section(subsection, section_num)
            
            # Process top-level sections
            for section in sections_list:
                process_section(section, [])
            
            return flat_sections
        
        # Convert nested structure to flat list with proper numbering
        flat_sections = flatten_sections(sections)
        logger.info(f"Section processing complete. Generated {len(flat_sections)} total sections")
        return flat_sections

# For backward compatibility
def process_html(content: str, title: Optional[str] = None) -> HTMLContent:
    """Process HTML content into structured format. For backward compatibility."""
    processor = HTMLProcessor()
    structured_json = processor.to_structured_json(content, title)
    return HTMLContent.from_json(structured_json) 