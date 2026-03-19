# Deployment Guide — ChainIQ Full Stack

This guide covers deploying the complete ChainIQ system: two backend microservices, a Next.js frontend, and a MySQL database.

## Architecture

```
                    Internet
                       │
          ┌────────────┼────────────┐
          │            │            │
     port 3000    port 8000    port 8080
          │            │            │
    ┌─────▼─────┐ ┌────▼──────────┐ ┌──────▼──────────┐
    │  Frontend  │ │ Organisational│ │  Logical Layer   │
    │  (Next.js) │ │    Layer      │ │ (procurement AI) │
    │            │ │  (CRUD API)   │ │                  │
    └─────┬─────┘ └────┬──────────┘ └──────┬──────────┘
          │            │                    │
          │ HTTP       │ SQL                │ HTTP (internal)
          │            │                    │
          │       ┌────▼──────────┐         │
          │       │  MySQL / RDS  │         │
          │       │  (22 tables)  │◄────────┘
          │       └───────────────┘
          │            ▲
          └────────────┘
           via backend API
```

| Service | Port | Compose Stack | Purpose |
|---|---|---|---|
| **Frontend** | 3000 | `docker-compose.yml` (root) | Next.js web UI |
| **MySQL** | 3306 | `docker-compose.yml` (root) | Database (local dev only; use RDS on AWS) |
| **Migrator** | — | `docker-compose.yml` (root) | One-shot data bootstrap |
| **Organisational Layer** | 8000 | `backend/docker-compose.yml` | CRUD + analytics API over MySQL |
| **Logical Layer** | 8080 | `backend/docker-compose.yml` | Procurement decision engine |

The two compose stacks communicate via a shared Docker network called `chainiq-network`.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker Engine 20.10+ | With Docker Compose plugin (`docker compose`) |
| Git | To clone the repository |
| AWS EC2 instance | `t3.small` or larger (for AWS deployment) |
| AWS RDS MySQL | Pre-provisioned (for AWS deployment; local dev uses containerised MySQL) |

---

## 1. Local Development

### 1.1 Clone and configure

```bash
git clone https://github.com/your-org/chainIQ-START-Hack.git
cd chainIQ-START-Hack

# Root env (frontend + MySQL)
cp .env.example .env

# Backend env files
cp backend/organisational_layer/.env.example backend/organisational_layer/.env
cp backend/logical_layer/.env.example backend/logical_layer/.env
```

Defaults work out of the box for local development. No edits needed.

### 1.2 Create the shared Docker network

This is required once. Both compose stacks join this network so services can discover each other by name.

```bash
docker network create chainiq-network
```

### 1.3 Start the backend stack

```bash
cd backend
docker compose up --build -d
```

This starts:
- **organisational-layer** on port 8000
- **logical-layer** on port 8080

Wait for both to be healthy:

```bash
docker compose ps
```

### 1.4 Start the frontend stack

```bash
cd ..   # back to repo root
docker compose up --build
```

This starts:
- **mysql** on port 3306
- **frontend** on port 3000

In development mode (default, uses `docker-compose.override.yml`):
- Frontend runs `next dev` with hot reload
- Source files are mounted into the container

For production-like mode (no hot reload):

```bash
docker compose -f docker-compose.yml up --build
```

### 1.5 Bootstrap the database (first run only)

After MySQL is healthy:

```bash
docker compose --profile tools run --rm migrator
```

This creates all 22 tables and imports the dataset from `data/`.

### 1.6 Verify

```bash
curl http://localhost:8000/health   # Organisational Layer
curl http://localhost:8080/health   # Logical Layer
curl http://localhost:3000          # Frontend
```

Open in browser:
- Frontend: http://localhost:3000
- Organisational Layer Swagger: http://localhost:8000/docs
- Logical Layer Swagger: http://localhost:8080/docs

---

## 2. AWS Deployment (EC2 + RDS)

### 2.1 Provision infrastructure

**EC2 instance:**
- AMI: Amazon Linux 2023 or Ubuntu 22.04
- Instance type: `t3.small` or larger
- Security group inbound rules:

| Type | Protocol | Port | Source |
|---|---|---|---|
| SSH | TCP | 22 | Your IP / bastion |
| HTTP | TCP | 80 | `0.0.0.0/0` (if using nginx) |
| Custom TCP | TCP | 3000 | `0.0.0.0/0` (frontend, if no nginx) |
| Custom TCP | TCP | 8000 | `0.0.0.0/0` (Organisational Layer API) |
| Custom TCP | TCP | 8080 | `0.0.0.0/0` (Logical Layer API / n8n) |

