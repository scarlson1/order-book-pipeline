"""Redis client wrapper."""

from typing import Dict, List, Optional
import redis.asyncio as redis
from loguru import logger
import json
from src.config import settings

class RedisClient:
    """Async Redis client for caching order book data.
    
    Uses connection pooling for efficient Redis access.
    All data is stored as JSON with automatic TTL (time-to-live).
    
    Key Naming Convention:
        orderbook:{symbol}:latest       - Latest metrics
        orderbook:{symbol}:snapshot     - Latest order book snapshot
        orderbook:alerts:{symbol}       - Recent alerts list
        orderbook:stats:{symbol}        - Statistical summary
    
    Documentation:
    - redis.asyncio: https://redis-py.readthedocs.io/en/stable/examples/asyncio_examples.html
    
    Example (Context Manager - Recommended):
        >>> async with RedisClient() as redis_client:
        ...     await redis_client.cache_metrics('BTCUSDT', metrics, ttl=60)
        ...     data = await redis_client.get_cached_metrics('BTCUSDT')
    
    Example (Manual):
        >>> client = RedisClient()
        >>> await client.connect()
        >>> try:
        ...     await client.cache_metrics('BTCUSDT', metrics)
        ... finally:
        ...     await client.close()
    """

    def __init__(self) -> None:
        self.client: Optional[redis.Redis] = None
        self._closed = False

    async def connect(self):
        # self.client = redis.from_url(settings.redis_url())
        if self.client is not None:
            logger.warning("Redis client already connected")
            return

        logger.info(f"Connecting to Redis at {settings.redis_host}:{settings.redis_port}")

        try:
            # Create connection pool
            pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=0,
                decode_responses=True,  # Automatically decode bytes to strings
                max_connections=20,
                socket_keepalive=True,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            
            # Create client with pool
            self.client = redis.Redis(connection_pool=pool)
            
            # Test connection
            await self.client.ping()
            logger.info("✓ Connected to Redis")
            
            self._closed = False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self):
        """Close Redis connection gracefully.
        
        Reference: https://redis-py.readthedocs.io/en/stable/connections.html#closing-connections
        """
        if self._closed:
            logger.debug("Redis already closed")
            return
        
        if self.client:
            try:
                await self.client.aclose()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis: {e}")
            finally:
                self.client = None
                self._closed = True

    # ===== Health & status ===== #

    def is_connected(self) -> bool:
        """Check if Redis is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.client is not None and not self._closed
    
    async def health_check(self) -> bool:
        """Check Redis health.
        
        Returns:
            True if healthy, False otherwise
            
        Reference: https://redis.io/commands/ping/
        """
        if not self.is_connected():
            return False
        
        try:
            response = await self.client.ping()
            return response is True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    async def get_info(self) -> Dict:
        """Get Redis server information.
        
        Returns:
            Dictionary with server info
            
        Reference: https://redis.io/commands/info/
        """
        if not self.is_connected():
            return {}
        
        try:
            info = await self.client.info()
            return {
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_connections_received': info.get('total_connections_received'),
                'keyspace_hits': info.get('keyspace_hits'),
                'keyspace_misses': info.get('keyspace_misses'),
            }
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")
            return {}

    # ===== Name helpers ===== #

    @staticmethod
    def _metrics_key(symbol: str) -> str:
        """Generate key for latest metrics."""
        return f"orderbook:{symbol.upper()}:latest"
    
    @staticmethod
    def _snapshot_key(symbol: str) -> str:
        """Generate key for order book snapshot."""
        return f"orderbook:{symbol.upper()}:snapshot"
    
    @staticmethod
    def _alerts_key(symbol: str) -> str:
        """Generate key for alerts list."""
        return f"orderbook:alerts:{symbol.upper()}"
    
    @staticmethod
    def _stats_key(symbol: str, window: str) -> str:
        """Generate key for statistics."""
        return f"orderbook:stats:{window.lower()}:{symbol.upper()}"

    @staticmethod
    def _windowed_key(symbol: str, window: str) -> str:
        """Generate key for statistics."""
        return f"orderbook:windowed:{window.lower()}:{symbol.upper()}"

    # ===== Metrics Caching ===== #

    async def insert_metrics(
        self,
        symbol: str,
        metrics: Dict,
        ttl: int = 60
    ) -> bool:
        """Cache latest metrics for a symbol.
        
        Args:
            symbol: Trading symbol
            metrics: Metrics dictionary
            ttl: Time-to-live in seconds (default: 60)
            
        Returns:
            True if successful, False otherwise
            
        Reference: https://redis.io/commands/setex/
        """
        if not self.is_connected():
            logger.error("Redis not connected")
            return False

        try:
            key = self._metrics_key(symbol)

            data = json.dumps(metrics, default=str)

            await self.client.setex(key, ttl, data)

            logger.debug(f'Cached metrics for {symbol} (TTL: {ttl}s)')
            return True

        except Exception as e:
            logger.error(f'Failed to cache metrics for {symbol}: {e}')
            return False

    async def get_cached_metrics(self, symbol: str) -> Optional[Dict]:
        """Get cached metrics for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Metrics dictionary or None if not found
        """
        if not self.is_connected():
            return None
        
        try:
            key = self._metrics_key(symbol)
            data = await self.client.get(key)

            if data:
                return json.loads(data)

            logger.debug(f'Cache miss for {symbol}')
            return None

        except Exception as e:
            logger.error(f'Failed to get cached metrics for {symbol}: {e}')
            return None
    
    # ===== Order Book Snapshot Caching ===== #

    async def cache_orderbook(
        self,
        symbol: str,
        orderbook: Dict,
        ttl: int = 30
    ) -> bool:
        """Cache order book snapshot.
        
        Args:
            symbol: Trading symbol
            orderbook: Order book data
            ttl: Time-to-live in seconds (default: 30)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            key = self._snapshot_key(symbol)
            data = json.dumps(orderbook, default=str)
            await self.client.setex(key, ttl, data)
            
            logger.debug(f"Cached orderbook for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache orderbook for {symbol}: {e}")
            return False

    async def get_cached_orderbook(self, symbol: str) -> Optional[Dict]:
        """Get cached order book snapshot.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Order book dictionary or None
        """
        if not self.is_connected():
            return None
        
        try:
            key = self._snapshot_key(symbol)
            data = await self.client.get(key)
            
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached orderbook for {symbol}: {e}")
            return None
    
    # ===== Alert Caching (List) ===== #

    async def add_alert(
        self,
        symbol: str,
        alert: Dict,
        max_alerts: int = 100
    ) -> bool:
        """Add alert to symbol's alert list.
        
        Uses Redis list to maintain recent alerts.
        
        Args:
            symbol: Trading symbol
            alert: Alert dictionary
            max_alerts: Maximum alerts to keep (default: 100)
            
        Returns:
            True if successful, False otherwise
            
        Reference: https://redis.io/commands/lpush/
        """
        if not self.is_connected():
            return False

        try:
            key = self._alerts_key(symbol)
            data = json.dumps(alert, default=str)
            timestamp = alert['timestamp'] # parse_timestamp(alert['timestamp'])

            # use zadd for sorted list
            # Add to sorted set
            await self.client.zadd(
                key,
                {data: timestamp}
            )
            
            # Also add to "all" feed
            await self.client.zadd(
                self._alerts_key('all'),
                {data: timestamp}
            )
            
            # Trim to last 100 (prevent unbounded growth)
            await self.client.zremrangebyrank(
                key,
                0, -max_alerts  # Keep only last 100
            )
            await self.client.zremrangebyrank(
                self._alerts_key('all'),
                0, -max_alerts  # Keep only last 100
            )

            # await self.client.lpush(key, data)

            # await self.client.ltrim(key, 0, max_alerts - 1)

            # await self.client.expire(key, 3600) # 1 hour

            logger.debug(f'Added alert for {symbol}')
            return True

        except Exception as e:
            logger.error(f'Failed to add alert for {symbol}: {e}')
            return False

    async def get_alerts(
        self,
        symbol: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get recent alerts for a symbol.
        
        Args:
            symbol: Trading symbol
            limit: Maximum number of alerts to return
            
        Returns:
            List of alert dictionaries
            
        Reference: https://redis.io/commands/lrange/
        """
        if not self.is_connected():
            return []

        try:
            key = self._alerts_key(symbol)

            # alerts = await self.client.lrange(key, 0, limit - 1)

            # return [json.loads(alert) for alert in alerts]
            
            
            # Redis Sorted Set: scores are timestamps, values are alert JSON
            # returns: list[tuple[ts, alert]]
            # e.g. [[timestamp, { alert_type: 'VELOCITY_SPIKE', symbol: 'BTCUSDT', ... }]]
            # https://redis.io/docs/latest/commands/zrevrange/
            # deprecated - TODO update redis to current version (v5 -> v8) - replace zrevrange with "ZRANGE with the REV argument"
            alerts = await self.client.zrevrange(
                key,
                0,
                limit - 1,
                withscores=True
            )

            if alerts:
                return [
                    {**json.loads(alert), 'timestamp': score }
                    for alert, score in alerts
                ]
        
        except Exception as e:
            logger.error(f'failed to get alerts for {symbol}: {e}')
            return []

    # ===== Windowed Metrics Caching ===== #

    async def add_windowed(
        self,
        symbol: str,
        window_type: str,
        window_data: Dict,
        ttl: int = 3600
    ) -> bool:
        """Add windowed metrics to Redis.
        
        Args:
            symbol: Trading symbol
            window_type: Window type ('1m_tumbling' or '5m_sliding')
            window_data: Windowed metrics dictionary with window_end timestamp
            ttl: Time-to-live in seconds (default: 1 hour)
            
        Reference: https://redis.io/commands/zadd/
        """
        if not self.is_connected():
            logger.error("Redis not connected")
            return False

        try:
            # Get window_end timestamp for sorting
            window_end = window_data.get('window_end')
            if not window_end:
                logger.error("window_data missing 'window_end' field")
                return False

            # Convert to float for sorted set score
            if isinstance(window_end, str):
                from datetime import datetime
                window_end = datetime.fromisoformat(window_end.replace('Z', '+00:00'))
            score = window_end.timestamp() if hasattr(window_end, 'timestamp') else float(window_end)

            # Key for sorted set (history)
            sorted_set_key = self._windowed_key(symbol, window_type)
            
            # latest_key = self._windowed_latest_key(symbol, window_type)

            # Serialize data
            data = json.dumps(window_data, default=str)

            # Use pipeline for atomic operations
            async with self.client.pipeline() as pipe:
                # Add to sorted set (score = window_end timestamp)
                pipe.zadd(sorted_set_key, {data: score})
                
                # Set latest key
                # pipe.set(latest_key, data, ex=ttl)
                
                # Trim sorted set to keep only last 100 windows
                # Remove oldest entries (lowest scores)
                pipe.zremrangebyrank(sorted_set_key, 0, -101)
                
                # Set TTL on sorted set key
                pipe.expire(sorted_set_key, ttl)
                
                await pipe.execute()

            logger.debug(f'Added windowed metrics for {symbol} ({window_type})')
            return True

        except Exception as e:
            logger.error(f'Failed to add windowed metrics for {symbol}: {e}')
            return False

    async def get_windowed(
        self,
        symbol: str,
        window_type: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get windowed metrics for a symbol.
        
        Args:
            symbol: Trading symbol
            window_type: Window type ('1m_tumbling' or '5m_sliding')
            limit: Maximum number of windows to return (default: 10)
            
        Returns:
            List of windowed metrics dictionaries, most recent first
            
        Reference: https://redis.io/commands/zrevrange/
        """
        if not self.is_connected():
            return []

        try:
            key = self._windowed_key(symbol, window_type)

            # Get most recent windows (highest scores = most recent)
            results = await self.client.zrevrange(
                key,
                0,
                limit - 1,
                withscores=True
            )

            if results:
                return [
                    {**json.loads(data), 'window_end_ts': score}
                    for data, score in results
                ]

            logger.debug(f'No windowed data found for {symbol} ({window_type})')
            return []

        except Exception as e:
            logger.error(f'Failed to get windowed metrics for {symbol}: {e}')
            return []
    
    # ===== Statistics Caching ===== #

    async def cache_statistics(
        self,
        symbol: str,
        stats: Dict,
        ttl: int = 300
    ) -> bool:
        """Cache statistical summary.
        
        Args:
            symbol: Trading symbol
            stats: Statistics dictionary
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False

        window_type = stats.get('window_type')
        window = '5m' if window_type == '5m_sliding' else '1m' if window_type == '1m_tumble' else None
        if not window:
            logger.warning('statistics message missing "window_type" field')
            return False

        try:
            key = self._stats_key(symbol, window)
            await self.client.setex(key, ttl, json.dumps(stats, default=str))

            logger.debug(f'Cached stats for {symbol}')
            return True

        except Exception as e:
            logger.error(f'Failed to cache stats for {symbol}: {e}')
            return False

    async def get_cached_statistics(self, symbol: str, window: str) -> Optional[Dict]:
        """Get cached statistics.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Statistics dictionary or None
        """
        if not self.is_connected():
            return None
        
        try:
            key = self._stats_key(symbol, window)
            data = await self.client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f'Failed to get cached stats for {symbol}')
            return None

    # ===== Batch Operations ===== #

    async def cache_multiple_metrics(
        self,
        metrics_list: List[Dict],
        ttl: int = 60
    ) -> int:
        """Cache metrics for multiple symbols at once.
        
        Args:
            metrics_list: List of metrics dictionaries (each must have 'symbol' key)
            ttl: Time-to-live in seconds
            
        Returns:
            Number of successfully cached items
            
        Reference: https://redis.io/commands/mset/
        """
        if not self.is_connected():
            return 0

        success_count = 0

        try:
            async with self.client.pipeline() as pipe:
                for metrics in metrics_list:
                    symbol = metrics.get('symbol')
                    if not symbol:
                        continue

                    key = self._metrics_key(symbol)
                    data = json.dumps(metrics, default=str)
                    pipe.setex(key, ttl, data)

                # execute all at once
                results = await pipe.execute()
                success_count = sum(1 for r in results if r)
            
            logger.debug(f'Batch cached {success_count}/{len(metrics_list)} metrics')
            return success_count

        except Exception as e:
            logger.error(f'Failed batch cache: {e}')
            return success_count

    async def get_multiple_metrics(
        self,
        symbols: List[str]
    ) -> Dict[str, Optional[Dict]]:
        """Get cached metrics for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Dictionary mapping symbol to metrics (or None if not cached)
            
        Reference: https://redis.io/commands/mget/
        """
        if not self.is_connected():
            return {symbol: None for symbol in symbols}

        try:
            keys = [self._metrics_key(symbol) for symbol in symbols]

            values = await self.client.mget(keys)

            result = {}
            for symbol, value in zip(symbols, values):
                if value:
                    result[symbol] = json.loads(value)
                else:
                    result[symbol] = None

            return result

        except Exception as e:
            logger.error(f'Failed batch get: {e}')
            return {symbol: None for symbol in symbols}

    # ===== Utility Methods ===== #

    async def delete_key(self, key: str) -> bool:
        """Delete a specific key.
        
        Args:
            key: Redis key to delete
            
        Returns:
            True if deleted, False otherwise
            
        Reference: https://redis.io/commands/del/
        """
        if not self.is_connected():
            return False

        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f'Failed to delete key {key}: {e}')
            return False

    async def clear_symbol_cache(self, symbol: str) -> int:
        """Clear all cached data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Number of keys deleted
        """
        if not self.is_connected():
            return 0

        try:
            pattern = f'orderbook:*:{symbol.upper()}*'
            keys=[]

            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            # delete all
            if keys:
                deleted = await self.client.delete(*keys)
                logger.info(f'cleared {deleted} cached items for {symbol}')
                return deleted
            
            return 0
        
        except Exception as e:
            logger.error(f'Failed to clear cache for {symbol}: {e}')
            return 0

    async def get_all_cached_symbols(self) -> List[str]:
        """Get list of all symbols with cached data.
        
        Returns:
            List of trading symbols
            
        Reference: https://redis.io/commands/scan/
        """
        if not self.is_connected():
            return []

        try:
            symbols = set()
            async for key in self.client.scan_iter(match="orderbook:*:latest"):
                parts = key.split(':')
                if len(parts) >= 2:
                    symbols.add(parts[1])

            return sorted(list(symbols))
        
        except Exception as e:
            logger.error(f'Failed to get cached symbols: {e}')
            return []

        # ===== Context Manager Support =====
    
    # ===== Context Switching ===== #

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
