## 0) Prepare the base VM (VM1)
- Shut it down cleanly.
- Remove anything you don’t want cloned (logs/temp), optional.

## 1) Clone into three machines (initial setup)
- Make linked clones to save space:
  - Clone 1 → cop-client
  - Clone 2 → cop-app
  - Clone 3 → cop-db
- In the clone dialog: "Linked Clone", "Generate new MAC addresses".
- Note: Additional VMs (cop-ca, cop-group) will be cloned later in their respective sections.

## 2) Create/attach networks
- We'll use two internal/host-only nets:
  - front-net (client ↔ app ↔ ca ↔ group)
  - back-net (app ↔ db)

- Attach adapters:
  - cop-client: Adapter1 = Internal Network front-net;
  - cop-app: Adapter1 = Internal front-net; Adapter2 = Internal back-net; 
  - cop-db: Adapter1 = Internal back-net;
  - cop-ca: Adapter1 = Internal front-net;
  - cop-group: Adapter1 = Internal front-net;

- Promiscuous mode: Allow VMs (helpful for captures).

## 3) Boot each VM and set static IPs (temporary)
- Interface names may differ (`ip a` to confirm). Use these IPs:
  - cop-client (front):
    ```
    sudo ip addr add 10.10.10.100/24 dev eth0
    sudo ip link set eth0 up
    ```
  - cop-app (front + back):
    ```
    sudo ip addr add 10.10.10.10/24 dev eth0
    sudo ip addr add 10.10.20.10/24 dev eth1
    sudo ip link set eth0 up
    sudo ip link set eth1 up
    ```
  - cop-db (back):
    ```
    sudo ip addr add 10.10.20.20/24 dev eth0
    sudo ip link set eth0 up
    ```
  - cop-ca (front):
    ```
    sudo ip addr add 10.10.10.30/24 dev eth0
    sudo ip link set eth0 up
    ```
  - cop-group (front):
    ```
    sudo ip addr add 10.10.10.20/24 dev eth0
    sudo ip link set eth0 up
    ```

## 4) Quick connectivity checks
- From cop-client: `ping 10.10.10.10`
- From cop-app: `ping 10.10.20.20`
- From cop-client to DB should fail (no route) — expected.


## 5) Persist the network config
- Edit `/etc/network/interfaces` on each VM:
  - cop-client:
    ```
    source /etc/network/interfaces.d/*
    auto lo eth0
    iface lo inet loopback
    iface eth0 inet static
        address 10.10.10.100
        netmask 255.255.255.0
    ```
  - cop-app:
    ```
    source /etc/network/interfaces.d/*
    auto lo eth0 eth1
    iface lo inet loopback
    iface eth0 inet static
        address 10.10.10.10
        netmask 255.255.255.0
    iface eth1 inet static
        address 10.10.20.10
        netmask 255.255.255.0
    ```
  - cop-db:
    ```
    source /etc/network/interfaces.d/*
    auto lo eth0
    iface lo inet loopback
    iface eth0 inet static
        address 10.10.20.20
        netmask 255.255.255.0
    ```
  - cop-ca:
    ```
    source /etc/network/interfaces.d/*
    auto lo eth0
    iface lo inet loopback
    iface eth0 inet static
        address 10.10.10.30
        netmask 255.255.255.0
    ```
  - cop-group:
    ```
    source /etc/network/interfaces.d/*
    auto lo eth0
    iface lo inet loopback
    iface eth0 inet static
        address 10.10.10.20
        netmask 255.255.255.0
    ```
- After editing:
  ```
  sudo systemctl restart networking || sudo systemctl restart NetworkManager
  ```

## 6) Optional: NAT adapter for Internet/apt
- Add a NAT adapter in the VM settings (keep the front/back adapters unchanged).
- Bring it up and request DHCP (replace `eth2` with the NAT NIC name you see in `ip -o addr show`, e.g., `eth1` if it has a `10.x.x.x` address):
  ```
  sudo ip link set eth2 up
  sudo dhclient eth2
  ```
- To persist with ifupdown, add to `/etc/network/interfaces`:
  ```
  auto eth2
  iface eth2 inet dhcp
  ```
- Do **not** add a gateway to the front/back NICs; the NAT NIC will install the default route for Internet/DNS.


## 7) Name the hosts
- Set `/etc/hostname` and `/etc/hosts` appropriately on each VM (cop-client, cop-app, cop-db, cop-ca, cop-group).
- Example for `/etc/hosts` on cop-app:
  ```
  127.0.0.1   localhost
  127.0.1.1   cop-app   # change to cop-client, cop-db, cop-ca, or cop-group on the other VMs
  10.10.10.10 cop-app
  10.10.10.100 cop-client
  10.10.10.20 cop-group
  10.10.10.30 cop-ca
  10.10.20.10 cop-app-back
  10.10.20.20 cop-db
  ```
- cop-client doesn't have IPs from cop_db (and has cop-app, cop-group, cop-ca)
- cop-db doesn't have IPs from cop-client (and has cop-app-back)
- cop-ca and cop-group are on front-net only

