"""
Repository layer for protected documents database operations.
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional, List
from models.protected_document import ProtectedDocument
import json
import logging

logger = logging.getLogger(__name__)


class ProtectedDocumentRepository:
    """Repository for protected document database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, document_data: dict) -> ProtectedDocument:
        """
        Create a new protected document.
        
        Args:
            document_data: Dictionary with ciphertext, iv, wrapped_keys, signatures, metadata, access_list
        
        Returns:
            Created ProtectedDocument instance
        
        Raises:
            Exception: If database operation fails
        """
        access_list = document_data.get("access_list")
        if access_list is None:
            access_list = []

        protected_doc = ProtectedDocument(
            ciphertext=document_data["ciphertext"],
            iv=document_data["iv"],
            wrapped_keys=document_data["wrapped_keys"],
            signatures=document_data["signatures"],
            access_list=access_list,
            document_metadata=document_data["metadata"],
            timestamp=document_data.get("timestamp"),
            nonce=document_data.get("nonce")
        )
        try:
            self.db.add(protected_doc)
            self.db.commit()
            self.db.refresh(protected_doc)
            return protected_doc
        except IntegrityError as e:
            self.db.rollback()
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            logger.error(f"Database integrity error creating document: {error_msg}")
            # Check if it's a sequence/ID issue
            if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
                raise Exception(f"ID conflict detected. This may be due to sequence issues. Error: {error_msg}")
            raise Exception(f"Database integrity error: {error_msg}")
        except SQLAlchemyError as e:
            self.db.rollback()
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            logger.error(f"Database error creating document: {error_msg}")
            raise Exception(f"Database error: {error_msg}")

    def get_by_id(self, document_id: int) -> Optional[ProtectedDocument]:
        """Get a protected document by ID."""
        return self.db.query(ProtectedDocument).filter(ProtectedDocument.id == document_id).first()

    def get_all(self) -> List[ProtectedDocument]:
        """Get all protected documents."""
        return self.db.query(ProtectedDocument).all()

    def update(self, document_id: int, document_data: dict) -> Optional[ProtectedDocument]:
        """
        Update an existing protected document.
        
        Args:
            document_id: ID of the document to update
            document_data: Dictionary with fields to update
        
        Returns:
            Updated ProtectedDocument instance or None if not found
        """
        protected_doc = self.get_by_id(document_id)
        if not protected_doc:
            return None

        if "ciphertext" in document_data:
            protected_doc.ciphertext = document_data["ciphertext"]
        if "iv" in document_data:
            protected_doc.iv = document_data["iv"]
        if "wrapped_keys" in document_data:
            protected_doc.wrapped_keys = document_data["wrapped_keys"]
        if "signatures" in document_data:
            protected_doc.signatures = document_data["signatures"]
        if "access_list" in document_data:
            protected_doc.access_list = document_data["access_list"] if document_data["access_list"] else []
        if "metadata" in document_data:
            protected_doc.document_metadata = document_data["metadata"]
        if "timestamp" in document_data:
            protected_doc.timestamp = document_data["timestamp"]
        if "nonce" in document_data:
            protected_doc.nonce = document_data["nonce"]  

        self.db.commit()
        self.db.refresh(protected_doc)
        return protected_doc

    def delete(self, document_id: int) -> bool:
        """
        Delete a protected document.
        
        Returns:
            True if deleted, False if not found
        """
        protected_doc = self.get_by_id(document_id)
        if not protected_doc:
            return False

        self.db.delete(protected_doc)
        self.db.commit()
        return True

    def get_by_metadata_transaction_id(self, transaction_id: int) -> Optional[ProtectedDocument]:
        """Get a protected document by transaction_id in metadata."""
        documents = self.db.query(ProtectedDocument).all()
        for doc in documents:
            if doc.document_metadata and doc.document_metadata.get("transaction_id") == transaction_id:
                return doc
        return None

