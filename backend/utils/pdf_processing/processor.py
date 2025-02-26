"""Module for processing PDF files with clear separation between detection and structure building."""

import fitz
import json
import logging
from typing import Dict, Tuple, Optional, Union
import typing
from dataclasses import dataclass, asdict
from nltk.tokenize import sent_tokenize
import nltk
from statistics import mode
import re
import os
import glob
import sys
from utils.content_processing.base import ContentProcessor

# Ensure NLTK data is downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

logger = logging.getLogger(__name__)

def sanitize_text(text: str) -> str:
    """Sanitize text by removing NUL characters and normalizing whitespace."""
    if not isinstance(text, str):
        text = str(text)
    return ' '.join(text.replace('\x00', '').split())

@dataclass
class Line:
    """Represents a line of text with its properties and classification"""
    text: str
    x_min: float
    size: float
    color: int
    is_bold: bool
    is_italic: bool
    is_all_caps: bool
    block_num: int  # Which block this belongs to
    spans: typing.List[Dict]  # Original spans that make up this line
    
    # Classification flags (can be multiple)
    is_header: bool = False
    is_paragraph_start: bool = False
    is_list_item: bool = False
    list_type: Optional[str] = None
    list_marker_x: Optional[float] = None
    continuation_lines: typing.List['Line'] = None
    
    # Debug info
    classification_reason: str = ""

    def __post_init__(self):
        # Sanitize text during initialization
        self.text = sanitize_text(self.text)

@dataclass
class Block:
    """Statistics and properties of a block of text"""
    block_num: int
    lines: typing.List[Line]
    predominant_x: float
    predominant_size: float
    predominant_color: int
    is_mostly_bold: bool
    is_mostly_italic: bool

@dataclass
class ListItem:
    """Represents a list item with its continuation lines"""
    text: str
    continuation_texts: typing.List[str]
    marker_type: str

@dataclass
class Paragraph:
    """Represents a paragraph with its sentences"""
    sentences: typing.List[str]
    is_first_in_section: bool = False

@dataclass
class DocumentList:
    """Represents a list with its items"""
    items: typing.List[ListItem]
    marker_type: str

@dataclass
class Section:
    """Represents a section in the document"""
    header: str
    content: typing.List[Union[Paragraph, ListItem, DocumentList]]  # Mixed list of paragraphs, list items, and lists in order

