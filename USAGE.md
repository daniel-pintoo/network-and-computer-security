# Secure Documents - ChainOfProduct Usage Guide

## Test Plan: Real-World Organization Interactions

This test plan simulates real-world interactions between organizations in the ChainOfProduct ecosystem. Tests are organized by VM to demonstrate the complete workflow.

**Note**: All client VMs (Samsung, Xiaomi, Apple, PCDiga) need **CA‑signed X.509 certificates** before they can protect documents for each other.  
Certificates are obtained from the Certificate Authority (cop-ca) and must be signed by the Root CA.  
Each client registers its certificate in the group server (cop-group); other clients and the application server can then fetch peer certificates from cop-group instead of copying them manually between VMs.  
The Root CA certificate (`root_ca.crt`) must be available to both cop-group and cop-app services for certificate validation.

---

## Initial Setup: All Client VMs

### Setup Step 1: Generate Key Pairs on Each Client VM

Each client VM must generate their own key pair first. The keys are generated in DER format.

#### Samsung VM
```bash
./generate-client-keys.sh Samsung
```

#### Xiaomi VM
```bash
./generate-client-keys.sh Xiaomi
```

#### Apple VM
```bash
./generate-client-keys.sh Apple
```

#### PCDiga VM
```bash
./generate-client-keys.sh PCDiga
```

### Setup Step 2: Convert Private Keys from DER to PEM Format for CSR Generation

The generated private keys are in DER format, but OpenSSL's `req` command requires PEM format. Convert each private key:

#### Samsung VM
```bash
openssl pkcs8 -inform DER -in keys/Samsung-priv.key -out keys/Samsung-priv.pem -nocrypt
```

#### Xiaomi VM
```bash
openssl pkcs8 -inform DER -in keys/Xiaomi-priv.key -out keys/Xiaomi-priv.pem -nocrypt
```

#### Apple VM
```bash
openssl pkcs8 -inform DER -in keys/Apple-priv.key -out keys/Apple-priv.pem -nocrypt
```

#### PCDiga VM
```bash
openssl pkcs8 -inform DER -in keys/PCDiga-priv.key -out keys/PCDiga-priv.pem -nocrypt
```

### Setup Step 3: Create Certificate Signing Requests (CSR)

Create CSR configuration files and generate CSRs for each client:

#### Samsung VM
```bash
cat > samsung.cnf << EOF
[req]
distinguished_name=req_dn
prompt=no
[req_dn]
CN=Samsung
O=Samsung Electronics
EOF

openssl req -new -key keys/Samsung-priv.pem -out samsung.csr -config samsung.cnf
```
**Expected**: `samsung.csr` created in PEM format

#### Xiaomi VM
```bash
cat > xiaomi.cnf << EOF
[req]
distinguished_name=req_dn
prompt=no
[req_dn]
CN=Xiaomi
O=Xiaomi Corporation
EOF

openssl req -new -key keys/Xiaomi-priv.pem -out xiaomi.csr -config xiaomi.cnf
```
**Expected**: `xiaomi.csr` created in PEM format

#### Apple VM
```bash
cat > apple.cnf << EOF
[req]
distinguished_name=req_dn
prompt=no
[req_dn]
CN=Apple
O=Apple Inc.
EOF

openssl req -new -key keys/Apple-priv.pem -out apple.csr -config apple.cnf
```
**Expected**: `apple.csr` created in PEM format

#### PCDiga VM
```bash
cat > pcdiga.cnf << EOF
[req]
distinguished_name=req_dn
prompt=no
[req_dn]
CN=PCDiga
O=PCDiga Retail
EOF

openssl req -new -key keys/PCDiga-priv.pem -out pcdiga.csr -config pcdiga.cnf
```
**Expected**: `pcdiga.csr` created in PEM format

### Setup Step 4: Register Certificates in Group Server

The group-server acts as a certificate repository. Each client must register their signed certificate with the group-server. Other clients can then retrieve certificates from the group-server when needed.

**Note**: Certificates must be signed by the Root CA. The group-server validates all certificates against the Root CA before storing them. Invalid or expired certificates will be rejected.

**Registration will be done in the group-server test section (Test 2.3-2.6)** after the certificates are signed by the CA.

---

## cop-ca (Certificate Authority) - 10.10.10.30:8002

### Test 1.1: Verify CA Service Health
```bash
curl http://10.10.10.30:8002/
```
**Expected**: `{"status": "ok", "service": "certificate-authority"}`

### Test 1.2: Retrieve Root CA Certificate
```bash
curl http://10.10.10.30:8002/root-ca
```
**Expected**: Root CA certificate in PEM format (save this for later verification)

**Save Root CA certificate**:
```bash
curl http://10.10.10.30:8002/root-ca | jq -r '.certificate_pem' > root-ca.crt
```

### Test 1.3: Sign CSR for Samsung

**From Samsung VM**, copy CSR to cop-ca or submit directly:
```bash
curl -X POST http://10.10.10.30:8002/sign \
  -F "csr_file=@samsung.csr" | jq -r '.certificate_pem' > samsung.crt
```
**Expected**: Signed certificate saved to `samsung.crt` in PEM format

**Verify certificate**:
```bash
openssl x509 -in samsung.crt -text -noout
```

### Test 1.4: Sign CSR for Xiaomi

