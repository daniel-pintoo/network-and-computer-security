"""
Database models for protected documents.
"""
from sqlalchemy import Column, Integer, BigInteger, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from database import Base


class ProtectedDocument(Base):
    """Model for protected documents table."""
    __tablename__ = "protected_documents"

    id = Column(Integer, primary_key=True, index=True)
    ciphertext = Column(Text, nullable=False)
    iv = Column(Text, nullable=False)
    wrapped_keys = Column(JSON, nullable=False)  
    signatures = Column(JSON, nullable=False)  
    access_list = Column(JSON, nullable=True)  
    document_metadata = Column("metadata", JSON, nullable=False)
    timestamp = Column(BigInteger, nullable=True)  
    nonce = Column(String, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        """Convert model to dictionary matching the JSON structure."""
        return {
            "id": self.id,
            "ciphertext": self.ciphertext,
            "iv": self.iv,
            "wrapped_keys": self.wrapped_keys,
            "signatures": self.signatures,
            "access_list": self.access_list if self.access_list else [],
            "metadata": self.document_metadata,  
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def to_json(self):
        """Convert to JSON structure (without id, created_at, updated_at)."""
        return {
            "ciphertext": self.ciphertext,
            "iv": self.iv,
            "wrapped_keys": self.wrapped_keys,
            "signatures": self.signatures,
            "access_list": self.access_list if self.access_list else [],
            "metadata": self.document_metadata,
            "timestamp": self.timestamp,
            "nonce": self.nonce
        }

