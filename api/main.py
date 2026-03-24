from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import protected_document_router
from core.pki import load_root_ca

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        load_root_ca()
        print("Root CA loaded successfully")
    except Exception as e:
        print(f"ERROR: Failed to load Root CA: {e}")
        raise
    yield


app = FastAPI(
    title="SecureDocument API",
    description="API for cryptographic document protection operations",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(protected_document_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "SecureDocument API",
        "version": "1.0.0",
        "endpoints": {
            "protect": "POST /api/documents/protect",
            "check": "POST /api/documents/{document_id}/check",
            "unprotect": "POST /api/documents/{document_id}/unprotect",
            "share": "POST /api/documents/{document_id}/share",
            "list": "GET /api/documents/",
            "delete": "DELETE /api/documents/{document_id}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="10.10.10.10", port=8000)

