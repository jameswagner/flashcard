"""Image processing module for extracting text from images using OCR."""

import json
import logging
from typing import Dict, List, Optional, Tuple
import pytesseract
from PIL import Image
import io
import os
import nltk
from nltk.tokenize import sent_tokenize

from models.enums import FileType
from utils.content_processing.base import ContentProcessor

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Configure Tesseract path for Windows
if os.name == 'nt':  # Windows
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.environ.get('TESSERACT_PATH')
    ]
    
    for path in tesseract_paths:
        if path and os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.info(f"Found Tesseract at: {path}")
            break
    else:
        error_msg = """
        Tesseract is not installed or not found in the expected locations.
        Please install Tesseract OCR:
        1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
        2. Install it (remember the installation path)
        3. Either:
           - Install to default location (C:\\Program Files\\Tesseract-OCR)
           - Or set TESSERACT_PATH environment variable to your installation path
        """
        logger.error(error_msg)

def is_new_paragraph(current_block: Dict, prev_block: Optional[Dict]) -> bool:
    """Determine if a block starts a new paragraph based on position and content.
    
    Args:
        current_block: Current OCR block
        prev_block: Previous OCR block or None
        
    Returns:
        True if this block should start a new paragraph
    """
    if not prev_block:
        return True
        
    # Get block positions
    curr_bbox = current_block.get("bbox", [0, 0, 0, 0])
    prev_bbox = prev_block.get("bbox", [0, 0, 0, 0])
    
    # Check for significant vertical gap (> 1.5x typical line height)
    vertical_gap = curr_bbox[1] - (prev_bbox[3] if prev_bbox else 0)
    typical_line_height = 20  # Approximate
    if vertical_gap > typical_line_height * 1.5:
        return True
        
    # Check for indentation
    indent = curr_bbox[0] - prev_bbox[0]
    if abs(indent) > 20:  # Significant indentation
        return True
        
    return False