**From Xiaomi VM**:
```bash
curl -X POST http://10.10.10.30:8002/sign \
  -F "csr_file=@xiaomi.csr" | jq -r '.certificate_pem' > xiaomi.crt
```
**Expected**: Signed certificate saved to `xiaomi.crt` in PEM format

**Verify certificate**:
```bash
openssl x509 -in xiaomi.crt -text -noout
```

### Test 1.5: Sign CSR for Apple

**From Apple VM**:
```bash
curl -X POST http://10.10.10.30:8002/sign \
  -F "csr_file=@apple.csr" | jq -r '.certificate_pem' > apple.crt
```
**Expected**: Signed certificate saved to `apple.crt` in PEM format

**Verify certificate**:
```bash
openssl x509 -in apple.crt -text -noout
```

### Test 1.6: Sign CSR for PCDiga

**From PCDiga VM**:
```bash
curl -X POST http://10.10.10.30:8002/sign \
  -F "csr_file=@pcdiga.csr" | jq -r '.certificate_pem' > pcdiga.crt
```
**Expected**: Signed certificate saved to `pcdiga.crt` in PEM format

**Verify certificate**:
```bash
openssl x509 -in pcdiga.crt -text -noout
```

### Test 1.7: Verify All Certificates Against Root CA

**On any VM with root-ca.crt and all client certificates**:
```bash
openssl verify -CAfile root-ca.crt samsung.crt

openssl verify -CAfile root-ca.crt xiaomi.crt

openssl verify -CAfile root-ca.crt apple.crt

openssl verify -CAfile root-ca.crt pcdiga.crt
```
**Expected**: All certificates show "OK"

---

## cop-group (Group Server) - 10.10.10.20:8001

### Test 2.1: Verify Group Service Health
```bash
curl http://10.10.10.20:8001/
```
**Expected**: Service information and available endpoints

### Test 2.2: Copy Root CA Certificate to Group Server

**On cop-group VM**, copy the Root CA certificate:
```bash
# Copy root_ca.crt to the group-server directory
# This can be done via scp from cop-ca or any VM that has it
# Example: scp user@cop-ca-ip:/path/to/root_ca.crt /path/to/group-server/root_ca.crt
```

**Verify Root CA is present**:
```bash
ls -la root_ca.crt
```
**Expected**: `root_ca.crt` exists in the group-server directory

### Test 2.3: Register Samsung as Member

**From Samsung VM** (using the signed certificate from cop-ca):
```bash
curl -X POST http://10.10.10.20:8001/api/members/upload \
  -F "name=Samsung" \
  -F "cert_file=@samsung.crt"
```
**Expected**: `{"success": true, "member": {"name": "Samsung", "certificate_pem": "..."}}`

**Note**: The certificate is validated against the Root CA before being stored. Invalid or expired certificates will be rejected.

### Test 2.4: Register Xiaomi as Member

**From Xiaomi VM** (using the signed certificate from cop-ca):
```bash
curl -X POST http://10.10.10.20:8001/api/members/upload \
  -F "name=Xiaomi" \
  -F "cert_file=@xiaomi.crt"
```
**Expected**: `{"success": true, "member": {"name": "Xiaomi", "certificate_pem": "..."}}`

### Test 2.5: Register Apple as Member

**From Apple VM** (using the signed certificate from cop-ca):
```bash
curl -X POST http://10.10.10.20:8001/api/members/upload \
  -F "name=Apple" \
  -F "cert_file=@apple.crt"
```
**Expected**: `{"success": true, "member": {"name": "Apple", "certificate_pem": "..."}}`

### Test 2.6: Register PCDiga as Member

**From PCDiga VM** (using the signed certificate from cop-ca):
```bash
curl -X POST http://10.10.10.20:8001/api/members/upload \
  -F "name=PCDiga" \
  -F "cert_file=@pcdiga.crt"
```
**Expected**: `{"success": true, "member": {"name": "PCDiga", "certificate_pem": "..."}}`

### Test 2.7: List All Registered Members
```bash
curl http://10.10.10.20:8001/api/members
```
**Expected**: List containing Samsung, Xiaomi, Apple, and PCDiga with their certificates

**Verify output**:
```bash
curl http://10.10.10.20:8001/api/members | jq '.members[] | .name'
```
**Expected**: `"Samsung"`, `"Xiaomi"`, `"Apple"`, `"PCDiga"`

**Verify certificates are stored**:
```bash
curl http://10.10.10.20:8001/api/members | jq '.members[] | {name, has_certificate: (.certificate_pem != null)}'
```
**Expected**: All members have `certificate_pem` field

### Test 2.8: Create "Smartphone Supply Chain" Group
```bash
curl -X POST http://10.10.10.20:8001/api/groups \
  -H "Content-Type: application/json" \
  -d '{"name": "SmartphoneSupplyChain", "members": ["Samsung", "Xiaomi", "Apple"]}'
```
**Expected**: `{"success": true, "group": {"name": "SmartphoneSupplyChain", "members": ["Samsung", "Xiaomi", "Apple"], "created_at": "..."}}`

### Test 2.9: Create "Retail Partners" Group
```bash
curl -X POST http://10.10.10.20:8001/api/groups \
  -H "Content-Type: application/json" \
  -d '{"name": "RetailPartners", "members": ["PCDiga", "Apple"]}'
```
**Expected**: `{"success": true, "group": {"name": "RetailPartners", "members": ["PCDiga", "Apple"], "created_at": "..."}}`

