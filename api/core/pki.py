"""
PKI utilities for certificate validation and public key extraction.
"""
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import HTTPException

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_CA_PATH = Path(os.getenv("ROOT_CA_PATH", BASE_DIR / "secure_storage" / "root-ca.crt"))

_root_ca_cert: Optional[x509.Certificate] = None


def load_root_ca() -> x509.Certificate:
    global _root_ca_cert
    
    if _root_ca_cert is not None:
        return _root_ca_cert
    
    if not ROOT_CA_PATH.exists():
        raise FileNotFoundError(
            f"Root CA certificate not found at {ROOT_CA_PATH}. "
            f"Set ROOT_CA_PATH environment variable or place root_ca.crt in {BASE_DIR / 'secure_storage'}"
        )
    
    with ROOT_CA_PATH.open("rb") as f:
        _root_ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    
    logger.info(f"Root CA loaded successfully from {ROOT_CA_PATH}")
    return _root_ca_cert


def validate_and_extract_public_key(cert_pem_bytes: bytes):
    """
    Validate a certificate and extract its public key.
    
    Args:
        cert_pem_bytes: PEM-encoded certificate bytes
        
    Returns:
        PublicKey object from the certificate
        
    Raises:
        HTTPException(400): If certificate is invalid, not signed by Root CA, or expired
    """
    root_ca = load_root_ca()
    
    try:
        cert_pem_str = cert_pem_bytes.decode("utf-8") if isinstance(cert_pem_bytes, bytes) else cert_pem_bytes
        cert = x509.load_pem_x509_certificate(cert_pem_str.encode("utf-8"), default_backend())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid certificate format: {str(e)}")
    
    if cert.issuer != root_ca.subject:
        raise HTTPException(
            status_code=400,
            detail=f"Certificate issuer does not match Root CA subject. Issuer: {cert.issuer}, Root CA: {root_ca.subject}"
        )
    
    try:
        public_key = root_ca.public_key()
        
        public_key.verify(
            cert.signature,
            cert.tbs_certificate_bytes,
            padding.PKCS1v15(),
            cert.signature_hash_algorithm,
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Certificate signature verification failed: {str(e)}. Certificate not signed by Root CA."
        )
    
    now = datetime.now(timezone.utc)
    
    not_valid_before = cert.not_valid_before_utc
    not_valid_after = cert.not_valid_after_utc
    
    if now < not_valid_before:
        raise HTTPException(
            status_code=400,
            detail=f"Certificate not yet valid. Valid from: {not_valid_before}"
        )
    if now > not_valid_after:
        raise HTTPException(
            status_code=400,
            detail=f"Certificate expired. Expired on: {not_valid_after}"
        )
    
    return cert.public_key()


def extract_cn_from_certificate(cert_pem_bytes: bytes) -> str:
    """
    Extract the Common Name (CN) from a certificate's subject.
    
    Args:
        cert_pem_bytes: PEM-encoded certificate bytes
    """
    try:
        cert_pem_str = cert_pem_bytes.decode("utf-8") if isinstance(cert_pem_bytes, bytes) else cert_pem_bytes
        cert = x509.load_pem_x509_certificate(cert_pem_str.encode("utf-8"), default_backend())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid certificate format: {str(e)}")
    
    subject = cert.subject
    cn_attributes = subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    
    if not cn_attributes:
        raise HTTPException(status_code=400, detail="Certificate does not contain a Common Name (CN) in subject")
    
    return cn_attributes[0].value