@dataclass
class ProcessedDocument:
    """Final processed document structure"""
    title: str
    sections: typing.List[Section]
    metadata: Dict

    def __post_init__(self):
        # Sanitize title during initialization
        self.title = sanitize_text(self.title)

    def to_json(self) -> Dict:
        """Convert the document to a JSON-serializable dictionary"""
        return {
            'title': sanitize_text(self.title),
            'sections': [
                {
                    'header': sanitize_text(section.header),
                    'content': [
                        {
                            'sentences': [sanitize_text(s) for s in item.sentences],
                            'is_first_in_section': item.is_first_in_section
                        } if isinstance(item, Paragraph) else (
                            {
                                'items': [
                                    {
                                        'text': sanitize_text(li.text),
                                        'continuation_texts': [sanitize_text(t) for t in li.continuation_texts],
                                        'marker_type': li.marker_type
                                    } for li in item.items
                                ],
                                'marker_type': item.marker_type
                            } if isinstance(item, DocumentList) else {
                                'text': sanitize_text(item.text),
                                'continuation_texts': [sanitize_text(t) for t in item.continuation_texts],
                                'marker_type': item.marker_type
                            }
                        ) for item in section.content
                    ]
                } for section in self.sections
            ],
            'metadata': self.metadata
        }

    @classmethod
    def from_json(cls, json_data: Dict) -> 'ProcessedDocument':
        """Create a ProcessedDocument from a JSON dictionary."""
        sections = []
        for section_data in json_data.get('sections', []):
            content = []
            for item in section_data.get('content', []):
                if 'sentences' in item:
                    content.append(Paragraph(
                        sentences=item['sentences'],
                        is_first_in_section=item.get('is_first_in_section', False)
                    ))
                elif 'items' in item:
                    # It's a list
                    list_items = [
                        ListItem(
                            text=li['text'],
                            continuation_texts=li.get('continuation_texts', []),
                            marker_type=li.get('marker_type', '')
                        ) for li in item['items']
                    ]
                    content.append(DocumentList(
                        items=list_items,
                        marker_type=item.get('marker_type', '')
                    ))
                elif 'text' in item:
                    # Single list item (for backward compatibility)
                    content.append(ListItem(
                        text=item['text'],
                        continuation_texts=item.get('continuation_texts', []),
                        marker_type=item.get('marker_type', '')
                    ))
            sections.append(Section(
                header=section_data.get('header', ''),
                content=content
            ))
        
        return cls(
            title=json_data.get('title', ''),
            sections=sections,
            metadata=json_data.get('metadata', {})
        )

    def to_prompt_text(self) -> str:
        """Convert the document to a text format with section, paragraph, and sentence markers."""
        lines = []
        current_paragraph = 1
        current_sentence = 1

        for section_num, section in enumerate(self.sections, 1):
            # Add section header
            lines.append(f"[Section {section_num}] {section.header}")

            for item in section.content:
                if isinstance(item, Paragraph):
                    # Add paragraph with sentences
                    lines.append(f"[Paragraph {current_paragraph}]")
                    for sentence in item.sentences:
                        lines.append(f"[SENTENCE {current_sentence}] {sentence}")
                        current_sentence += 1
                    current_paragraph += 1
                elif isinstance(item, DocumentList):
                    # Add list with all its items
                    lines.append(f"[List {current_paragraph} Type: {item.marker_type}]")
                    for list_item in item.items:
                        lines.append(list_item.text)
                        if list_item.continuation_texts:
                            for cont in list_item.continuation_texts:
                                lines.append(cont)
                    current_paragraph += 1
                elif isinstance(item, ListItem):
                    # Handle single list items (for backward compatibility)
                    lines.append(f"[List {current_paragraph}]")
                    lines.append(item.text)
                    if item.continuation_texts:
                        for cont in item.continuation_texts:
                            lines.append(cont)
                    current_paragraph += 1

        return "\n".join(lines)

def extract_line_properties(span: Dict) -> Dict:
    """Extract relevant properties from a text span"""
    font = span.get('font', 'unknown')
    return {
        'text': sanitize_text(span.get('text', '').strip()),
        'x_min': span['bbox'][0],
        'size': float(span.get('size', 0)),
        'color': span.get('color', 0),
        'is_bold': 'Bold' in font or ',B' in font,
        'is_italic': 'Italic' in font or ',I' in font,
    }

def consolidate_spans_to_line(spans: typing.List[Dict], block_num: int) -> Line:
    """Combine spans into a single line with properties"""
    if not spans:
        logger.info("No spans to consolidate")
        return None
        
    # Sort spans by x position
    spans = sorted(spans, key=lambda s: s['bbox'][0])
    
    
    # Get properties from first (leftmost) span
    first_span = spans[0]
    props = extract_line_properties(first_span)
    
    # Combine text from all spans
    raw_texts = [span.get('text', '').strip() for span in spans]
    text = ' '.join(raw_texts)
    text = ' '.join(text.split())  # Normalize whitespace
    
    if not text:
        return None
        
    return Line(
        text=text,
        x_min=props['x_min'],
        size=props['size'],
        color=props['color'],
        is_bold=props['is_bold'],
        is_italic=props['is_italic'],
        is_all_caps=text.isupper() and len(text) > 3,
        block_num=block_num,
        spans=spans,  # Store original spans
        continuation_lines=[]
    )

