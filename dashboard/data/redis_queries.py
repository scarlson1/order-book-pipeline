"""Redis data fetching for dashboard."""
import json
from typing import Dict, List, Optional
import streamlit as st

from dashboard.data.db_queries import get_db_client, get_redis_client
from src.common.redis_client import RedisClient

@st.cache_resource
def get_redis_client():
    """Get or create Redis client."""
    if 'redis_client' not in st.session_state:
        client = RedisClient()
        import asyncio
        asyncio.run(client.connect())
        st.session_state.redis_client = client
    return st.session_state.redis_client


class RedisQueries:

    def __init__(self):
        self.redis = get_redis_client()
    

    async def get_latest_metrics(self, symbol: str):
        # redis = get_redis_client()
        cached = await self.redis.get_cached_metrics(symbol)
        if cached:
            return json.loads(cached)
        else:
            return None
        # db = get_db_client()
        # metric = await db.fetch_recent_metrics(symbol, 1)
        # # need to cache ??
        # return metric
        

    async def get_multiple_symbols(self, symbols: list[str]):
        # redis = get_redis_client()
        cached = self.redis.get_multiple_metrics(symbols)
        if cached:
            return json.loads(cached)
        else: 
            return None

        # db = get_db_client()
        # metrics = await db.fetch_multiple_symbols_metrics()
        # return metrics

    async def get_recent_alerts(self, limit: int = 50):
        alerts = await self.redis.get_alerts('all', limit)
        return alerts if alerts else None

    # TODO: understand where this value is coming from ??
    # what's summary stats referring to vs windowed aggregates
    async def fetch_summary_stats(self, symbol: str, window: str = '5m') -> dict:
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