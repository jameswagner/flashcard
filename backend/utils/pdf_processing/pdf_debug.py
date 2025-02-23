"""Debug script to output raw PDF structure and formatted spans."""

import os
import glob
import json
import fitz
from collections import Counter, defaultdict
from statistics import mean, median, mode
from typing import Dict, List, Tuple

class PDFJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle bytes and other special types."""
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        try:
            return super().default(obj)
        except:
            return str(obj)

def decode_bytes_or_str(value) -> str:
    """Safely decode bytes or return string value."""
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value) if value is not None else ""

def extract_pdf_metadata(doc: fitz.Document) -> Dict:
    """Extract and decode PDF metadata."""
    metadata = {}
    
    # Get raw metadata
    raw_metadata = doc.metadata
    if raw_metadata:
        # Decode all metadata fields
        for key, value in raw_metadata.items():
            metadata[key] = decode_bytes_or_str(value)
    
    # Try to get title from different sources
    title = None
    
    # 1. Try metadata title
    if metadata.get('title'):
        title = metadata['title']
    
    # 2. If no title in metadata, try first page's text
    if not title:
        first_page = doc[0]
        blocks = first_page.get_text("dict")['blocks']
        
        # Look for the first text block with significantly larger text
        if blocks:
            largest_size = 0
            largest_text = ""
            
            for block in blocks:
                if block['type'] == 0:  # Text block
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            size = float(span.get('size', 0))
                            if size > largest_size:
                                largest_size = size
                                text = span.get('text', '').strip()
                                if text:
                                    largest_text = text
            
            if largest_text:
                title = largest_text
    
    metadata['extracted_title'] = title
    return metadata

def analyze_block_fonts(block: Dict) -> Dict[str, List]:
    """Analyze font patterns in a block."""
    fonts = []
    sizes = []
    colors = []
    
    for line in block.get('lines', []):
        for span in line.get('spans', []):
            if span.get('text', '').strip():
                fonts.append(span.get('font', 'unknown'))
                sizes.append(float(span.get('size', 0)))
                colors.append(span.get('color', 0))
    
    return {
        'fonts': fonts,
        'sizes': sizes,
        'colors': colors
    }

def analyze_text_properties(doc: fitz.Document) -> Dict:
    """Analyze document to determine typical text properties."""
    sizes = []
    colors = []
    fonts = []
    
    # Collect all text properties
    for page in doc:
        blocks = page.get_text("dict")['blocks']
        for block in blocks:
            if block['type'] == 0:  # Text block
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        text = span.get('text', '').strip()
                        if text:
                            sizes.append(float(span.get('size', 0)))
                            colors.append(span.get('color', 0))
                            fonts.append(span.get('font', 'unknown'))
    
    # Analyze sizes
    size_stats = {
        'median': median(sizes),
        'mean': mean(sizes),
        'mode': mode(sizes),
        'counts': Counter(sizes)
    }
    
    # Find the most common size and color (main body text)
    main_size = mode(sizes)
    main_color = mode(colors)
    main_font = mode(fonts)
    
    # Calculate thresholds for headers
    size_threshold = main_size * 1.2  # 20% larger than main text
    
    return {
        'main_size': main_size,
        'main_color': main_color,
        'main_font': main_font,
        'size_threshold': size_threshold,
        'size_stats': size_stats,
        'color_counts': Counter(colors),
        'font_counts': Counter(fonts)
    }

def get_line_style(line_spans: List[Dict]) -> Dict:
    """Get the dominant style characteristics of a line."""
    if not line_spans:
        return {}
    
    # Get text content and width
    text = ' '.join(span.get('text', '').strip() for span in line_spans)
    x_min = min(span['bbox'][0] for span in line_spans)
    x_max = max(span['bbox'][2] for span in line_spans)
    width = x_max - x_min
    
    # Get the first span's style (usually determines the line's style)
    first_span = min(line_spans, key=lambda s: s['bbox'][0])
    font = first_span.get('font', 'unknown')
    size = float(first_span.get('size', 0))
    color = first_span.get('color', 0)
    
    # Parse font style
    is_bold = 'Bold' in font or ',B' in font
    is_italic = 'Italic' in font or ',I' in font
    
    # Determine capitalization style
    words = text.split()
    if words:
        # Check if all words are uppercase (excluding numbers and special characters)
        alpha_words = [w for w in words if any(c.isalpha() for c in w)]
        is_all_caps = all(w.isupper() for w in alpha_words) if alpha_words else False
    else:
        is_all_caps = False
    
    return {
        'text': text,
        'width': width,
        'font': font,
        'size': size,
        'color': color,
        'is_bold': is_bold,
        'is_italic': is_italic,
        'is_all_caps': is_all_caps,
        'x_min': x_min,
        'x_max': x_max
    }

def is_likely_header(current_line: List[Dict], next_line: List[Dict], prev_line: List[Dict], text_props: Dict, is_single_line_block: bool = False, next_block_first_line: List[Dict] = None) -> Tuple[bool, str]:
    """Determine if a line is likely a header based on style transitions and block structure."""
    if not current_line:
        return False, ""
    
    # Get style information
    current_style = get_line_style(current_line)
    next_style = get_line_style(next_line) if next_line else {}
    next_block_style = get_line_style(next_block_first_line) if next_block_first_line else {}
    
    # Skip very short text
    if len(current_style['text'].strip()) < 2:
        return False, ""
    
    reasons = []
    
    # Case 1: Entire block is a single line and next block exists
    if is_single_line_block and next_block_first_line:
        if next_block_style:  # If there is content in the next block
            # Check for style differences with next block
            if current_style['is_bold'] and not next_block_style.get('is_bold'):
                reasons.append(f"bold to normal transition ({current_style['font']} -> {next_block_style['font']})")
            if current_style['is_italic'] and not next_block_style.get('is_italic'):
                reasons.append(f"italic to normal transition ({current_style['font']} -> {next_block_style['font']})")
            if current_style['size'] > next_block_style.get('size', 0):
                reasons.append(f"size decrease ({current_style['size']:.2f} -> {next_block_style['size']:.2f})")
            if current_style['is_all_caps'] and not next_block_style.get('is_all_caps'):
                reasons.append("caps to normal case transition")
            if current_style['color'] != next_block_style.get('color', 0):
                reasons.append(f"color transition ({current_style['color']} -> {next_block_style['color']})")
            if reasons:
                reasons.append("standalone block")
    
    # Case 2: Style transitions within a block
    elif not is_single_line_block:  # Only check transitions if not a single-line block
        # Check for bold/italic/size/caps/color transitions
        if current_style['is_bold'] and next_style and not next_style['is_bold']:
            reasons.append(f"bold to normal transition ({current_style['font']} -> {next_style['font']})")
        if current_style['is_italic'] and next_style and not next_style['is_italic']:
            reasons.append(f"italic to normal transition ({current_style['font']} -> {next_style['font']})")
        if current_style['size'] > text_props['main_size'] * 1.1 and next_style:
            if current_style['size'] > next_style['size']:
                reasons.append(f"size decrease ({current_style['size']:.2f} -> {next_style['size']:.2f})")
        if current_style['is_all_caps'] and next_style and not next_style['is_all_caps']:
            reasons.append("caps to normal case transition")
        if next_style and current_style['color'] != next_style['color']:
            reasons.append(f"color transition ({current_style['color']} -> {next_style['color']})")
    
    # Check for significant size differences
    if current_style['size'] > text_props['size_threshold']:
        reasons.append(f"larger than threshold ({current_style['size']:.2f} > {text_props['size_threshold']:.2f})")
    
    return bool(reasons), " and ".join(reasons)

def consolidate_line_spans(spans: List[Dict]) -> List[List[Dict]]:
    """Group spans that belong to the same line based on vertical position and font size."""
    if not spans:
        return []
    
    # Sort spans by vertical position (y0) and then horizontal position (x0)
    sorted_spans = sorted(spans, key=lambda s: (s['bbox'][1], s['bbox'][0]))
    
    lines = []
    current_line = []
    last_y = None
    last_size = None
    main_size = max(float(s.get('size', 0)) for s in spans)  # Use largest size as reference
    
    for span in sorted_spans:
        y0 = span['bbox'][1]  # Top y-coordinate
        size = float(span.get('size', 0))
        
        # If this is the first span
        if last_y is None:
            current_line.append(span)
            last_y = y0
            last_size = size
            continue
        
        # Calculate vertical threshold based on font sizes
        # Use a much stricter threshold - about half a line height
        base_threshold = main_size * 0.5
        
        # For superscripts/subscripts (smaller fonts), allow slightly more vertical variation
        # but still keep it strict
        size_ratio = size / main_size
        threshold = base_threshold * (1.2 if size_ratio < 0.8 else 1.0)
        
        # Check if this span belongs to the current line:
        # 1. Very close vertically (standard case)
        # 2. OR smaller size and within reasonable super/subscript distance
        if abs(y0 - last_y) < threshold:  # Much stricter threshold
            current_line.append(span)
            # Update last_y to the main text's y position (ignore super/subscript y)
            if size >= last_size:
                last_y = y0
                last_size = size
        else:
            # Start a new line
            if current_line:
                # Sort spans within line by x position
                current_line.sort(key=lambda s: s['bbox'][0])
                lines.append(current_line)
            current_line = [span]
            last_y = y0
            last_size = size
    
    # Add the last line
    if current_line:
        current_line.sort(key=lambda s: s['bbox'][0])
        lines.append(current_line)
    
    # For each line, sort spans to handle super/subscripts:
    # - First by x position
    # - For spans with similar x positions, put superscripts before and subscripts after
    for line in lines:
        if not line:  # Skip empty lines
            continue
            
        # Find the main text spans (largest font size in the line)
        main_size = max(float(s.get('size', 0)) for s in line)
        main_spans = [s for s in line if float(s.get('size', 0)) == main_size]
        if not main_spans:
            continue
            
        # Use the average y position of main text spans as reference
        main_y = sum(s['bbox'][1] for s in main_spans) / len(main_spans)
        
        # Sort spans by x position first, then by their position relative to main text
        line.sort(key=lambda s: (
            s['bbox'][0],  # Primary sort by x position
            -1 if float(s.get('size', 0)) < main_size and s['bbox'][1] < main_y else  # Superscripts go first
            1 if float(s.get('size', 0)) < main_size and s['bbox'][1] > main_y else  # Subscripts go last
            0  # Main text in the middle
        ))
    
    return lines

def is_paragraph_start(line_spans: List[Dict], regular_x: float = None, prev_was_header: bool = False) -> Tuple[bool, float]:
    """Determine if a line starts a new paragraph based on indentation or if it follows a header."""
    if not line_spans:
        return False, None
    
    # Get the x position of the first span in the line
    first_span = min(line_spans, key=lambda s: s['bbox'][0])
    x0 = first_span['bbox'][0]
    
    # If this line follows a header, it's a paragraph start
    if prev_was_header:
        return True, x0
    
    if regular_x is None:
        return False, x0
    
    # If this line is indented compared to the regular x position
    return x0 > regular_x + 5, regular_x  # Using 5 point threshold for indentation

def get_span_position_key(span: Dict, bbox_height: float) -> str:
    """Generate a position key for a span that can be compared across pages."""
    x0, y0, x1, y1 = span['bbox']
    font = span.get('font', 'unknown')
    size = float(span.get('size', 0))
    # Round coordinates and size to 2 decimal places for comparison
    return f"{x0:.2f}_{y0:.2f}_{x1:.2f}_{y1:.2f}_{font}_{size:.2f}"

def should_filter_span(span: Dict, bbox_height: float, repeated_positions: Dict[str, List[str]], total_pages: int) -> Tuple[bool, str]:
    """Check if a span should be filtered out."""
    x0, y0, x1, y1 = span['bbox']
    width = x1 - x0
    height = y1 - y0
    text = span.get('text', '').strip()
    
    # Skip very short text for vertical filtering
    if len(text) >= 2:
        # Check for vertical text (height significantly larger than width)
        if height > width * 3:
            return True, "vertical text"
    
    # Check if this text appears in the exact same position with same font on multiple pages
    pos_key = get_span_position_key(span, bbox_height)
    if pos_key in repeated_positions:
        repeated_texts = repeated_positions[pos_key]
        if text in repeated_texts:
            occurrences = sum(1 for t in repeated_texts if t == text)
            # Only filter if it appears on at least 50% of pages
            if occurrences >= total_pages / 2:
                return True, f"repeated on {occurrences}/{total_pages} pages"
    
    return False, ""

def collect_position_metadata(doc: fitz.Document) -> Dict[str, List[str]]:
    """Collect text position metadata across all pages."""
    position_texts = defaultdict(list)  # Maps position_key -> [(page_num, text)]
    
    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        blocks = page.get_text("dict")['blocks']
        
        for block in blocks:
            if block['type'] == 0:  # Text block
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        text = span.get('text', '').strip()
                        if text:
                            pos_key = get_span_position_key(span, page_height)
                            position_texts[pos_key].append((page_num, text))
    
    # Find positions where text repeats across pages
    repeated_positions = {}
    for pos, occurrences in position_texts.items():
        # Get unique pages where this position appears
        pages = set(page_num for page_num, _ in occurrences)
        if len(pages) > 1:  # Position appears on multiple pages
            texts = [text for _, text in occurrences]
            repeated_positions[pos] = texts
    
    return repeated_positions

def write_json_debug(doc: fitz.Document, json_path: str):
    """Write the raw JSON debug output."""
    with open(json_path, 'w', encoding='utf-8') as f:
        pages_data = []
        for page in doc:
            page_dict = page.get_text("dict")
            pages_data.append(page_dict)
        json.dump(pages_data, f, indent=2, cls=PDFJSONEncoder)

def process_line(line_spans: List[Dict], line_context: Dict, text_props: Dict) -> Tuple[bool, bool, str, str]:
    """Process a single line and return header/paragraph status and reasons.
    
    Args:
        line_spans: List of spans in the line
        line_context: Dict containing context like:
            - prev_line: Previous line spans
            - next_line: Next line spans
            - is_first_line: If this is first line in block
            - regular_x: Regular x position for indentation
            - prev_was_header: If previous line was header
            - last_block_was_header: If last block was header
            - is_single_line_block: If this is the only line in block
            - next_block_first_line: First line of next block if any
        text_props: Document text properties
    
    Returns:
        Tuple of (is_header, is_para_start, header_reason, para_reason)
    """
    # Sort spans within line by x position
    line_spans.sort(key=lambda s: s['bbox'][0])
    
    # Check if this line starts a new paragraph
    is_para_start, _ = is_paragraph_start(
        line_spans, 
        line_context['regular_x'], 
        line_context['prev_was_header'] or 
        (line_context['is_first_line'] and line_context['last_block_was_header'])
    )
    
    # Check for header based on style transitions
    is_header, header_reason = is_likely_header(
        line_spans, 
        line_context['next_line'], 
        line_context['prev_line'], 
        text_props,
        is_single_line_block=line_context['is_single_line_block'],
        next_block_first_line=line_context['next_block_first_line']
    )
    
    return is_header, is_para_start, header_reason, ""

def write_formatted_span(f, span: Dict, is_header: bool, is_para_start: bool, header_reason: str, filter_reason: str, span_idx: int):
    """Write a single span in the formatted output."""
    text = span.get('text', '').strip()
    if text:
        font = span.get('font', 'unknown')
        size = float(span.get('size', 0))
        color = span.get('color', 0)
        bbox = span.get('bbox', [0, 0, 0, 0])
        x0, y0, x1, y1 = bbox
        
        # Add markers
        header_marker = " [HEADER: " + header_reason + "]" if span_idx == 0 and is_header else ""
        para_marker = " [PARAGRAPH_START]" if span_idx == 0 and is_para_start else ""
        filter_marker = f" [FILTERED: {filter_reason}]" if filter_reason else ""
        
        # Write span with pipe delimited format
        f.write(f"{text}|{font}|{size:.2f}|{color}|{x0:.2f},{y0:.2f},{x1:.2f},{y1:.2f}{header_marker}{para_marker}{filter_marker}\n")

def process_block(f, block: Dict, block_num: int, next_block: Dict, text_props: Dict, last_block_was_header: bool, page_height: float, repeated_positions: Dict, total_pages: int) -> bool:
    """Process a single text block and return if it was a header.
    
    Args:
        f: File handle to write output to
        block: The block to process
        block_num: Block number
        next_block: Next block if any
        text_props: Document text properties
        last_block_was_header: If previous block was a header
        page_height: Height of the page
        repeated_positions: Dict of repeated text positions
        total_pages: Total number of pages
    
    Returns:
        bool: Whether this block was a header block
    """
    # Collect all spans from the block
    all_spans = []
    for line in block.get('lines', []):
        all_spans.extend(line.get('spans', []))
    
    # Consolidate spans into proper lines
    consolidated_lines = consolidate_line_spans(all_spans)
    
    # Get next block's first line for block-level transitions
    next_block_first_line = None
    if next_block and next_block['type'] == 0:
        next_block_spans = []
        for line in next_block.get('lines', []):
            next_block_spans.extend(line.get('spans', []))
        next_block_lines = consolidate_line_spans(next_block_spans)
        if next_block_lines:
            next_block_first_line = next_block_lines[0]
    
    # Check if this is a single-line block
    is_single_line_block = len(consolidated_lines) == 1
    
    # Find the regular (non-indented) x position
    x_positions = []
    for line in consolidated_lines:
        if line:
            x_positions.append(min(span['bbox'][0] for span in line))
    regular_x = min(x_positions) if x_positions else None
    
    # Process each consolidated line
    prev_was_header = False  # For headers within the same block
    last_header = False
    
    for line_idx, line_spans in enumerate(consolidated_lines):
        # Get previous and next lines for context
        prev_line = consolidated_lines[line_idx - 1] if line_idx > 0 else None
        next_line = consolidated_lines[line_idx + 1] if line_idx < len(consolidated_lines) - 1 else None
        
        # Prepare line context
        line_context = {
            'prev_line': prev_line,
            'next_line': next_line,
            'is_first_line': line_idx == 0,
            'regular_x': regular_x,
            'prev_was_header': prev_was_header,
            'last_block_was_header': last_block_was_header,
            'is_single_line_block': is_single_line_block,
            'next_block_first_line': next_block_first_line if is_single_line_block else None
        }
        
        # Process the line
        is_header, is_para_start, header_reason, _ = process_line(line_spans, line_context, text_props)
        
        # Process each span in the line
        for span_idx, span in enumerate(line_spans):
            # Check if span should be filtered
            should_filter, filter_reason = should_filter_span(span, page_height, repeated_positions, total_pages)
            
            # Write the formatted span
            write_formatted_span(f, span, is_header, is_para_start, header_reason, filter_reason if should_filter else "", span_idx)
        
        # Update prev_was_header for next line in this block
        prev_was_header = is_header
        last_header = is_header
        
        # Add line break between actual lines
        f.write("\n")
    
    # A block is considered a header block if it's a single line and that line is a header
    return is_single_line_block and last_header

def process_pdf_debug(pdf_path: str):
    """Process a PDF and output both raw JSON and formatted span data."""
    filename = os.path.basename(pdf_path)
    print(f"\nProcessing {filename}...")
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # Extract metadata including title
        metadata = extract_pdf_metadata(doc)
        print("\nPDF Metadata:")
        for key, value in metadata.items():
            print(f"{key}: {value}")
        
        # Analyze text properties
        text_props = analyze_text_properties(doc)
        print("\nDocument text properties:")
        print(f"Main text size: {text_props['main_size']:.2f}")
        print(f"Header size threshold: {text_props['size_threshold']:.2f}")
        print(f"Main text color: {text_props['main_color']}")
        print(f"Main font: {text_props['main_font']}")
        print("\nFont usage:")
        for font, count in text_props['font_counts'].most_common():
            print(f"- {font}: {count} spans")
        print("\nSize usage:")
        for size, count in text_props['size_stats']['counts'].most_common():
            print(f"- {size:.2f}: {count} spans")
        
        # Collect position metadata
        print("First pass: analyzing repeated text...")
        repeated_positions = collect_position_metadata(doc)
        print(f"Found {len(repeated_positions)} positions with repeated text across pages")
        
        # Write raw JSON debug output
        json_path = pdf_path + ".debug.json"
        write_json_debug(doc, json_path)
        print(f"\nSaved raw JSON to {os.path.basename(json_path)}")
        
        # Process and write formatted output
        text_path = pdf_path + ".debug.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            for page_num, page in enumerate(doc):
                # Write page delimiter
                f.write(f"\n{'='*40}\n")
                f.write(f"PAGE {page_num + 1}\n")
                f.write(f"{'='*40}\n\n")
                
                # Get page height for filtering
                page_height = page.rect.height
                
                # Track if previous block ended with a header
                last_block_was_header = False
                
                blocks = page.get_text("dict")['blocks']
                for block_num, block in enumerate(blocks):
                    if block['type'] == 0:  # Text block
                        # Write block delimiter
                        f.write(f"\n{'-'*20} Block {block_num + 1} {'-'*20}\n")
                        
                        # Get next block if it exists
                        next_block = blocks[block_num + 1] if block_num + 1 < len(blocks) else None
                        
                        # Process the block
                        last_block_was_header = process_block(
                            f, block, block_num, next_block, text_props,
                            last_block_was_header, page_height,
                            repeated_positions, total_pages
                        )
        
        print(f"Saved formatted spans to {os.path.basename(text_path)}")
        
    except Exception as e:
        print(f"Error processing {filename}: {str(e)}")
        raise  # Re-raise to see full traceback during development

def main():
    # Get the directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Find all PDF files in the directory
    pdf_files = glob.glob(os.path.join(current_dir, "*.pdf"))
    
    if not pdf_files:
        print("No PDF files found in directory")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_path in pdf_files:
        process_pdf_debug(pdf_path)

if __name__ == "__main__":
    main() 