def consolidate_lines(doc: fitz.Document) -> typing.List[Block]:
    """Extract and consolidate lines from document, preserving block order"""
    blocks = []
    
    for page_num, page in enumerate(doc):
        page_dict = page.get_text("dict")
        
        for block in page_dict['blocks']:
            if block['type'] != 0:  # Skip non-text blocks
                continue
                
            # Group spans by vertical position (y-coordinate)
            spans_by_line = {}
            for line in block.get('lines', []):
                y = line['bbox'][1]  # Top y-coordinate
                spans = line.get('spans', [])
                spans_by_line.setdefault(y, []).extend(spans)
            
            # Convert each group of spans to a Line
            lines = []
            for y in sorted(spans_by_line.keys()):
                line = consolidate_spans_to_line(spans_by_line[y], len(blocks))
                if line:
                    lines.append(line)
            
            if not lines:
                continue
                
            # Calculate block statistics
            x_positions = [line.x_min for line in lines]
            sizes = [line.size for line in lines]
            colors = [line.color for line in lines]
            bold_count = sum(1 for line in lines if line.is_bold)
            italic_count = sum(1 for line in lines if line.is_italic)
            
            block = Block(
                block_num=len(blocks),
                lines=lines,
                predominant_x=mode(x_positions),
                predominant_size=mode(sizes),
                predominant_color=mode(colors),
                is_mostly_bold=bold_count / len(lines) > 0.8,
                is_mostly_italic=italic_count / len(lines) > 0.8
            )
            
            blocks.append(block)
    
    return blocks

def detect_headers(blocks: typing.List[Block]) -> None:
    """Detect header lines based on style differences"""
    for block in blocks:
        for i, line in enumerate(block.lines):
            # Skip lines that look like bibliography entries
            if re.match(r'^\d+\s+[A-Z]', line.text):  # Bibliography pattern like "1 Author"
                continue
                
            # Clear header indicators
            reasons = []
            
            if line.size > block.predominant_size * 1.1:
                reasons.append(f"larger size: {line.size:.1f} vs {block.predominant_size:.1f}")
                
            if line.color != block.predominant_color:
                reasons.append(f"different color: {line.color} vs {block.predominant_color}")
                
            if line.is_bold and not block.is_mostly_bold:
                reasons.append("bold in non-bold block")
                
            # Only count all caps if it's not a short reference
            if line.is_all_caps and len(line.text.split()) > 3:
                reasons.append("all caps")
            
            if reasons:
                line.is_header = True
                line.classification_reason = "Header: " + ", ".join(reasons)
                logger.info(f"Header detected [Block {block.block_num}, Line {i}]: {line.text[:100]}")

def detect_paragraphs(blocks: typing.List[Block]) -> None:
    """Detect paragraph starts based on indentation and headers"""
    prev_line = None
    first_content_line = True  # Track if we've seen the first non-header line
    
    for block in blocks:
        for i, line in enumerate(block.lines):
            # Skip if already classified as header or processed as list item/continuation
            if line.is_header or getattr(line, 'is_processed', False):
                prev_line = line
                continue
            
            # Clear paragraph indicators
            reasons = []
            
            if first_content_line:
                reasons.append("first content line")
                first_content_line = False
            elif prev_line and prev_line.is_header:
                reasons.append("follows header")
            elif prev_line and line.x_min > prev_line.x_min + 5:
                reasons.append(f"indented: {line.x_min:.1f} vs {prev_line.x_min:.1f}")
            
            if reasons:
                line.is_paragraph_start = True
                line.classification_reason = "Paragraph start: " + ", ".join(reasons)
                logger.info(f"Paragraph start [Block {block.block_num}, Line {i}]: {line.text[:100]}")
            
            prev_line = line

