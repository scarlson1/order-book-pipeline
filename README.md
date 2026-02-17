# Real-Time Order Book Imbalance Monitor

A production-ready streaming data pipeline that monitors order book imbalances in real-time from cryptocurrency exchanges.

## Architecture

```
Binance WebSocket
      ↓
Python Ingestion Service
      ↓
Redpanda (orderbook.raw)        ← Message broker / buffer
      ↓
Apache Flink                    ← Stream processing
  ├── Windowed aggregations
  ├── Metrics calculation
  ├── Alert detection
  └── Complex event patterns
      ↓
Redpanda (orderbook.processed / orderbook.alerts)
      ↓
  Consumers
  ├── TimescaleDB               ← Persistent storage
  ├── Redis                     ← Low-latency cache
  └── Streamlit Dashboard       ← Visualization
```

## Features

- **Real-time streaming** from Binance WebSocket API
- **Redpanda streaming platform** - Kafka-compatible message broker for scalable data pipelines
- **Multiple metrics**: Imbalance ratio, weighted imbalance, spread analysis, VTOB ratio
- **Intelligent alerts**: Extreme imbalance, imbalance flips, spread widening
- **Time-series storage** with TimescaleDB for historical analysis
- **Redis caching** for ultra-low latency reads
- **Interactive dashboard** with Streamlit
- **Grafana integration** for advanced visualization (optional)

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- 4GB+ RAM available
- Ports available: 5432, 6379, 8501 (and optionally 3000, 5050, 9092)