class ImageProcessor(ContentProcessor):
    """Processor for extracting and structuring text from images using OCR."""

    def __init__(self):
        """Initialize the image processor."""
        super().__init__()
        self.file_type = FileType.IMAGE

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using NLTK.
        
        Args:
            text: Text to split into sentences
            
        Returns:
            List of sentences
        """
        # Split into sentences using NLTK
        sentences = sent_tokenize(text)
        
        # Clean up sentences
        sentences = [s.strip() for s in sentences]
        sentences = [s for s in sentences if s]  # Remove empty sentences
        
        return sentences

    def _split_into_paragraphs(self, blocks: List[Dict]) -> List[Dict[str, List[str]]]:
        """Split blocks into paragraphs based on position and content.
        
        Args:
            blocks: List of OCR blocks with position and text
            
        Returns:
            List of paragraph dictionaries with sentences
        """
        paragraphs = []
        current_paragraph_text = []
        prev_block = None
        
        for block in blocks:
            # Check if this is a block from the structured JSON or a raw block
            if "metadata" in block and "original_text" in block["metadata"]:
                # This is a block from the structured JSON
                text = block["metadata"]["original_text"].strip()
            else:
                # This is a raw block from OCR processing
                text = " ".join(block.get("text", [])).strip()
                
            if text:
                # For simplicity, treat each block as its own paragraph
                sentences = self._split_into_sentences(text)
                if sentences:
                    paragraphs.append({"sentences": sentences})
        
        return paragraphs

    def to_structured_json(self, raw_content: bytes) -> Dict:
        """Convert raw image bytes to structured JSON format with OCR results.
        
        Args:
            raw_content: Raw image bytes
            
        Returns:
            Dict containing structured OCR results with blocks, paragraphs, and sentences
        """
        try:
            # Verify Tesseract is properly configured
            if not self._verify_tesseract():
                raise RuntimeError(
                    "Tesseract OCR is not properly configured. "
                    "Please install Tesseract and set the correct path."
                )
            
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(raw_content))
            
            # Get OCR data using layout analysis
            ocr_data = self._get_ocr_data(image)
            
            # Process OCR results into blocks
            blocks = self._process_ocr_results(ocr_data)
            
            # Create structured blocks with paragraphs
            structured_blocks = []
            for block in blocks:
                # Create block with metadata
                block_text = " ".join(block["text"])
                structured_block = {
                    "id": block["block_num"],
                    "bbox": block["bbox"],
                    "confidence": block["confidence"],
                    "metadata": {
                        "original_text": block_text
                    }
                }
                
                # Process text into paragraphs and sentences
                sentences = self._split_into_sentences(block_text)
                if sentences:
                    structured_block["paragraphs"] = [{"sentences": sentences}]
                else:
                    structured_block["paragraphs"] = []
                    
                structured_blocks.append(structured_block)
            
            # Create structured JSON with metadata
            return {
                "type": "image",
                "blocks": structured_blocks,
                "metadata": {
                    "total_blocks": len(structured_blocks),
                    "image_size": image.size,
                    "average_confidence": sum(b["confidence"] for b in blocks) / len(blocks) if blocks else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to process image: {str(e)}")

    def _verify_tesseract(self) -> bool:
        """Verify Tesseract is properly configured."""
        try:
            if os.name == 'nt' and not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
                return False
            # Try a simple OCR operation
            Image.new('RGB', (1, 1)).save('test.png')
            pytesseract.get_tesseract_version()
            os.remove('test.png')
            return True
        except Exception as e:
            logger.error(f"Tesseract verification failed: {str(e)}")
            return False

    def to_prompt_text(self, structured_json: Dict) -> str:
        """Convert structured JSON to prompt text with markers.
        
        Args:
            structured_json: Dict containing structured OCR results.
            
        Returns:
            String containing formatted text with paragraph and sentence markers for citations.
        """
        try:
            lines = []
            paragraph_number = 1
            sentence_number = 1
            
            # Add source type marker
            lines.append("_________SOURCE TYPE: IMAGE_____________________________")
            lines.append("")
            
            # Process all blocks and their paragraphs
            for block in structured_json.get("blocks", []):
                block_id = block.get("id", 0)
                lines.append(f"[BLOCK {block_id}]")
                
                # Process paragraphs within this block
                paragraphs = block.get("paragraphs", [])
                if not paragraphs:
                    # If no paragraphs defined, treat the whole block as one paragraph
                    text = block.get("metadata", {}).get("original_text", "").strip()
                    if text:
                        lines.append(f"[PARAGRAPH {paragraph_number}]")
                        paragraph_number += 1
                        
                        # Split text into sentences
                        sentences = self._split_into_sentences(text)
                        
                        # Add each sentence with its marker
                        for sentence in sentences:
                            if sentence.strip():
                                lines.append(f"[SENTENCE {sentence_number}] {sentence}")
                                sentence_number += 1
                else:
                    # Process each paragraph in the block
                    for paragraph in paragraphs:
                        lines.append(f"[PARAGRAPH {paragraph_number}]")
                        paragraph_number += 1
                        
                        # Add each sentence with its marker
                        for sentence in paragraph.get("sentences", []):
                            if sentence.strip():
                                lines.append(f"[SENTENCE {sentence_number}] {sentence}")
                                sentence_number += 1
                
                # Add paragraph break after each block
                lines.append("")
            
            # Remove trailing blank line if present
            if lines and lines[-1] == "":
                lines.pop()
                
            # Add end marker
            lines.append("_________END OF SOURCE TEXT_____________________________")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error converting OCR results to prompt text: {str(e)}")
            raise 

    def _get_ocr_data(self, image):
        """Get OCR data from an image using Tesseract.
        
        Args:
            image: PIL Image object
            
        Returns:
            Dict containing OCR data
        """
        return pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
    def _process_ocr_results(self, ocr_data):
        """Process OCR results into blocks.
        
        Args:
            ocr_data: Dict containing OCR data from Tesseract
            
        Returns:
            List of blocks with text and position data
        """
        blocks = []
        current_block = {
            "block_num": None,
            "text": [],
            "bbox": None,
            "confidence": 0,
            "paragraphs": []
        }
        
        for i in range(len(ocr_data["text"])):
            text = ocr_data["text"][i].strip()
            if not text:
                continue
                
            block_num = ocr_data["block_num"][i]
            confidence = ocr_data["conf"][i]
            left = ocr_data["left"][i]
            top = ocr_data["top"][i]
            width = ocr_data["width"][i]
            height = ocr_data["height"][i]
            
            # Start new block if block number changes
            if block_num != current_block["block_num"]:
                if current_block["block_num"] is not None:
                    blocks.append(current_block)
                current_block = {
                    "block_num": block_num,
                    "text": [],
                    "bbox": [left, top, left + width, top + height],
                    "confidence": confidence,
                    "paragraphs": []
                }
            
            # Update block
            current_block["text"].append(text)
            current_block["confidence"] = min(current_block["confidence"], confidence)
            current_block["bbox"] = [
                min(current_block["bbox"][0], left),
                min(current_block["bbox"][1], top),
                max(current_block["bbox"][2], left + width),
                max(current_block["bbox"][3], top + height)
            ]
        
        # Add final block
        if current_block["block_num"] is not None:
            blocks.append(current_block)
            
        return blocks 