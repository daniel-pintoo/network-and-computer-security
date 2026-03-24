# ChainOfProduct Secure Document Platform

Secure multi-service platform for protecting, validating, and selectively sharing transaction documents across organizations in a zero-trust supply-chain setting.

Developed in the context of the Network and Computer Security course at Instituto Superior Tecnico, this project combines applied cryptography, backend services, PKI, TLS, and segmented infrastructure.

## Overview

The system protects Delivery-vs-Payment transaction documents while preserving:

- confidentiality for authorized parties only
- integrity and authenticity of stored documents
- auditable sharing history
- controlled disclosure to individual partners or dynamic partner groups

At a high level, the platform encrypts each document once, wraps the session key for each authorized recipient, signs critical data, and validates certificates before any disclosure action.

## Architecture

![Final infrastructure](img/final-infrastructure.drawio.png)

The platform is split across multiple services:

- `api/` - FastAPI application exposing document protection, validation, unprotection, and sharing endpoints
- `src/pt/tecnico/secure/` - Java cryptographic library and CLI for secure document operations
- `group-server/` - FastAPI service for group and member management
- `certificate_authority/` - internal CA service for CSR signing and Root CA distribution
- `secure_storage/` - public certificate material used by services

Infrastructure-wise, the project uses:

- a front network for client-facing services
- a back network for database access
- PostgreSQL for protected document storage
- Nginx for HTTPS termination
- UFW firewall rules to restrict machine-to-machine communication

## Security Design

Core document protection is based on:

- `AES-256-GCM` for document confidentiality and integrity
- `RSA-OAEP` for per-recipient key wrapping
- `RSASSA-PSS` for digital signatures
- `X.509 certificates` and a private CA for identity validation

The group-sharing extension adds:

- dynamic resolution of group membership
- certificate-backed authorization for recipients
- snapshot-based sharing semantics so new group members cannot retroactively access old disclosures

## Main Features

- Protect a JSON transaction for seller and buyer
- Validate document integrity, signatures, and freshness
- Unprotect documents only for authorized recipients
- Share documents with new recipients while preserving an audit trail
- Share documents to groups resolved at disclosure time
- Validate partner certificates against an internal Root CA
- Secure client-to-app and app-to-database traffic with TLS

## Tech Stack

- Python / FastAPI
- Java / Maven / JCA
- PostgreSQL
- Nginx
- OpenSSL
- VirtualBox
- Linux / UFW

## Repository Structure

```text
.
|-- api/
|-- certificate_authority/
|-- group-server/
|-- secure_storage/
|-- src/pt/tecnico/secure/
|-- FIREWALL_TLS_SETUP.md
|-- REPORT.md
|-- USAGE.md
|-- creating-vms.md
|-- generate-client-keys.sh
|-- pom.xml
`-- requirements.txt
```

## Running The Project

This repository is designed for a multi-VM demonstration environment. The full setup requires multiple Kali Linux machines and network segmentation.

Recommended reading order:

1. `REPORT.md` for the rationale and security model
2. `creating-vms.md` for infrastructure provisioning
3. `FIREWALL_TLS_SETUP.md` for TLS and firewall setup
4. `USAGE.md` for the end-to-end demo flow

### Minimal application setup

Python dependencies:

```sh
python3 -m venv api-venv
source api-venv/bin/activate
pip install -r requirements.txt
```

Java build:

```sh
mvn compile
```

API configuration:

```sh
export DATABASE_URL="postgresql://appuser:change-me@localhost:5432/appdb"
```

The file `api/.env.example` documents the expected format if you want to keep local values in a separate untracked file.

## Supporting Documentation

- `REPORT.md` - detailed design, attacker model, infrastructure, and challenge solution
- `USAGE.md` - demonstration script with concrete commands
- `creating-vms.md` - VM, network, and connectivity setup
- `FIREWALL_TLS_SETUP.md` - firewall and TLS configuration

## Notes For Public Sharing

This version of the repository is prepared for public viewing:

- local secrets and machine-specific `.env` values are excluded
- generated private keys are ignored
- documentation focuses on the implemented system rather than raw course handout material

## Possible Future Improvements

- mutual TLS between internal services
- certificate revocation support
- stronger secret management for deployment
- automated infrastructure provisioning
- integration tests for multi-service flows