**Note:** This project uses [uv](https://github.com/astral-sh/uv) for ultra-fast Python package installation. It's automatically installed in the Docker containers for 10-100x faster builds!

### 1. Clone and Setup

```bash
# Create project directory
mkdir orderbook-monitor
cd orderbook-monitor

# Copy the docker-compose.yml and other files here
# (All files should be in the root directory)

# Create environment file
cp .env.example .env

# Edit .env if you want to change any settings
# Default values work fine for getting started
```

### 2. Create Required Directories

```bash
mkdir -p src/ingestion src/common dashboard logs
```

### 3. Start Core Services

```bash
# Start TimescaleDB and Redis only
docker-compose up -d timescaledb redis

# Wait for services to be healthy (about 10-15 seconds)
docker-compose ps

# Verify database is initialized
docker-compose logs timescaledb | grep "database system is ready"
```

### 4. Start All Services

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### 5. Access the Dashboard

Open your browser to:

- **Streamlit Dashboard**: http://localhost:8501

### 6. Optional Services

```bash
# Start with Redpanda (recommended for production-grade streaming)
docker-compose --profile with-redpanda up -d

# Start with Grafana
docker-compose --profile with-grafana up -d

# Start with pgAdmin (database management)
docker-compose --profile with-pgadmin up -d

# Start everything
docker-compose --profile with-redpanda --profile with-grafana --profile with-pgadmin up -d
```

Access optional services:

- **Redpanda Console**: http://localhost:8080 (when with-redpanda profile is enabled)
- **Grafana**: http://localhost:3000 (admin/admin)
- **pgAdmin**: http://localhost:5050 (admin@orderbook.com/admin)

**Note:** While Redpanda is optional for initial setup, it's highly recommended for production deployments to enable scalable, distributed data processing.

## Docker Compose Profiles

The docker-compose.yml uses profiles to optionally enable additional services:

- **Default** (no profile): Core services only (TimescaleDB, Redis, Ingestion, RedPanda, Flink, Dashboard)
- **with-grafana**: Adds Grafana for advanced visualization
- **with-pgadmin**: Adds pgAdmin for database management

**Why Redpanda?**

- **Simpler**: No Zookeeper needed - single binary deployment
- **Faster**: Written in C++ for 10x better performance vs Kafka
- **Lighter**: Uses less memory and CPU (~1GB vs ~4GB for Kafka+Zookeeper)
- **Compatible**: Drop-in Kafka replacement - use existing Kafka clients
- **Better DX**: Built-in web console and rpk CLI tool
- **Production-ready**: Powers real-time data pipelines at scale

**Use Cases:**

- Enable multiple consumers (dashboard, alerts, analytics)
- Replay historical events for debugging
- Scale horizontally with partitioning
- Decouple ingestion from processing

## Configuration

Edit `.env` to customize:

### Symbols to Monitor

```bash
SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,ADAUSDT
```

### Alert Thresholds

```bash
ALERT_THRESHOLD_HIGH=0.70    # 70% imbalance triggers alert
ALERT_THRESHOLD_MEDIUM=0.50  # 50% imbalance warning
SPREAD_ALERT_MULTIPLIER=2.0  # Alert when spread 2x normal
```

### Calculation Depth

```bash
CALCULATE_DEPTH=10  # Use top 10 levels for calculations
DEPTH_LEVELS=20     # Fetch 20 levels from exchange
```

## Project Structure

```
.
├── docker-compose.yml          # Main orchestration file
├── init-db.sql                 # Database schema
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
├── Dockerfile.ingestion       # Ingestion service image
├── Dockerfile.dashboard       # Dashboard service image
├── src/
│   ├── ingestion/
│   │   ├── main.py           # Main ingestion script
│   │   ├── websocket_client.py
│   │   ├── metrics_calculator.py
│   │   └── alert_engine.py
│   ├── common/
│   │   ├── database.py       # Database connection
│   │   ├── redis_client.py   # Redis client
│   │   └── models.py         # Data models
│   └── config.py             # Configuration loader
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── grafana/
│   ├── datasources/          # Grafana datasources
│   └── dashboards/           # Dashboard definitions
└── logs/                     # Application logs
```

## TODO:

1. **Ingestion Service** (`src/ingestion/`)
   - Order book parser
   - Metrics calculator
   - Database writer
   - Alert engine

2. **Dashboard** (`dashboard/`)
   - Streamlit app with visualizations
   - Real-time metric display
   - Alert feed
   - Historical analysis

## Useful Commands

### Service Management

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a specific service
docker-compose restart ingestion

# View logs
docker-compose logs -f ingestion
docker-compose logs -f dashboard

# Rebuild after code changes
docker-compose up -d --build
```

### Database Management

```bash
# Connect to database
docker-compose exec timescaledb psql -U orderbook_user -d orderbook

# Run SQL queries
docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT * FROM dashboard_summary;"

# Check table size
docker-compose exec timescaledb psql -U orderbook_user -d orderbook -c "SELECT pg_size_pretty(pg_total_relation_size('orderbook_metrics'));"
```

### Redis Management

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check cached data
docker-compose exec redis redis-cli KEYS "orderbook:*"

# Get latest metrics for a symbol
docker-compose exec redis redis-cli GET "orderbook:BTCUSDT:latest"
```

### Monitoring

```bash
# Check container resource usage
docker stats

# Check service health
docker-compose ps

# Follow all logs
docker-compose logs -f
```

## Troubleshooting

### Services won't start

```bash
# Check if ports are already in use
lsof -i :5432  # TimescaleDB
lsof -i :6379  # Redis
lsof -i :8501  # Streamlit

# Reset everything
docker-compose down -v
docker-compose up -d
```

### Database connection errors

```bash
# Verify database is ready
docker-compose exec timescaledb pg_isready -U orderbook_user

# Check database logs
docker-compose logs timescaledb
```

### WebSocket connection issues

```bash
# Check ingestion service logs
docker-compose logs ingestion

# Verify network connectivity
docker-compose exec ingestion ping -c 3 stream.binance.us
```

### Dashboard not loading

```bash
# Check dashboard logs
docker-compose logs dashboard

# Rebuild dashboard
docker-compose up -d --build dashboard
```

## Performance Tuning

### For High-Throughput Scenarios

1. **Enable Redpanda** for better message buffering:

   ```bash
   docker-compose --profile with-redpanda up -d
   ```

2. **Increase PostgreSQL connection pool**:
   Edit `docker-compose.yml` and add to timescaledb environment:

   ```yaml
   POSTGRES_MAX_CONNECTIONS: 200
   ```

3. **Optimize TimescaleDB**:

   ```sql
   -- Increase chunk interval
   SELECT set_chunk_time_interval('orderbook_metrics', INTERVAL '1 day');

   -- Enable compression
   ALTER TABLE orderbook_metrics SET (
       timescaledb.compress,
       timescaledb.compress_segmentby = 'symbol'
   );
   ```

## Production Considerations

Before deploying to production:

1. **Security**:
   - Change default passwords in `.env`
   - Use secrets management (Docker secrets, Vault)
   - Enable SSL/TLS for all connections
   - Restrict network access with firewall rules

2. **Monitoring**:
   - Add Prometheus metrics
   - Set up alerting (PagerDuty, Slack)
   - Monitor container health
   - Track database performance

3. **Scaling**:
   - Use Redpanda for multi-consumer pattern
   - Scale ingestion service horizontally
   - Set up TimescaleDB replication
   - Use Redis Cluster for high availability

4. **Data Retention**:
   - Enable automatic data cleanup in `init-db.sql`
   - Compress older data
   - Archive to S3/object storage

## License

MIT License - feel free to use for your personal or commercial projects.

## Local Development with uv

For local development outside Docker, you can use uv for extremely fast dependency installation:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install all dependencies (10-100x faster than pip!)
uv pip install -e ".[dev]"

# Or install from requirements.txt
uv pip install -r requirements.txt

# Install with Redpanda support
uv pip install -e ".[redpanda,dev]"

# Run tests
pytest

# Format code
black src/ dashboard/ tests/
ruff check src/ dashboard/ tests/
```

**Why uv?**

- 10-100x faster than pip for installing packages
- Better dependency resolution
- Built in Rust for maximum performance
- Drop-in replacement for pip
- Used in our Docker builds for faster image building

## Contributing

This is a portfolio project, but suggestions and improvements are welcome!

## Support

For issues or questions, please check:

- Docker logs: `docker-compose logs`
- Database status: `docker-compose exec timescaledb pg_isready`
- Service health: `docker-compose ps`
