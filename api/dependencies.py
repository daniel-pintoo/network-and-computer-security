"""
Dependency injection functions for FastAPI.
"""
from fastapi import Depends
from sqlalchemy.orm import Session
from database import get_db
from repositories.protected_document_repository import ProtectedDocumentRepository
from services.protected_document_service import ProtectedDocumentService
from services.java_service import JavaSecureDocumentService

# Initialize Java service (shared instance)
java_service = JavaSecureDocumentService()


def get_service(db: Session = Depends(get_db)) -> ProtectedDocumentService:
    """Dependency to get ProtectedDocumentService."""
    repository = ProtectedDocumentRepository(db)
    return ProtectedDocumentService(repository, java_service)