## 8) Database (cop-db)
- Install Postgres:
  ```
  sudo apt update
  sudo apt install postgresql
  ```
- Create DB/user:
  ```
  sudo systemctl start postgresql
  sudo -u postgres psql
  CREATE USER appuser WITH PASSWORD 'strongpass';
  CREATE DATABASE appdb OWNER appuser;
  GRANT ALL PRIVILEGES ON DATABASE appdb TO appuser;
  \q
  ```
- Allow app VM (cop-app at 10.10.20.10) to connect (md5 for now):
  - Edit `/etc/postgresql/17/main/pg_hba.conf` and add:
    ```
    host    appdb   appuser   10.10.20.10/32   md5
    ```
- Bind Postgres to back-net only:
  - In `/etc/postgresql/17/main/postgresql.conf` set:
    ```
    listen_addresses = '10.10.20.20, 127.0.0.1'
    ```
- Restart Postgres:
  ```
  sudo systemctl restart postgresql
  ```
- Local checks on cop-db:
  ```
  sudo -u postgres psql -d appdb -c '\dt'
  sudo -u postgres psql -d appdb -c '\conninfo'
  ```

## 9) App VM (cop-app) basic tools + DB connectivity test
- Install Python and psql client:
  ```
  sudo apt update
  sudo apt install python3 python3-venv postgresql-client
  ```
- Test DB connectivity from cop-app to cop-db:
  ```
  psql "host=10.10.20.20 dbname=appdb user=appuser password=strongpass" -c '\conninfo'
  ```
- (Later) run your API here and point it to the same connection string; set `sslmode=require` once TLS is enabled on Postgres.


## 10) Certificate Authority VM (cop-ca)
- Clone a new VM from the base image:
  - Name it `cop-ca`.
  - Linked clone, generate new MAC addresses.
- Attach adapters:
  - Adapter1 = Internal Network `front-net` (same name as cop-client/cop-app front-net).
  - (Optional) Adapter2 = NAT for apt updates.

- Set static IP on front-net (example using `eth0`):
  - Temporary:
    ```
    sudo ip addr add 10.10.10.30/24 dev eth0
    sudo ip link set eth0 up
    ```
  - Persist in `/etc/network/interfaces`:
    ```
    source /etc/network/interfaces.d/*

    auto lo eth0
    iface lo inet loopback

    iface eth0 inet static
        address 10.10.10.30
        netmask 255.255.255.0
    ```
    Then:
    ```
    sudo systemctl restart networking || sudo systemctl restart NetworkManager
    ```
- Quick connectivity:
  - From cop-client/cop-app:
    ```
    ping 10.10.10.30
    ```

- Basic firewall for cop-ca (see FIREWALL_TLS_SETUP.md for full details):
  - Default deny incoming, allow outgoing.
  - Allow only cop-app to reach the certificate-authority port:
    ```
    sudo ufw reset
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow from 10.10.10.10 to any port 8002 proto tcp
    sudo ufw enable
    sudo ufw status verbose
    ```

- Run the certificate-authority on cop-ca:
  ```
  cd /path/to/T50-ChainOfProduct
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  uvicorn certificate_authority.main:app --host 0.0.0.0 --port 8002
  ```
  Access Swagger UI from cop-client/cop-app at:
  - `http://10.10.10.30:8002/docs`
  - Health check: `http://10.10.10.30:8002/`
  - Root CA certificate: `http://10.10.10.30:8002/root-ca`

## 11) Group Server VM (cop-group)
- Clone a new VM from the base image:
  - Name it `cop-group`.
  - Linked clone, generate new MAC addresses.
- Attach adapters:
  - Adapter1 = Internal Network `front-net` (same name as cop-client/cop-app front-net).
  - (Optional) Adapter2 = NAT for apt updates.

- Set static IP on front-net (example using `eth0`):
  - Temporary:
    ```
    sudo ip addr add 10.10.10.20/24 dev eth0
    sudo ip link set eth0 up
    ```
  - Persist in `/etc/network/interfaces`:
    ```
    source /etc/network/interfaces.d/*

    auto lo eth0
    iface lo inet loopback

    iface eth0 inet static
        address 10.10.10.20
        netmask 255.255.255.0
    ```
    Then:
    ```
    sudo systemctl restart networking || sudo systemctl restart NetworkManager
    ```
- Quick connectivity:
  - From cop-client/cop-app:
    ```
    ping 10.10.10.20
    ```

- Basic firewall for cop-group (see FIREWALL_TLS_SETUP.md for full details):
  - Default deny incoming, allow outgoing.
  - Allow only cop-app to reach the group-server port:
    ```
    sudo ufw reset
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow from 10.10.10.10 to any port 8001 proto tcp
    sudo ufw enable
    sudo ufw status verbose
    ```

- Run the group-server on cop-group:
  ```
  cd /path/to/T50-ChainOfProduct/group-server
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  uvicorn main:app --host 0.0.0.0 --port 8001
  ```
  Access Swagger UI from cop-client/cop-app at:
  - `http://10.10.10.20:8001/docs`

