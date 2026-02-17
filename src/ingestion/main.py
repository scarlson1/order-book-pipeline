# TODO: implement

"""Main ingestion service entry point."""
import asyncio
# import time
from loguru import logger
from src.config import settings
from src.ingestion.websocket_client import BinanceWebSocketClient

# Binance WebSocket
#       ↓ raw JSON string
# _handle_message()       ← Parses JSON, validates structure
#       ↓ Python dict
# callback(symbol, data)  ← Passes to pipeline (defined in main.py)
#       ↓
# orderbook_parser.py     ← Converts to OrderBookSnapshot model
#       ↓
# metrics_calculator.py   ← Calculates imbalance, spread, etc.
#       ↓
# data_writer.py          ← Saves to TimescaleDB + Redis + Redpanda

async def main():
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Monitoring symbols: {settings.symbol_list}")
    logger.info(f"Database: {settings.postgres_host}:{settings.postgres_port}")
    
    # Use settings throughout
    # for symbol in settings.symbol_list:
    #     logger.info(f"Subscribing to {symbol}")

    db = DatabaseClient()
    redis = RedisClient()
    parser = OrderBookParser()
    calculator = MetricsCalculator()

    await db.connect()
    await redis.connect()

    # THIS is how data flows through the pipeline
    async def handle_orderbook(symbol: str, data: dict):
        # Step 1: Parse raw data into model
        snapshot = parser.parse(symbol, data)

        # Step 2: Calculate metrics
        metrics = calculator.calculate(snapshot)

        # Step 3: Write to storage
        # await db.insert_metrics(metrics.model_dump())
        # await redis.cache_metrics(symbol, metrics.model_dump())

        # Step 3: publish to redpanda --> Flick consumers

    # Pass callback to WebSocket client
    client = BinanceWebSocketClient(callback=handle_orderbook)
    await client.start()

if __name__ == "__main__":
    asyncio.run(main())

# logger.info("Ingestion service starting...")
# logger.warning("This is a placeholder - implementation needed!")
# logger.info("Container will stay alive. Press Ctrl+C to stop.")

# # Keep container running indefinitely
# while True:
#     time.sleep(60)
#     logger.info("Still running... (waiting for implementation)")



# # Things Flink handles that are hard to do in plain Python:

# # 1. Windowed aggregations
# #    "Average imbalance over last 1 minute, sliding every 10 seconds"
# SELECT symbol, 
#     AVG(imbalance_ratio) OVER (
#         PARTITION BY symbol 
#         ORDER BY event_time 
#         RANGE BETWEEN INTERVAL '1' MINUTE PRECEDING AND CURRENT ROW
#     )

# # 2. Cross-stream joins
# #    "Join order book data with trade data to correlate imbalance with price moves"

# # 3. Complex event patterns
# #    "Alert when imbalance exceeds 70% AND spread widens by 2x within 30 seconds"

# # 4. Exactly-once processing
# #    "Guarantee every message is processed exactly once, even on failures"

# # 5. State management across millions of events
# #    "Track rolling statistics per symbol without running out of memory"
# ```

# ## 🤔 Does Your Project Actually Need Flink?

# **Honestly, probably not yet.** Here's a practical breakdown:

# ### Your Current Stack (Without Flink) Can Handle:
# - ✅ Real-time imbalance calculations
# - ✅ Basic rolling windows (Python deque/dictionary)
# - ✅ Alert detection with thresholds
# - ✅ TimescaleDB continuous aggregates (built-in time bucketing)
# - ✅ Redis caching for dashboard
# - ✅ ~10-50 symbols at 100ms updates

# ### You'd Need Flink When:
# - ❌ Processing 1000+ symbols
# - ❌ Complex multi-stream joins (order book + trades + news)
# - ❌ Sub-millisecond latency requirements
# - ❌ Exactly-once processing guarantees critical
# - ❌ Team of engineers maintaining the system

# ## 🎯 Recommended Architecture for YOUR Project

# ### Phase 1: What You're Building Now (Simple)
# ```
# Binance WebSocket
#       ↓
# Python Ingestion Service
#   ├── Parse order book
#   ├── Calculate metrics (in-process)
#   └── Check alerts (in-process)
#       ↓
#   Redpanda
#   ├── orderbook.metrics topic
#   └── orderbook.alerts topic
#       ↓
#   Consumers (Python)
#   ├── DB Writer → TimescaleDB
#   ├── Cache Writer → Redis
#   └── Dashboard → Streamlit
# ```

# ### Phase 2: If You Want to Add Flink Later
# ```
# Binance WebSocket
#       ↓
# Python Ingestion Service (raw data only)
#       ↓
# Redpanda (orderbook.raw)
#       ↓
#    Flink Job
#   ├── Windowed aggregations
#   ├── Cross-symbol analytics
#   └── Complex alert patterns
#       ↓
# Redpanda (orderbook.processed)
#       ↓
#   Consumers
#   ├── TimescaleDB
#   ├── Redis
#   └── Dashboard
# ```

# ## 📊 Comparison Table

# | | **Your Project** | **Flink** | **Redpanda** |
# |---|---|---|---|
# | **Role** | Ingestion + calculation | Stream processing | Message broker |
# | **Complexity** | Low | High | Medium |
# | **Needed now?** | ✅ Yes | ❌ Not yet | ✅ Yes |
# | **Adds value** | Core | At scale | Immediately |
# | **Learning curve** | Low | High (Java/Scala) | Medium |

# ## 💡 For Your Portfolio

# If you want to **mention Flink** without fully implementing it, add it to your architecture diagram as a future consideration:
# ```
# README.md:

# Current Architecture:
#   Binance → Python Ingestion → Redpanda → Consumers → TimescaleDB + Redis

# Scaling Path (Future):
#   Binance → Python Ingestion → Redpanda → Flink → Redpanda → TimescaleDB + Redis
  
#   Flink would enable:
#   - Windowed aggregations across multiple symbols
#   - Complex event detection patterns  
#   - Cross-stream joins with trade data
#   - Sub-millisecond processing guarantees