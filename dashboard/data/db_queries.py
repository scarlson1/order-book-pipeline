"""Database query functions."""

import datetime
import json
import streamlit as st

from src.common.database import DatabaseClient
from redis_queries import get_redis_client


@st.cache_resource  
def get_db_client():
    """Get or create database client."""
    if 'db_client' not in st.session_state:
        client = DatabaseClient()
        import asyncio
        asyncio.run(client.connect())
        st.session_state.db_client = client
    return st.session_state.db_client


class DatabaseQueries:

    def __init__(self):
        self.db = get_db_client()
        self.redis = get_redis_client()

    async def fetch_metrics(self, symbol: str = None) -> dict:
        """Try Redis, fallback on TimescaleDB"""

        if symbol:
            # cached = await self.redis.get_cached_metrics(symbol)
            # if cached:
            #     return json.loads(cached)

            metrics = await self.db.fetch_recent_metrics(symbol, limit=1)

            if metrics:
                await self.redis.insert_metrics(symbol, metrics, ttl=60)

            return metrics

        # get all symbols
        else:
            # symbols = settings.symbol_list

            # pipeline = redis_client.client.pipeline()
            # for sym in symbols:
            #     pipeline.get(redis_client._metrics_key(sym))

            # results = await pipeline.execute()

            # all_cached = all(r is not None for r in results)

            # if all_cached:
            #     return {
            #         symbols[i]: json.loads(results[i])
            #         for i in range(len(symbols))
            #     }

            async with self.db.pool.acquire() as conn:

                metrics = await conn.fetch("""
                    SELECT DISTINCT ON (symbol)
                        *
                    FROM orderbook_metrics
                    ORDER BY symbol, time DESC
                """)

            pipeline = self.redis.pipeline()
            for m in metrics:
                pipeline.setex(
                    self.redis._metrics_key(m['symbol']),
                    60,
                    json.dumps(m)
                )
            await pipeline.execute()

            return metrics


    async def fetch_time_series(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = '1m'  # '1m', '5m', '1h'
    ) -> list[dict]:
        """
            Use Case: Historical charts (last 1 hour, 24 hours, 7 days)
            Strategy: TimescaleDB ONLY, NO REDIS CACHING
        """
        # for small intervals (1m, 5m), query raw data
        if interval in ('1m', '5m'):
            return await self.db.query("""
                SELECT
                    time,
                    symbol,
                    mid_price,
                    imbalance_ratio,
                    spread_bps,
                    bid_volume,
                    ask_volume
                FROM orderbook_metrics
                WHERE symbol = $1
                    AND time >= $2
                    AND time <= $3
                ORDER BY time ASC
            """, symbol, start_time, end_time)

            # for large intervals use time_bucket aggregation
            # TimescaleDB Docs: https://www.tigerdata.com/docs/use-timescale/latest/time-buckets/use-time-buckets
        else:
            bucket_interval = '1 hour' if interval == '1h' else '1 day'
            
            return await self.db.query('''
                SELECT
                    time_bucket($1, time) AS avg_mid_price,
                    symbol,
                    AVG(mid_price) AS avg_mid_price,
                    AVG(imbalance_ratio) AS avg_imbalance,
                    AVG(spread_bps) AS avg_spread,
                    SUM(bid_volume) AS total_bid_volume,
                    SUM(ask_volume) AS total_ask_volume
                FROM orderbook_metrics
                WHERE symbol = $2
                    AND time >= $3
                    AND time <= $4
                GROUP BY bucket, symbol
                ORDER BY bucket ASC
            ''', bucket_interval, symbol, start_time, end_time)


    async def fetch_alerts(
        self,
        symbol: str = None,
        limit: int = 50,
        since: datetime = None
    ) -> list[dict]:
        '''use since param to either return alerts from redis or db'''
        query = '''
            SELECT *
            FROM orderbook_alerts
            WHERE 1=1
        '''
        params = []

        if symbol:
            query += ' AND symbol = $1'
            params.append(symbol)
        
        if since:
            param_num = len(params) + 1
            query += f' AND time >= ${param_num}'
            params.append(since)

        query += f' ORDER BY time DESC LIMIT ${len(params) + 1}'
        params.append(limit)

        return await self.db.query(query, *params)