### Test 2.9: List All Groups
```bash
curl http://10.10.10.20:8001/api/groups
```
**Expected**: List of all groups

### Test 2.10: Get Smartphone Supply Chain Group Details
```bash
curl http://10.10.10.20:8001/api/groups/SmartphoneSupplyChain
```
**Expected**: Group details with member list

### Test 2.11: Add PCDiga to Smartphone Supply Chain Group
```bash
curl -X POST "http://10.10.10.20:8001/api/groups/SmartphoneSupplyChain/members?member_name=PCDiga"
```
**Expected**: `{"success": true, "group": {"name": "SmartphoneSupplyChain", "members": ["Samsung", "Xiaomi", "Apple", "PCDiga"], ...}}`

### Test 2.12: Resolve Smartphone Supply Chain Group
```bash
curl -X POST http://10.10.10.20:8001/api/groups/SmartphoneSupplyChain/resolve
```
**Expected**: Group snapshot with all current members and their certificates:
```json
{
  "snapshot_id": "...",
  "group_name": "SmartphoneSupplyChain",
  "resolved_at": "...",
  "members": [
    {"name": "Samsung", "certificate_pem": "-----BEGIN CERTIFICATE-----\n..."},
    {"name": "Xiaomi", "certificate_pem": "-----BEGIN CERTIFICATE-----\n..."},
    {"name": "Apple", "certificate_pem": "-----BEGIN CERTIFICATE-----\n..."},
    {"name": "PCDiga", "certificate_pem": "-----BEGIN CERTIFICATE-----\n..."}
  ]
}
```

---

## Samsung VM (Client)

### Test 3.1: Verify Keys and Certificates Are Generated
```bash
ls -la keys/Samsung-*
ls -la samsung.crt
```
**Expected**: `Samsung-priv.key`, `Samsung-pub.key`, and `samsung.crt` exist

### Test 3.2: Copy Root CA Certificate to cop-app

**On cop-app VM**, ensure the Root CA certificate is present:
```bash
# Copy root_ca.crt to the api directory
# This can be done via scp from cop-ca or any VM that has it
# Example: scp user@cop-ca-ip:/path/to/root_ca.crt /path/to/api/root_ca.crt
```

**Verify Root CA is present**:
```bash
ls -la root_ca.crt
```
**Expected**: `root_ca.crt` exists in the api directory

### Test 3.3: Retrieve Certificates from Group Server

**Note**: Certificates are stored in the group-server repository. Retrieve certificates as needed from the group-server:

**Retrieve all member certificates**:
```bash
# Get all registered members and their certificates
curl http://10.10.10.20:8001/api/members | jq '.'
```

**Retrieve specific certificates** (if needed locally):
```bash
# Get Xiaomi's certificate
curl http://10.10.10.20:8001/api/members | jq -r '.members[] | select(.name=="Xiaomi") | .certificate_pem' > xiaomi.crt

# Get Apple's certificate
curl http://10.10.10.20:8001/api/members | jq -r '.members[] | select(.name=="Apple") | .certificate_pem' > apple.crt

# Get PCDiga's certificate
curl http://10.10.10.20:8001/api/members | jq -r '.members[] | select(.name=="PCDiga") | .certificate_pem' > pcdiga.crt
```

**Note**: The group-server acts as the certificate repository. Clients can retrieve certificates from the group-server when needed, rather than manually exchanging them.

### Test 3.4: Create Transaction Document
```bash
cat > transaction-samsung-xiaomi.json << EOF
{
  "id": "TXN-001",
  "timestamp": "2024-01-15T10:30:00Z",
  "seller": "Samsung",
  "buyer": "Xiaomi",
  "product": "OLED Display Panels",
  "units": 5000,
  "amount": 2500000.00
}
EOF
```
**Expected**: Transaction JSON file created

**Verify transaction file**:
```bash
cat transaction-samsung-xiaomi.json | jq .
```

### Test 3.5: Protect Transaction Document
```bash
curl -X POST http://10.10.10.10:8000/api/documents/protect \
  -F "input_document=@transaction-samsung-xiaomi.json" \
  -F "seller_priv_key=@keys/Samsung-priv.key" \
  -F "seller_cert_file=@samsung.crt" \
  -F "buyer_cert_file=@xiaomi.crt" \
  -o protect-response.json
```
**Expected**: Protected document stored, returns document_id

**Note**: The certificates are validated against the Root CA before use. Invalid or expired certificates will cause the request to fail with a 400 error.

**Extract document_id**:
```bash
DOC_ID=$(jq -r '.document_id' protect-response.json)
echo "Document ID: $DOC_ID"
```

### Test 3.6: Check Document Integrity
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$DOC_ID/check \
  -F "seller_cert_file=@samsung.crt" \
  -o check-response.json
```
**Expected**: 
```json
{
  "is_fresh": true,
  "seller_signature_ok": true,
  "access_list_ok": true,
  "access_list_details": [...]
}
```

**Verify response**:
```bash
jq . check-response.json
```

### Test 3.7: Unprotect Own Document
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$DOC_ID/unprotect \
  -F "recipient_priv_key=@keys/Samsung-priv.key" \
  -o decrypted-samsung.json
```
**Expected**: Decrypted document saved to file

**Verify decrypted content matches original**:
```bash
diff <(jq -S . transaction-samsung-xiaomi.json) <(jq -S . decrypted-samsung.json)
```
**Expected**: No differences (files match)

