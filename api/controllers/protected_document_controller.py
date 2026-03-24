from fastapi import Depends, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from database import get_db
from repositories.protected_document_repository import ProtectedDocumentRepository
from services.protected_document_service import ProtectedDocumentService
from dependencies import get_service
import requests
import os
import logging

logger = logging.getLogger(__name__)


async def protect(
    input_document: UploadFile = File(..., description="Plaintext JSON document"),
    seller_priv_key: UploadFile = File(..., description="Seller's private key (for signing)"),
    seller_cert_file: UploadFile = File(..., description="Seller's X.509 certificate (PEM)"),
    buyer_cert_file: UploadFile = File(..., description="Buyer's X.509 certificate (PEM)"),
    service: ProtectedDocumentService = Depends(get_service)
):
    """
    Protect a document with encryption, integrity, and freshness protection.
    Called by seller only. Seller signs the document.
    Seller and buyer certificates are validated and their public keys are extracted
    to create wrapped keys so both can decrypt.
    
    Returns the document ID and protected document data.
    """
    try:
        # Read all files
        input_doc_bytes = await input_document.read()
        seller_priv_bytes = await seller_priv_key.read()
        seller_cert_bytes = await seller_cert_file.read()
        buyer_cert_bytes = await buyer_cert_file.read()

        success, document_id, error = service.protect(
            input_doc_bytes,
            seller_priv_bytes,
            seller_cert_bytes,
            buyer_cert_bytes
        )

        if success and document_id:
            # Get the created document
            document = service.get_document(document_id)
            return JSONResponse(content={
                "success": True,
                "document_id": document_id,
                "document": document
            })
        else:
            raise HTTPException(status_code=400, detail=f"Protection failed: {error}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
        

async def check(
    document_id: int,
    seller_cert_file: UploadFile = File(..., description="Seller's X.509 certificate (PEM)"),
    service: ProtectedDocumentService = Depends(get_service)
):
    """
    Verify the integrity and freshness of a protected document.
    Only verifies the seller's signature.
    The seller's certificate is validated against the Root CA before use.
    
    Returns verification results as JSON.
    """
    try:
        seller_cert_bytes = await seller_cert_file.read()

        success, result, error = service.check(document_id, seller_cert_bytes)

        if success and result:
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=f"Check failed: {error}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


async def unprotect(
    document_id: int,
    recipient_priv_key: UploadFile = File(..., description="Recipient's private key"),
    service: ProtectedDocumentService = Depends(get_service)
):
    """
    Decrypt a protected document.
    
    Returns the decrypted document as JSON, or error details if decryption fails.
    """
    try:
        recipient_priv_bytes = await recipient_priv_key.read()

        # Call service
        success, decrypted_doc, error = service.unprotect(document_id, recipient_priv_bytes)

        if success and decrypted_doc:
            return Response(
                content=decrypted_doc,
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=decrypted-document-{document_id}.json"}
            )
        else:
            # Return 200 OK with error details in JSON (for better testing/debugging)
            return JSONResponse(
                content={"success": False, "detail": f"Unprotect failed: {error}"},
                status_code=200
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


async def share(
    document_id: int,
    new_recipient_cert_file: UploadFile = File(..., description="New recipient's X.509 certificate (PEM)"),
    new_recipient_name: str = Form(..., description="Name of the new recipient"),
    sharer_priv_key: UploadFile = File(..., description="Sharer's private key (must match a wrapped_key in document)"),
    sharer_name: str = Form(..., description="Name of the sharer (e.g., Seller, Buyer, or recipient name)"),
    service: ProtectedDocumentService = Depends(get_service)
):
    """
    Share a protected document with a new recipient.
    Anyone with a wrapped_key in the document can share.
    The sharer must be able to unwrap one of the keys to prove they have access.
    The recipient's certificate is validated against the Root CA before use.
    
    Returns the updated document.
    """
    try:
        new_recipient_cert_bytes = await new_recipient_cert_file.read()
        sharer_priv_bytes = await sharer_priv_key.read()

        success, updated_document_id, error = service.share(
            document_id,
            new_recipient_cert_bytes,
            new_recipient_name,
            sharer_priv_bytes,
            sharer_name
        )

        if success and updated_document_id:
            # Get the updated document
            document = service.get_document(updated_document_id)
            return JSONResponse(content={
                "success": True,
                "document_id": updated_document_id,
                "document": document
            })
        else:
            raise HTTPException(status_code=400, detail=f"Share failed: {error}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


async def list_documents(
    service: ProtectedDocumentService = Depends(get_service)
):
    """
    List all protected documents.
    
    Returns a list of all protected documents in the database.
    """
    try:
        documents = service.list_documents()
        return JSONResponse(content={
            "success": True,
            "count": len(documents),
            "documents": documents
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a protected document.
    
    Returns success status.
    """
    repository = ProtectedDocumentRepository(db)
    success = repository.delete(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return JSONResponse(content={"success": True, "message": "Document deleted"})


async def share_to_group(
    document_id: int,
    group_name: str = Form(..., description="Name of the group to share with"),
    sharer_priv_key: UploadFile = File(..., description="Sharer's private key"),
    sharer_name: str = Form(..., description="Name of the sharer"),
    service: ProtectedDocumentService = Depends(get_service)
):
    """
    Share a protected document with all members of a group.
    
    Dynamically resolves group members at the moment of sharing,
    enforcing the rules valid at that moment.
    
    Returns the list of members who received access.
    """
    try:
        GROUP_SERVER_URL = os.getenv("GROUP_SERVER_URL", "http://localhost:8001")
        
        try:
            response = requests.post(
                f"{GROUP_SERVER_URL}/api/groups/{group_name}/resolve",
                timeout=10
            )
            response.raise_for_status()
            group_snapshot = response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=503, 
                detail=f"Group Server unavailable or group not found: {str(e)}"
            )
        
        sharer_priv_bytes = await sharer_priv_key.read()
        
        results = []
        for member in group_snapshot["members"]:
            try:
                cert_pem = member.get("certificate_pem")
                if not cert_pem:
                    logger.warning(f"Member {member.get('name')} has no certificate_pem, skipping")
                    results.append({
                        "member": member.get("name"),
                        "success": False,
                        "error": "Member certificate_pem missing"
                    })
                    continue

                success, _, error = service.share(
                    document_id,
                    cert_pem.encode("utf-8"),
                    member["name"],
                    sharer_priv_bytes,
                    sharer_name
                )
                
                if not success and error and "Certificate validation failed" in error:
                    logger.warning(f"Member {member.get('name')} has invalid/expired certificate: {error}")
                
                results.append({
                    "member": member["name"],
                    "success": success,
                    "error": error if not success else None
                })
                
            except Exception as e:
                logger.error(f"Error processing member {member.get('name')}: {str(e)}")
                results.append({
                    "member": member.get("name", "unknown"),
                    "success": False,
                    "error": str(e)
                })
        
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        return JSONResponse(content={
            "success": True,
            "group": group_name,
            "snapshot_id": group_snapshot["snapshot_id"],
            "resolved_at": group_snapshot["resolved_at"],
            "total_members": len(group_snapshot["members"]),
            "successful_shares": len(successful),
            "failed_shares": len(failed),
            "results": results
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

