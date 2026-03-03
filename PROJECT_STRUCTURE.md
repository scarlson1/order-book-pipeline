# Project Structure Overview

## Complete Directory Layout

```
orderbook-monitor/
├── docker-compose.yml              # Main orchestration file
├── docker-compose.override.yml.example  # Dev overrides template
├── Dockerfile.ingestion           # Ingestion service container
├── Dockerfile.dashboard           # Dashboard service container
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── .env                          # Your local config (gitignored)
├── .gitignore                    # Git ignore rules
├── Makefile                      # Common commands
├── setup.sh                      # Initial setup script
├── README.md                     # Documentation
├── init-db.sql                   # Database schema
│
├── src/                          # Source code
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   │
│   ├── ingestion/               # Data ingestion service
│   │   ├── __init__.py
│   │   ├── main.py              # Entry point
│   │   ├── websocket_client.py  # Binance WebSocket client
│   │   ├── orderbook_parser.py  # Parse order book data
│   │   ├── metrics_calculator.py # Calculate imbalance metrics
│   │   ├── alert_engine.py      # Alert logic
│   │   └── data_writer.py       # Write to DB and Redis
│   │
│   └── common/                  # Shared utilities
│       ├── __init__.py
│       ├── database.py          # PostgreSQL/TimescaleDB client
│       ├── redis_client.py      # Redis client wrapper
│       ├── kafka_client.py      # Kafka producer/consumer (optional)
│       └── models.py            # Pydantic data models
│
├── dashboard/                   # Streamlit dashboard
│   ├── app.py                   # Main dashboard app
│   ├── components/              # Reusable UI components
│   │   ├── __init__.py
│   │   ├── gauge.py            # Imbalance gauge
│   │   ├── timeseries.py       # Time series charts
│   │   ├── orderbook_viz.py    # Order book visualization
│   │   ├── metrics_cards.py    # Metric display cards
│   │   └── alert_feed.py       # Alert feed component
│   ├── data/                   # Data fetching layer
│   │   ├── __init__.py
│   │   ├── db_queries.py       # Database queries
│   │   └── redis_cache.py      # Redis data fetching
│   └── utils/                  # Dashboard utilities
│       ├── __init__.py
│       ├── formatting.py       # Data formatting
│       └── charts.py           # Chart helpers
│
├── grafana/                    # Grafana configuration
│   ├── datasources/
│   │   └── datasource.yml      # TimescaleDB datasource
│   └── dashboards/
│       ├── dashboard-provider.yml
│       └── orderbook.json      # Pre-built dashboard (to create)
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── test_metrics.py         # Test metric calculations
│   ├── test_alerts.py          # Test alert logic
│   ├── test_websocket.py       # Test WebSocket handling
│   └── fixtures/               # Test data fixtures
│
├── scripts/                    # Utility scripts
│   ├── backfill_data.py       # Backfill historical data
│   ├── test_connection.py     # Test external connections
│   └── benchmark.py           # Performance benchmarking
│
├── docs/                       # Additional documentation
│   ├── ARCHITECTURE.md         # System architecture
│   ├── METRICS.md             # Metric definitions
│   ├── API.md                 # API documentation
│   └── DEPLOYMENT.md          # Production deployment guide
│
└── logs/                       # Application logs (gitignored)
    ├── ingestion.log
    └── dashboard.log
```

## File Responsibilities

### Configuration Files

**docker-compose.yml**

- Defines all services (CockroachDB, Redis, Kafka, Ingestion, Dashboard, Grafana)
- Sets up networking between containers
- Manages volumes for data persistence
- Health checks and dependencies

**Dockerfile.ingestion**

- Container image for data ingestion service
- Installs Python dependencies
- Sets up logging directory

**Dockerfile.dashboard**

- Container image for Streamlit dashboard
- Exposes port 8501
- Includes health check

**requirements.txt**

- All Python dependencies
- Pinned versions for reproducibility

**.env**

- Database credentials
- API keys (if needed)
- Configuration parameters
- Alert thresholds

**db/migrations**

- Database schema (tables, indexes)
- Materialized views
- Retention policies
- Helper functions

### Source Code Files

**src/config.py**

```python
# Load environment variables
# Provide typed settings via Pydantic
# Export settings singleton
```

**src/ingestion/main.py**

```python
# Main entry point
# Initialize connections (DB, Redis, Kafka)
# Start WebSocket client
# Handle graceful shutdown
```

**src/ingestion/websocket_client.py**

```python
# Connect to Binance WebSocket
# Subscribe to order book streams
# Handle reconnection logic
# Parse incoming messages
```

**src/ingestion/orderbook_parser.py**

```python
# Parse raw WebSocket data
# Validate order book structure
# Convert to internal data model
# Handle full snapshots vs deltas
```

**src/ingestion/metrics_calculator.py**

```python
# Calculate imbalance ratio
# Calculate weighted imbalance
# Calculate spread (bps)
# Calculate VTOB ratio
# Calculate depth metrics
# Calculate velocity (time derivatives)
```

**src/ingestion/alert_engine.py**

```python
# Check alert conditions
# Track historical statistics
# Detect imbalance flips
# Detect spread widening
# Generate alert objects
```

**src/ingestion/data_writer.py**

```python
# Write metrics to TimescaleDB
# Cache latest data in Redis
# Publish to Kafka topic (optional)
# Handle write failures
# Batch writes for efficiency
```

**src/common/database.py**

```python
# PostgreSQL/TimescaleDB connection pool
# Async database operations
# Query builders
# Connection health checks
```

**src/common/redis_client.py**

```python
# Redis connection management
# Get/set operations
# Key naming conventions
# TTL management
```

**src/common/models.py**

```python
# Pydantic models for:
#   - OrderBookSnapshot
#   - OrderBookMetrics
#   - Alert
#   - Config
```

### Dashboard Files

**dashboard/app.py**

```python
# Main Streamlit app
# Page layout
# Symbol selector
# Auto-refresh logic
# Navigation
```

**dashboard/components/gauge.py**

```python
# Imbalance gauge visualization
# Plotly indicator chart
# Color coding by severity
```

**dashboard/components/timeseries.py**

```python
# Time series charts
# Dual-axis plots (imbalance + price)
# Zooming and panning
```

**dashboard/components/orderbook_viz.py**

```python
# Order book depth visualization
# Bid/ask stacked areas
# Heatmap over time
```

**dashboard/components/metrics_cards.py**

```python
# Metric display cards
# Delta indicators
# Sparklines
```

**dashboard/components/alert_feed.py**

```python
# Alert table/feed
# Filtering by severity
# Time formatting
```

**dashboard/data/db_queries.py**

```python
# Fetch recent metrics
# Fetch time series data
# Fetch alerts
# Fetch aggregated stats
```

**dashboard/data/redis_cache.py**

```python
# Fetch latest cached data
# Fetch multiple symbols
# Handle cache misses
```

## Environment Variables Reference

TODO: update env vars reference

```bash
# Database
POSTGRES_HOST=timescaledb
POSTGRES_PORT=5432
POSTGRES_DB=orderbook
POSTGRES_USER=orderbook_user
POSTGRES_PASSWORD=orderbook_pass

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Kafka (optional)
KAFKA_ENABLED=false
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Binance
BINANCE_WS_URL=wss://stream.binance.us:9443/ws
SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT
DEPTH_LEVELS=20
UPDATE_SPEED=100ms

# Metrics
CALCULATE_DEPTH=10
ALERT_THRESHOLD=0.70
ROLLING_WINDOW_SECONDS=60

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/orderbook.log
```
