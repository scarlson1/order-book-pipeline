# Development Guide

## Quick Start for Developers

This guide covers local development setup using modern Python tooling.

## Prerequisites

- Python 3.11+
- Docker Desktop (for running infrastructure)
- [uv](https://github.com/astral-sh/uv) - Ultra-fast Python package installer
- [just](https://just.systems/) - Modern task runner (optional, alternative to make)

## Setup Development Environment

### 1. Install uv (Lightning Fast Package Manager)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or use the Makefile
make uv-install
```

**Why uv?**

- 10-100x faster than pip
- Better dependency resolution
- Built in Rust for maximum performance
- Drop-in replacement for pip

### 2. Create Virtual Environment & Install Dependencies

```bash
# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# Or on Windows: .venv\Scripts\activate

# Install all dependencies (including dev tools)
uv pip install -e ".[kafka,dev]"

# Using Makefile
make uv-sync
```

### 3. Install Pre-commit Hooks (Optional but Recommended)

```bash
# Install pre-commit hooks for automatic code quality checks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Using Makefile
make pre-commit
```

### 5. Configure Environment

```bash
# Copy example config & update .env
cp .env.example .env
```

### 4. Start Infrastructure Services

You still need Docker for the database, Redis, etc:

```bash
# Start services
docker-compose up -d

# Or use make/just
make up
just up
```

Local CockroachDB Admin UI: `http://localhost:8088`  
Redpanda Console remains on `http://localhost:8080`
Flink: `http://localhost:8081`
Streamlit: `http://localhost:8501`

### Code Quality Tools

```bash
# Format code (YAPF + Ruff)
make format
just format

# Lint code
make lint
just lint

# Run type checking
mypy src/
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Using make/just
make test
just test-cov
```

### Useful Commands

#### Using Makefile

```bash
make up              # Start Docker services
make down            # Stop Docker services
make logs            # View logs
make db-shell        # Connect to database
make redis-shell     # Connect to Redis
make format          # Format code
make lint            # Lint code
make test            # Run tests
make help            # See all commands
```

#### Using justfile (Modern Alternative)

```bash
just up              # Start Docker services
just down            # Stop Docker services
just logs            # View logs
just db-shell        # Connect to database
just format          # Format code
just test            # Run tests
just                 # List all commands
```

## Adding Dependencies with uv

```bash
# Add a package
uv pip install package-name

# Add to pyproject.toml
# Edit pyproject.toml and add to dependencies list, then:
uv pip install -e ".[dev]"

# For development-only dependencies
# Add to [project.optional-dependencies] dev section
```

## Docker Development

### Development with Hot Reload

The `docker-compose.override.yml.example` shows how to mount code for live reload:

```bash
# Copy the example
cp docker-compose.override.yml.example docker-compose.override.yml

# build flink docker file (download connectors)
docker-compose build --no-cache

# Start with overrides (auto-reloads on code changes)
docker-compose up -d
```

### Rebuild After Changes

```bash
# Rebuild specific service
docker-compose build ingestion

# Rebuild and restart
docker-compose up -d --build

# Using make/just
make rebuild
just rebuild
```

## Debugging

### VS Code Launch Configuration

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Ingestion Service",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/src/ingestion/main.py",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env"
    },
    {
      "name": "Python: Dashboard",
      "type": "python",
      "request": "launch",
      "module": "streamlit",
      "args": ["run", "dashboard/app.py"],
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

### PyCharm Configuration

1. Add Python interpreter: Settings → Project → Python Interpreter → Add → Virtualenv Environment → Existing → Select `.venv/bin/python`
2. Add run configuration for `src/ingestion/main.py`
3. Add run configuration for Streamlit: Module name: `streamlit`, Parameters: `run dashboard/app.py`

## Database Development

### Connecting to Database

```bash
# Using Docker
docker-compose exec cockroachdb psql -U orderbook_user -d orderbook

# Using make/just
make db-shell
just db-shell

# Using psql directly (if installed locally)
psql -h localhost -U orderbook_user -d orderbook
```

### Schema Migrations

Use `db/migrations/` as the schema source of truth.
`init-db.sql` is legacy bootstrap and should not be used for ongoing schema changes.

For local Docker Compose, migrations are applied automatically by the one-shot
`db-migrate` service before DB-dependent app services start.
You still use `dbmate` manually when creating or testing migration changes.

Create and apply migrations with [dbmate](https://github.com/amacneil/dbmate):

```bash
# Install dbmate if not already installed (macOS example)
brew install dbmate

# From repo root
cd /order-book-pipeline

# Example DATABASE_URL (Cockroach)
export DATABASE_URL='postgresql://<user>:<password>@<host>:26257/<db>?sslmode=require'

# Create a new migration
dbmate --migrations-dir db/migrations new add_example_change

# Apply pending migrations
dbmate --migrations-dir db/migrations up

# Show migration state
dbmate --migrations-dir db/migrations status

# If needed, rollback one step
dbmate --migrations-dir db/migrations down
```

Retention policies are managed via migrations:

- `orderbook_metrics` TTL: 7 days (raw metrics)
- `orderbook_metrics_windowed` TTL: 30 days (windowed aggregates)

When changing retention, add a new migration instead of editing existing migration files.

### Query Performance

```bash
# Check query performance
EXPLAIN ANALYZE SELECT * FROM orderbook_metrics WHERE symbol = 'BTCUSDT' AND time > NOW() - INTERVAL '1 hour';

# Check index usage
SELECT schemaname, tablename, indexname, idx_scan FROM pg_stat_user_indexes ORDER BY idx_scan;
```

## Performance Profiling

### Python Profiling

```bash
# Install profiling tools
uv pip install line-profiler memory-profiler

# Profile CPU
python -m cProfile -o output.prof src/ingestion/main.py
python -m pstats output.prof

# Profile memory
python -m memory_profiler src/ingestion/main.py
```

### Database Profiling

```sql
-- Enable query logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = on;
SELECT pg_reload_conf();

-- Check slow queries
SELECT calls, total_time, mean_time, query
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

## Testing Strategy

### Unit Tests

```bash
# Test individual functions
pytest tests/test_metrics.py -v

# Test with markers
pytest -m "not slow" -v
```

### Integration Tests

```bash
# Test with real database (Docker must be running)
pytest tests/test_integration.py -v
```

### Load Testing

```bash
# Install locust
uv pip install locust

# Run load test
locust -f tests/load_test.py
```

## CI/CD

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_PASSWORD: test
      redis:
        image: redis:7-alpine

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v1

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv pip install -e ".[dev]"

      - name: Run tests
        run: pytest

      - name: Run linting
        run: |
          ruff check .
          yapf --diff -r src dashboard tests
```

## Tips & Best Practices

### Development Tips

1. **Use uv for everything** - It's massively faster than pip
2. **Enable pre-commit hooks** - Catch issues before committing
3. **Write tests first** - TDD helps design better APIs
4. **Use type hints** - mypy will catch bugs early
5. **Format on save** - Configure your IDE to run yapf/ruff automatically

### Code Style

- Follow PEP 8 (enforced by yapf and ruff)
- Use type hints everywhere
- Write docstrings for public functions
- Keep functions small (<50 lines)
- Use meaningful variable names

### Performance Tips

1. **Batch database writes** - Don't write every metric individually
2. **Use connection pooling** - Reuse database connections
3. **Cache in Redis** - For frequently accessed data
4. **Use async/await** - For I/O-bound operations
5. **Profile before optimizing** - Measure first, then optimize

### Security Tips

1. **Never commit .env** - Use .env.example as template
2. **Use environment variables** - For all secrets
3. **Validate all inputs** - Use Pydantic models
4. **Keep dependencies updated** - Run `uv pip list --outdated` regularly

## Troubleshooting

### uv Issues

```bash
# Clear uv cache
uv cache clean

# Reinstall everything
rm -rf .venv
uv venv
uv pip install -e ".[dev]"
```

### Docker Issues

```bash
# Reset Docker
docker-compose down -v
docker system prune -a

# Check Docker resources
docker system df
```

### Database Issues

```bash
# Check database logs
docker-compose logs timescaledb

# Verify connection
docker-compose exec timescaledb pg_isready
```

## Getting Help

- Check the logs: `make logs` or `just logs`
- Review the README.md
- Check PROJECT_STRUCTURE.md for implementation details
- Ask in GitHub issues (if you open-source this)

Happy coding! 🚀
