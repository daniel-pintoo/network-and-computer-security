"""
Router configuration for API endpoints.
"""
from fastapi import APIRouter
from controllers import protected_document_controller

# Create router for protected documents
protected_document_router = APIRouter(prefix="/api/documents", tags=["documents"])

# Register all endpoints
protected_document_router.add_api_route("/protect", protected_document_controller.protect, methods=["POST"])
protected_document_router.add_api_route("/{document_id}/check", protected_document_controller.check, methods=["POST"])
protected_document_router.add_api_route("/{document_id}/unprotect", protected_document_controller.unprotect, methods=["POST"])
protected_document_router.add_api_route("/{document_id}/share", protected_document_controller.share, methods=["POST"])
protected_document_router.add_api_route("/{document_id}/share-to-group", protected_document_controller.share_to_group, methods=["POST"])
protected_document_router.add_api_route("/{document_id}", protected_document_controller.delete_document, methods=["DELETE"])
protected_document_router.add_api_route("/", protected_document_controller.list_documents, methods=["GET"])
