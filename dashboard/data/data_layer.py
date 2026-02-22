import datetime
from typing import Optional, Dict, List
from loguru import logger

from dashboard.data.db_queries import DatabaseQueries
from dashboard.data.redis_queries import RedisQueries

# TODO: prior to deploying, verify secrets are handled correctly
# https://docs.streamlit.io/get-started/fundamentals/advanced-concepts

class DataLayer:
    """
    Unified interface that handles Redis/DB decision-making.
    
    Dashboard code doesn't need to know about caching strategy.
    """
    
    def __init__(self):
        self.redis = RedisQueries()
        self.db = DatabaseQueries()

    # ===== Real-time Metrics ===== #
    
    async def get_latest_metrics(self, symbol: str) -> Optional[Dict]:
        """Try Redis, fallback to DB, populate cache."""
        # Try Redis cache first
        cached = await self.redis.get_latest_metrics(symbol)
        if cached:
            return cached
        
        # Fallback to database
        logger.info(f"Cache miss for {symbol}, querying database")
        db_result = await self.db.fetch_latest_metrics(symbol)
        
        if db_result:
            await self.redis.redis.insert_metrics(symbol, db_result, ttl=60)
        
        return db_result

    async def get_latest_metrics_with_changes(self, symbol: str) -> Optional[Dict]:
        """Get latest metrics with percentage changes.
        
        This is the PRIMARY method for dashboard metric cards.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            {
                'current': {...},      # Current metrics
                'changes': {           # Percentage changes
                    'price_pct': 2.3,
                    'imbalance_pct': 15.2,
                    'spread_pct': -8.5,
                    'volume_pct': 12.1
                },
                'comparison': {...},    # Previous period values
                'comparison_period': '24h'
            }
        """
        # Try to get pre-computed changes from Redis
        cached_changes = await self.redis.get_metric_changes(symbol)
        if cached_changes:
            # Get current metrics
            current = await self.get_latest_metrics(symbol)
            if current:
                return {
                    'current': current,
                    'changes': cached_changes,
                    'comparison_period': cached_changes.get('comparison_period', 'recent')
                }
        
        # Fallback: compute from database
        logger.info(f"Computing changes from DB for {symbol}")
        return await self._compute_changes_from_db(symbol)

    async def _compute_changes_from_db(self, symbol: str) -> Optional[Dict]:
        """Compute percentage changes by querying database.
        
        Falls back to this when Redis cache doesn't have pre-computed changes.
        """
        # Get current metrics
        current = await self.db.fetch_latest_metrics(symbol)
        if not current:
            return None
        
        # Get 24h price change
        price_change = await self.db.compute_price_change_24h(symbol)
        
        # Get metric deviations from windowed average
        metric_deviations = await self.db.compute_metric_vs_windowed(symbol)
        
        # Combine all changes
        changes = {}
        
        if price_change:
            changes['price_pct'] = price_change['change_pct']
        
        if metric_deviations:
            changes['imbalance_pct'] = metric_deviations['deviation_pct']['imbalance']
            changes['spread_pct'] = metric_deviations['deviation_pct']['spread']
            changes['volume_pct'] = metric_deviations['deviation_pct']['volume']
        
        return {
            'current': current,
            'changes': changes,
            'comparison': {
                'price': price_change,
                'metrics': metric_deviations
            },
            'comparison_period': '24h (price) / 5m avg (metrics)'
        }

    async def get_multiple_symbols(self, symbols: List[str]) -> Dict[str, Optional[Dict]]:
        """Get latest metrics for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Dict mapping symbol -> metrics
        """
        # Try Redis batch get first
        cached = await self.redis.get_multiple_metrics(symbols)
        
        # For any cache misses, query DB
        missing_symbols = [s for s, v in cached.items() if v is None]
        
        if missing_symbols:
            logger.info(f"Fetching {len(missing_symbols)} symbols from DB")
            db_results = await self.db.fetch_multiple_symbols_latest()
            
            # Merge DB results into cached dict
            for result in db_results:
                symbol = result['symbol']
                if symbol in cached and cached[symbol] is None:
                    cached[symbol] = result
        
        return cached

    # ===== Time Series Data ===== #
    
    async def get_time_series(
        self,
        symbol: str,
        start: datetime.datetime,
        end: datetime.datetime,
        interval: str = '5m'
    ) -> List[Dict]:
        """Get time series data for charting.
        
        Always queries database (no caching for historical data).
        
        Args:
            symbol: Trading symbol
            start: Start timestamp
            end: End timestamp
            interval: Data interval ('1m', '5m', '1h', '1d')
            
        Returns:
            List of time-series points
        """
        return await self.db.fetch_time_series(symbol, start, end, interval)

    async def get_time_series_last_n_hours(
        self,
        symbol: str,
        hours: int = 1,
        interval: str = '5m'
    ) -> List[Dict]:
        """Get time series for the last N hours.
        
        Convenience method for common dashboard use case.
        
        Args:
            symbol: Trading symbol
            hours: Number of hours to look back
            interval: Data interval
            
        Returns:
            List of time-series points
        """
        end = datetime.datetime.now(datetime.timezone.utc)
        start = end - datetime.timedelta(hours=hours)
        return await self.get_time_series(symbol, start, end, interval)

    # ===== Alerts ===== #

    async def get_recent_alerts(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
        since: Optional[datetime.datetime] = None
    ) -> List[Dict]:
        """Get recent alerts (Redis first, DB fallback).
        
        Args:
            symbol: Trading symbol (None for all)
            limit: Maximum number of alerts
            since: Only alerts after this timestamp
            
        Returns:
            List of alert dicts
        """
        # If no time filter, try Redis cache
        if since is None:
            cached = await self.redis.get_recent_alerts(symbol, limit)
            if cached:
                return cached
        
        # Fallback to database
        logger.info(f"Fetching alerts from DB (since={since})")
        return await self.db.fetch_alerts(symbol, limit, since)

    # ===== Windowed Aggregates ===== #

    async def get_windowed_aggregates(
        self,
        symbol: str,
        window_type: str = '5m_sliding',
        limit: int = 12
    ) -> List[Dict]:
        """Get windowed aggregates (hybrid Redis/DB).
        
        Tries Redis for latest, DB for history, deduplicates.
        
        Args:
            symbol: Trading symbol
            window_type: Window type ('1m_tumbling' or '5m_sliding')
            limit: Number of windows to return
            
        Returns:
            List of windowed metrics (most recent first)
        """
        # Get from Redis (latest windows)
        redis_windows = await self.redis.get_windowed_metrics(symbol, window_type, limit)
        
        # Get from DB (historical windows)
        db_windows = await self.db.fetch_windowed_aggregates(symbol, window_type, limit)
        
        # Combine and deduplicate
        results = []
        seen_timestamps = set()
        
        # Add Redis results first (most recent)
        if redis_windows:
            for window in redis_windows:
                window_end = window['window_end']
                if window_end not in seen_timestamps:
                    results.append(window)
                    seen_timestamps.add(window_end)
        
        # Add DB results (fill in gaps)
        if db_windows:
            for window in db_windows:
                window_end = window['window_end']
                if window_end not in seen_timestamps:
                    results.append(window)
                    seen_timestamps.add(window_end)
        
        # Return limited results
        return results[:limit]

    async def get_latest_windowed(
        self,
        symbol: str,
        window_type: str = '5m_sliding'
    ) -> Optional[Dict]:
        """Get the most recent windowed aggregate.
        
        Args:
            symbol: Trading symbol
            window_type: Window type
            
        Returns:
            Latest window dict or None
        """
        # Try Redis first
        cached = await self.redis.get_latest_windowed(symbol, window_type)
        if cached:
            return cached
        
        # Fallback to DB
        return await self.db.fetch_latest_windowed(symbol, window_type)

    # ===== Summary Statistics ===== #

    async def get_summary_stats(self, symbol: str) -> Optional[Dict]:
        """
        Get summary statistics (Redis-only, pre-computed).
        These are computed by redis_consumer from windowed aggregates.
        """
        return await self.redis.get_summary_stats(symbol, window='5m')

    # ===== System Health ===== #

    async def health_check(self) -> Dict:
        """Check health of all data sources.
        
        Returns:
            Dict with health status of Redis, DB, and overall system
        """
        cache_health = await self.redis.check_cache_health()
        db_health = await self.db.health_check()
        
        return {
            'overall': cache_health['healthy'] and db_health,
            'redis': cache_health,
            'database': {
                'healthy': db_health,
                'pool': await self.db.get_connection_stats()
            }
        }

    async def get_cached_symbols(self) -> List[str]:
        """Get list of symbols with active data.
        
        Returns:
            List of trading symbols
        """
        return await self.redis.get_cached_symbols()