### Test 3.8: Share Document with Apple
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$DOC_ID/share \
  -F "new_recipient_cert_file=@apple.crt" \
  -F "new_recipient_name=Apple" \
  -F "sharer_priv_key=@keys/Samsung-priv.key" \
  -F "sharer_name=Samsung" \
  -o share-response.json
```
**Expected**: Document shared successfully, Apple added to access list

**Verify sharing response**:
```bash
jq . share-response.json
```

### Test 3.9: Verify Access List After Sharing
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$DOC_ID/check \
  -F "seller_cert_file=@samsung.crt" \
  -o check-after-share.json
```
**Expected**: Access list shows Apple was added by Samsung

**Verify access list**:
```bash
jq '.access_list_details' check-after-share.json
```

---

## Xiaomi VM (Client)

### Test 4.1: Verify Keys and Certificates Are Generated
```bash
ls -la keys/Xiaomi-*
ls -la xiaomi.crt
```
**Expected**: `Xiaomi-priv.key`, `Xiaomi-pub.key`, and `xiaomi.crt` exist

### Test 4.2: Retrieve Certificates from Group Server

**Note**: Retrieve certificates from the group-server repository as needed:
```bash
# Retrieve Apple's certificate (buyer for this transaction)
curl http://10.10.10.20:8001/api/members | jq -r '.members[] | select(.name=="Apple") | .certificate_pem' > apple.crt

# Verify certificate is available
ls -la apple.crt
```
**Expected**: Certificate retrieved from group-server and available locally

### Test 4.3: Create Transaction Document
```bash
cat > transaction-xiaomi-apple.json << EOF
{
  "id": "TXN-002",
  "timestamp": "2024-01-16T14:20:00Z",
  "seller": "Xiaomi",
  "buyer": "Apple",
  "product": "Lithium-Ion Batteries",
  "units": 10000,
  "amount": 1500000.00
}
EOF
```
**Expected**: Transaction JSON file created

### Test 4.4: Protect Transaction Document
```bash
curl -X POST http://10.10.10.10:8000/api/documents/protect \
  -F "input_document=@transaction-xiaomi-apple.json" \
  -F "seller_priv_key=@keys/Xiaomi-priv.key" \
  -F "seller_cert_file=@xiaomi.crt" \
  -F "buyer_cert_file=@apple.crt" \
  -o protect-response.json

XIAOMI_DOC_ID=$(jq -r '.document_id' protect-response.json)
echo "Xiaomi Document ID: $XIAOMI_DOC_ID"
```
**Expected**: Protected document stored, returns document_id

### Test 4.5: Check Document Integrity
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$XIAOMI_DOC_ID/check \
  -F "seller_cert_file=@xiaomi.crt" \
  -o check-response.json
```
**Expected**: Integrity check passes

### Test 4.6: Unprotect Document Received from Samsung

**Note**: Get the document_id from Samsung's protect operation (TXN-001)
```bash
# Set SAMSUNG_DOC_ID (obtained from Samsung VM or from listing documents)
SAMSUNG_DOC_ID=1  # Replace with actual document ID

curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/unprotect \
  -F "recipient_priv_key=@keys/Xiaomi-priv.key" \
  -o decrypted-xiaomi-samsung.json
```
**Expected**: Decrypted document saved to file

**Verify decrypted content**:
```bash
jq . decrypted-xiaomi-samsung.json
```
**Expected**: Shows original transaction from Samsung to Xiaomi

### Test 4.7: Share Document with PCDiga
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$XIAOMI_DOC_ID/share \
  -F "new_recipient_cert_file=@pcdiga.crt" \
  -F "new_recipient_name=PCDiga" \
  -F "sharer_priv_key=@keys/Xiaomi-priv.key" \
  -F "sharer_name=Xiaomi" \
  -o share-response.json
```
**Expected**: Document shared successfully, PCDiga added to access list

---

## Apple VM (Client)

### Test 5.1: Verify Keys and Certificates Are Generated
```bash
ls -la keys/Apple-*
ls -la apple.crt
```
**Expected**: `Apple-priv.key`, `Apple-pub.key`, and `apple.crt` exist

### Test 5.2: Retrieve Certificates from Group Server

**Note**: Retrieve certificates from the group-server repository as needed:
```bash
# Retrieve PCDiga's certificate (buyer for this transaction)
curl http://10.10.10.20:8001/api/members | jq -r '.members[] | select(.name=="PCDiga") | .certificate_pem' > pcdiga.crt

# Verify certificate is available
ls -la pcdiga.crt
```
**Expected**: Certificate retrieved from group-server and available locally

### Test 5.3: Create Transaction Document
```bash
cat > transaction-apple-pcdiga.json << EOF
{
  "id": "TXN-003",
  "timestamp": "2024-01-17T09:15:00Z",
  "seller": "Apple",
  "buyer": "PCDiga",
  "product": "iPhone 15 Pro Max",
  "units": 500,
  "amount": 750000.00
}
EOF
```
**Expected**: Transaction JSON file created

