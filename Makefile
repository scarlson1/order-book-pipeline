.PHONY: help up down restart logs build clean db-shell redis-shell test uv-install uv-sync flink-ui flink-logs

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "Docker commands:"
	@echo "  make up              - Start core services"
	@echo "  make down            - Stop all services"
	@echo "  make restart         - Restart all services"
	@echo "  make logs            - Follow logs from all services"
	@echo "  make build           - Rebuild all services"
	@echo "  make clean           - Remove all containers and volumes"
	@echo ""
	@echo "Database commands:"
	@echo "  make db-shell        - Connect to PostgreSQL"
	@echo "  make redis-shell     - Connect to Redis"
	@echo "  make db-size         - Check database size"
	@echo "  make table-sizes     - Check table sizes"
	@echo ""
	@echo "Flink commands:"
	@echo "  make flink-ui        - Open Flink Web UI"
	@echo "  make flink-logs      - View Flink logs"
	@echo "  make flink-jobs      - List running Flink jobs"
	@echo "  make flink-metrics   - Run orderbook_metrics job"
	@echo "  make flink-alert   	- Run orderbook_alerts job"
	@echo "  make flink-windows   - Run orderbook_windows job"
	@echo ""
	@echo "Monitoring commands:"
	@echo "  make status          - Check service status"
	@echo "  make stats           - Monitor resource usage"
	@echo "  make recent-metrics  - View recent metrics"
	@echo "  make recent-alerts   - View recent alerts"
	@echo ""
	@echo "Profile commands:"
	@echo "  make up-streaming    - Start with Redpanda + Flink"
	@echo "  make up-grafana      - Start with Grafana"
	@echo "  make up-all          - Start all services"
	@echo ""
	@echo "Local development (uv):"
	@echo "  make uv-install      - Install uv package manager"
	@echo "  make uv-sync         - Sync dependencies with uv"
	@echo "  make test            - Run tests locally"
	@echo "  make format          - Format code with black and ruff"

# Start services
up:
	docker-compose up -d
	@echo "Services starting... Dashboard will be available at http://localhost:8501"

# Start with Redpanda + Flink (core streaming stack)
up-streaming:
	docker-compose up -d
	@echo "Streaming stack starting..."
	@echo "  Redpanda Console: http://localhost:8080"
	@echo "  Flink Web UI:     http://localhost:8081"

# Start with Grafana
up-grafana:
	docker-compose --profile with-grafana up -d

# Start with pgAdmin
up-pgadmin:
	docker-compose --profile with-pgadmin up -d

# Start everything
up-all:
	docker-compose --profile with-grafana --profile with-pgadmin up -d

# Flink commands
flink-ui:
	open http://localhost:8081

flink-logs:
	docker-compose logs -f flink-jobmanager flink-taskmanager

flink-jobs:
	docker-compose exec flink-jobmanager flink list

flink-metrics:
	docker compose exec flink-jobmanager ./bin/flink run -py /opt/src/jobs/orderbook_metrics.py --pyFiles /opt/src -d

flink-alerts:
	docker compose exec flink-jobmanager ./bin/flink run -py /opt/src/jobs/orderbook_alerts.py --pyFiles /opt/src -d

flink-windows:
	docker compose exec flink-jobmanager ./bin/flink run -py /opt/src/jobs/orderbook_windows.py --pyFiles /opt/src -d

# Stop services
down:
	docker-compose down

# Restart services
restart:
	docker-compose restart

# View logs
logs:
	docker-compose logs -f

# View specific service logs
logs-ingestion:
	docker-compose logs -f ingestion

logs-dashboard:
	docker-compose logs -f dashboard

logs-db:
	docker-compose logs -f timescaledb

# Build services
build:
	docker-compose build

# Rebuild and start
rebuild: build up

# Clean everything (including volumes)
clean:
	docker-compose down -v
	@echo "All containers and volumes removed"

# Database shell
db-shell:
	docker-compose exec timescaledb psql -U orderbook_user -d orderbook

# Redis shell
redis-shell:
	docker-compose exec redis redis-cli

# Check status
status:
	docker-compose ps

# Run database migrations (when you add them)
db-migrate:
	docker-compose exec timescaledb psql -U orderbook_user -d orderbook -f /docker-entrypoint-initdb.d/init-db.sql

# Check database size
db-size:
	docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT pg_size_pretty(pg_database_size('orderbook'));"

# Check table sizes
table-sizes:
	docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "\
		SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size \
		FROM pg_tables \
		WHERE schemaname = 'public' \
		ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# View recent metrics
recent-metrics:
	docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT * FROM orderbook_metrics ORDER BY time DESC LIMIT 10;"

# View recent alerts
recent-alerts:
	docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT * FROM orderbook_alerts ORDER BY time DESC LIMIT 10;"

# View dashboard summary
dashboard-summary:
	docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT * FROM dashboard_summary;"

# Check Redis keys
redis-keys:
	docker-compose exec redis redis-cli KEYS "*"

# Get latest cached data for BTC
redis-btc:
	docker-compose exec redis redis-cli GET "orderbook:BTCUSDT:latest"

# Setup development environment
dev-setup:
	cp .env.example .env
	mkdir -p logs
	@echo "Development environment setup complete"
	@echo "Edit .env with your settings, then run 'make up'"

# Run tests (when implemented)
test:
	docker-compose exec ingestion pytest tests/

# Monitor resource usage
stats:
	docker stats

# Backup database
backup:
	docker-compose exec timescaledb pg_dump -U orderbook_user orderbook > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Database backed up to backup_*.sql"

# Restore database from backup
# Usage: make restore BACKUP=backup_20240101_120000.sql
restore:
	docker-compose exec -T timescaledb psql -U orderbook_user orderbook < $(BACKUP)

# Local development with uv
uv-install:
	@echo "Installing uv..."
	@curl -LsSf https://astral.sh/uv/install.sh | sh
	@echo "uv installed! Restart your shell or run: source ~/.cargo/env"

uv-sync:
	@echo "Syncing dependencies with uv (this is fast!)..."
	uv venv
	uv pip install -e ".[dev]"
	@echo "Dependencies installed! Activate venv: source .venv/bin/activate"

# Format code
format:
	black src/ dashboard/ tests/
	ruff check --fix src/ dashboard/ tests/

# Lint code
lint:
	ruff check src/ dashboard/ tests/
	mypy src/

# Run tests locally
test-local:
	pytest tests/ -v

# Install pre-commit hooks
pre-commit:
	pre-commit install