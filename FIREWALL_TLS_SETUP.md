## Overview

This document explains how to:
- Configure firewalls on the core VMs (`cop-client`, `cop-app`, `cop-db`, `cop-group`, `cop-ca`).
- Enable TLS on the **back-net** (API ↔ DB / PostgreSQL).
- Enable TLS on the **front-net** (client ↔ API / HTTPS).

Assumed IPs and roles:
- `cop-client`: `10.10.10.100/24` (front-net only)
- `cop-app`: `10.10.10.10/24` (front-net), `10.10.20.10/24` (back-net)
- `cop-db`: `10.10.20.20/24` (back-net, PostgreSQL)
- `cop-group`: `10.10.10.20/24` (front-net, group server)
- `cop-ca`: `10.10.10.30/24` (front-net, certificate authority)

---

## 1) Firewall Configuration (UFW)

### 1.1 cop-client (10.10.10.100)

No inbound services; only initiates connections to `cop-app`.

```bash
sudo ufw reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
sudo ufw status verbose
```

### 1.2 cop-app (10.10.10.10 front, 10.10.20.10 back)

Allow only API traffic from front-net and (optionally) SSH. Outbound to DB is allowed by default.

#### Initial HTTP (port 8000) setup

```bash
sudo ufw reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# API (HTTP, before HTTPS/nginx is enabled)
sudo ufw allow from 10.10.10.0/24 to any port 8000 proto tcp

# Optional: SSH from front-net (for admin/SSH tunnels)
sudo ufw allow from 10.10.10.0/24 to any port 22 proto tcp

sudo ufw enable
sudo ufw status verbose
```

#### After enabling HTTPS (port 443 via nginx)

Replace the API rule:

```bash
sudo ufw delete allow from 10.10.10.0/24 to any port 8000 proto tcp
sudo ufw allow from 10.10.10.0/24 to any port 443 proto tcp
sudo ufw status verbose
```

### 1.3 cop-db (10.10.20.20)

Only the app server (`cop-app` at `10.10.20.10`) may reach PostgreSQL.

```bash
sudo ufw reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

sudo ufw allow from 10.10.20.10 to any port 5432 proto tcp

sudo ufw enable
sudo ufw status verbose
```

Result:
- Client → App allowed (HTTP/HTTPS).
- App → DB allowed (5432).
- Client → DB blocked (no rule, default deny, different network).

### 1.4 cop-group (10.10.10.20)

`cop-group` runs the Group Server; **any host on the front-net** may need to reach it (there can be several different client VMs).

```bash
sudo ufw reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow all front-net hosts to reach group-server HTTP port (8001)
sudo ufw allow from 10.10.10.0/24 to any port 8001 proto tcp

sudo ufw enable
sudo ufw status verbose
```

Result:
- Any VM on `10.10.10.0/24` (front-net) can call `cop-group` (`10.10.10.20:8001`) to register and resolve groups.

### 1.5 cop-ca (10.10.10.30)

`cop-ca` runs the internal Certificate Authority; only front-net clients and servers need to reach it on port 8002.

```bash
sudo ufw reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow front-net to reach CA HTTP API (8002)
sudo ufw allow from 10.10.10.0/24 to any port 8002 proto tcp

sudo ufw enable
sudo ufw status verbose
```

Result:
- Only machines on `front-net` can obtain certificates or fetch the Root CA from `cop-ca` (`10.10.10.30:8002`).

### 1.6 Firewall summary table

| VM        | IP addresses                         | Purpose                          | Inbound allowed                               | Outbound policy            |
|-----------|--------------------------------------|----------------------------------|-----------------------------------------------|----------------------------|
| cop-client| `10.10.10.100/24`                    | External client / demo driver    | None (default deny)                           | Allow all                  |
| cop-app   | `10.10.10.10/24`, `10.10.20.10/24`   | API server + TLS termination     | From `10.10.10.0/24` → 443/tcp (HTTPS)        | Allow all (incl. DB @5432) |
| cop-db    | `10.10.20.20/24`                     | PostgreSQL database              | From `10.10.20.10` → 5432/tcp (PostgreSQL)    | Allow all                  |
| cop-group | `10.10.10.20/24`                     | Group server (certificate dir.)  | From `10.10.10.0/24` → 8001/tcp (group API)   | Allow all                  |
| cop-ca    | `10.10.10.30/24`                     | Certificate Authority            | From `10.10.10.0/24` → 8002/tcp (CA API)      | Allow all                  |

