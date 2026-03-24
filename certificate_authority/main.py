from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Body, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from cryptography.hazmat.primitives import serialization

from pki import RootCA, load_or_create_root_ca, sign_csr


@asynccontextmanager
async def lifespan(app: FastAPI):
    ca_state.ca = load_or_create_root_ca()
    yield


app = FastAPI(
    title="Certificate Authority",
    description="Internal Root CA service for issuing certificates from CSRs",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CSRRequest(BaseModel):
    csr_pem: str


class CertificateResponse(BaseModel):
    certificate_pem: str


class CAState:
    def __init__(self) -> None:
        self.ca: Optional[RootCA] = None


ca_state = CAState()


def get_ca() -> RootCA:
    """Dependency to access the loaded Root CA instance."""
    if ca_state.ca is None:
        ca_state.ca = load_or_create_root_ca()
    return ca_state.ca


@app.get("/")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok", "service": "certificate-authority"}


@app.get("/root-ca")
async def get_root_ca(ca: RootCA = Depends(get_ca)) -> dict:
    """Return the Root CA certificate (PEM, public part only)."""
    pem = ca.certificate.public_bytes(encoding=serialization.Encoding.PEM)
    return {"certificate_pem": pem.decode("utf-8")}


@app.post("/sign", response_model=CertificateResponse)
async def sign_endpoint(
    csr_body: Optional[CSRRequest] = Body(default=None),
    csr_file: Optional[UploadFile] = File(default=None),
    ca: RootCA = Depends(get_ca),
) -> CertificateResponse:
    """
    Sign a CSR and return a certificate.

    Accepts either:
    - JSON body: {"csr_pem": "..."}
    - Or a file upload: form-data with key `csr_file`
    """
    csr_pem: Optional[str] = None

    if csr_body and csr_body.csr_pem:
        csr_pem = csr_body.csr_pem
    elif csr_file is not None:
        try:
            raw = await csr_file.read()
            if not raw:
                raise HTTPException(status_code=400, detail="Uploaded CSR file is empty")
            csr_pem = raw.decode("utf-8")
        except UnicodeDecodeError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=400, detail="Uploaded CSR file must be PEM text"
            ) from exc

    if not csr_pem:
        raise HTTPException(
            status_code=400,
            detail="You must provide either a JSON body with 'csr_pem' or upload a 'csr_file'",
        )

    try:
        certificate_pem = sign_csr(csr_pem, ca)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  
        raise HTTPException(
            status_code=500, detail=f"Failed to sign CSR: {exc}"
        ) from exc

    return CertificateResponse(certificate_pem=certificate_pem)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="10.10.10.30", port=8002, reload=True)