### Test 5.4: Protect Transaction Document
```bash
curl -X POST http://10.10.10.10:8000/api/documents/protect \
  -F "input_document=@transaction-apple-pcdiga.json" \
  -F "seller_priv_key=@keys/Apple-priv.key" \
  -F "seller_cert_file=@apple.crt" \
  -F "buyer_cert_file=@pcdiga.crt" \
  -o protect-response.json

APPLE_DOC_ID=$(jq -r '.document_id' protect-response.json)
echo "Apple Document ID: $APPLE_DOC_ID"
```
**Expected**: Protected document stored, returns document_id

### Test 5.5: Check Document Integrity
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$APPLE_DOC_ID/check \
  -F "seller_cert_file=@apple.crt" \
  -o check-response.json
```
**Expected**: Integrity check passes

### Test 5.6: Unprotect Document Received from Samsung

**Note**: Get the document_id from Samsung's protect operation
```bash
# Set SAMSUNG_DOC_ID (obtained from Samsung VM)
SAMSUNG_DOC_ID=1  # Replace with actual document ID

curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/unprotect \
  -F "recipient_priv_key=@keys/Apple-priv.key" \
  -o decrypted-apple-samsung.json
```
**Expected**: Decrypted document saved to file (Apple can decrypt because Samsung shared it with Apple)

**Verify decrypted content**:
```bash
jq . decrypted-apple-samsung.json
```

### Test 5.7: Unprotect Document Received from Xiaomi
```bash
# Set XIAOMI_DOC_ID (obtained from Xiaomi VM)
XIAOMI_DOC_ID=2  # Replace with actual document ID

curl -X POST http://10.10.10.10:8000/api/documents/$XIAOMI_DOC_ID/unprotect \
  -F "recipient_priv_key=@keys/Apple-priv.key" \
  -o decrypted-apple-xiaomi.json
```
**Expected**: Decrypted document saved to file

**Verify decrypted content**:
```bash
jq . decrypted-apple-xiaomi.json
```

### Test 5.8: Verify Access List Integrity
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/check \
  -F "seller_cert_file=@samsung.crt" \
  -o check-access-list.json
```
**Expected**: Access list shows Apple was added by Samsung

**Verify access list details**:
```bash
jq '.access_list_details' check-access-list.json
```

---

## PCDiga VM (Client)

### Test 6.1: Verify Keys and Certificates Are Generated
```bash
ls -la keys/PCDiga-*
ls -la pcdiga.crt
```
**Expected**: `PCDiga-priv.key`, `PCDiga-pub.key`, and `pcdiga.crt` exist

### Test 6.2: Retrieve Certificates from Group Server

**Note**: Retrieve certificates from the group-server repository as needed:
```bash
# Retrieve Samsung's certificate (buyer for this transaction)
curl http://10.10.10.20:8001/api/members | jq -r '.members[] | select(.name=="Samsung") | .certificate_pem' > samsung.crt

# Verify certificate is available
ls -la samsung.crt
```
**Expected**: Certificate retrieved from group-server and available locally

### Test 6.3: Create Transaction Document
```bash
cat > transaction-pcdiga-samsung.json << EOF
{
  "id": "TXN-004",
  "timestamp": "2024-01-18T16:45:00Z",
  "seller": "PCDiga",
  "buyer": "Samsung",
  "product": "Customer Returns - Refurbished Devices",
  "units": 200,
  "amount": 120000.00
}
EOF
```
**Expected**: Transaction JSON file created

### Test 6.4: Protect Transaction Document
```bash
curl -X POST http://10.10.10.10:8000/api/documents/protect \
  -F "input_document=@transaction-pcdiga-samsung.json" \
  -F "seller_priv_key=@keys/PCDiga-priv.key" \
  -F "seller_cert_file=@pcdiga.crt" \
  -F "buyer_cert_file=@samsung.crt" \
  -o protect-response.json

PCDIGA_DOC_ID=$(jq -r '.document_id' protect-response.json)
echo "PCDiga Document ID: $PCDIGA_DOC_ID"
```
**Expected**: Protected document stored, returns document_id

### Test 6.5: Check Document Integrity
```bash
curl -X POST http://10.10.10.10:8000/api/documents/$PCDIGA_DOC_ID/check \
  -F "seller_cert_file=@pcdiga.crt" \
  -o check-response.json
```
**Expected**: Integrity check passes

### Test 6.6: Unprotect Document Received from Apple
```bash
# Set APPLE_DOC_ID (obtained from Apple VM)
APPLE_DOC_ID=3  # Replace with actual document ID

curl -X POST http://10.10.10.10:8000/api/documents/$APPLE_DOC_ID/unprotect \
  -F "recipient_priv_key=@keys/PCDiga-priv.key" \
  -o decrypted-pcdiga-apple.json
```
**Expected**: Decrypted document saved to file

**Verify decrypted content**:
```bash
jq . decrypted-pcdiga-apple.json
```

### Test 6.7: Unprotect Document Received from Xiaomi
```bash
# Set XIAOMI_DOC_ID (obtained from Xiaomi VM)
XIAOMI_DOC_ID=2  # Replace with actual document ID

curl -X POST http://10.10.10.10:8000/api/documents/$XIAOMI_DOC_ID/unprotect \
  -F "recipient_priv_key=@keys/PCDiga-priv.key" \
  -o decrypted-pcdiga-xiaomi.json
```
**Expected**: Decrypted document saved to file (PCDiga can decrypt because Xiaomi shared it)

**Verify decrypted content**:
```bash
jq . decrypted-pcdiga-xiaomi.json
```

---

## cop-app (Application Server) - 10.10.10.10:8000

