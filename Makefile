SHELL := /bin/bash

NETWORK := chainiq-network
ENV_LOCAL := .env.local
ENV_DEPLOYED := .env.deployed

.PHONY: help init-network env-local env-deployed backend-env local-up local-dev deployed-up local-down deployed-down local-logs backend-logs status reset-local-db

help:
	@echo "ChainIQ run commands"
	@echo ""
	@echo "Setup"
	@echo "  make init-network      Create shared Docker network if missing"
	@echo "  make env-local         Create .env.local from template if missing"
	@echo "  make env-deployed      Create .env.deployed from template if missing"
	@echo "  make backend-env       Create backend .env files from templates if missing"
	@echo ""
	@echo "Run modes"
	@echo "  make local-up          Full local stack: DB + migrator + backend + frontend"
	@echo "  make local-dev         Full local stack with frontend hot reload"
	@echo "  make deployed-up       Frontend only, pointed to deployed backend URLs"
	@echo ""
	@echo "Operations"
	@echo "  make local-down        Stop local frontend + backend stacks"
	@echo "  make deployed-down     Stop deployed-mode frontend stack"
	@echo "  make local-logs        Tail frontend logs for local mode"
	@echo "  make backend-logs      Tail backend services logs"
	@echo "  make status            Show running containers"
	@echo "  make reset-local-db    Remove local DB volume data"

init-network:
	@docker network inspect "$(NETWORK)" >/dev/null 2>&1 || docker network create "$(NETWORK)"

env-local:
	@test -f "$(ENV_LOCAL)" || cp .env.local.example "$(ENV_LOCAL)"
	@echo "Using $(ENV_LOCAL)"

env-deployed:
	@test -f "$(ENV_DEPLOYED)" || cp .env.deployed.example "$(ENV_DEPLOYED)"
	@echo "Using $(ENV_DEPLOYED)"

backend-env:
	@test -f backend/organisational_layer/.env || cp backend/organisational_layer/.env.example backend/organisational_layer/.env
	@test -f backend/logical_layer/.env || cp backend/logical_layer/.env.example backend/logical_layer/.env
	@echo "Backend env files ready"

local-up: init-network env-local backend-env
	@docker compose --env-file "$(ENV_LOCAL)" --profile localdb up -d mysql
	@docker compose --env-file "$(ENV_LOCAL)" --profile tools run --rm migrator
	@docker compose -f backend/docker-compose.yml up --build -d
	@docker compose --env-file "$(ENV_LOCAL)" up --build -d frontend
	@echo "Local stack is up: frontend(3000), organisational(8000), logical(8080), mysql(3306)"

local-dev: init-network env-local backend-env
	@docker compose --env-file "$(ENV_LOCAL)" --profile localdb up -d mysql
	@docker compose --env-file "$(ENV_LOCAL)" --profile tools run --rm migrator
	@docker compose -f backend/docker-compose.yml up --build -d
	@docker compose --env-file "$(ENV_LOCAL)" -f docker-compose.yml -f docker-compose.dev.yml up --build -d frontend
	@echo "Local dev stack is up with hot reload frontend"

deployed-up: init-network env-deployed
	@docker compose --env-file "$(ENV_DEPLOYED)" up --build -d frontend
	@echo "Frontend is up in deployed-backend mode"

local-down:
	@docker compose --env-file "$(ENV_LOCAL)" down
	@docker compose -f backend/docker-compose.yml down
	@echo "Local stacks stopped"

deployed-down:
	@docker compose --env-file "$(ENV_DEPLOYED)" down
	@echo "Deployed-mode frontend stopped"

local-logs:
	@docker compose --env-file "$(ENV_LOCAL)" logs -f frontend

backend-logs:
	@docker compose -f backend/docker-compose.yml logs -f organisational-layer logical-layer

status:
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

reset-local-db:
	@docker compose --env-file "$(ENV_LOCAL)" down -v
	@echo "Local frontend stack + DB volumes removed"
