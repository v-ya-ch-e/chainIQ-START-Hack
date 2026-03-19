# Deployment Guide — ChainIQ Backend Services (EC2 + Docker Compose)

This guide covers deploying **both** backend microservices to an AWS EC2 instance using Docker Compose:

| Service | Port | Purpose |
|---|---|---|
| **Organisational Layer** | 8000 | CRUD + analytics API over the MySQL database |
| **Logical Layer** | 8080 | Procurement decision engine called by n8n |

Both services are orchestrated by `backend/docker-compose.yml`. The logical layer depends on the organisational layer and will wait for it to be healthy before starting.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| AWS EC2 instance | `t3.small` or larger recommended; Amazon Linux 2023 or Ubuntu 22.04 |
| Security Group | Inbound: TCP 8000, TCP 8080, TCP 22 (SSH). Outbound: all |
| AWS RDS MySQL | Already populated via `database_init/migrate.py` |
| EC2 IAM Role | No special IAM permissions required (RDS accessed via credentials) |
| Docker + Docker Compose | Installed on the EC2 instance (see below) |

---

## 1. Provision the EC2 Instance

Launch an EC2 instance from the AWS console or CLI:

```bash
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.small \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxxxxx \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=chainiq-backend}]'
```

### Security Group Rules

| Type | Protocol | Port | Source |
|---|---|---|---|
| SSH | TCP | 22 | Your IP / bastion |
| Custom TCP | TCP | 8000 | `0.0.0.0/0` (Organisational Layer API) |
| Custom TCP | TCP | 8080 | `0.0.0.0/0` (Logical Layer API / n8n) |
| All outbound | All | All | `0.0.0.0/0` |

> For production, restrict ports 8000 and 8080 to the frontend/n8n/load balancer security group only.

---

## 2. Install Docker on the EC2 Instance

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
# Re-login for group change to take effect
exit
ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP>
docker --version  # verify
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
docker --version  # verify
```

---

## 3. Copy the Backend to EC2

### Option A — rsync (recommended for quick iteration)

From your local machine, inside the repo root:

```bash
rsync -avz \
  --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
  -e "ssh -i your-key.pem" \
  backend/ \
  ec2-user@<EC2_PUBLIC_IP>:/home/ec2-user/backend/
```

### Option B — git clone on the instance

```bash
# On EC2
git clone https://github.com/your-org/chainIQ-START-Hack.git
cd chainIQ-START-Hack/backend
```

---

## 4. Configure Environment Variables

Each service has its own `.env` file.

### Organisational Layer

```bash
cd /home/ec2-user/backend/organisational_layer
cp .env.example .env
nano .env
```

```dotenv
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=your-rds-password
DB_NAME=chainiq-data
```

### Logical Layer

```bash
cd /home/ec2-user/backend/logical_layer
cp .env.example .env
nano .env
```

```dotenv
ORGANISATIONAL_LAYER_URL=http://organisational-layer:8000
```

> The URL uses the Docker Compose service name `organisational-layer` — Docker's internal DNS resolves this automatically. No external IP needed.

> **Security:** Never commit `.env` files to git. They are already listed in `.gitignore`.

### Verify RDS Connectivity

Before building containers, confirm the EC2 instance can reach RDS:

```bash
sudo dnf install -y mysql  # Amazon Linux
# or
sudo apt-get install -y mysql-client  # Ubuntu

mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_PASSWORD $DB_NAME -e "SHOW TABLES;"
```

---

## 5. Build and Run with Docker Compose

```bash
cd /home/ec2-user/backend

docker compose up -d --build
```

This builds and starts both services. The logical layer waits for the organisational layer's health check to pass before starting.

To build/start a single service:

```bash
docker compose up -d --build organisational-layer
docker compose up -d --build logical-layer
```

---

## 6. Verify the Deployment

```bash
# Check both containers are running
docker compose ps

# Check logs
docker compose logs -f

# Health checks
curl http://localhost:8000/health   # Organisational Layer
curl http://localhost:8080/health   # Logical Layer

# Swagger UI (from your browser)
# http://<EC2_PUBLIC_IP>:8000/docs   — Organisational Layer
# http://<EC2_PUBLIC_IP>:8080/docs   — Logical Layer
```

Expected health response from both:

```json
{"status": "ok"}
```

### Test the processing endpoint

```bash
curl -X POST http://localhost:8080/api/process-request \
  -H "Content-Type: application/json" \
  -d '{"request_id": "REQ-000004"}'
```

---

## 7. Common Operations

### View logs

```bash
docker compose logs -f                        # all services
docker compose logs -f organisational-layer   # single service
docker compose logs -f logical-layer
```

### Restart after a code change

```bash
# Re-copy files (if using rsync)
rsync -avz \
  --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
  -e "ssh -i your-key.pem" \
  backend/ \
  ec2-user@<EC2_PUBLIC_IP>:/home/ec2-user/backend/

# On EC2
cd /home/ec2-user/backend
docker compose up -d --build
```

### Stop all services

```bash
docker compose down
```

### Update environment variables

```bash
nano organisational_layer/.env   # or logical_layer/.env
docker compose up -d --build     # restart to pick up new env
```

---

## 8. (Optional) Run Behind nginx Reverse Proxy

If you want to serve APIs on port 80/443 or add TLS:

```bash
sudo dnf install -y nginx   # Amazon Linux
# or
sudo apt-get install -y nginx  # Ubuntu
```

Create `/etc/nginx/conf.d/chainiq.conf`:

```nginx
server {
    listen 80;
    server_name <EC2_PUBLIC_IP_OR_DOMAIN>;

    location /api/process-request {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
sudo nginx -t && sudo systemctl reload nginx
```

Add inbound rule for TCP 80 (and 443 if using TLS) to the EC2 security group.

---

## 9. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Container exits immediately | Missing or wrong `.env` values | `docker compose logs <service>`; check credentials |
| `Connection refused` on port 8000 | Container not running or SG blocks port | `docker compose ps`; check SG inbound rules |
| `Connection refused` on port 8080 | Logical layer not running or SG blocks port | Check if org layer is healthy first: `docker compose ps` |
| Logical layer `502` errors | Org layer not reachable from logical layer | Check `ORGANISATIONAL_LAYER_URL` in logical layer `.env` |
| `Access denied` to RDS | Wrong DB_USER / DB_PASSWORD | Verify with `mysql` CLI from EC2 |
| `Unknown database` error | Wrong `DB_NAME` | Check `DB_NAME` in org layer `.env` |
| RDS timeout | EC2 SG not allowed in RDS SG | Add EC2 SG as inbound source on RDS SG, port 3306 |
| Slow cold start | Docker images not cached | Subsequent builds are fast after first run |

---

## Architecture Reference

```
Internet / n8n
   │
   ├── POST /api/process-request ──► port 8080
   │                                     │
   │                          ┌──────────▼───────────┐
   │                          │   Logical Layer       │
   │                          │   (procurement logic) │
   │                          └──────────┬───────────┘
   │                                     │ HTTP (Docker internal network)
   │                          ┌──────────▼───────────┐
   └── GET /api/* ──────────► │  Organisational Layer │
                              │  (CRUD + analytics)   │
                              └──────────┬───────────┘
                                         │ SQL
                              ┌──────────▼───────────┐
                              │  AWS RDS MySQL        │
                              │  chainiq-data         │
                              │  (22 tables)          │
                              └──────────────────────┘
```
