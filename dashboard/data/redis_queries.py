"""Redis data fetching for dashboard."""
import json
from typing import Dict, List, Optional
import streamlit as st
from loguru import logger

from src.common.redis_client import RedisClient

@st.cache_resource
def get_redis_client():
    """Get or create Redis client."""
    if 'redis_client' not in st.session_state:
        client = RedisClient()
        import asyncio
        try:
            asyncio.run(client.connect())
            st.session_state.redis_client = client
            logger.info("✓ Redis client connected")
        except Exception as e:
            logger.error(f"Failed to connect Redis client: {e}")
            raise
    return st.session_state.redis_client


class RedisQueries:

    def __init__(self):
        self.redis = get_redis_client()
    
    # ===== Metrics Queries ===== #

    async def get_latest_metrics(self, symbol: str) -> Optional[Dict]:
        try:
            cached = await self.redis.get_cached_metrics(symbol)
            if cached:
                logger.debug(f"Cache HIT: latest metrics for {symbol}")
                return cached
            
            logger.debug(f"Cache MISS: latest metrics for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching metrics for {symbol}: {e}")
            return None

    async def get_multiple_metrics(self, symbols: List[str]) -> Dict[str, Optional[Dict]]:
        """Get latest metrics for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Dict mapping symbol -> metrics (or None if not cached)
        """
        try:
            result = await self.redis.get_multiple_metrics(symbols)
            
            # Log cache hit rate
            hits = sum(1 for v in result.values() if v is not None)
            logger.debug(f"Multi-metric cache: {hits}/{len(symbols)} hits")
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching multiple metrics: {e}")
            return {symbol: None for symbol in symbols}

    # ===== Alert Queries ===== #

    async def get_recent_alerts(
        self,
        symbol: Optional[str] = None,
        limit: int = 50
    )-> Optional[List[Dict]]:
        try:
            symbol_key = symbol if symbol else 'all'
            alerts = await self.redis.get_alerts(symbol_key, limit)
            
            if alerts:
                logger.debug(f"Cache HIT: {len(alerts)} alerts for {symbol_key}")
                return alerts
            
            logger.debug(f"Cache MISS: alerts for {symbol_key}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching alerts: {e}")
            return None

    # ===== Windowed Statistics Queries ===== #

    async def get_windowed_metrics(
        self,
        symbol: str,
        window_type: str = '5m_sliding',
        limit: int = 12
    ) -> Optional[List[Dict]]:
        """Get windowed aggregates from Redis sorted set.
        
        Args:
            symbol: Trading symbol
            window_type: Window type ('1m_tumbling' or '5m_sliding')
            limit: Number of windows to retrieve
            
        Returns:
            List of windowed metrics or None if not cached
        """
        try:
            windows = await self.redis.get_windowed(symbol, window_type, limit)
            
            if windows:
                logger.debug(f"Cache HIT: {len(windows)} windows for {symbol} ({window_type})")
                return windows
            
            logger.debug(f"Cache MISS: windowed for {symbol} ({window_type})")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching windowed metrics: {e}")
            return None

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
        windows = await self.get_windowed_metrics(symbol, window_type, limit=1)
        return windows[0] if windows else None

    async def get_summary_stats(
        self,
        symbol: str,
        window: str = '5m'
    ) -> Optional[Dict]:
        """Get pre-computed summary statistics.
        
        These are computed by redis_consumer from windowed aggregates.
        
        Args:
            symbol: Trading symbol
            window: Time window ('1m' or '5m')
            
        Returns:
            Stats dict or None if not cached
        """
        try:
            cached = await self.redis.get_cached_statistics(symbol, window)
            
            if cached:
                logger.debug(f"Cache HIT: summary stats for {symbol} ({window})")
                return cached
            
            logger.debug(f"Cache MISS: summary stats for {symbol} ({window})")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching summary stats: {e}")
            return None

    # ===== Change Calculation Queries ===== #

    async def get_metric_changes(self, symbol: str) -> Optional[Dict]:
        """Get pre-computed percentage changes for metrics.
        
        These should be cached by redis_consumer when processing metrics.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict with percentage changes or None
            
        Example:
            {
                'price_pct': 2.3,
                'imbalance_pct': 15.2,
                'spread_pct': -8.5,
                'volume_pct': 12.1,
                'comparison_period': 'recent'
            }
        """
        try:
            key = f"orderbook:metrics:changes:{symbol}"
            cached = await self.redis.client.get(key)
            
            if cached:
                logger.debug(f"Cache HIT: metric changes for {symbol}")
                return json.loads(cached)
            
            logger.debug(f"Cache MISS: metric changes for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching metric changes: {e}")
            return None

    # ===== Cache Management ===== #

    async def get_cached_symbols(self) -> List[str]:
        """Get list of all symbols with cached data.
        
        Returns:
            List of symbols with active cache entries
        """
        try:
            symbols = await self.redis.get_all_cached_symbols()
            logger.debug(f"Found {len(symbols)} cached symbols")
            return symbols
            
        except Exception as e:
            logger.error(f"Error fetching cached symbols: {e}")
            return []

    async def check_cache_health(self) -> Dict:
        """Check Redis cache health and stats.
        
        Returns:
            Dict with cache health information
        """
        try:
            is_healthy = await self.redis.health_check()
            info = await self.redis.get_info()
            
            return {
                'healthy': is_healthy,
                'connected': self.redis.is_connected(),
                **info
            }
            
        except Exception as e:
            logger.error(f"Error checking cache health: {e}")
            return {
                'healthy': False,
                'connected': False,
                'error': str(e)
            }

    # ===== Utility Methods ===== #

    async def clear_symbol_cache(self, symbol: str) -> bool:
        """Clear all cached data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if successful
        """
        try:
            count = await self.redis.clear_symbol_cache(symbol)
            logger.info(f"Cleared {count} cache entries for {symbol}")
            return count > 0
            
        except Exception as e:
            logger.error(f"Error clearing cache for {symbol}: {e}")
            return False
            