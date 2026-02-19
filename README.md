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
│   ├── jobs/                 # Flink jobs
│   │   ├── orderbook_metrics.py       # Database connection
│   │   ├── redis_client.py   # Redis client
│   ├── producers/            # Flink producers
│   └── config.py             # Configuration loader
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── grafana/
│   ├── datasources/          # Grafana datasources
│   └── dashboards/           # Dashboard definitions
└── logs/                     # Application logs
```

**End-to-end flow (where the data lives at each step)**

1. **Binance WebSocket (external source)**
   - **Location in code:** [`src/ingestion/websocket_client.py`](src/ingestion/websocket_client.py)
   - **Entry point:** `BinanceWebSocketClient.start()` → `_connect_symbol()` → `_handle_message()`
   - **Data shape:** raw JSON string → parsed dict, expected keys include `bids`/`asks` for partial book depth (see inline docstring in `BinanceWebSocketClient`).
   - **What happens:** `_handle_message()` does `json.loads(...)` and calls the callback with `(symbol, data)`.

2. **Ingestion Service callback**
   - **Location in code:** [`src/ingestion/main.py`](src/ingestion/main.py)
   - **Function:** `IngestionService.handle_orderbook(symbol, raw_data)`
   - **Data shape:** `raw_data` is a dict from Binance; `symbol` is the trading symbol string.

3. **Parsing + validation**
   - **Location in code:** [`src/ingestion/orderbook_parser.py`](src/ingestion/orderbook_parser.py)
   - **Function:** `OrderBookParser.parse(symbol, raw)`
   - **Data shape in:** raw Binance dict
   - **Data shape out:** `OrderBookSnapshot` model (or `None` if invalid)
   - **Model definition:** `OrderBookSnapshot` in `src/common/models.py`
   - **What happens:** converts price/volume to floats, sorts bids/asks, filters invalid levels, builds a typed snapshot.

4. **Enrichment + publish to Redpanda**
   - **Location in code:** [`src/ingestion/main.py`](src/ingestion/main.py)
   - **Function:** `IngestionService.handle_orderbook(...)`
   - **Data shape:** `snapshot.model_dump()` merged with:
     - `ingested_at` (ISO timestamp)
     - `source` = `"binance_websocket"`
   - **Topic name:** `settings.redpanda_topics["raw"]` from `src/config.py`
   - **Publisher:** `RedpandaProducer.publish(...)` in `src/common/redpanda_client.py`

5. **Redpanda topic: `orderbook.raw`**
   - **Location in code:** config in [`src/config.py`](src/config.py) (`settings.redpanda_topics`)
   - **Runtime storage:** Redpanda broker (external)
   - **Message schema:** dict with keys like `timestamp`, `symbol`, `bids`, `asks`, `update_id`, `ingested_at`, `source`.
   - **Validated by:** `OrderBookSnapshot` in [`src/common/models.py`](src/common/models.py) before publish.

6. **Flink (downstream processing)**
   - **Intended flow:** Flink consumes `orderbook.raw`, calculates metrics/alerts, produces to:
     - `settings.redpanda_topics["metrics"]`
     - `settings.redpanda_topics["alerts"]`

7. **Persistence layer (TimescaleDB / Redis)**
   - **Database client:** [`src/common/database.py`](src/common/database.py)
   - **Functions:** `insert_metrics(...)`, `insert_alert(...)`
   - **Expected data shape:** matches `OrderBookMetrics` and `Alert` in [`src/common/models.py`](src/common/models.py).

---

## TODO:

2. **Dashboard** (`dashboard/`)
   - Streamlit app with visualizations
   - Real-time metric display
   - Alert feed
   - Historical analysis

## Useful Commands

### Service Management

```bash
# run once to build Flick with connectors
docker compose build --no-cache

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
   - Connect rocksDB to external storage (S3, GCS)

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

## Flink Connectors

**Required connectors:**

- Flink Kafka connector: `flink-connector-kafka-1.18.0.jar`
- Kafka Clients Library (dependency) - `kafka-clients-3.2.3.jar`
-

### Installation options

**Option 1: download \* mount**

- update `docker-compose.yml` with volume mount to locally installed connector directory
- use setup script to download

```bash
#!/bin/bash
# Download Flink Kafka connector JARs
#
# These JARs are required for Flink to read/write from Redpanda.
# Run this once before starting Flink services.

set -e  # Exit on error

FLINK_VERSION="1.18.0"
KAFKA_VERSION="3.2.3"
SCALA_VERSION="2.12"

FLINK_LIB_DIR="./flink/lib"

echo "======================================"
echo "Downloading Flink Kafka Connector JARs"
echo "======================================"

# Create lib directory
mkdir -p "$FLINK_LIB_DIR"

# Flink Kafka Connector
KAFKA_CONNECTOR_JAR="flink-sql-connector-kafka-${FLINK_VERSION}.jar"
KAFKA_CONNECTOR_URL="https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${FLINK_VERSION}/${KAFKA_CONNECTOR_JAR}"

if [ -f "$FLINK_LIB_DIR/$KAFKA_CONNECTOR_JAR" ]; then
    echo "✓ $KAFKA_CONNECTOR_JAR already exists"
else
    echo "Downloading $KAFKA_CONNECTOR_JAR..."
    curl -L -o "$FLINK_LIB_DIR/$KAFKA_CONNECTOR_JAR" "$KAFKA_CONNECTOR_URL"
    echo "✓ Downloaded $KAFKA_CONNECTOR_JAR"
fi

# Kafka Clients (dependency)
KAFKA_CLIENTS_JAR="kafka-clients-${KAFKA_VERSION}.jar"
KAFKA_CLIENTS_URL="https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/${KAFKA_VERSION}/${KAFKA_CLIENTS_JAR}"

if [ -f "$FLINK_LIB_DIR/$KAFKA_CLIENTS_JAR" ]; then
    echo "✓ $KAFKA_CLIENTS_JAR already exists"
else
    echo "Downloading $KAFKA_CLIENTS_JAR..."
    curl -L -o "$FLINK_LIB_DIR/$KAFKA_CLIENTS_JAR" "$KAFKA_CLIENTS_URL"
    echo "✓ Downloaded $KAFKA_CLIENTS_JAR"
fi

echo ""
echo "======================================"
echo "✓ All Flink connector JARs downloaded"
echo "======================================"
echo ""
echo "Files in $FLINK_LIB_DIR:"
ls -lh "$FLINK_LIB_DIR"
echo ""
echo "You can now start Flink:"
echo "  docker compose --profile with-redpanda up -d"
```

```bash
# Make script executable
chmod +x flink/download-jars.sh

# Download JARs (one-time setup)
make flink-jars

# Or run directly:
./flink/download-jars.sh
```

```yaml
# docker-compose.yml
flink-jobmanager:
  volumes:
    - ./flink/lib:/opt/flink/lib # ← Local JARs mounted to Flink's lib
```

**Option 2: Dockerfile**

See `Dockerfile.flink` - this is the current implimentation.

- `Dockerfile.flink` to build custom image that downloads the connectors
- results in larger docker image, but easier to maintain / removes dev setup step

## Contributing

This is a portfolio project, but suggestions and improvements are welcome!

## Support

For issues or questions, please check:

- Docker logs: `docker-compose logs`
- Database status: `docker-compose exec timescaledb pg_isready`
- Service health: `docker-compose ps`
