from sqlalchemy.orm import Session
from typing import Optional, Any, Dict, List, Tuple
import logging
from models.source import Citation, SourceFile
from models.enums import CitationType, FileType
import json

from utils.citation_processing import HTMLCitationProcessor, TextCitationProcessor, CitationProcessor
from utils.citation_processing.youtube_citation_processor import YouTubeCitationProcessor
from utils.citation_processing.pdf_citation_processor import PDFCitationProcessor
from utils.citation_processing.image_citation_processor import ImageCitationProcessor

logger = logging.getLogger(__name__)

class CitationService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_citation(
        self,
        flashcard_id: int,
        source_id: int,
        start_value: float,
        end_value: float,
        citation_type: Optional[str] = None,
        context: Optional[str] = None,
        preview_text: str = "",
        transaction=None
    ) -> Citation:
        """
        Create a citation record
        
        Args:
            flashcard_id: ID of the flashcard
            source_id: ID of the source file
            start_value: Start position/value of the citation
            end_value: End position/value of the citation
            citation_type: Type of citation (e.g., line_numbers, video_timestamp)
            context: Additional context for the citation (e.g., section heading)
            preview_text: Formatted preview text for display
            transaction: Optional transaction to use
            
        Returns:
            The created Citation object
        """
        session = transaction or self.db
        
        # Format citation data as expected by the database
        citation_data = [[start_value, end_value]]
        
        # Determine default citation type if not provided
        if not citation_type:
            citation_type = CitationType.line_numbers.value
            
        # Create the citation record
        citation = Citation(
            flashcard_id=flashcard_id,
            source_file_id=source_id,
            citation_type=citation_type,
            citation_data=citation_data,
            preview_text=preview_text
        )
        
        # Add to database
        session.add(citation)
        session.flush()
        
        logger.debug(f"Created citation: id={citation.id}, type={citation_type}")
        return citation
    

        
    def get_citation_processor(self, source_file: SourceFile):
        """
        Get the appropriate citation processor based on file type.
        
        Args:
            source_file: The source file to get a processor for
            
        Returns:
            The appropriate citation processor instance
        """
        if source_file.file_type == FileType.HTML.value:
            processor = HTMLCitationProcessor()
            logger.debug(f"Using HTML citation processor for file {source_file.id} ({source_file.filename})")
        elif source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
            processor = YouTubeCitationProcessor()
            logger.debug(f"Using YouTube citation processor for file {source_file.id} ({source_file.filename})")
        elif source_file.file_type == FileType.TXT.value:
            processor = TextCitationProcessor()
            logger.debug(f"Using Text citation processor for file {source_file.id} ({source_file.filename})")
        elif source_file.file_type == FileType.PDF.value:
            processor = PDFCitationProcessor()
            logger.debug(f"Using PDF citation processor for file {source_file.id} ({source_file.filename})")
        elif source_file.file_type == FileType.IMAGE.value:
            processor = ImageCitationProcessor()
            logger.debug(f"Using Image citation processor for file {source_file.id} ({source_file.filename})")
        else:
            processor = CitationProcessor()
            logger.debug(f"Using base citation processor for file {source_file.id} ({source_file.filename}) with type {source_file.file_type}")
        
        return processor
    
    def parse_citation_data(self, citation, citation_processor, file_type):
        """
        Parse citation data into standardized components for all content types.
        
        Args:
            citation: The citation data to parse
            citation_processor: The citation processor to use
            file_type: The file type of the source
            
        Returns:
            Tuple of (start_value, end_value, citation_type, context) or None if parsing fails
        """
        try:
            # Simple, unified code path for all processors
            logger.debug(f"Parsing citation for {file_type}: {citation}")
            
            # All processors return the same tuple structure: (start, end, type, context)
            result = citation_processor.parse_citation(citation)
            
            if not result:
                logger.warning(f"Failed to parse citation: {citation}")
                return None
            
            logger.debug(f"Citation processor returned: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing citation: {str(e)}", exc_info=True)
            return None
            
    def create_citation_from_parsed_data(
        self,
        parsed_citation,
        flashcard_id: int,
        source_file: SourceFile,
        citation_processor,
        document_json: str,
        use_sentences: bool = True
    ) -> Optional[Citation]:
        """
        Create a citation record from parsed citation data.
        
        Args:
            parsed_citation: Tuple of (start_value, end_value, citation_type, context)
            flashcard_id: ID of the flashcard
            source_file: Source file object
            citation_processor: Citation processor to use
            document_json: JSON string of document content
            use_sentences: Whether to use sentence ranges (True) or line numbers (False)
            
        Returns:
            Created Citation object or None if creation fails
        """
        # Unpack the standardized citation data
        start_value, end_value, citation_type, context = parsed_citation
        logger.debug(f"Parsed citation: start={start_value}, end={end_value}, type={citation_type}")
        
        # Get preview text using parameter names compatible with all processors
        preview_text = citation_processor.get_preview_text(
            text_content=document_json,
            start_num=start_value,
            end_num=end_value,
            citation_type=citation_type
        )
        
        # Log a sample of the preview text
        preview_sample = preview_text[:100] + "..." if len(preview_text) > 100 else preview_text
        logger.debug(f"Generated preview text: '{preview_sample}'")
        
        # Determine default citation type based on file type and settings
        if source_file.file_type == FileType.YOUTUBE_TRANSCRIPT.value:
            default_type = CitationType.video_timestamp.value
        else:
            default_type = CitationType.sentence_range.value if use_sentences else CitationType.line_numbers.value
            
        # Create the citation using the existing method
        return self.create_citation(
            flashcard_id=flashcard_id,
            source_id=source_file.id,
            start_value=start_value,
            end_value=end_value,
            citation_type=citation_type or default_type,
            context=context,
            preview_text=preview_text
        )
        
    def process_flashcard_citations(
        self,
        citations: List,
        flashcard_id: int,
        source_file: SourceFile,
        document_json: str,
        use_sentences: bool = True,
        card_index: int = None,
        total_cards: int = None,
        citation_processor = None
    ) -> int:
        """
        Process all citations for a single flashcard.
        
        Args:
            citations: List of citation data
            flashcard_id: ID of the flashcard
            source_file: Source file object
            document_json: JSON string of document content
            use_sentences: Whether to use sentence ranges (True) or line numbers (False)
            card_index: Optional index of the card for logging
            total_cards: Optional total number of cards for logging
            citation_processor: Optional pre-instantiated citation processor
            
        Returns:
            Number of citations created
        """
        card_info = f"(card {card_index} of {total_cards})" if card_index and total_cards else ""
        logger.debug(f"Processing {len(citations)} citations for flashcard {flashcard_id} {card_info}")
        citation_count = 0
        
        # Get the appropriate citation processor if not provided
        if citation_processor is None:
            citation_processor = self.get_citation_processor(source_file)
        
        for citation_idx, citation in enumerate(citations):
            logger.debug(f"Processing citation #{citation_idx+1}: {citation}")
            
            # Parse citation with the appropriate processor
            parsed_citation = self.parse_citation_data(
                citation=citation, 
                citation_processor=citation_processor,
                file_type=source_file.file_type
            )
            
            if not parsed_citation:
                logger.warning(f"Failed to parse citation: {citation}")
                continue
            
            # Create citation record
            db_citation = self.create_citation_from_parsed_data(
                parsed_citation=parsed_citation,
                flashcard_id=flashcard_id,
                source_file=source_file,
                citation_processor=citation_processor,
                document_json=document_json,
                use_sentences=use_sentences
            )
            
            if db_citation:
                citation_count += 1
                logger.debug(f"Created citation record: id={db_citation.id}, type={db_citation.citation_type}")
        
        return citation_count 