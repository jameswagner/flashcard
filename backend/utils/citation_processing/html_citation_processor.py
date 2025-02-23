"""HTML-specific citation processing."""

from typing import Dict, Tuple, Optional
import re
import logging
import json
from .citation_processor import CitationProcessor
from models.enums import CitationType

logger = logging.getLogger(__name__)

class HTMLCitationProcessor(CitationProcessor):
    """Processor for HTML citations with nested structure support."""
    
    def __init__(self):
        super().__init__()
        self._element_type_order = {
            'html_section': 0,
            'html_paragraph': 1,
            'html_list': 2,
            'html_table': 3
        }
        self._position_tuple_length = 10  # 9 levels + element type

    def build_element_index(self, html_structure: dict) -> Dict[str, Tuple[Tuple[int, ...], int]]:
        """Build an index of HTML elements for position lookups.
        
        Args:
            html_structure: Dictionary containing parsed HTML structure
            
        Returns:
            dict: Mapping of {element_key: (position_tuple, element_type)}
            where position_tuple is (level_1_idx, level_2_idx, ..., element_idx)
        """
        element_index = {}

        def process_section(section: dict, current_path: tuple) -> None:
            """Recursively process a section and its subsections."""
            # Extract section number from heading
            if 'heading' in section:
                section_match = re.search(r'\[Section (\d+)(?:\.\d+)*\]', section['heading'])
                if section_match:
                    section_num = int(section_match.group(1))
                    element_index[f"section_{section_num}"] = (
                        current_path + (0,) * (self._position_tuple_length - len(current_path) - 1),
                        self._element_type_order['html_section']
                    )
            
            # Process elements at this level
            for i, element in enumerate(section.get('paragraphs', [])):
                for element_type in ['Paragraph', 'List', 'Table']:
                    match = re.search(fr'\[{element_type} (\d+)\]', element)
                    if match:
                        num = int(match.group(1))
                        type_key = f"html_{element_type.lower()}"
                        element_index[f"{element_type.lower()}_{num}"] = (
                            current_path + (i,) + (0,) * (self._position_tuple_length - len(current_path) - 2),
                            self._element_type_order[type_key]
                        )
                        break
            
            # Process nested sections
            for i, subsection in enumerate(section.get('sections', [])):
                level = subsection.get('level', len(current_path) + 1)
                padding_needed = level - len(current_path) - 1
                if padding_needed > 0:
                    new_path = current_path + (0,) * padding_needed + (i,)
                else:
                    new_path = current_path + (i,)
                process_section(subsection, new_path)

        # Process each top-level section
        for i, section in enumerate(html_structure.get('sections', [])):
            process_section(section, (i,))
        
        return element_index

    def get_element_position(
        self, 
        citation: dict, 
        html_structure: dict, 
        element_index: Optional[Dict[str, Tuple[Tuple[int, ...], int]]] = None
    ) -> Tuple[int, ...]:
        """Get the position of an element in the HTML structure.
        
        Args:
            citation: Citation dictionary with type and location info
            html_structure: Dictionary containing parsed HTML structure
            element_index: Optional pre-built element index
            
        Returns:
            tuple: Position tuple for sorting (level_1_idx, level_2_idx, ..., element_type)
        """
        # Default position for unfound elements
        default_position = (float('inf'),) * (self._position_tuple_length - 1) + (4,)
        
        citation_type = citation.get('citation_type')
        if not citation_type:
            return default_position
        
        # Build or use existing element index
        if element_index is None:
            element_index = self.build_element_index(html_structure)
        
        # Try to get position from index
        element_num = None
        if citation.get('range'):
            element_num = citation['range'][0]  # Use start of range
        elif citation.get('id'):
            element_num = citation['id']
            
        if element_num is not None:
            element_key = f"{citation_type.split('html_')[1]}_{element_num}"
            indexed_position = element_index.get(element_key)
            if indexed_position:
                position_tuple, element_type = indexed_position
                return position_tuple + (element_type,)
        
        return default_position

    def get_preview_text(
        self, 
        text_content: str, 
        start_num: int, 
        end_num: int, 
        citation_type: str
    ) -> str:
        """Extract preview text from HTML content based on citation type.
        
        Args:
            text_content: JSON string containing HTML structure
            start_num: Starting element number
            end_num: Ending element number
            citation_type: Type of citation (section, paragraph, list, table)
            
        Returns:
            Preview text for the citation
        """
        logger.info(f"Getting preview text for citation: type={citation_type}, start={start_num}, end={end_num}")
        
        try:
            # Parse the JSON content
            content = json.loads(text_content)
            logger.info("Successfully parsed JSON content")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON content: {e}")
            return ""

        def find_section_by_number(sections, target_num):
            """Recursively find a section by its number."""
            for section in sections:
                if 'heading' in section:
                    match = re.search(r'\[Section (\d+(?:\.\d+)*)\]', section['heading'])
                    if match and match.group(1).split('.')[0] == str(target_num):
                        return section
                # Check nested sections
                if 'sections' in section:
                    result = find_section_by_number(section['sections'], target_num)
                    if result:
                        return result
            return None

        # For section citations
        if citation_type == CitationType.section.value:
            section = find_section_by_number(content.get('sections', []), start_num)
            if section:
                # Include heading and all paragraphs
                preview = [section['heading']]
                preview.extend(section.get('paragraphs', []))
                return "\n".join(preview)

        # For paragraph citations
        elif citation_type == CitationType.paragraph.value:
            paragraphs = []
            # Search through all sections and their nested sections
            def gather_paragraphs(sections):
                for section in sections:
                    for para in section.get('paragraphs', []):
                        match = re.search(r'\[Paragraph (\d+)\]', para)
                        if match and start_num <= int(match.group(1)) <= end_num:
                            paragraphs.append(para)
                    # Check nested sections
                    if 'sections' in section:
                        gather_paragraphs(section['sections'])
            
            gather_paragraphs(content.get('sections', []))
            return "\n".join(paragraphs)

        # For list and table citations
        elif citation_type in [CitationType.list.value, CitationType.table.value]:
            element_type = citation_type.split('_')[1].upper()
            # Search through all sections and their nested sections
            def find_element(sections):
                for section in sections:
                    for para in section.get('paragraphs', []):
                        if para.startswith(f"[{element_type} {start_num}]"):
                            return para
                    # Check nested sections
                    if 'sections' in section:
                        result = find_element(section['sections'])
                        if result:
                            return result
                return None
            
            element = find_element(content.get('sections', []))
            return element if element else ""

        logger.warning(f"Unsupported citation type: {citation_type}")
        return "" 