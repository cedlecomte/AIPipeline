.PHONY: help build start stop restart logs clean test

# Detect if podman-compose or podman compose is available
COMPOSE := $(shell command -v podman-compose 2> /dev/null)
ifndef COMPOSE
	COMPOSE := podman compose
endif

help:
	@echo "Ansible Agent Pipeline - Make Commands (Podman)"
	@echo ""
	@echo "  make build       - Build all Podman images"
	@echo "  make start       - Start all services"
	@echo "  make stop        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - Tail logs from all services"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make test        - Run tests"
	@echo "  make shell       - Shell into orchestrator container"
	@echo ""

build:
	@echo "Building base image with Podman..."
	podman build -t ansible-agent-base:latest -f Dockerfile.base .
	@echo "Building all agent images..."
	$(COMPOSE) build

start:
	@echo "Starting all services with Podman..."
	$(COMPOSE) up -d
	@echo "Waiting for services to be healthy..."
	sleep 5
	$(COMPOSE) ps
	@echo ""
	@echo "Dashboard available at: http://localhost:${DASHBOARD_PORT:-8080}"

stop:
	@echo "Stopping all services..."
	$(COMPOSE) down

restart: stop start

logs:
	$(COMPOSE) logs -f

logs-agent:
	@read -p "Enter agent name (jira, architect, developer, tester, reviewer, release, certification, orchestrator, dashboard): " agent; \
	$(COMPOSE) logs -f $${agent}-agent || $(COMPOSE) logs -f $${agent}

clean:
	@echo "Removing all containers, networks, and volumes..."
	$(COMPOSE) down -v
	podman rmi ansible-agent-base:latest || true

test:
	pytest tests/ -v

shell:
	$(COMPOSE) exec orchestrator /bin/bash

status:
	@echo "Service Status:"
	@$(COMPOSE) ps
	@echo ""
	@echo "Redis Status:"
	@$(COMPOSE) exec redis redis-cli ping || echo "Redis not responding"

trigger-pipeline:
	@read -p "Enter Jira Issue Key: " issue; \
	curl -X POST http://localhost:${DASHBOARD_PORT:-8080}/api/pipeline/start \
		-H "Content-Type: application/json" \
		-d "{\"jira_issue_key\": \"$$issue\", \"jira_data\": {\"summary\": \"Test\", \"description\": \"Test issue\"}}"
