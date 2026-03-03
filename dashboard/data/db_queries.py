"""Database query functions."""

import datetime
import streamlit as st
from loguru import logger
from typing import Dict, List, Optional

from dashboard.utils.async_runner import run_async
from dashboard.utils.formatting import get_valid_timezone
from src.common.database import DatabaseClient
from dashboard.data.redis_queries import get_redis_client

# should streamlit's connection be used instead of DatabaseClient ??
# https://docs.streamlit.io/develop/tutorials/databases/postgresql


@st.cache_resource
def get_db_client():
    """Get or create database client."""
    if 'db_client' not in st.session_state:
        client = DatabaseClient()
        # import asyncio
        try:
            run_async(client.connect(), timeout=15)
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

    @staticmethod
    def _normalize_windowed_row(row: Dict) -> Dict:
        """Ensure dashboard consumers always receive window_duration_seconds."""
        normalized = dict(row)
        duration_seconds = normalized.get('window_duration_seconds')
        if duration_seconds is not None:
            normalized['window_duration_seconds'] = int(duration_seconds)
            return normalized

        legacy_duration = normalized.get('window_duration')
        if legacy_duration is not None:
            normalized['window_duration_seconds'] = int(legacy_duration)
            return normalized

        window_start = normalized.get('window_start')
        window_end = normalized.get('window_end')
        if isinstance(window_start, datetime.datetime) and isinstance(window_end, datetime.datetime):
            computed_duration = int((window_end - window_start).total_seconds())
            if computed_duration > 0:
                normalized['window_duration_seconds'] = computed_duration

        return normalized

    # ===== Metrics Queries ===== #

    async def fetch_latest_metrics(self, symbol: str) -> Optional[Dict]:
        """Fetch the most recent metrics for a symbol."""
        try:
            results = await self.db.fetch_recent_metrics(symbol, limit=1)
            # logger.info(f"Results count: {len(results) if results else 0}")
            # if results:
            #     logger.info(f"First result keys: {results[0].keys()}")
            #     logger.info(f"First result: {results[0]}")

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

    async def fetch_time_series(self,
                                symbol: str,
                                start_time: datetime.datetime,
                                end_time: datetime.datetime,
                                interval: str = '1m') -> List[Dict]:
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
                    rows = await conn.fetch(
                        """
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

                # Cockroach-compatible bucketed aggregation for larger intervals.
                else:
                    if interval == '1h':
                        bucket_granularity = 'hour'
                    elif interval == '1d':
                        bucket_granularity = 'day'
                    else:
                        logger.warning(
                            f'Unsupported interval {interval}; falling back to raw range query')
                        rows = await conn.fetch(
                            """
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
                        return [dict(row) for row in rows]

                    rows = await conn.fetch(
                        f"""
                        SELECT
                            date_trunc('{bucket_granularity}', time) AS time,
                            symbol,
                            AVG(avg_mid_price) AS mid_price,
                            AVG(avg_imbalance) AS imbalance_ratio,
                            AVG(avg_spread_bps) AS spread_bps,
                            SUM(total_bid_volume) AS bid_volume,
                            SUM(total_ask_volume) AS ask_volume,
                            SUM(total_volume) AS total_volume
                        FROM orderbook_metrics_windowed
                        WHERE symbol = $1
                            AND window_type = '1m_tumbling'
                            AND time BETWEEN $2 AND $3
                        GROUP BY 1, 2
                        ORDER BY time ASC
                    """, symbol, start_time, end_time)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching time series for {symbol}: {e}")
            return []

    # ===== Alert Queries ===== #

    async def fetch_alerts(self,
                           symbol: Optional[str] = None,
                           limit: int = 50,
                           since: Optional[datetime.datetime] = None) -> List[Dict]:
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
            limit: int = 60  # Last hour of 5-min windows (rolling every 1m)
    ):
        '''
            Flink Window Output
            Use Case: Display rolling averages on charts
            Strategy: Hybrid - Redis for latest window, CockroachDB for history
        '''
        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        *
                    FROM orderbook_metrics_windowed
                    WHERE symbol = $1
                        AND window_type = $2
                    ORDER BY window_end DESC
                    LIMIT $3
                """, symbol, window_type, limit)

                return [self._normalize_windowed_row(dict(row)) for row in rows]

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

    async def fetch_latest_windowed(self,
                                    symbol: str,
                                    window_type: str = '5m_sliding') -> Optional[Dict]:
        """Fetch the most recent windowed aggregate."""
        try:
            row = await self.db.fetch_latest_windowed_metrics(symbol, window_type)
            if not row:
                return None
            return self._normalize_windowed_row(row)

        except Exception as e:
            logger.error(f"Error fetching latest windowed: {e}")
            return None

    async def get_volatility_data(self,
                                  symbol: str,
                                  timezone_pref: str = 'America/New_York',
                                  days: int = 7):
        # exclude holidays ??
        # use more than 7 days ??
        try:
            timezone = get_valid_timezone(timezone_pref)

            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT 
                        EXTRACT(DOW FROM window_end AT TIME ZONE $2) as day_of_week,
                        EXTRACT(HOUR FROM window_end AT TIME ZONE $2) as hour,
                        AVG(max_imbalance - min_imbalance) as avg_volatility
                    FROM orderbook_metrics_windowed
                    WHERE symbol = $1
                        AND window_type = '5m_sliding'
                        AND window_end >= NOW() - INTERVAL '{days} days'
                    GROUP BY day_of_week, hour
                    ORDER BY day_of_week, hour
                """, symbol, timezone)

                # self.redis.insert_volatility_data(symbol, timezone, rows)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching windowed aggregates: {e}")
            return []

    # ===== Percentage Change Queries ===== #

    async def fetch_price_at_time(self, symbol: str,
                                  timestamp: datetime.datetime) -> Optional[Dict]:
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

    async def compute_metric_vs_windowed(self,
                                         symbol: str,
                                         window_type: str = '5m_sliding') -> Optional[Dict]:
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
                    'imbalance':
                    calc_deviation(current['imbalance_ratio'], windowed['avg_imbalance']),
                    'spread':
                    calc_deviation(current['spread_bps'], windowed['avg_spread_bps']),
                    'volume':
                    calc_deviation(current.get('total_volume', 0), windowed['avg_total_volume'])
                },
                'comparison_period': window_type
            }

        except Exception as e:
            logger.error(f"Error computing metric deviations: {e}")
            return None

    # ===== Statistics Queries ===== #

    async def fetch_summary_statistics(self, symbol: str, hours: int = 1) -> Optional[Dict]:
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