---

## 2) TLS on Back-Net (cop-app ↔ cop-db / PostgreSQL)

We use a small internal CA and issue a server cert for the DB. The API uses TLS when connecting to PostgreSQL.

### 2.1 Generate CA and DB cert (on cop-app or host)

On **cop-app** (example):

```bash
mkdir -p ~/tls && cd ~/tls

# CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -key ca.key -sha256 -days 365 -out ca.crt -subj "/CN=cop-ca"

# DB cert (SAN = 10.10.20.20)
cat > db.cnf <<'EOF'
[req]
distinguished_name=req_dn
req_extensions=req_ext
prompt=no
[req_dn]
CN=cop-db
[req_ext]
subjectAltName=IP:10.10.20.20
EOF

openssl genrsa -out db.key 2048
openssl req -new -key db.key -out db.csr -config db.cnf
openssl x509 -req -in db.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out db.crt -days 365 -sha256 -extfile db.cnf -extensions req_ext
```

You now have: `ca.key`, `ca.crt`, `db.key`, `db.crt` in `~/tls` on `cop-app`.

### 2.2 Copy DB certs to cop-db

1. Ensure SSH on cop-db:

```bash
sudo apt install openssh-server
sudo systemctl enable --now ssh
sudo ufw allow from 10.10.20.10 to any port 22 proto tcp   # temporary for copy
```

2. From **cop-app**:

```bash
cd ~/tls
scp db.crt db.key ca.crt kali@10.10.20.20:~/tls/
```

3. On **cop-db**:

```bash
sudo mkdir -p /etc/postgresql/17/main/tls
sudo mv ~/tls/db.crt ~/tls/db.key ~/tls/ca.crt /etc/postgresql/17/main/tls/
sudo chmod 600 /etc/postgresql/17/main/tls/db.key
```

### 2.3 Configure PostgreSQL to use TLS (cop-db)

Edit `postgresql.conf`:

```bash
sudo nano /etc/postgresql/17/main/postgresql.conf
```

Set:

```conf
listen_addresses = '10.10.20.20'

ssl = on
ssl_cert_file = '/etc/postgresql/17/main/tls/db.crt'
ssl_key_file  = '/etc/postgresql/17/main/tls/db.key'
ssl_ca_file   = '/etc/postgresql/17/main/tls/ca.crt'
```

Edit `pg_hba.conf`:

```bash
sudo nano /etc/postgresql/17/main/pg_hba.conf
```

Add/replace the relevant line with:

```conf
hostssl appdb appuser 10.10.20.10/32 md5
```

Restart the cluster:

```bash
sudo systemctl restart postgresql@17-main
sudo -u postgres pg_lsclusters   # should show 17 main online
```

### 2.4 Test TLS from cop-app

Ensure `ca.crt` exists on `cop-app` in `~/tls/`.

```bash
cd ~/tls
psql "host=10.10.20.20 dbname=appdb user=appuser password=strongpass sslmode=require sslrootcert=$HOME/tls/ca.crt" -c '\conninfo'
```

Expected output includes:
- `SSL Connection       | true`
- `SSL Protocol         | TLSv1.3`



---

## 3) TLS on Front-Net (cop-client ↔ cop-app / HTTPS)

Here we terminate HTTPS on `cop-app` with nginx and proxy to uvicorn on localhost:8000.

### 3.1 Generate API server cert (already done alongside DB cert)

If not yet done, on **cop-app**:

```bash
cd ~/tls

cat > app.cnf <<'EOF'
[req]
distinguished_name=req_dn
req_extensions=req_ext
prompt=no
[req_dn]
CN=cop-app
[req_ext]
subjectAltName=IP:10.10.10.10
EOF

openssl genrsa -out app.key 2048
openssl req -new -key app.key -out app.csr -config app.cnf
openssl x509 -req -in app.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out app.crt -days 365 -sha256 -extfile app.cnf -extensions req_ext
```

