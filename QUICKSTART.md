# 🚀 Quick Start Guide

### Start Services (if you skipped in setup)

```bash
docker-compose up -d
```

### Verify Services

```bash
docker-compose ps
```

You should see:

- ✅ timescaledb (healthy)
- ✅ redis (healthy)
- ✅ ingestion (running)
- ✅ dashboard (running)

### Access Dashboard

Open http://localhost:8501

**Note:** The dashboard will show a placeholder until you implement the code!

## What's Running?

| Service     | Port | Purpose                 |
| ----------- | ---- | ----------------------- |
| TimescaleDB | 5432 | Time-series database    |
| Redis       | 6379 | Real-time cache         |
| Streamlit   | 8501 | Dashboard UI            |
| Grafana     | 3000 | (optional) Dashboard UI |

## Common Commands

```bash
# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart a service
docker-compose restart ingestion

# Connect to database
docker-compose exec timescaledb psql -U orderbook_user -d orderbook

# Connect to Redis
docker-compose exec redis redis-cli

# Check status
docker-compose ps
```

## Using the Makefile

```bash
make up          # Start services
make down        # Stop services
make up-grafana  # Start with profile
make logs        # Follow logs
make status      # Check status
make db-shell    # Database shell
make redis-shell # Redis shell
make help        # See all commands
make clean       # remove containers & volumes
make test        # run tests locally
```

## Optional Services

### Start with Grafana

```bash
docker-compose --profile with-grafana up -d
```

Access at http://localhost:3000 (admin/admin)

### Start with pgAdmin

```bash
docker-compose --profile with-pgadmin up -d
```

Access at http://localhost:5050 (admin@orderbook.com/admin)

<!-- ### Start with Kafka

```bash
docker-compose --profile with-redpanda up -d
``` -->

## Next Steps: Implementation

The infrastructure is ready! Now implement:

1. **Data Models** (`src/common/models.py`)
   - OrderBookSnapshot
   - OrderBookMetrics
   - Alert models

2. **Database Client** (`src/common/database.py`)
   - Connection pool
   - Query methods

3. **WebSocket Client** (`src/ingestion/websocket_client.py`)
   - Connect to Binance
   - Subscribe to order book streams
   - Handle reconnection

4. **Metrics Calculator** (`src/ingestion/metrics_calculator.py`)
   - Imbalance ratio
   - Weighted imbalance
   - Spread calculations

5. **Dashboard** (`dashboard/app.py`)
   - Real-time visualizations
   - Metric displays
   - Alert feed

See `PROJECT_STRUCTURE.md` for detailed implementation guide.

## Troubleshooting

### Port Already in Use

```bash
# Find what's using the port
lsof -i :5432
lsof -i :6379
lsof -i :8501

# Kill the process or change the port in docker-compose.yml
```

### Services Won't Start

```bash
# Reset everything
docker-compose down -v
docker-compose up -d

# Check logs
docker-compose logs timescaledb
docker-compose logs redis
```

### Database Connection Issues

```bash
# Verify database is ready
docker-compose exec timescaledb pg_isready -U orderbook_user

# Check if tables exist
docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "\dt"
```

### Out of Disk Space

```bash
# Clean up Docker
docker system prune -a --volumes

# Check sizes
docker system df
```

## Getting Help

1. Check logs: `docker-compose logs -f`
2. Verify services: `docker-compose ps`
3. Check database: `make db-shell`
4. Review README.md for detailed docs

## Done / TODO

✅ Complete infrastructure setup
✅ Database schema ready
✅ Docker orchestration configured
✅ Logging configured
✅ Development environment ready

❌ Application code (you implement this!)
❌ WebSocket client (to be implemented)
❌ Dashboard components (to be implemented)
❌ Alert logic (to be implemented)

## Resources

- `README.md` - Full documentation
- [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) - Implementation guide
- [`Makefile`](Makefile) - Common commands
- [`init-db.sql`](init-db.sql) - Database schema
- [`.env.example`](.env.example) - Configuration options
- [`pyproject.toml`](pyproject.toml) - Python project configuration (uv compatible)

## Local Development (Without Docker)

Want to develop locally? Install [`uv`](https://docs.astral.sh/uv/) if you don't already have it:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (super fast!)
uv pip install -e ".[dev]"

# Run tests
pytest

# Start coding!
```

Happy coding! 🎉