> For production, restrict 8000 and 8080 to the frontend/n8n security group only.

**RDS MySQL:**
- Engine: MySQL 8.0+
- Ensure the EC2 security group is allowed in the RDS security group on port 3306.

### 2.2 Install Docker on EC2

SSH into the instance:

```bash
ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP>
```

**Amazon Linux 2023:**

```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user

# Install Docker Compose plugin
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m) \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Re-login for group change
exit
ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP>
docker --version && docker compose version
```

**Ubuntu 22.04:**

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu
exit
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>
docker --version && docker compose version
```

### 2.3 Copy the project to EC2

**Option A — rsync (recommended for quick iteration):**

```bash
rsync -avz \
  --exclude='.venv' --exclude='node_modules' --exclude='.next' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
  --exclude='.git' --exclude='mysql_data' \
  -e "ssh -i your-key.pem" \
  . \
  ec2-user@<EC2_PUBLIC_IP>:/home/ec2-user/chainiq/
```

**Option B — git clone on the instance:**

```bash
git clone https://github.com/your-org/chainIQ-START-Hack.git /home/ec2-user/chainiq
```

### 2.4 Configure environment variables

```bash
cd /home/ec2-user/chainiq
```

**Backend — Organisational Layer** (`backend/organisational_layer/.env`):

```bash
cp backend/organisational_layer/.env.example backend/organisational_layer/.env
nano backend/organisational_layer/.env
```

```dotenv
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=your-rds-password
DB_NAME=chainiq
```

**Backend — Logical Layer** (`backend/logical_layer/.env`):

```bash
cp backend/logical_layer/.env.example backend/logical_layer/.env
nano backend/logical_layer/.env
```

```dotenv
ORGANISATIONAL_LAYER_URL=http://organisational-layer:8000
```

**Frontend** (`.env`):

```bash
cp .env.aws.example .env
nano .env
```

```dotenv
FRONTEND_PORT=3000
BACKEND_INTERNAL_URL=http://organisational-layer:8000
NEXT_PUBLIC_API_BASE_URL=/api
```

> The URLs use Docker service names — Docker's internal DNS resolves them on the shared network. No external IPs needed when running on the same machine.

> **Security:** Never commit `.env` files to git. They are already in `.gitignore`.

### 2.5 Verify RDS connectivity

```bash
sudo dnf install -y mysql   # Amazon Linux
# or: sudo apt-get install -y mysql-client   # Ubuntu

mysql -h <RDS_ENDPOINT> -P 3306 -u admin -p<PASSWORD> chainiq -e "SELECT 1;"
```

### 2.6 Create the shared network and deploy

```bash
cd /home/ec2-user/chainiq

# Create the shared Docker network
docker network create chainiq-network

# Start backend services
cd backend
docker compose up -d --build

# Wait for backend to be healthy
docker compose ps

# Start frontend (no MySQL needed — using RDS)
cd ..
docker compose -f docker-compose.yml up -d --build
```

> On AWS the root compose doesn't need the local MySQL service. If you only need the frontend, the MySQL container will start but remain unused since backend connects directly to RDS. To avoid starting MySQL, you can scale it to zero: `docker compose -f docker-compose.yml up -d --build --scale mysql=0`

### 2.7 Bootstrap the database (first run only)

The migrator connects to whatever MySQL is available. For RDS, override the env:

```bash
DB_HOST=your-rds-endpoint.rds.amazonaws.com \
DB_USER=admin \
DB_PASSWORD=your-rds-password \
DB_NAME=chainiq \
docker compose -f docker-compose.yml --profile tools run --rm migrator
```

### 2.8 Verify the deployment

```bash
curl http://localhost:8000/health   # Organisational Layer
curl http://localhost:8080/health   # Logical Layer
curl http://localhost:3000          # Frontend

# Test the processing endpoint
curl -X POST http://localhost:8080/api/process-request \
  -H "Content-Type: application/json" \
  -d '{"request_id": "REQ-000004"}'
```

From your browser:
- `http://<EC2_PUBLIC_IP>:3000` — Frontend
- `http://<EC2_PUBLIC_IP>:8000/docs` — Organisational Layer Swagger
- `http://<EC2_PUBLIC_IP>:8080/docs` — Logical Layer Swagger

---

## 3. (Optional) Nginx Reverse Proxy

To serve everything on port 80 behind a single domain, use the provided nginx config.

A reference config is included at `deploy/nginx/aws.conf`. It routes:
- `/api/*` and `/health` to the organisational layer (port 8000)
- Everything else to the frontend (port 3000)

