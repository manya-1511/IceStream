.PHONY: up down build logs restart health clean

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

restart:
	docker compose down
	docker compose up -d

health:
	bash scripts/health-check.sh

clean:
	docker compose down -v --remove-orphans

# ------------------------------------------------------------------
# Windows (no `make`?) — run the equivalent Docker Compose commands:
#   docker compose up -d
#   docker compose down
#   docker compose build
#   docker compose logs -f
#   docker compose down; docker compose up -d
#   bash scripts/health-check.sh   (or run the checks in scripts/health-check.sh manually via PowerShell)
#   docker compose down -v --remove-orphans
# ------------------------------------------------------------------
