"""
Service layer for protected document operations.
Combines database operations with Java cryptographic operations.
"""
from typing import Optional, Dict, Any, Tuple
from repositories.protected_document_repository import ProtectedDocumentRepository
from services.java_service import JavaSecureDocumentService
from core.pki import validate_and_extract_public_key, extract_cn_from_certificate
from cryptography.hazmat.primitives import serialization
import json


class ProtectedDocumentService:
    """Service for protected document operations."""

    def __init__(self, repository: ProtectedDocumentRepository, java_service: JavaSecureDocumentService):
        self.repository = repository
        self.java_service = java_service

    def protect(
        self,
        input_document: bytes,
        seller_priv_key: bytes,
        seller_cert: bytes,
        buyer_cert: bytes
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Protect a document and save it to the database.
        
        Args:
            input_document: Plaintext document bytes
            seller_priv_key: Seller's private key bytes
            seller_cert: Seller's X.509 certificate bytes (PEM)
            buyer_cert: Buyer's X.509 certificate bytes (PEM)
        
        Returns:
            Tuple of (success, document_id, error_message)
        """
        try:
            seller_pub_key = validate_and_extract_public_key(seller_cert)
            buyer_pub_key = validate_and_extract_public_key(buyer_cert)
            seller_name = extract_cn_from_certificate(seller_cert)
            buyer_name = extract_cn_from_certificate(buyer_cert)
        except Exception as e:
            return False, None, f"Certificate validation failed: {str(e)}"
        
        seller_pub_bytes = seller_pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        buyer_pub_bytes = buyer_pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        success, protected_doc_bytes, error = self.java_service.protect(
            input_document,
            seller_priv_key,
            seller_pub_bytes,
            buyer_pub_bytes,
            seller_name,
            buyer_name
        )

        if not success or not protected_doc_bytes:
            return False, None, error

        try:
            protected_doc_json = json.loads(protected_doc_bytes.decode('utf-8'))
        except json.JSONDecodeError as e:
            return False, None, f"Failed to parse protected document: {str(e)}"

        try:
            protected_doc = self.repository.create(protected_doc_json)
            return True, protected_doc.id, None
        except Exception as e:
            error_msg = str(e)
            # Provide helpful message if it's a sequence issue
            if "ID conflict" in error_msg or "duplicate key" in error_msg.lower():
                error_msg += " Try running: python3 api/fix_sequence.py"
            return False, None, f"Failed to save to database: {error_msg}"

    def check(self, document_id: int, seller_cert: bytes) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Check document integrity.
        
        Args:
            document_id: ID of the protected document
            seller_cert: Seller's X.509 certificate bytes (PEM)
        
        Returns:
            Tuple of (success, result_dict, error_message)
        """
        try:
            seller_pub_key = validate_and_extract_public_key(seller_cert)
        except Exception as e:
            return False, None, f"Certificate validation failed: {str(e)}"
        
        seller_pub_bytes = seller_pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        protected_doc = self.repository.get_by_id(document_id)
        if not protected_doc:
            return False, None, "Document not found"

        try:
            doc_json = json.dumps(protected_doc.to_json())
            protected_doc_bytes = doc_json.encode('utf-8')
        except Exception as e:
            return False, None, f"Failed to serialize document: {str(e)}"

        success, result, error = self.java_service.check(
            protected_doc_bytes,
            seller_pub_bytes
        )

        return success, result, error

    def unprotect(self, document_id: int, recipient_priv_key: bytes) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Decrypt a protected document.
        
        Args:
            document_id: ID of the protected document
            recipient_priv_key: Recipient's private key bytes
        
        Returns:
            Tuple of (success, decrypted_document_bytes, error_message)
        """
        protected_doc = self.repository.get_by_id(document_id)
        if not protected_doc:
            return False, None, "Document not found"

        try:
            doc_json = json.dumps(protected_doc.to_json())
            protected_doc_bytes = doc_json.encode('utf-8')
        except Exception as e:
            return False, None, f"Failed to serialize document: {str(e)}"

        success, decrypted_doc, error = self.java_service.unprotect(
            protected_doc_bytes,
            recipient_priv_key
        )

        return success, decrypted_doc, error

    def share(
        self,
        document_id: int,
        new_recipient_cert: bytes,
        new_recipient_name: str,
        sharer_priv_key: bytes,
        sharer_name: str
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Share a protected document with a new recipient.
        
        Args:
            document_id: ID of the protected document
            new_recipient_cert: New recipient's X.509 certificate bytes (PEM)
            new_recipient_name: Name of the new recipient
            sharer_priv_key: Sharer's private key bytes
            sharer_name: Name of the sharer
        
        Returns:
            Tuple of (success, document_id, error_message)
        """
        try:
            new_recipient_pub_key = validate_and_extract_public_key(new_recipient_cert)
        except Exception as e:
            return False, None, f"Certificate validation failed: {str(e)}"
        
        new_recipient_pub_bytes = new_recipient_pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        protected_doc = self.repository.get_by_id(document_id)
        if not protected_doc:
            return False, None, "Document not found"

        try:
            doc_json = json.dumps(protected_doc.to_json())
            protected_doc_bytes = doc_json.encode('utf-8')
        except Exception as e:
            return False, None, f"Failed to serialize document: {str(e)}"

        success, shared_doc_bytes, error = self.java_service.share(
            protected_doc_bytes,
            new_recipient_pub_bytes,
            new_recipient_name,
            sharer_priv_key,
            sharer_name
        )

        if not success or not shared_doc_bytes:
            return False, None, error

        try:
            shared_doc_json = json.loads(shared_doc_bytes.decode('utf-8'))
        except json.JSONDecodeError as e:
            return False, None, f"Failed to parse shared document: {str(e)}"

        try:
            updated_doc = self.repository.update(document_id, shared_doc_json)
            if not updated_doc:
                return False, None, "Failed to update document in database"
            return True, updated_doc.id, None
        except Exception as e:
            return False, None, f"Failed to update database: {str(e)}"

    def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a protected document by ID.
        
        Returns:
            Document dictionary or None if not found
        """
        protected_doc = self.repository.get_by_id(document_id)
        if not protected_doc:
            return None
        return protected_doc.to_dict()

    def list_documents(self) -> list:
        """
        List all protected documents.
        
        Returns:
            List of document dictionaries
        """
        documents = self.repository.get_all()
        return [doc.to_dict() for doc in documents]

