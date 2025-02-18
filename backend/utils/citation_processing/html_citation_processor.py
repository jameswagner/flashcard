"""HTML-specific citation processing."""

from typing import Dict, Tuple, Optional
import re
import logging
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
            text_content: Raw HTML content with markers
            start_num: Starting element number
            end_num: Ending element number
            citation_type: Type of citation (section, paragraph, list, table)
            
        Returns:
            Preview text for the citation
        """
        lines = text_content.split('\n')
        
        # For element-based citations (tables, lists)
        if citation_type in [CitationType.html_table.value, CitationType.html_list.value]:
            marker = f"[{citation_type.split('_')[1].upper()} {start_num}]"
            for i, line in enumerate(lines):
                if marker in line:
                    # Extract until the next element or section
                    end_i = i + 1
                    while end_i < len(lines) and not any(
                        marker in lines[end_i] 
                        for marker in ['[SECTION:', '[TABLE', '[LIST', '[PARAGRAPH']
                    ):
                        end_i += 1
                    return "\n".join(lines[i:end_i])
        
        # For paragraph citations
        elif citation_type == CitationType.html_paragraph.value:
            paragraphs = []
            current_paragraph = 0
            
            for line in lines:
                if line.strip().startswith('[Paragraph '):
                    current_paragraph += 1
                    if start_num <= current_paragraph <= end_num:
                        paragraphs.append(line.strip())
            
            return "\n".join(paragraphs)
        
        # For section citations
        elif citation_type == CitationType.html_section.value:
            section_content = []
            in_target_section = False
            current_section = 0
            
            for line in lines:
                if line.strip().startswith('[Section '):
                    current_section += 1
                    if current_section == start_num:
                        in_target_section = True
                        section_content.append(line.strip())
                    elif current_section > end_num:
                        break
                elif in_target_section:
                    if line.strip().startswith('[Section '):
                        break
                    section_content.append(line.strip())
            
            return "\n".join(section_content)
        
        # Fallback for other citation types
        return super().get_preview_text(text_content, start_num, end_num) 