**Install and configure nginx on EC2:**

```bash
sudo dnf install -y nginx   # Amazon Linux
# or: sudo apt-get install -y nginx   # Ubuntu

sudo cp deploy/nginx/aws.conf /etc/nginx/conf.d/chainiq.conf
```

Edit `/etc/nginx/conf.d/chainiq.conf` to point upstreams to `127.0.0.1` instead of Docker service names (since nginx runs on the host, not in Docker):

```nginx
upstream frontend_upstream {
    server 127.0.0.1:3000;
}

upstream backend_upstream {
    server 127.0.0.1:8000;
}
```

```bash
sudo nginx -t && sudo systemctl enable nginx && sudo systemctl start nginx
```

Add inbound rule for TCP 80 to the EC2 security group.

---

## 4. Multi-Machine Deployment

If backend and frontend run on **separate EC2 instances**, they cannot share a Docker network. Instead, configure services to use IP addresses:

**On the frontend machine** (`.env`):

```dotenv
BACKEND_INTERNAL_URL=http://<BACKEND_EC2_PRIVATE_IP>:8000
```

**On the backend machine** (`backend/organisational_layer/.env`):

```dotenv
DB_HOST=your-rds-endpoint.rds.amazonaws.com
```

No `docker network create` is needed — each machine uses its own default network.

---

## 5. Environment Variables Reference

### Root compose (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `root` | MySQL root password |
| `MYSQL_DATABASE` | `chainiq` | Database name |
| `MYSQL_USER` | `chainiq` | MySQL application user |
| `MYSQL_PASSWORD` | `chainiq` | MySQL application password |
| `MYSQL_PORT` | `3306` | Published MySQL port |
| `FRONTEND_PORT` | `3000` | Published frontend port |
| `BACKEND_INTERNAL_URL` | `http://organisational-layer:8000` | Backend URL for Next.js SSR |
| `NEXT_PUBLIC_API_BASE_URL` | `/api` | Client-side API base path |

### Backend — Organisational Layer (`backend/organisational_layer/.env`)

| Variable | Example | Purpose |
|---|---|---|
| `DB_HOST` | `mysql` / RDS endpoint | MySQL hostname |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `chainiq` | MySQL user |
| `DB_PASSWORD` | `chainiq` | MySQL password |
| `DB_NAME` | `chainiq` | Database name |

### Backend — Logical Layer (`backend/logical_layer/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ORGANISATIONAL_LAYER_URL` | `http://organisational-layer:8000` | Internal URL to organisational layer |

---

## 6. Common Operations

### View logs

```bash
# Backend logs
cd backend
docker compose logs -f
docker compose logs -f organisational-layer
docker compose logs -f logical-layer

# Frontend logs
cd ..   # repo root
docker compose logs -f
docker compose logs -f frontend
```

### Restart after code changes

```bash
# Re-copy files if using rsync, then:
cd backend && docker compose up -d --build
cd .. && docker compose -f docker-compose.yml up -d --build
```

### Stop all services

```bash
# Stop frontend + MySQL
docker compose down

# Stop backend
cd backend && docker compose down
```

### Full reset (wipe database)

```bash
docker compose down -v   # removes mysql_data volume
docker compose --profile tools run --rm migrator   # re-bootstrap
```

---

## 7. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `docker network create` fails | Network already exists | Safe to ignore; or run `docker network ls` to verify |
| Container exits immediately | Missing or wrong `.env` values | `docker compose logs <service>`; check credentials |
| `Connection refused` on 8000 | Container not running or SG blocks port | `docker compose ps`; check security group inbound rules |
| `Connection refused` on 8080 | Logical layer waiting for org layer | Check if org layer is healthy: `cd backend && docker compose ps` |
| Frontend shows API errors | Backend not reachable from frontend container | Verify `BACKEND_INTERNAL_URL`; verify both stacks are on `chainiq-network` |
| Logical layer `502` errors | Org layer unreachable | Check `ORGANISATIONAL_LAYER_URL` in logical layer `.env` |
| `Access denied` to RDS | Wrong DB credentials | Verify with `mysql` CLI from EC2 |
| `Unknown database` error | Wrong `DB_NAME` | Check `DB_NAME` in org layer `.env` |
| RDS timeout | EC2 SG not allowed in RDS SG | Add EC2 SG as inbound source on RDS SG, port 3306 |
| Slow cold start | Docker images not cached | Subsequent builds are fast after first run |
| Network not found | `chainiq-network` not created | Run `docker network create chainiq-network` |
