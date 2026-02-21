import datetime

from dashboard.data.db_queries import DatabaseQueries
from dashboard.data.redis_queries import RedisQueries


class DataLayer:
    """
    Unified interface that handles Redis/DB decision-making.
    
    Dashboard code doesn't need to know about caching strategy.
    """
    
    def __init__(self):
        self.redis = RedisQueries()
        self.db = DatabaseQueries()
    
    async def get_latest_metrics(self, symbol: str):
        """Try Redis, fallback to DB, populate cache."""
        if symbol:
            cached = self.redis.get_latest_metrics(symbol)
            if cached:
                return cached

            metrics = await self.db.get_metrics(symbol)

            return metrics
    
    async def get_time_series(self, symbol: str, start: datetime, end: datetime):
        """Always query DB (no caching)."""
        data = await self.db.fetch_time_series(symbol, start_time=start, end_time=end, interval='5m')
        return data

    async def get_recent_alerts(self, symbol: str | None, limit: int = 50, since: datetime = None):
        """Try Redis sorted set, fallback to DB."""
        cached = await self.redis.get_recent_alerts()
        if cached:
            return cached

        return await self.db.fetch_alerts(symbol, limit, since)

    async def get_windowed(self, symbol: str, window_type: str = '5m_sliding', limit: int = 12):
        return await self.db.fetch_windowed_aggregates(symbol, window_type, limit)

    async def get_windowed_aggregates(self, symbol: str, window_type: str = '5m_sliding', limit: int = 12): # Last hour of 5-min windows
        return await self.db.fetch_windowed_aggregates(symbol, window_type, limit)

    async def get_summary_stats(self, symbol: str):
        return await self.redis.get_summary_stats(symbol)