### Test 7.1: Verify Application Service Health
```bash
curl http://10.10.10.10:8000/
```
**Expected**: Service information and available endpoints

**Verify response**:
```bash
curl http://10.10.10.10:8000/ | jq .
```

### Test 7.2: List All Protected Documents
```bash
curl http://10.10.10.10:8000/api/documents/
```
**Expected**: List of all protected documents in the system

**Format output**:
```bash
curl http://10.10.10.10:8000/api/documents/ | jq '.documents[] | {id, created_at}'
```

### Test 7.3: List Documents with Pagination
```bash
curl "http://10.10.10.10:8000/api/documents/?skip=0&limit=10"
```
**Expected**: First 10 documents

### Test 7.4: Get Specific Document by ID
```bash
DOC_ID=1  # Replace with actual document ID
curl http://10.10.10.10:8000/api/documents/$DOC_ID
```
**Expected**: Document details (without decryption)

### Test 7.5: Verify Cross-Organization Document Access
```bash
# Test that access lists are properly maintained
curl -X POST http://10.10.10.10:8000/api/documents/$PCDIGA_DOC_ID/check \
  -F "seller_cert_file=@pcdiga.crt" \
  -o check-pcdiga-doc.json
```
**Expected**: Access list verification shows all authorized recipients

**Verify access list**:
```bash
jq '.access_list_details' check-pcdiga-doc.json
```

---

## cop-db (Database Server) - 10.10.20.20

### Test 8.1: Verify Database Connectivity
```bash
# From cop-app or any client with DB access
psql -h 10.10.20.20 -U appuser -d appdb -c "SELECT COUNT(*) FROM protected_documents;"
```
**Expected**: Count of stored documents

### Test 8.2: Verify Document Persistence
```bash
# After creating documents, verify they persist in database
psql -h 10.10.20.20 -U appuser -d appdb -c "SELECT id, created_at FROM protected_documents ORDER BY created_at DESC LIMIT 5;"
```
**Expected**: List of recent documents with timestamps

### Test 8.3: Verify Access List Storage
```bash
# Check that access lists are properly stored
psql -h 10.10.20.20 -U appuser -d appdb -c "SELECT id, jsonb_array_length(document->'access_list') as access_count FROM protected_documents;"
```
**Expected**: Access list counts for each document

### Test 8.4: Verify Document Structure
```bash
# Verify document structure in database
psql -h 10.10.20.20 -U appuser -d appdb -c "SELECT id, document->'metadata' as metadata, document->'timestamp' as timestamp FROM protected_documents LIMIT 1;"
```
**Expected**: Document metadata and timestamp

### Test 8.5: Verify Wrapped Keys Storage
```bash
# Check that wrapped keys are stored
psql -h 10.10.20.20 -U appuser -d appdb -c "SELECT id, jsonb_array_length(document->'wrapped_keys') as key_count FROM protected_documents;"
```
**Expected**: Number of wrapped keys per document (should match number of recipients)

---

## Cross-VM Integration Tests

### Test 9.1: End-to-End Transaction Flow
**Scenario**: Samsung sells to Xiaomi, shares with Apple, Apple shares with PCDiga

1. **Samsung**: Protect transaction document (TXN-001)
   ```bash
   # Already done in Test 3.4
   SAMSUNG_DOC_ID=1  # Use actual ID
   ```

2. **Xiaomi**: Unprotect and verify document
   ```bash
   # Already done in Test 4.6
   curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/unprotect \
     -F "recipient_priv_key=@keys/Xiaomi-priv.key" \
     -o xiaomi-verification.json
   ```

3. **Samsung**: Share document with Apple
   ```bash
   # Already done in Test 3.7
   ```

4. **Apple**: Unprotect document, verify access
   ```bash
   # Already done in Test 5.6
   curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/unprotect \
     -F "recipient_priv_key=@keys/Apple-priv.key" \
     -o apple-verification.json
   ```

5. **Apple**: Share document with PCDiga
   ```bash
   curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/share \
     -F "new_recipient_cert_file=@pcdiga.crt" \
     -F "new_recipient_name=PCDiga" \
     -F "sharer_priv_key=@keys/Apple-priv.key" \
     -F "sharer_name=Apple" \
     -o apple-share-response.json
   ```

6. **PCDiga**: Unprotect document, verify access
   ```bash
   curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/unprotect \
     -F "recipient_priv_key=@keys/PCDiga-priv.key" \
     -o pcdiga-verification.json
   ```

7. **All parties**: Check document integrity independently
   ```bash
   # From each VM (using their own certificate)
   curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/check \
     -F "seller_cert_file=@samsung.crt" \
     -o check-from-{vm-name}.json
   ```

**Expected**: All parties can verify integrity and access documents as authorized

### Test 9.2: Group-Based Document Sharing
**Scenario**: Use group resolution for bulk sharing

1. **cop-group**: Resolve "SmartphoneSupplyChain" group
   ```bash
   curl -X POST http://10.10.10.20:8001/api/groups/SmartphoneSupplyChain/resolve \
     -o group-snapshot.json
   ```