You now have: `app.key`, `app.crt`, `ca.crt` in `~/tls` on cop-app.

### 3.2 Install nginx and place certs (cop-app)

```bash
sudo apt update
sudo apt install nginx

sudo mkdir -p /etc/nginx/tls
sudo cp ~/tls/app.crt ~/tls/app.key ~/tls/ca.crt /etc/nginx/tls/
sudo chmod 600 /etc/nginx/tls/app.key

# start nginx if not already running
sudo systemctl start nginx
sudo systemctl status nginx
```

### 3.3 nginx HTTPS → uvicorn proxy

Create a site config:

```bash
sudo tee /etc/nginx/sites-available/secure-docs >/dev/null <<'EOF'
server {
    listen 443 ssl;
    server_name 10.10.10.10;

    ssl_certificate     /etc/nginx/tls/app.crt;
    ssl_certificate_key /etc/nginx/tls/app.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/secure-docs /etc/nginx/sites-enabled/secure-docs
sudo nginx -t
sudo systemctl reload nginx
```

Run the FastAPI app behind nginx:

```bash
source ~/api-venv/bin/activate
cd /path/to/T50-ChainOfProduct/api
uvicorn main:app --host 127.0.0.1 --port 8000
```

### 3.4 Adjust firewall for HTTPS (cop-app)

```bash
# remove HTTP rule if it exists
sudo ufw delete allow from 10.10.10.0/24 to any port 8000 proto tcp || true

# allow HTTPS from front-net
sudo ufw allow from 10.10.10.0/24 to any port 443 proto tcp
sudo ufw status verbose
```

### 3.5 Install CA on cop-client (optional but recommended)

This makes the client trust your internal CA so HTTPS works without warnings.

#### 3.5.1 Copy `ca.crt` from cop-app to cop-client (via SSH)

On **cop-client** (enable SSH once):

```bash
sudo apt update
sudo apt install openssh-server
sudo systemctl enable --now ssh

# allow SSH from front-net (you can restrict to a single admin IP if desired)
sudo ufw allow from 10.10.10.0/24 to any port 22 proto tcp
sudo ufw status
```

On **cop-app**:

```bash
cd ~/tls
scp ca.crt kali@10.10.10.100:~/tls/
```

Now `~/tls/ca.crt` exists on `cop-client`.

#### 3.5.2 Add CA to system trust store (cop-client)

On **cop-client**:

```bash
sudo mkdir -p /usr/local/share/ca-certificates/sirs
sudo cp ~/tls/ca.crt /usr/local/share/ca-certificates/sirs/cop-ca.crt
sudo update-ca-certificates
```

`curl` and other system TLS clients will now trust `https://10.10.10.10` automatically.

#### 3.5.3 Import CA into browser (example: Firefox)

In Firefox on **cop-client**:
- Settings → Privacy & Security → **Certificates** → **View Certificates…**
- Tab **Authorities** → **Import…**
- Select `~/tls/ca.crt`
- Check “Trust this CA to identify websites” → OK.

### 3.6 Test from cop-client

From **cop-client**:

```bash
curl https://10.10.10.10/
curl https://10.10.10.10/docs
```

In a browser on `cop-client`, open:
- `https://10.10.10.10/`   (API root)
- `https://10.10.10.10/docs` (Swagger)

If you skip the CA import, use `curl -k https://10.10.10.10/...` and accept the browser warning.

---

## 4) Summary of Security Properties

- **Network isolation**
  - Client only reaches `cop-app` on API port (HTTP/HTTPS).
  - Only `cop-app` can reach `cop-db` on `5432`.
  - Client cannot reach DB directly.

- **TLS on back-net**
  - `cop-app` ↔ `cop-db` use PostgreSQL over TLS with a CA-signed server cert.
  - App connects with `sslmode=require` and can verify DB’s certificate using `ca.crt`.

- **TLS on front-net**
  - `cop-client` ↔ `cop-app` use HTTPS terminated by nginx with a CA-signed cert.
  - Traffic between client and API is encrypted.

This matches a realistic deployment: each server keeps its own private key, public certs and CA are distributed, and firewalls enforce least-privilege network access. 

---


