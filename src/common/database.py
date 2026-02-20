"""PostgreSQL/TimescaleDB client."""

# timescale DB: https://github.com/timescale/timescaledb
# asyncpg: https://magicstack.github.io/asyncpg/current/usage.html

import asyncpg
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger
from src.config import settings

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

    async def insert_batch_metrics(self, metrics: list[dict]) -> None:
        """Insert batch of order book metrics efficiently.
        
        Uses asyncpg's copy_records_to_table for optimal bulk insert performance
        (10-100x faster than individual inserts via COPY protocol).
        
        Args:
            metrics: List of metric dictionaries with all required fields
            
        Reference: https://magicstack.github.io/asyncpg/current/api/index.html#asyncpg.Connection.copy_records_to_table
        """
        if not metrics:
            return
        
        # Prepare records as tuples matching column order exactly
        records = [
            (
                m['timestamp'],
                m['symbol'],
                m['mid_price'],
                m['best_bid'],
                m['best_ask'],
                m['imbalance_ratio'],
                m.get('weighted_imbalance'),
                m['bid_volume'],
                m['ask_volume'],
                m.get('total_volume'),
                m['spread_bps'],
                m.get('spread_abs'),
                m.get('vtob_ratio'),
                m.get('best_bid_volume'),
                m.get('best_ask_volume'),
                m.get('imbalance_velocity'),
                m.get('depth_levels'),
                m.get('update_id')
            )
            for m in metrics
        ]
        
        columns = [
            'time', 'symbol', 'mid_price', 'best_bid', 'best_ask',
            'imbalance_ratio', 'weighted_imbalance',
            'bid_volume', 'ask_volume', 'total_volume',
            'spread_bps', 'spread_abs',
            'vtob_ratio', 'best_bid_volume', 'best_ask_volume',
            'imbalance_velocity', 'depth_levels', 'update_id'
        ]
        
        async with self.pool.acquire() as conn:
            await conn.copy_records_to_table(
                'orderbook_metrics',
                records=records,
                columns=columns
            )
        
        logger.debug(f"Inserted batch of {len(metrics)} metrics")

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

    # ====== WINDOWED METRICS METHODS ====== #

    async def insert_batch_windowed_metrics(self, windowed_list: List[Dict]) -> None:
        """Insert batch of windowed metrics efficiently.
        
        Args:
            windowed_list: List of windowed metric dictionaries
        """
        if not windowed_list:
            return
        
        records = [
            (
                w['window_end'],  # time column
                w['symbol'],
                w['window_type'],
                w['window_start'],
                w['window_end'],
                w['window_duration_seconds'],
                w.get('avg_imbalance'),
                w.get('min_imbalance'),
                w.get('max_imbalance'),
                w.get('avg_spread_bps'),
                w.get('min_spread_bps'),
                w.get('max_spread_bps'),
                w.get('avg_bid_volume'),
                w.get('avg_ask_volume'),
                w.get('avg_total_volume'),
                w.get('total_bid_volume'),
                w.get('total_ask_volume'),
                w.get('total_volume'),
                w['sample_count'],
                w.get('window_velocity')
            )
            for w in windowed_list
        ]
        
        columns = [
            'time', 'symbol', 'window_type', 'window_start', 'window_end', 'window_duration_seconds',
            'avg_imbalance', 'min_imbalance', 'max_imbalance',
            'avg_spread_bps', 'min_spread_bps', 'max_spread_bps',
            'avg_bid_volume', 'avg_ask_volume', 'avg_total_volume',
            'total_bid_volume', 'total_ask_volume', 'total_volume',
            'sample_count', 'window_velocity'
        ]
        
        async with self.pool.acquire() as conn:
            await conn.copy_records_to_table(
                'orderbook_metrics_windowed',
                records=records,
                columns=columns
            )
        
        logger.debug(f"Inserted batch of {len(windowed_list)} windowed metrics")


    async def fetch_latest_windowed_metrics(
        self,
        symbol: str,
        window_type: str = '5m_sliding'
    ) -> Optional[Dict]:
        """Fetch the most recent windowed metrics for a symbol.
        
        Args:
            symbol: Trading symbol
            window_type: Window type ('1m_tumbling' or '5m_sliding')
            
        Returns:
            Dictionary with windowed metrics or None
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT time, symbol, window_type, window_start, window_end,
                       avg_imbalance, avg_spread_bps, avg_total_volume,
                       sample_count, window_velocity
                FROM orderbook_metrics_windowed
                WHERE symbol = $1 AND window_type = $2
                ORDER BY time DESC
                LIMIT 1
            """, symbol, window_type)
            
            return dict(row) if row else None

    # ===== STATS METHODS ===== #

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
