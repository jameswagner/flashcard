"""Citation sorting utilities."""

from typing import List, Dict, Any, Optional, Tuple
import logging
from models.enums import CitationType, FileType

logger = logging.getLogger(__name__)

def sort_flashcards_by_earliest_citation(
    flashcards: List[Dict[str, Any]], 
    file_type: str,
    html_content: Optional[Dict] = None
) -> List[Dict[str, Any]]:
    """Sort flashcards by their earliest citation position.
    
    Args:
        flashcards: List of flashcard dictionaries with citations
        file_type: Type of source file (HTML, TXT, YOUTUBE_TRANSCRIPT)
        html_content: JSON structure of HTML content with sections, paragraphs, lists, tables
        
    Returns:
        Sorted list of flashcards
    """
    def get_earliest_position(card: Dict[str, Any]) -> tuple:
        citations = card.get('citations', [])
        if not citations:
            return (float('inf'),)
            
        # HTML needs special handling due to nested structure
        if file_type == FileType.HTML.value:
            if not html_content:
                return (float('inf'),)
            return _get_earliest_html_position(citations, html_content)
        else:  # Linear content (text, YouTube) just sorts by first number
            return (_get_earliest_linear_position(citations),)
    
    return sorted(flashcards, key=get_earliest_position)

def _get_earliest_linear_position(citations: List[Dict[str, Any]]) -> int:
    """Get earliest citation position for linear content (text/YouTube)."""
    earliest = float('inf')
    
    for citation in citations:
        if isinstance(citation, dict) and 'range' in citation:
            start = citation['range'][0]
            earliest = min(earliest, start)
        elif isinstance(citation, (list, tuple)) and len(citation) == 2:
            earliest = min(earliest, citation[0])
            
    return earliest

def _build_element_index(html_content: Dict) -> Dict[str, Tuple[int, ...]]:
    """Build index mapping each element to its hierarchical position in the document.
    
    Args:
        html_content: JSON structure containing sections and their contents
        
    Returns:
        Dict mapping element keys (e.g. 'paragraph_1', 'list_2') to their position tuple.
        Position tuple format: (section_level_1, section_level_2, ..., element_index)
    """
    element_index = {}
    
    def process_section(section: Dict, current_path: Tuple[int, ...], section_idx: int):
        # Current section's path includes its index at this level
        section_path = current_path + (section_idx,)
        
        # Process section itself
        if 'heading' in section:
            # Extract section number from heading, preserving hierarchical structure
            section_parts = section['heading'].split('[Section ')[1].split(']')[0].split('.')
            section_key = f'section_{section_parts[0]}'  # Use first number as main identifier
            element_index[section_key] = section_path
            
            # Also index the full hierarchical path
            if len(section_parts) > 1:
                full_section_key = f'section_{"_".join(section_parts)}'
                element_index[full_section_key] = section_path
        
        # Process elements in this section
        for elem_idx, paragraph in enumerate(section.get('paragraphs', [])):
            # Element path includes its index within the section
            element_path = section_path + (elem_idx,)
            
            # Check for different element types
            if paragraph.startswith('[Paragraph '):
                num = int(paragraph.split('[Paragraph ')[1].split(']')[0])
                element_index[f'paragraph_{num}'] = element_path
            elif paragraph.startswith('[List '):
                num = int(paragraph.split('[List ')[1].split(']')[0])
                element_index[f'list_{num}'] = element_path
            elif paragraph.startswith('[Table '):
                num = int(paragraph.split('[Table ')[1].split(']')[0])
                element_index[f'table_{num}'] = element_path
            
        # Process nested sections, maintaining their level in the path
        for subsection_idx, subsection in enumerate(section.get('sections', [])):
            process_section(subsection, section_path, subsection_idx)
    
    # Process all top-level sections
    for section_idx, section in enumerate(html_content.get('sections', [])):
        process_section(section, (), section_idx)
        
    return element_index

def _get_earliest_html_position(citations: List[Dict[str, Any]], html_content: Dict) -> tuple:
    """Get earliest position for HTML content using document structure."""
    element_index = _build_element_index(html_content)
    earliest_position = None
    
    for citation in citations:
        if isinstance(citation, dict):
            citation_type = citation.get('citation_type')
            if not citation_type:
                continue
                
            # Get element number from range or id
            element_num = None
            if 'range' in citation:
                element_num = citation['range'][0]  # Use start of range
            elif 'id' in citation:
                element_num = citation['id']
                
            if element_num is not None:
                # Convert citation type to element key format
                element_type = citation_type.split('html_')[1]  # e.g. 'html_paragraph' -> 'paragraph'
                element_key = f'{element_type}_{element_num}'
                
                # Get position from index
                position = element_index.get(element_key)
                if position:
                    if earliest_position is None:
                        earliest_position = position
                    else:
                        earliest_position = min(earliest_position, position)
    
    return earliest_position if earliest_position is not None else (float('inf'),) 