2. **Samsung**: Share document with all group members using group resolution
   ```bash
   # Use the share_to_group endpoint which automatically validates certificates
   curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/share_to_group \
     -F "group_name=SmartphoneSupplyChain" \
     -F "sharer_priv_key=@keys/Samsung-priv.key" \
     -F "sharer_name=Samsung" \
     -o group-share-response.json
   ```
   
   **Note**: The `share_to_group` endpoint automatically:
   - Resolves the group from cop-group
   - Validates each member's certificate against the Root CA
   - Skips members with invalid/expired certificates (logs warning)
   - Shares the document with all valid members

3. **All group members**: Verify access to shared document
   ```bash
   # Each member should be able to unprotect the document
   ```

**Expected**: All group members can access the document

### Test 9.3: Access Control Verification
**Scenario**: Verify unauthorized access is prevented

1. **Samsung**: Create document with only Xiaomi as recipient
   ```bash
   curl -X POST http://10.10.10.10:8000/api/documents/protect \
     -F "input_document=@transaction-samsung-xiaomi.json" \
     -F "seller_priv_key=@keys/Samsung-priv.key" \
     -F "seller_cert_file=@samsung.crt" \
     -F "buyer_cert_file=@xiaomi.crt" \
     -o restricted-doc.json
   
   RESTRICTED_DOC_ID=$(jq -r '.document_id' restricted-doc.json)
   ```

2. **Apple**: Attempt to unprotect document (should fail)
   ```bash
   curl -X POST http://10.10.10.10:8000/api/documents/$RESTRICTED_DOC_ID/unprotect \
     -F "recipient_priv_key=@keys/Apple-priv.key" \
     -o apple-attempt.json
   ```
   **Expected**: Error response (Apple is not authorized)

3. **PCDiga**: Attempt to unprotect document (should fail)
   ```bash
   curl -X POST http://10.10.10.10:8000/api/documents/$RESTRICTED_DOC_ID/unprotect \
     -F "recipient_priv_key=@keys/PCDiga-priv.key" \
     -o pcdiga-attempt.json
   ```
   **Expected**: Error response (PCDiga is not authorized)

4. **Xiaomi**: Successfully unprotect document
   ```bash
   curl -X POST http://10.10.10.10:8000/api/documents/$RESTRICTED_DOC_ID/unprotect \
     -F "recipient_priv_key=@keys/Xiaomi-priv.key" \
     -o xiaomi-success.json
   ```
   **Expected**: Successful decryption

**Expected**: Only authorized recipients can decrypt documents

### Test 9.4: Audit Trail Verification
**Scenario**: Verify access list integrity and audit trail

1. **Samsung**: Create and protect document
   ```bash
   # Already done in Test 3.4
   AUDIT_DOC_ID=$SAMSUNG_DOC_ID
   ```

2. **Samsung**: Share with multiple parties sequentially
   ```bash
   # Share with Apple
   curl -X POST http://10.10.10.10:8000/api/documents/$AUDIT_DOC_ID/share \
     -F "new_recipient_cert_file=@apple.crt" \
     -F "new_recipient_name=Apple" \
     -F "sharer_priv_key=@keys/Samsung-priv.key" \
     -F "sharer_name=Samsung"
   
   # Share with PCDiga (by Apple after receiving)
   curl -X POST http://10.10.10.10:8000/api/documents/$AUDIT_DOC_ID/share \
     -F "new_recipient_cert_file=@pcdiga.crt" \
     -F "new_recipient_name=PCDiga" \
     -F "sharer_priv_key=@keys/Apple-priv.key" \
     -F "sharer_name=Apple"
   ```

3. **All parties**: Check document and verify access list
   ```bash
   curl -X POST http://10.10.10.10:8000/api/documents/$AUDIT_DOC_ID/check \
     -F "seller_cert_file=@samsung.crt" \
     -o audit-check.json
   ```

4. **Verify**: Access list shows correct sharing chain with timestamps
   ```bash
   jq '.access_list_details' audit-check.json
   ```
   **Expected**: Shows sharing chain:
   - Initial: Samsung (seller), Xiaomi (buyer)
   - Shared by Samsung: Apple
   - Shared by Apple: PCDiga
   - Each entry has timestamp and signature

**Expected**: Complete audit trail of all sharing operations

### Test 9.5: Certificate Chain Verification
**Scenario**: Verify all certificates are properly signed by the Root CA

1. **On any VM with all certificates**:
   ```bash
   # Verify all client certificates against Root CA
   openssl verify -CAfile root-ca.crt samsung.crt
   openssl verify -CAfile root-ca.crt xiaomi.crt
   openssl verify -CAfile root-ca.crt apple.crt
   openssl verify -CAfile root-ca.crt pcdiga.crt
   ```

2. **Verify certificate details**:
   ```bash
   # Check each certificate's subject and issuer
   openssl x509 -in samsung.crt -noout -subject -issuer
   openssl x509 -in xiaomi.crt -noout -subject -issuer
   openssl x509 -in apple.crt -noout -subject -issuer
   openssl x509 -in pcdiga.crt -noout -subject -issuer
   ```

**Expected**: All certificates are valid and signed by the Root CA

---

## Security Requirement Validation

### SR1 (Confidentiality) Tests

#### Test SR1.1: Verify Documents Are Encrypted
```bash
# Attempt to read protected document without decryption
curl http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID | jq '.document.ciphertext'
```
**Expected**: Ciphertext is base64-encoded and not readable as plaintext