def is_list_marker(text: str, font: str = None) -> Tuple[bool, str]:
    """Check if text starts with a list marker"""
    text = text.strip()
    if not text:
        return False, ""
        
    # Check for numeric markers - allow bare numbers at start of line
    if text[0].isdigit():
        num_str = ""
        for c in text:
            if c.isdigit():
                num_str += c
            elif not c.isspace():
                break
        if num_str:
            # Found a number at start of line
            return True, "numeric"
            
    # Check for letter markers with proper formatting (a., A., etc)
    if text[0].isalpha() and len(text) > 1:
        match = re.match(r'^[A-Za-z][\.\)](\s+|$)', text)
        if match:
            return True, "letter"
            
    # Check for roman numerals with proper formatting
    roman_pattern = r'^[IVXLCDM]+[\.\)](\s+|$)'
    if re.match(roman_pattern, text):
        return True, "roman"
        
    # Check for bullet points and dashes at start of line
    if text[0] in '•-–—*' and (len(text) == 1 or text[1].isspace()):
        return True, "bullet"
        
    # Check for bibliographic entries with strict formatting
    # Must be: Author, Initial(s).
    biblio_pattern = r'^[A-Z][a-z]+,\s+[A-Z]\.(\s+[A-Z]\.)*\s'
    if re.match(biblio_pattern, text):
        return True, "bibliographic"
        
    return False, ""

def detect_lists(blocks: typing.List[Block]) -> None:
    """Detect list items and their continuations"""
    for block_idx, block in enumerate(blocks):
        pattern_buffer = []  # [(line, marker_type, x_min, first_span, marker_num), ...]
        current_marker_x = None
        current_marker_type = None
        current_item = None
        last_number = None
        
        # Find consistent continuation indent if it exists
        continuation_indent = find_continuation_indent(block.lines)
        
        for line_idx, line in enumerate(block.lines):
            if not line.spans:
                continue
                
            is_marker, marker_type = is_list_marker(line.text)
            if not is_marker:
                # Check if this is a continuation of current item
                if current_item and continuation_indent and abs(line.x_min - continuation_indent) < 2:
                    if current_item.continuation_lines is None:
                        current_item.continuation_lines = []
                    current_item.continuation_lines.append(line)
                    logger.info(f"Found continuation line [Block {block_idx}, Line {line_idx}]: {line.text[:100]}")
                continue
            
            # Process numeric markers and check sequence
            current_number = None
            if marker_type == "numeric":
                num_match = re.match(r'^\d+', line.text)
                if num_match:
                    current_number = int(num_match.group(0))
                    if last_number is not None and current_number != last_number + 1:
                        process_list_buffer(pattern_buffer, continuation_indent)
                        pattern_buffer = []
                        current_marker_x = None
                        last_number = None
                        continue
            
            # Check if this matches current pattern
            if current_marker_x is not None:
                x_matches = abs(line.x_min - current_marker_x) < 2
                type_matches = marker_type == current_marker_type
                
                if not (x_matches and type_matches):
                    process_list_buffer(pattern_buffer, continuation_indent)
                    pattern_buffer = []
                    current_marker_x = None
            
            # Start new pattern if needed
            if current_marker_x is None:
                current_marker_x = line.x_min
                current_marker_type = marker_type
            
            # Add to buffer
            pattern_buffer.append((line, marker_type, line.x_min, line.spans[0], current_number))
            current_item = line
            last_number = current_number
            logger.info(f"Found list marker [Block {block_idx}, Line {line_idx}]: {line.text[:100]}")
        
        # Process any remaining items
        if pattern_buffer:
            process_list_buffer(pattern_buffer, continuation_indent)

def find_continuation_indent(lines: typing.List[Line]) -> Optional[float]:
    """Find consistent continuation indent in a block of lines"""
    for i in range(len(lines)-1):
        line = lines[i]
        next_line = lines[i+1]
        if line.x_min < next_line.x_min:
            return next_line.x_min
    # Return None only after checking all pairs of lines
    return None
        
