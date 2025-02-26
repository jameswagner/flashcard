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
    
    def to_prompt_text(self, structured_json: Dict) -> str:
        """Convert structured JSON to prompt text with paragraph and sentence markers.
        
        Args:
            structured_json: Output from to_structured_json()
            
        Returns:
            Text with [PARAGRAPH X] and [SENTENCE Y] markers
        """
        result = []
        for paragraph in structured_json["paragraphs"]:
            result.append(f"[PARAGRAPH {paragraph['number']}]")
            for sentence_num, sentence in zip(paragraph["sentence_numbers"], paragraph["sentences"]):
                result.append(f"[SENTENCE {sentence_num}] {sentence}")
            result.append("")  # Add blank line between paragraphs
        
        return "\n".join(result).strip()