# TODO: understand where this value is coming from ??
# what's summary stats referring to vs windowed aggregates
async def fetch_summary_stats(symbol: str, window: str = '5m') -> dict:
    '''
        Use Case: Dashboard summary cards (avg imbalance, total volume, etc.)
        Strategy: Redis ONLY (pre-computed by consumer)

        Why Redis ONLY:
            - Summary stats change slowly (every 30-60s)
            - Computing on-the-fly is expensive (avg of 1000s of rows)
            - Better to pre-compute in consumer (redis_consumer.py)
    '''
    redis_client = get_redis_client()

    redis_key = redis_client._stats_key_windowed(symbol, window)
    cached = await redis_client.get(redis_key)

    if cached:
        return json.loads(cached)

    return None

# **Redis Key Pattern**:
# ```
# orderbook:stats:5m:BTCUSDT → {
#     "avg_imbalance": 0.35,
#     "avg_spread": 2.5,
#     "total_volume": 15000.0,
#     "sample_count": 300,
#     "window_start": "2024-01-01T12:00:00Z",
#     "window_end": "2024-01-01T12:05:00Z"
# }

async def fetch_windowed_aggregates(
    symbol: str,
    window_type: str = '5m_sliding',
    limit: int = 12  # Last hour of 5-min windows
):
    '''
        Flink Window Output
        Use Case: Display rolling averages on charts
        Strategy: Hybrid - Redis for latest window, TimescaleDB for history
    '''
    redis = get_redis_client()
    db = get_db_client()
    # Get latest window from Redis
    # latest_key = f"orderbook:windowed:{window_type}:{symbol}:latest"
    # TODO: need to add windowed key & methods to RedisClient
    # latest_key = f'orderbook:windowed:{window_type}:{symbol}:latest'
    # latest_key = redis._windowed_key(symbol, window_type)
    # latest = await redis.client.get(latest_key)
    latest = await redis.get_windowed(symbol, window_type)
    
    
    # Get historical windows from database
    async with db.pool.acquire() as conn:
        historical = await conn.execute("""
            SELECT *
            FROM orderbook_metrics_windowed
            WHERE symbol = $1
            AND window_type = $2
            ORDER BY window_end DESC
            LIMIT $3
        """, symbol, window_type, limit)
    
    # Combine (latest might duplicate most recent historical)
    results = []
    if latest:
        results.append(json.loads(latest))
    
    # Deduplicate by window_end timestamp
    seen_timestamps = {r['window_end'] for r in results}
    for h in historical:
        if h['window_end'] not in seen_timestamps:
            results.append(h)
    
    return results[:limit]


async def fetch_alerts(
        symbol: str = None,
        limit: int = 50,
        since: datetime = None
    ) -> list[dict]:
        '''use since param to either return alerts from redis or db'''
        redis_client = get_redis_client()
        if since is None:
            alerts = await redis_client.get_alerts(symbol, limit)
            if alerts:
                return alerts
            # alerts = await redis_client.client.zrevrange(
            #     redis_client._alerts_key(symbol or 'all'),
            #     0,
            #     limit - 1,
            #     withscores=True
            # )

            # if alerts:
            #     return [
            #         {**json.loads(alert), 'timestamp': score }
            #         for alert, score in alerts
            #     ]

        db = get_db_client()

        query = '''
            SELECT *
            FROM orderbook_alerts
            WHERE 1=1
        '''
        params = []

        if symbol:
            query += ' AND symbol = $1'
            params.append(symbol)
        
        if since:
            param_num = len(params) + 1
            query += f' AND time >= ${param_num}'
            params.append(since)

        query += f' ORDER BY time DESC LIMIT ${len(params) + 1}'
        params.append(limit)

        return await db.query(query, *params)