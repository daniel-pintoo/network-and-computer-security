from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import NameOID


BASE_DIR = Path(__file__).resolve().parent.parent
SECURE_DIR = BASE_DIR / "secure_storage"
ROOT_KEY_PATH = SECURE_DIR / "root_ca.key"
ROOT_CERT_PATH = SECURE_DIR / "root_ca.crt"


@dataclass
class RootCA:
    private_key: rsa.RSAPrivateKey
    certificate: x509.Certificate


def load_or_create_root_ca(common_name: str = "Local Development Root CA") -> RootCA:

    SECURE_DIR.mkdir(parents=True, exist_ok=True)

    if ROOT_KEY_PATH.exists() and ROOT_CERT_PATH.exists():
        with ROOT_KEY_PATH.open("rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )

        with ROOT_CERT_PATH.open("rb") as f:
            certificate = x509.load_pem_x509_certificate(f.read(), default_backend())

        return RootCA(private_key=private_key, certificate=certificate)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend(),
    )

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "PT"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "T50 ChainOfProduct"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365 * 10))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    with ROOT_KEY_PATH.open("wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with ROOT_CERT_PATH.open("wb") as f:
        f.write(
            certificate.public_bytes(encoding=serialization.Encoding.PEM)
        )

    return RootCA(private_key=private_key, certificate=certificate)


def sign_csr(csr_pem: str, ca: RootCA) -> str:
    """Sign a PEM-encoded CSR and return a PEM-encoded certificate string.

    Steps:
    - Parse CSR
    - Verify CSR signature (ensures requester owns the private key)
    - Build a new X.509 certificate:
      - Subject: from CSR
      - Issuer: Root CA subject
      - Public Key: from CSR
      - Serial: random secure integer
      - Validity: 1 year from now
      - Signed with Root CA private key (SHA-256)
    - Return PEM-encoded certificate
    """
    try:
        csr = x509.load_pem_x509_csr(csr_pem.encode("utf-8"), default_backend())
    except Exception as exc: 
        raise ValueError("Invalid CSR format") from exc

    try:
        public_key = csr.public_key()
        public_key.verify(
            csr.signature,
            csr.tbs_certrequest_bytes,
            padding.PKCS1v15(),
            csr.signature_hash_algorithm,
        )
    except Exception as exc: 
        raise ValueError("Invalid CSR signature") from exc

    now = datetime.now(timezone.utc)

    builder = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca.certificate.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
    )

    certificate = builder.sign(
        private_key=ca.private_key,
        algorithm=hashes.SHA256(),
        backend=default_backend(),
    )

    return certificate.public_bytes(serialization.Encoding.PEM).decode("utf-8")


