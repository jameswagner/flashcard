from sqlalchemy.orm import Session
from typing import Optional, List
import logging
from models.source import SourceFile

logger = logging.getLogger(__name__)

class SourceService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_source_by_id(self, source_id: int, user_id: Optional[int] = None) -> Optional[SourceFile]:
        """
        Get a source file by its ID
        
        Args:
            source_id: ID of the source file
            user_id: Optional user ID to verify ownership
            
        Returns:
            SourceFile object if found and owned by the user (if user_id provided),
            None otherwise
        """
        query = self.db.query(SourceFile).filter(SourceFile.id == source_id)
        
        if user_id is not None:
            query = query.filter(SourceFile.user_id == user_id)
            
        return query.first()
    
    def get_sources_for_user(self, user_id: int) -> List[SourceFile]:
        """
        Get all source files for a user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of SourceFile objects
        """
        return self.db.query(SourceFile).filter(SourceFile.user_id == user_id).all()
    
    def add_source_file(
        self, 
        filename: str,
        file_type: str,
        file_path: str,
        text_content: str,
        user_id: int,
        metadata: dict = None
    ) -> SourceFile:
        """
        Add a new source file
        
        Args:
            filename: Name of the file
            file_type: Type of the file (e.g., PDF, YOUTUBE)
            file_path: Path to the file
            text_content: Extracted text content
            user_id: ID of the user who owns the file
            metadata: Optional metadata for the file
            
        Returns:
            Created SourceFile object
        """
        source_file = SourceFile(
            filename=filename,
            file_type=file_type,
            file_path=file_path,
            text_content=text_content,
            user_id=user_id,
            metadata=metadata or {}
        )
        
        self.db.add(source_file)
        self.db.commit()
        self.db.refresh(source_file)
        
        logger.info(f"Added source file: {filename} (ID: {source_file.id})")
        return source_file
    
    def delete_source_file(self, source_id: int, user_id: int) -> bool:
        """
        Delete a source file
        
        Args:
            source_id: ID of the source file
            user_id: ID of the user (for ownership verification)
            
        Returns:
            True if successful, False otherwise
        """
        source_file = self.get_source_by_id(source_id, user_id)
        if not source_file:
            return False
            
        self.db.delete(source_file)
        self.db.commit()
        
        logger.info(f"Deleted source file: {source_file.filename} (ID: {source_id})")
        return True 