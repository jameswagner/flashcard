"""Image-specific citation processing."""

import json
import logging
from typing import Dict, List, Optional, Tuple

# Use absolute imports
from models.enums import FileType, CitationType
from models.source import Citation
from utils.citation_processing.citation_processor import CitationProcessor

logger = logging.getLogger(__name__)

class ImageCitationProcessor(CitationProcessor):
    """Processor for image citations with OCR text blocks."""

    def __init__(self):
        """Initialize the image citation processor."""
        super().__init__()
        self.file_type = FileType.IMAGE

    def process_citations(self, structured_json: Dict, file_id: str) -> List[Citation]:
        """Process citations from structured JSON data.
        
        Args:
            structured_json: Dict containing structured OCR results.
            file_id: ID of the source file.
            
        Returns:
            List of Citation objects.
        """
        try:
            citations = []
            blocks = structured_json.get("blocks", [])
            
            for block in blocks:
                block_id = block["id"]
                bbox = block["bbox"]
                paragraphs = block.get("paragraphs", [])
                
                # Create citation for each paragraph that has content
                for i, paragraph in enumerate(paragraphs):
                    sentences = paragraph.get("sentences", [])
                    if not sentences:
                        continue
                        
                    # Join sentences for preview text
                    preview_text = ". ".join(sentences)
                    if preview_text:
                        citation = Citation(
                            file_id=file_id,
                            block_id=str(block_id),
                            paragraph_index=i,
                            preview_text=preview_text,
                            metadata={
                                "bbox": bbox,
                                "confidence": block["confidence"],
                                "sentence_count": len(sentences)
                            }
                        )
                        citations.append(citation)
            
            return citations
            
        except Exception as e:
            logger.error(f"Error processing image citations: {str(e)}")
            raise

    def get_preview_text(
        self, 
        text_content: str, 
        start_num: int, 
        end_num: int, 
        citation_type: Optional[str] = None
    ) -> str:
        """Get preview text for a citation from structured JSON.
        
        Args:
            text_content: JSON string containing structured OCR results
            start_num: Starting block/paragraph ID
            end_num: Ending block/paragraph ID (usually same as start_num for image citations)
            citation_type: Type of citation (block or paragraph)
            
        Returns:
            Preview text for the citation
        """
        try:
            # Parse the JSON content
            structured_json = json.loads(text_content)
            
            # Handle different citation types
            if citation_type == "paragraph":
                # For paragraph citations, start_num is the paragraph number across all blocks
                # We need to find which block contains this paragraph
                paragraph_count = 0
                for block in structured_json.get("blocks", []):
                    block_paragraphs = block.get("paragraphs", [])
                    for paragraph in block_paragraphs:
                        paragraph_count += 1
                        if paragraph_count == start_num:
                            # Found the paragraph
                            sentences = paragraph.get("sentences", [])
                            return ". ".join(sentences)
                
                logger.warning(f"Paragraph {start_num} not found in image content")
                return ""
            else:
                # For block citations, start_num is the block ID
                for block in structured_json.get("blocks", []):
                    if block["id"] == start_num:
                        # Get all paragraphs in this block
                        all_sentences = []
                        for paragraph in block.get("paragraphs", []):
                            all_sentences.extend(paragraph.get("sentences", []))
                        
                        if all_sentences:
                            return ". ".join(all_sentences)
                        else:
                            # Fallback to original text if no sentences found
                            return block.get("metadata", {}).get("original_text", "")
                
                logger.warning(f"Block ID {start_num} not found in image content")
                return ""
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON content: {e}")
            return ""
        except Exception as e:
            logger.error(f"Error getting preview text: {str(e)}")
            return "" 