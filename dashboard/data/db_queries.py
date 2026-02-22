"""Database query functions."""

import datetime
import streamlit as st
from loguru import logger
from typing import Dict, List, Optional

from src.common.database import DatabaseClient
from dashboard.data.redis_queries import get_redis_client


@st.cache_resource  
def get_db_client():
    """Get or create database client."""
    if 'db_client' not in st.session_state:
        client = DatabaseClient()
        import asyncio
        try:
            asyncio.run(client.connect())
            st.session_state.db_client = client
            logger.info("✓ Database client connected")
        except Exception as e:
            logger.error(f"Failed to connect database client: {e}")
            raise
    return st.session_state.db_client


class DatabaseQueries:

    def __init__(self):
        self.db = get_db_client()
        self.redis = get_redis_client()

    # ===== Metrics Queries ===== #

    async def fetch_latest_metrics(
        self,
        symbol: str
    ) -> Optional[Dict]:
        """Fetch the most recent metrics for a symbol."""
        try:
            results = await self.db.fetch_recent_metrics(symbol, limit=1)
            return results[0] if results else None
            
        except Exception as e:
            logger.error(f"Error fetching latest metrics for {symbol}: {e}")
            return None

    async def fetch_multiple_symbols_latest(self) -> List[Dict]:
        """Fetch latest metrics for all symbols.
        
        Returns:
            List of metrics dicts (one per symbol)
        """
        try:
            return await self.db.fetch_multiple_symbols_metrics()
            
        except Exception as e:
            logger.error(f"Error fetching multiple symbols: {e}")
            return []

    # async def fetch_metrics(self, symbol: str = None) -> dict:
    #     """Try Redis, fallback on TimescaleDB"""

    #     if symbol:
    #         # cached = await self.redis.get_cached_metrics(symbol)
    #         # if cached:
    #         #     return json.loads(cached)

    #         metrics = await self.db.fetch_recent_metrics(symbol, limit=1)

    #         if metrics:
    #             await self.redis.insert_metrics(symbol, metrics, ttl=60)

    #         return metrics

    #     # get all symbols
    #     else:
    #         async with self.db.pool.acquire() as conn:

    #             metrics = await conn.fetch("""
    #                 SELECT DISTINCT ON (symbol)
    #                     *
    #                 FROM orderbook_metrics
    #                 ORDER BY symbol, time DESC
    #             """)

    #         pipeline = self.redis.pipeline()
    #         for m in metrics:
    #             pipeline.setex(
    #                 self.redis._metrics_key(m['symbol']),
    #                 60,
    #                 json.dumps(m)
    #             )
    #         await pipeline.execute()

    #         return metrics


    async def fetch_time_series(
        self,
        symbol: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: str = '1m'
    ) -> List[Dict]:
        """Fetch time series data for charting.
        
        Args:
            symbol: Trading symbol
            start_time: Start timestamp
            end_time: End timestamp
            interval: Aggregation interval ('1m', '5m', '1h', '1d')
            
        Returns:
            List of time-series data points
        """
        try:
            async with self.db.pool.acquire() as conn:
                # For small intervals, return raw data
                if interval in ('1m', '5m'):
                    rows = await conn.fetch("""
                        SELECT
                            time,
                            symbol,
                            mid_price,
                            imbalance_ratio,
                            spread_bps,
                            bid_volume,
                            ask_volume,
                            total_volume
                        FROM orderbook_metrics
                        WHERE symbol = $1
                            AND time BETWEEN $2 AND $3
                        ORDER BY time ASC
                    """, symbol, start_time, end_time)
                
                # For large intervals, use time_bucket aggregation
                # TimescaleDB Docs: https://www.tigerdata.com/docs/use-timescale/latest/time-buckets/use-time-buckets
                else:
                    bucket_interval = '1 hour' if interval == '1h' else '1 day'
                    
                    rows = await conn.fetch("""
                        SELECT
                            time_bucket($1, time) AS time,
                            symbol,
                            AVG(mid_price) AS mid_price,
                            AVG(imbalance_ratio) AS imbalance_ratio,
                            AVG(spread_bps) AS spread_bps,
                            SUM(bid_volume) AS bid_volume,
                            SUM(ask_volume) AS ask_volume,
                            SUM(total_volume) AS total_volume
                        FROM orderbook_metrics
                        WHERE symbol = $2
                            AND time BETWEEN $3 AND $4
                        GROUP BY time, symbol
                        ORDER BY time ASC
                    """, bucket_interval, symbol, start_time, end_time)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error fetching time series for {symbol}: {e}")
            return []

    # ===== Alert Queries ===== #

    async def fetch_alerts(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
        since: Optional[datetime.datetime] = None
    ) -> List[Dict]:
        '''Fetch alerts fromm the database'''
        try:
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

            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching alerts: {e}")
            return []

    # ===== Windowed Metrics Queries ===== #

    async def fetch_windowed_aggregates(
        self,
        symbol: str,
        window_type: str = '5m_sliding',
        limit: int = 12  # Last hour of 5-min windows
    ):
        '''
            Flink Window Output
            Use Case: Display rolling averages on charts
            Strategy: Hybrid - Redis for latest window, TimescaleDB for history
        '''
        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        *
                    FROM orderbook_metrics_windowed
                    WHERE symbol = $1
                        AND window_type = $2
                    ORDER BY window_end DESC
                    LIMIT $3
                """, symbol, window_type, limit)
                
                return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"Error fetching windowed aggregates: {e}")
            return []

        # # Get latest window from Redis
        # latest = await self.redis.get_windowed(symbol, window_type, limit)
        
        
        # # Get historical windows from database
        # async with self.db.pool.acquire() as conn:
        #     historical = await conn.execute("""
        #         SELECT *
        #         FROM orderbook_metrics_windowed
        #         WHERE symbol = $1
        #         AND window_type = $2
        #         ORDER BY window_end DESC
        #         LIMIT $3
        #     """, symbol, window_type, limit)
        
        # # Combine (latest might duplicate most recent historical)
        # results = []
        # if latest:
        #     results.append(json.loads(latest))
        
        # # Deduplicate by window_end timestamp
        # seen_timestamps = {r['window_end'] for r in results}
        # for h in historical:
        #     if h['window_end'] not in seen_timestamps:
        #         results.append(h)
        
        # return results[:limit]

    async def fetch_latest_windowed(
        self,
        symbol: str,
        window_type: str = '5m_sliding'
    ) -> Optional[Dict]:
        """Fetch the most recent windowed aggregate."""
        try:
            return await self.db.fetch_latest_windowed_metrics(symbol, window_type)
            
        except Exception as e:
            logger.error(f"Error fetching latest windowed: {e}")
            return None

    # ===== Percentage Change Queries ===== #

    async def fetch_price_at_time(
        self,
        symbol: str,
        timestamp: datetime.datetime
    ) -> Optional[Dict]:
        """Fetch price closest to a specific timestamp."""
        try:
            return await self.db.fetch_price_at_time(symbol, timestamp)
            
        except Exception as e:
            logger.error(f"Error fetching price at time: {e}")
            return None

    async def compute_price_change_24h(self, symbol: str) -> Optional[Dict]:
        """Compute 24-hour price change.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict with current/previous prices and percentage change
        """
        try:
            # Get current price
            current = await self.fetch_latest_metrics(symbol)
            if not current:
                return None
            
            # Get price 24h ago
            day_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
            previous = await self.fetch_price_at_time(symbol, day_ago)
            
            if not previous:
                return None
            
            current_price = float(current['mid_price'])
            previous_price = float(previous['mid_price'])
            
            change_pct = ((current_price - previous_price) / previous_price) * 100
            
            return {
                'current_price': current_price,
                'previous_price': previous_price,
                'change_pct': round(change_pct, 2),
                'change_direction': 'up' if change_pct >= 0 else 'down',
                'comparison_period': '24h'
            }
            
        except Exception as e:
            logger.error(f"Error computing price change: {e}")
            return None

    async def compute_metric_vs_windowed(
        self,
        symbol: str,
        window_type: str = '5m_sliding'
    ) -> Optional[Dict]:
        """Compare current metrics vs windowed average.
        
        Args:
            symbol: Trading symbol
            window_type: Window type for comparison
            
        Returns:
            Dict with current metrics, averages, and deviation percentages
        """
        try:
            # Get current metrics
            current = await self.fetch_latest_metrics(symbol)
            if not current:
                return None
            
            # Get windowed average
            windowed = await self.fetch_latest_windowed(symbol, window_type)
            if not windowed:
                return None
            
            # Calculate deviations
            def calc_deviation(current_val, avg_val):
                if avg_val == 0:
                    return 0.0
                return round(((current_val - avg_val) / abs(avg_val)) * 100, 2)
            
            return {
                'current': {
                    'imbalance': current['imbalance_ratio'],
                    'spread_bps': current['spread_bps'],
                    'volume': current.get('total_volume', 0)
                },
                'average': {
                    'imbalance': windowed['avg_imbalance'],
                    'spread_bps': windowed['avg_spread_bps'],
                    'volume': windowed['avg_total_volume']
                },
                'deviation_pct': {
                    'imbalance': calc_deviation(
                        current['imbalance_ratio'],
                        windowed['avg_imbalance']
                    ),
                    'spread': calc_deviation(
                        current['spread_bps'],
                        windowed['avg_spread_bps']
                    ),
                    'volume': calc_deviation(
                        current.get('total_volume', 0),
                        windowed['avg_total_volume']
                    )
                },
                'comparison_period': window_type
            }
            
        except Exception as e:
            logger.error(f"Error computing metric deviations: {e}")
            return None

    # ===== Statistics Queries ===== #

    async def fetch_summary_statistics(
        self,
        symbol: str,
        hours: int = 1
    ) -> Optional[Dict]:
        """Fetch summary statistics for a symbol."""
        try:
            return await self.db.get_statistics(symbol, hours)
            
        except Exception as e:
            logger.error(f"Error fetching summary statistics: {e}")
            return None

    # ===== Health & Monitoring ===== #

    async def health_check(self) -> bool:
        """Check database health.
        
        Returns:
            True if healthy
        """
        try:
            return await self.db.health_check()
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def get_connection_stats(self) -> Dict:
        """Get database connection pool statistics.
        
        Returns:
            Dict with pool stats
        """
        try:
            return await self.db.get_pool_stats()
            
        except Exception as e:
            logger.error(f"Error fetching connection stats: {e}")
            return {"status": "error", "error": str(e)}