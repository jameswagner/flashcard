from typing import List, Tuple, Dict
import re
import nltk
from nltk.tokenize import sent_tokenize
from utils.content_processing.base import ContentProcessor

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class PlainTextProcessor(ContentProcessor):
    """Processor for plain text files that adds paragraph and sentence markers."""
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using NLTK's sentence tokenizer.
        
        Args:
            text: Text to split into sentences
        
        Returns:
            List of sentences
        """    
        # Split into sentences
        sentences = sent_tokenize(text)
        
        # Clean up sentences
        sentences = [s.strip() for s in sentences]
        sentences = [s for s in sentences if s]  # Remove empty sentences
        
        return sentences

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs based on double newlines or first line indentation.
        
        Args:
            text: Text to split into paragraphs
        
        Returns:
            List of paragraphs
        """
        # First split by double newlines
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Further split by indented first lines (if not already split by newlines)
        result = []
        for p in paragraphs:
            # Check if paragraph starts with indentation
            lines = p.split('\n')
            current_para = []
            for line in lines:
                if line.startswith('    ') or line.startswith('\t'):
                    # If we have accumulated lines, add them as a paragraph
                    if current_para:
                        result.append('\n'.join(current_para))
                    current_para = [line]
                else:
                    current_para.append(line)
            # Add the last paragraph
            if current_para:
                result.append('\n'.join(current_para))
        
        # Clean up paragraphs
        result = [p.strip() for p in result]
        result = [p for p in result if p]
        
        return result
    
    def to_structured_json(self, raw_content: str) -> Dict:
        """Convert raw text to structured JSON format.
        
        The JSON structure contains:
        - paragraphs: List of paragraphs
        - sentences: List of all sentences with their paragraph numbers
        
        Args:
            raw_content: Raw text content
            
        Returns:
            Dict with structured content
        """
        paragraphs = self._split_into_paragraphs(raw_content)
        result = {
            "paragraphs": [],
            "metadata": {
                "total_paragraphs": len(paragraphs),
                "total_sentences": 0
            }
        }
        
        current_sentence = 1
        for para_num, paragraph in enumerate(paragraphs, 1):
            sentences = self._split_into_sentences(paragraph)
            if len(sentences) > 15:
                # Split into chunks of 8 sentences
                chunks = [sentences[i:i+8] for i in range(0, len(sentences), 8)]
                for chunk in chunks:
                    result["paragraphs"].append({
                        "number": para_num,
                        "sentences": chunk,
                        "sentence_numbers": list(range(current_sentence, current_sentence + len(chunk)))
                    })
                    current_sentence += len(chunk)
            else:
                result["paragraphs"].append({
                    "number": para_num,
                    "sentences": sentences,
                    "sentence_numbers": list(range(current_sentence, current_sentence + len(sentences)))
                })
                current_sentence += len(sentences)
        
        result["metadata"]["total_sentences"] = current_sentence - 1
        return result
    
    def _get_selected_content(self, selected_content: List[Dict]) -> Tuple[set, set]:
        """Helper function to extract selected paragraphs and sentences from content selection.
        
        Args:
            selected_content: List of content selection criteria
            
        Returns:
            Tuple of (selected_paragraphs, selected_sentences) as sets
        """
        selected_paragraphs, selected_sentences = set(), set()
        
        if not selected_content:
            return selected_paragraphs, selected_sentences
            
        for selection in selected_content:
            citation_type = selection.get("citation_type")
            start, end = selection.get("range", [None, None])
            
            if citation_type and start is not None and end is not None:
                if citation_type == "paragraph":
                    selected_paragraphs.update(range(int(start), int(end) + 1))
                elif citation_type == "sentence_range":
                    selected_sentences.update(range(int(start), int(end) + 1))
                    
        return selected_paragraphs, selected_sentences
    
    def to_prompt_text(self, structured_json: Dict, selected_content: List[Dict] = None) -> str:
        """Convert structured JSON to prompt text with paragraph and sentence markers.
        
        Args:
            structured_json: Output from to_structured_json()
            selected_content: Optional list of selected content to filter by. Format:
                [
                    {
                        "citation_type": "paragraph" or "sentence_range", 
                        "range": [start, end]
                    }
                ]
            
        Returns:
            Text with [PARAGRAPH X] and [SENTENCE Y] markers
        """
        # Extract selected paragraphs and sentences if selection is provided
        selected_paragraphs, selected_sentences = self._get_selected_content(selected_content)
        
        # Build the prompt text based on selection criteria
        result = []
        for paragraph in structured_json["paragraphs"]:
            para_num = paragraph['number']
            para_selected = para_num in selected_paragraphs
            
            # Skip paragraph if nothing selected or this paragraph not selected
            if selected_content and not para_selected and not any(s in selected_sentences for s in paragraph["sentence_numbers"]):
                continue
                
            # Add paragraph marker
            result.append(f"[PARAGRAPH {para_num}]")
            
            # Add selected sentences or all sentences if paragraph is selected
            for sentence_num, sentence in zip(paragraph["sentence_numbers"], paragraph["sentences"]):
                # Add sentence if: 
                # 1. No selection criteria (selected_content is None), OR
                # 2. The whole paragraph is selected, OR
                # 3. This specific sentence is selected
                if not selected_content or para_selected or sentence_num in selected_sentences:
                    result.append(f"[SENTENCE {sentence_num}] {sentence}")
            
            result.append("")  # Add blank line between paragraphs
        
        return "\n".join(result).strip()
