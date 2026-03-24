from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
import uuid
import json
from pathlib import Path
import os
from contextlib import asynccontextmanager

from cryptography import x509
from cryptography.hazmat.backends import default_backend

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load Root CA on startup."""
    try:
        load_root_ca()
        print(f"Root CA loaded successfully from {ROOT_CA_PATH}")
    except Exception as e:
        print(f"ERROR: Failed to load Root CA: {e}")
        raise
    yield

app = FastAPI(
    title="Group Server",
    description="Dynamic group and member management for transaction disclosure",
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

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
GROUPS_FILE = BASE_DIR / "groups.json"
MEMBERS_FILE = BASE_DIR / "members.json"

ROOT_CA_PATH = Path(os.getenv("ROOT_CA_PATH", PROJECT_ROOT / "secure_storage" / "root-ca.crt"))
root_ca_cert: x509.Certificate = None


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


groups_db = _load_json(GROUPS_FILE, {})
members_db = _load_json(MEMBERS_FILE, {})


def load_root_ca() -> x509.Certificate:
    global root_ca_cert
    if not ROOT_CA_PATH.exists():
        raise FileNotFoundError(
            f"Root CA certificate not found at {ROOT_CA_PATH}. "
            f"Set ROOT_CA_PATH environment variable or place root_ca.crt in {PROJECT_ROOT / 'secure_storage'}"
        )
    
    with ROOT_CA_PATH.open("rb") as f:
        root_ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    
    return root_ca_cert


def validate_uploaded_cert(cert_pem: str) -> x509.Certificate:
    """
    Validate an uploaded certificate against the Root CA.
    
    Args:
        cert_pem: PEM-encoded certificate string
        
    Returns:
        Parsed and validated x509.Certificate
        
    Raises:
        HTTPException(400): If certificate is invalid, not signed by Root CA, or expired
    """
    global root_ca_cert
    
    if root_ca_cert is None:
        raise HTTPException(status_code=500, detail="Root CA not loaded")
    
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"), default_backend())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid certificate format: {str(e)}")
    
    if cert.issuer != root_ca_cert.subject:
        raise HTTPException(
            status_code=400,
            detail=f"Certificate issuer does not match Root CA subject. Issuer: {cert.issuer}, Root CA: {root_ca_cert.subject}"
        )
    
    try:
        from cryptography.hazmat.primitives.asymmetric import padding
        public_key = root_ca_cert.public_key()
        
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
    
    not_valid_before = cert.not_valid_before
    not_valid_after = cert.not_valid_after
    
    if not_valid_before.tzinfo is None:
        not_valid_before = not_valid_before.replace(tzinfo=timezone.utc)
    if not_valid_after.tzinfo is None:
        not_valid_after = not_valid_after.replace(tzinfo=timezone.utc)
    
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
    
    return cert

class Member(BaseModel):
    name: str
    certificate_pem: str


class Group(BaseModel):
    name: str
    members: List[str]  


class GroupSnapshot(BaseModel):
    snapshot_id: str
    group_name: str
    resolved_at: str
    members: List[Member]


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Group Server",
        "version": "1.0.0",
        "endpoints": {
            "create_member": "POST /api/members",
            "list_members": "GET /api/members",
            "create_group": "POST /api/groups",
            "get_group": "GET /api/groups/{group_name}",
            "list_groups": "GET /api/groups",
            "add_member_to_group": "POST /api/groups/{group_name}/members",
            "remove_member_from_group": "DELETE /api/groups/{group_name}/members/{member_name}",
            "resolve_group": "POST /api/groups/{group_name}/resolve"
        }
    }


@app.post("/api/members")
async def create_member(member: Member):
    """Register a new member."""
    if member.name in members_db:
        raise HTTPException(status_code=400, detail="Member already exists")
    
    members_db[member.name] = member.dict()
    _save_json(MEMBERS_FILE, members_db)
    return {"success": True, "member": member}


@app.get("/api/members")
async def list_members():
    """List all registered members."""
    return {"members": list(members_db.values())}


@app.post("/api/members/upload")
async def create_member_from_file(
    name: str = Form(..., description="Member name"),
    cert_file: UploadFile = File(..., description="Member's X.509 certificate file (PEM)")
):
    """
    Register a new member using a name and an uploaded X.509 certificate file.
    The certificate is validated against the Root CA before storage.
    """
    if name in members_db:
        raise HTTPException(status_code=400, detail="Member already exists")

    cert_bytes = await cert_file.read()
    if not cert_bytes:
        raise HTTPException(status_code=400, detail="Empty certificate file")

    try:
        cert_pem = cert_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Certificate file must be PEM text format")

    validate_uploaded_cert(cert_pem)

    member = Member(name=name, certificate_pem=cert_pem)
    members_db[name] = member.dict()
    _save_json(MEMBERS_FILE, members_db)
    return {"success": True, "member": member}


@app.post("/api/groups")
async def create_group(group: Group):
    """Create a new group."""
    if group.name in groups_db:
        raise HTTPException(status_code=400, detail="Group already exists")
    
    for member_name in group.members:
        if member_name not in members_db:
            raise HTTPException(status_code=400, detail=f"Member '{member_name}' not found")
    
    groups_db[group.name] = {
        "name": group.name,
        "members": group.members,
        "created_at": datetime.now().isoformat()
    }
    _save_json(GROUPS_FILE, groups_db)
    
    return {"success": True, "group": groups_db[group.name]}


@app.get("/api/groups/{group_name}")
async def get_group(group_name: str):
    """Get group details."""
    if group_name not in groups_db:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = groups_db[group_name]
    members = [members_db[name] for name in group["members"]]
    
    return {
        "name": group["name"],
        "members": members,
        "created_at": group["created_at"]
    }


@app.get("/api/groups")
async def list_groups():
    """List all groups."""
    return {"groups": list(groups_db.values())}


@app.post("/api/groups/{group_name}/members")
async def add_member_to_group(group_name: str, member_name: str):
    """Add a member to a group."""
    if group_name not in groups_db:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if member_name not in members_db:
        raise HTTPException(status_code=404, detail="Member not found")
    
    if member_name in groups_db[group_name]["members"]:
        raise HTTPException(status_code=400, detail="Member already in group")
    
    groups_db[group_name]["members"].append(member_name)
    _save_json(GROUPS_FILE, groups_db)
    return {"success": True, "group": groups_db[group_name]}


@app.delete("/api/groups/{group_name}/members/{member_name}")
async def remove_member_from_group(group_name: str, member_name: str):
    """Remove a member from a group."""
    if group_name not in groups_db:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if member_name not in groups_db[group_name]["members"]:
        raise HTTPException(status_code=400, detail="Member not in group")
    
    groups_db[group_name]["members"].remove(member_name)
    _save_json(GROUPS_FILE, groups_db)
    return {"success": True, "group": groups_db[group_name]}


@app.post("/api/groups/{group_name}/resolve")
async def resolve_group(group_name: str) -> GroupSnapshot:
    """
    Resolve a group to its current members at this moment.
    This enforces the rules valid at the moment of resolution.
    Returns a snapshot that can be used for auditing.
    """
    if group_name not in groups_db:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = groups_db[group_name]
    
    members = []
    for member_name in group["members"]:
        if member_name in members_db:
            members.append(Member(**members_db[member_name]))
    
    snapshot = GroupSnapshot(
        snapshot_id=str(uuid.uuid4()),
        group_name=group_name,
        resolved_at=datetime.now().isoformat(),
        members=members
    )
    
    return snapshot


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="10.10.10.20", port=8001)
