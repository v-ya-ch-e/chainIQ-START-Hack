# Deployment Guide — Organisational Layer (FastAPI on EC2 + Docker)

This guide covers deploying the `organisational_layer` FastAPI service to an AWS EC2 instance using Docker.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| AWS EC2 instance | `t3.small` or larger recommended; Amazon Linux 2023 or Ubuntu 22.04 |
| Security Group | Inbound: TCP 8000 (API), TCP 22 (SSH). Outbound: all |
| AWS RDS MySQL | Already populated via `database_init/migrate.py` |
| EC2 IAM Role | No special IAM permissions required (RDS accessed via credentials) |
| Docker installed | Installed on the EC2 instance (see below) |

---

## 1. Provision the EC2 Instance

Launch an EC2 instance from the AWS console or CLI:

```bash
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \   # Amazon Linux 2023 (us-east-1); adjust per region
  --instance-type t3.small \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxxxxx \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=chainiq-organisational-layer}]'
```

### Security Group Rules

| Type | Protocol | Port | Source |
|---|---|---|---|
| SSH | TCP | 22 | Your IP / bastion |
| Custom TCP | TCP | 8000 | `0.0.0.0/0` (or frontend SG only) |
| All outbound | All | All | `0.0.0.0/0` |

> For production, restrict port 8000 to the frontend/load balancer security group only.

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

## 3. Copy the Service to EC2

### Option A — rsync (recommended for quick iteration)

From your local machine, inside the repo root:

```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  -e "ssh -i your-key.pem" \
  backend/organisational_layer/ \
  ec2-user@<EC2_PUBLIC_IP>:/home/ec2-user/organisational_layer/
```

### Option B — git clone on the instance

```bash
# On EC2
git clone https://github.com/your-org/chainIQ-START-Hack.git
cd chainIQ-START-Hack/backend/organisational_layer
```

---

## 4. Configure Environment Variables

The service reads database credentials from a `.env` file.

```bash
# On EC2, inside the organisational_layer directory
cp .env.example .env
nano .env
```

Fill in all values:

```dotenv
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=your-rds-password
DB_NAME=chainiq-data
```

> **Security:** Never commit `.env` to git. The file is already listed in `.gitignore`.
>
> For production, consider using AWS Secrets Manager or EC2 Instance Connect Endpoint and injecting credentials as environment variables at runtime instead of a file.

### Verify RDS Connectivity

Before building the container, confirm the EC2 instance can reach RDS:

```bash
# Install mysql client if needed
sudo dnf install -y mysql  # Amazon Linux
# or
sudo apt-get install -y mysql-client  # Ubuntu

mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_PASSWORD $DB_NAME -e "SHOW TABLES;"
```

---

## 5. Build and Run with Docker

### Using the Dockerfile directly

```bash
cd /home/ec2-user/organisational_layer

# Build the image
docker build -t chainiq-organisational-layer:latest .

# Run the container
docker run -d \
  --name organisational-layer \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  chainiq-organisational-layer:latest
```

### Using docker-compose

```bash
cd /home/ec2-user/organisational_layer

docker compose up -d --build
```

> `docker-compose.yml` is configured to use `.env` from the same directory, map port `8000:8000`, and run a health check on `/health`.

---

## 6. Verify the Deployment

```bash
# Check container is running
docker ps

# Check logs
docker logs organisational-layer --tail 50 -f

# Health check
curl http://localhost:8000/health

# Swagger UI (from your browser)
# http://<EC2_PUBLIC_IP>:8000/docs
```

Expected health response:

```json
{"status": "ok"}
```

---

## 7. Common Operations

### View logs

```bash
docker logs organisational-layer -f
```

### Restart after a code change

```bash
# Re-copy files (if using rsync)
rsync -avz --exclude='.venv' --exclude='__pycache__' \
  -e "ssh -i your-key.pem" \
  backend/organisational_layer/ \
  ec2-user@<EC2_PUBLIC_IP>:/home/ec2-user/organisational_layer/

# On EC2
cd /home/ec2-user/organisational_layer
docker compose up -d --build
```

### Stop the service

```bash
docker compose down
# or
docker stop organisational-layer && docker rm organisational-layer
```

### Update environment variables

```bash
nano .env          # edit values
docker compose up -d --build   # restart to pick up new env
```

---

## 8. (Optional) Run Behind nginx Reverse Proxy

If you want to serve the API on port 80/443 or add TLS:

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
| Container exits immediately | Missing or wrong `.env` values | `docker logs organisational-layer`; check DB credentials |
| `Connection refused` on port 8000 | Container not running or security group blocks port | `docker ps`; check SG inbound rules |
| `Access denied` to RDS | Wrong DB_USER / DB_PASSWORD | Verify with `mysql` CLI from EC2 |
| `Unknown database` error | Wrong `DB_NAME` | Check `DB_NAME` in `.env` matches the RDS database name |
| RDS timeout | EC2 SG not allowed in RDS SG | Add EC2 security group as inbound source on RDS SG, port 3306 |
| Slow cold start | Docker image not cached | Rebuild caches after first run; subsequent starts are fast |

---

## Architecture Reference

```
Internet
   │
   ▼
EC2 Instance (port 8000)
   │
   ├── Docker Container: chainiq-organisational-layer
   │       uvicorn app.main:app --host 0.0.0.0 --port 8000
   │
   └──► AWS RDS MySQL (port 3306, private subnet)
              DB: chainiq-data  (22 tables, populated by migrate.py)
```