def process_list_buffer(pattern_buffer: typing.List[tuple], indent_level: Optional[float]) -> None:
    """Process a buffer of list items"""
    if len(pattern_buffer) < 2:  # Require at least 2 items to confirm a list
        return
        
    for line, marker_type, marker_x, _, _ in pattern_buffer:
        # Log if this line was previously classified as something else
        if line.is_header or line.is_paragraph_start:
            logger.info(f"List item cancels previous classification [Block {line.block_num}]: {line.text[:100]}")
            if line.is_header:
                logger.info("  - Cancels header classification")
            if line.is_paragraph_start:
                logger.info("  - Cancels paragraph classification")
        
        # Update line classification
        line.is_header = False
        line.is_paragraph_start = False
        line.is_list_item = True
        line.list_type = marker_type
        line.list_marker_x = marker_x
        line.classification_reason = f"List item: {marker_type} marker"
        line.is_processed = True
        
        # Process continuation lines
        if line.continuation_lines:
            for cont in line.continuation_lines:
                cont.is_header = False
                cont.is_paragraph_start = False
                cont.is_processed = True
                cont.classification_reason = f"List continuation for {marker_type} item"

def build_sections(blocks: typing.List[Block], doc_title: str = "Introduction") -> typing.List[Section]:
    """Build sections based on detected headers"""
    sections = []
    current_content = []
    current_paragraph_lines = []
    current_list_items = []  # Buffer for collecting consecutive list items
    current_list_type = None
    current_list_x = None
    is_first_paragraph = True
    current_block = None
    
    # Start with a default section using document title
    current_section = Section(
        header=doc_title,
        content=[]
    )
    
    def process_current_paragraph():
        nonlocal current_paragraph_lines, current_content, is_first_paragraph, current_block
        if current_paragraph_lines:
            # Remove any lines that were later marked as list items
            original_len = len(current_paragraph_lines)
            current_paragraph_lines = [line for line in current_paragraph_lines 
                                     if not (line.is_list_item or 
                                           getattr(line, 'is_processed', False))]
            if len(current_paragraph_lines) != original_len:
                logger.info(f"Filtered out {original_len - len(current_paragraph_lines)} lines marked as list items")
            
            if current_paragraph_lines:  # Only process if we still have lines
                # Join lines and split into sentences
                text = ' '.join(line.text for line in current_paragraph_lines)
                sentences = sent_tokenize(text)
                current_content.append(Paragraph(
                    sentences=sentences,
                    is_first_in_section=is_first_paragraph
                ))
                logger.info(f"Added paragraph to section '{current_section.header[:30]}...' [Block {current_block}]:")
                logger.info(f"  First line: {current_paragraph_lines[0].text[:100]}")
                logger.info(f"  Sentences: {len(sentences)}")
            else:
                logger.info("Skipped empty paragraph after filtering")
            current_paragraph_lines = []
            is_first_paragraph = False
    
    def process_current_list():
        nonlocal current_list_items, current_content
        if current_list_items:
            # Create a list structure containing all items
            list_items = []
            for line in current_list_items:
                continuation_texts = []
                if line.continuation_lines:
                    continuation_texts = [cont.text for cont in line.continuation_lines]
                list_items.append(ListItem(
                    text=line.text,
                    continuation_texts=continuation_texts,
                    marker_type=line.list_type
                ))
            current_content.append(DocumentList(
                items=list_items,
                marker_type=current_list_type
            ))
            logger.info(f"Added list to section '{current_section.header[:30]}...' with {len(list_items)} items")
            current_list_items = []
    
    def save_current_section():
        nonlocal current_section, current_content, is_first_paragraph, current_list_items
        process_current_paragraph()  # Process any pending paragraph
        process_current_list()  # Process any pending list items
        if current_content:
            current_section.content = current_content
            sections.append(current_section)
            logger.info(f"Saved section '{current_section.header[:50]}...' with {len(current_content)} content items")
            current_content = []
            is_first_paragraph = True
    
    for block in blocks:
        current_block = block.block_num
        for line in block.lines:
            if line.is_header:
                # Save current section
                save_current_section()
                
                # Start new section
                current_section = Section(
                    header=line.text,
                    content=[]
                )
                logger.info(f"Starting new section: {line.text[:100]} [Block {block.block_num}]")
                
            elif line.is_list_item:
                # Process any pending paragraph
                process_current_paragraph()
                
                # Check if this is a continuation of the current list
                if (current_list_type == line.list_type and 
                    current_list_x is not None and 
                    abs(line.list_marker_x - current_list_x) < 2):
                    # Add to current list
                    current_list_items.append(line)
                else:
                    # Process previous list if any
                    process_current_list()
                    # Start new list
                    current_list_type = line.list_type
                    current_list_x = line.list_marker_x
                    current_list_items = [line]
                
            elif line.is_paragraph_start:
                # Process any pending list
                process_current_list()
                # Process any pending paragraph before starting new one
                process_current_paragraph()
                # Start new paragraph
                current_paragraph_lines = [line]
                logger.info(f"Starting new paragraph [Block {block.block_num}]: {line.text[:100]}")
                
            else:
                # Continue current paragraph
                if current_paragraph_lines:  # Only add if we have a paragraph started
                    current_paragraph_lines.append(line)
                else:
                    logger.info(f"Skipped line - no paragraph started [Block {block.block_num}]: {line.text[:100]}")
    
    # Save final section
    save_current_section()
    
    return sections