#### Test SR1.2: Verify Wrapped Keys Prevent Unauthorized Decryption
```bash
# Try to decrypt with wrong private key
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/unprotect \
  -F "recipient_priv_key=@keys/Apple-priv.key" \
  -o unauthorized-attempt.json
```
**Expected**: Decryption fails (if Apple is not authorized)

#### Test SR1.3: Verify Only Recipients with Private Keys Can Decrypt
```bash
# Authorized recipient should succeed
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/unprotect \
  -F "recipient_priv_key=@keys/Xiaomi-priv.key" \
  -o authorized-success.json
```
**Expected**: Successful decryption for authorized recipient

### SR2 (Authentication) Tests

#### Test SR2.1: Verify Only Parties with Wrapped Keys Can Share
```bash
# Unauthorized party attempts to share (should fail)
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/share \
  -F "new_recipient_cert_file=@pcdiga.crt" \
  -F "new_recipient_name=PCDiga" \
  -F "sharer_priv_key=@keys/PCDiga-priv.key" \
  -F "sharer_name=PCDiga" \
  -o unauthorized-share-attempt.json
```
**Expected**: Sharing fails if PCDiga doesn't have access

#### Test SR2.2: Verify Sharing Requires Valid Private Key Signature
```bash
# Authorized party (Samsung) shares successfully
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/share \
  -F "new_recipient_cert_file=@apple.crt" \
  -F "new_recipient_name=Apple" \
  -F "sharer_priv_key=@keys/Samsung-priv.key" \
  -F "sharer_name=Samsung" \
  -o authorized-share-success.json
```
**Expected**: Sharing succeeds with valid signature

### SR3 (Integrity 1) Tests

#### Test SR3.1: Verify Seller Signature Is Required
```bash
# Check document without seller signature (should fail)
# This would require creating a document without seller signature
# (implementation dependent)
```

#### Test SR3.2: Verify Document Tampering Is Detected
```bash
# Modify document in database and check integrity
# (This would require direct database access and modification)
# Then verify check operation detects tampering
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/check \
  -F "seller_cert_file=@samsung.crt" \
  -o tamper-check.json
```
**Expected**: Check operation detects any tampering

#### Test SR3.3: Verify Signature Verification in Check Operation
```bash
# Check operation verifies seller signature
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/check \
  -F "seller_cert_file=@samsung.crt" \
  -o signature-check.json

jq '.seller_signature_ok' signature-check.json
```
**Expected**: `true` for valid signature

### SR4 (Integrity 2) Tests

#### Test SR4.1: Verify Access List Is Signed
```bash
# Check access list integrity
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/check \
  -F "seller_cert_file=@samsung.crt" \
  -o access-list-check.json

jq '.access_list_ok' access-list-check.json
```
**Expected**: `true` for valid access list

#### Test SR4.2: Verify Access List Changes Are Properly Authenticated
```bash
# After sharing, verify access list entry is signed
curl -X POST http://10.10.10.10:8000/api/documents/$SAMSUNG_DOC_ID/check \
  -F "seller_cert_file=@samsung.crt" \
  -o access-list-details.json

jq '.access_list_details[] | {recipient, shared_by, timestamp}' access-list-details.json
```
**Expected**: Each access list entry shows who shared it and when

#### Test SR4.3: Verify Audit Trail Integrity
```bash
# Verify complete audit trail
curl -X POST http://10.10.10.10:8000/api/documents/$AUDIT_DOC_ID/check \
  -F "seller_cert_file=@samsung.crt" \
  -o audit-trail.json

jq '.access_list_details' audit-trail.json
```
**Expected**: Complete audit trail with all sharing operations, timestamps, and signatures

---

## Cleanup and Verification

### Final Verification: List All Documents
```bash
curl http://10.10.10.10:8000/api/documents/ | jq '.documents | length'
```
**Expected**: Count of all created documents

### Final Verification: List All Members
```bash
curl http://10.10.10.20:8001/api/members | jq '.members | length'
```
**Expected**: 4 members (Samsung, Xiaomi, Apple, PCDiga)

### Final Verification: List All Groups
```bash
curl http://10.10.10.20:8001/api/groups | jq '.groups | length'
```
**Expected**: 2 groups (SmartphoneSupplyChain, RetailPartners)

### Final Verification: Database State
```bash
psql -h 10.10.20.20 -U appuser -d appdb -c "SELECT COUNT(*) as total_documents, SUM(jsonb_array_length(document->'access_list')) as total_access_entries FROM protected_documents;"
```
**Expected**: Summary of documents and access list entries

---

## Notes

- **Document IDs**: Replace `{document_id}`, `$DOC_ID`, `$SAMSUNG_DOC_ID`, etc. with actual document IDs returned from protect operations
- **Certificate Repository**: The group-server (cop-group) acts as a certificate repository. Clients register their certificates with the group-server after getting them signed by the CA. When clients need other clients' certificates, they retrieve them from the group-server. Certificates must be signed by the Root CA and are validated by the group-server before storage.
- **Root CA Setup**: Both `cop-group` and `cop-app` services require `root_ca.crt` in their root directories (or set via `ROOT_CA_PATH` environment variable) for certificate validation
- **Network Connectivity**: Ensure all VMs can reach each other on the specified IP addresses
- **Error Handling**: All curl commands should check HTTP status codes and response content
- **Timing**: Some tests depend on previous tests completing successfully
- **Certificate Validity**: All certificates are automatically validated against the Root CA by the services. Invalid or expired certificates will be rejected with HTTP 400 errors
