"""PostgreSQL/TimescaleDB client."""

# timescale DB: https://github.com/timescale/timescaledb
# asyncpg: https://magicstack.github.io/asyncpg/current/usage.html

import asyncpg
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger
from src.config import settings
from src.common.models import OrderBookMetrics

# TODO: Implement database client
# - retry logic on failures
# - Error handling

class DatabaseClient:
    """Async PostgreSQL/TimescaleDB client.
    
    Uses connection pooling for efficient database access.
    
    Example:
        >>> db = DatabaseClient()
        >>> await db.connect()
        >>> await db.insert_metrics(metrics_dict)
        >>> await db.close()
    """

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create connection pool.
        
        Reference: https://magicstack.github.io/asyncpg/current/api/index.html#asyncpg.create_pool
        """
        logger.info(f"Connecting to database at {settings.postgres_host}:{settings.postgres_port}")
        
        try:
            self.pool = await asyncpg.create_pool(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=settings.postgres_user, 
                password=settings.postgres_password,
                database=settings.postgres_db,
                min_size=5,
                max_size=20,
                max_inactive_connection_lifetime=300, # 5 mins
                command_timeout=60
            )

            # Test connection
            async with self.pool.acquire() as conn:
                version = await conn.fetchval('SELECT version()')
                logger.info(f"Connected to database: {version}")
                
                # Check TimescaleDB extension
                has_timescale = await conn.fetchval(
                    "SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'"
                )
                if has_timescale:
                    logger.info("✓ TimescaleDB extension detected")
        
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info('Database connection pool closed')
            self.pool = None

    async def insert_metrics(self, metrics: Dict) -> None:
        """Insert order book metrics.
        
        Args:
            metrics: Dictionary with metric data
            
        Reference: https://magicstack.github.io/asyncpg/current/usage.html#inserting-data
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO orderbook_metrics (
                    time, symbol, mid_price, best_bid, best_ask,
                    imbalance_ratio, weighted_imbalance,
                    bid_volume, ask_volume, total_volume,
                    spread_bps, spread_abs,
                    vtob_ratio, best_bid_volume, best_ask_volume,
                    imbalance_velocity, depth_levels, update_id
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18
                )
            """,
                metrics['timestamp'],
                metrics['symbol'],
                metrics['mid_price'],
                metrics['best_bid'],
                metrics['best_ask'],
                metrics['imbalance_ratio'],
                metrics.get('weighted_imbalance'),
                metrics['bid_volume'],
                metrics['ask_volume'],
                metrics.get('total_volume'),
                metrics['spread_bps'],
                metrics.get('spread_abs'),
                metrics.get('vtob_ratio'),
                metrics.get('best_bid_volume'),
                metrics.get('best_ask_volume'),
                metrics.get('imbalance_velocity'),
                metrics.get('depth_levels'),
                metrics.get('update_id')
            )

    async def insert_alert(self, alert: Dict) -> None:
        """Insert alert.
        
        Args:
            alert: Dictionary with alert data
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO orderbook_alerts (
                    time, symbol, alert_type, severity, message,
                    metric_value, threshold_value, side,
                    mid_price, imbalance_ratio
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                alert['timestamp'],
                alert['symbol'],
                alert['alert_type'],
                alert['severity'],
                alert['message'],
                alert['metric_value'],
                alert.get('threshold_value'),
                alert.get('side'),
                alert.get('mid_price'),
                alert.get('imbalance_ratio')
            )

    async def fetch_recent_metrics(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Fetch recent metrics for a symbol.
        
        Args:
            symbol: Trading symbol
            limit: Maximum number of records
            
        Returns:
            List of metric dictionaries
            
        Reference: https://magicstack.github.io/asyncpg/current/usage.html#querying-data
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT time, symbol, mid_price, imbalance_ratio,
                       weighted_imbalance, spread_bps, bid_volume, ask_volume
                FROM orderbook_metrics
                WHERE symbol = $1
                ORDER BY time DESC
                LIMIT $2
            """, symbol, limit)
            return [dict(row) for row in rows]

    async def fetch_time_series(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Fetch time series data for a symbol.
        
        Args:
            symbol: Trading symbol
            start_time: Start timestamp
            end_time: End timestamp
            
        Returns:
            List of metric dictionaries
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT time, symbol, mid_price, imbalance_ratio,
                       weighted_imbalance, spread_bps
                FROM orderbook_metrics
                WHERE symbol = $1 AND time BETWEEN $2 AND $3
                ORDER BY time ASC
            """, symbol, start_time, end_time)
            
            return [dict(row) for row in rows]

    async def fetch_alerts(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Fetch recent alerts.
        
        Args:
            symbol: Optional symbol filter
            limit: Maximum number of records
            
        Returns:
            List of alert dictionaries
        """
        async with self.pool.acquire() as conn:
            if symbol:
                rows = await conn.fetch("""
                    SELECT time, symbol, alert_type, severity, message,
                           metric_value, threshold_value
                    FROM orderbook_alerts
                    WHERE symbol = $1
                    ORDER BY time DESC
                    LIMIT $2
                """, symbol, limit)
            else:
                rows = await conn.fetch("""
                    SELECT time, symbol, alert_type, severity, message,
                           metric_value, threshold_value
                    FROM orderbook_alerts
                    ORDER BY time DESC
                    LIMIT $1
                """, limit)
            
            return [dict(row) for row in rows]

    async def get_statistics(self, symbol: str, hours: int = 1) -> Dict:
        """Get statistical summary for a symbol.
        
        Args:
            symbol: Trading symbol
            hours: Number of hours to look back
            
        Returns:
            Dictionary with statistics
        """
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    AVG(weighted_imbalance) as avg_imbalance,
                    STDDEV(weighted_imbalance) as stddev_imbalance,
                    AVG(spread_bps) as avg_spread,
                    AVG(total_volume) as avg_volume,
                    COUNT(*) as sample_count
                FROM orderbook_metrics
                WHERE symbol = $1
                    AND time >= NOW() - ($2::text || ' hours')::interval
            """, symbol, hours)
            # AND time >= NOW() - INTERVAL '$2 hours'

            return dict(stats) if stats else {}

    async def health_check(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def get_pool_stats(self) -> Dict:
        """Get connection pool statistics.
        
        Returns:
            Dictionary with pool stats
        """
        if not self.pool:
            return {"status": "not_connected"}
        
        return {
            "size": self.pool.get_size(),
            "free": self.pool.get_idle_size(),
            "max_size": self.pool.get_max_size(),
            "min_size": self.pool.get_min_size(),
        }