def process_pdf(file_path: str, filename: str) -> ProcessedDocument:
    """Process a PDF file into a structured document"""
    doc = fitz.open(file_path)
    
    # Get title from metadata or filename
    metadata = doc.metadata
    title = metadata.get('title', '') if metadata else ''
    if not title:
        # Remove extension and convert to title case
        title = os.path.splitext(filename)[0].replace('_', ' ').title()
    
    # Step 1: Extract lines and block statistics
    blocks = consolidate_lines(doc)
    
    # Step 2: Detect structure
    detect_headers(blocks)
    detect_paragraphs(blocks)
    detect_lists(blocks)
    
    # Step 3: Build sections
    sections = build_sections(blocks, title)
    
    return ProcessedDocument(
        title=title,
        sections=sections,
        metadata={
            'page_count': len(doc),
            'filename': filename,
            'title': title
        }
    )

def main():
    """Main function for testing"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger.info("Starting PDF processing...")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_files = glob.glob(os.path.join(current_dir, "s*.pdf"))
    
    if not pdf_files:
        logger.info("No PDF files found in directory")
        return
        
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        logger.info(f"\n{'='*80}")
        logger.info(f"Processing {filename}...")
        logger.info(f"{'='*80}\n")
        
        try:
            processed_content = process_pdf(pdf_path, filename)
            out_path = pdf_path + ".out.txt"
            
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(processed_content.to_json(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"  Saved processed content to {os.path.basename(out_path)}")
            logger.info(f"  Found {len(processed_content.sections)} sections")
            logger.info(f"  Total paragraphs: {sum(len(s.content) for s in processed_content.sections)}")
            
        except Exception as e:
            logger.error(f"\nERROR processing {filename}:")
            logger.error(f"  {str(e)}")
            import traceback
            logger.error("\nFull traceback:")
            logger.error(traceback.format_exc())
            continue 

if __name__ == "__main__":
    main()

class PDFProcessor(ContentProcessor):
    """Processor for PDF files that implements the ContentProcessor interface."""
    
    def to_structured_json(self, raw_content: str) -> Dict:
        """Convert raw PDF content to structured JSON format.
        
        Args:
            raw_content: Raw PDF content (file path)
            
        Returns:
            Dict containing structured representation of the PDF
        """
        # Process the PDF
        processed_doc = process_pdf(raw_content, os.path.basename(raw_content))
        # Convert to JSON structure
        return processed_doc.to_json()
    
    def to_prompt_text(self, structured_json: Dict) -> str:
        """Convert structured JSON to prompt text with appropriate markers.
        
        Args:
            structured_json: Structured content from to_structured_json()
            
        Returns:
            String containing content with section, paragraph, and sentence markers
        """
        # Create ProcessedDocument from JSON
        doc = ProcessedDocument.from_json(structured_json)
        return doc.to_prompt_text() 