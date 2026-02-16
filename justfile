# justfile - Modern task runner (alternative to Makefile)
# Install: curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/bin
# Usage: just <command>
# List all commands: just --list

# Default recipe (runs when you type 'just')
default:
    @just --list

# Docker commands
alias u := up
alias d := down

# Start all services
up:
    docker-compose up -d
    @echo "Services started! Dashboard: http://localhost:8501"

# Stop all services
down:
    docker-compose down

# Restart all services
restart:
    docker-compose restart

# View logs
logs:
    docker-compose logs -f

# View logs for specific service
logs-service SERVICE:
    docker-compose logs -f {{SERVICE}}

# Build all services
build:
    docker-compose build

# Rebuild and start
rebuild: build up

# Clean everything (including volumes)
clean:
    docker-compose down -v
    @echo "All containers and volumes removed"

# Start with profiles
up-kafka:
    docker-compose --profile with-kafka up -d

up-grafana:
    docker-compose --profile with-grafana up -d

up-pgadmin:
    docker-compose --profile with-pgadmin up -d

up-all:
    docker-compose --profile with-kafka --profile with-grafana --profile with-pgadmin up -d

# Database commands
db-shell:
    docker-compose exec timescaledb psql -U orderbook_user -d orderbook

redis-shell:
    docker-compose exec redis redis-cli

# Check status
status:
    docker-compose ps

stats:
    docker stats

# Database utilities
db-size:
    docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT pg_size_pretty(pg_database_size('orderbook'));"

table-sizes:
    docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# View recent data
recent-metrics:
    docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT * FROM orderbook_metrics ORDER BY time DESC LIMIT 10;"

recent-alerts:
    docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT * FROM orderbook_alerts ORDER BY time DESC LIMIT 10;"

dashboard-summary:
    docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT * FROM dashboard_summary;"

# Redis utilities
redis-keys:
    docker-compose exec redis redis-cli KEYS "*"

redis-btc:
    docker-compose exec redis redis-cli GET "orderbook:BTCUSDT:latest"

# Backup and restore
backup:
    #!/usr/bin/env bash
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    docker-compose exec timescaledb pg_dump -U orderbook_user orderbook > backup_${TIMESTAMP}.sql
    echo "Database backed up to backup_${TIMESTAMP}.sql"

restore BACKUP:
    docker-compose exec -T timescaledb psql -U orderbook_user orderbook < {{BACKUP}}

# Local development with uv
uv-install:
    #!/usr/bin/env bash
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "uv installed! Restart your shell or run: source ~/.cargo/env"

uv-sync:
    #!/usr/bin/env bash
    echo "Syncing dependencies with uv (this is fast!)..."
    uv venv
    uv pip install -e ".[dev]"
    echo "Dependencies installed! Activate venv: source .venv/bin/activate"

# Code quality
format:
    black src/ dashboard/ tests/
    ruff check --fix src/ dashboard/ tests/

lint:
    ruff check src/ dashboard/ tests/
    mypy src/

# Testing
test:
    pytest tests/ -v

test-cov:
    pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing

# Development setup
dev-setup:
    #!/usr/bin/env bash
    cp .env.example .env
    mkdir -p src/ingestion src/common dashboard logs
    echo "Development environment setup complete"
    echo "Edit .env with your settings, then run 'just up'"

# Pre-commit hooks
pre-commit-install:
    pre-commit install

pre-commit-run:
    pre-commit run --all-files
