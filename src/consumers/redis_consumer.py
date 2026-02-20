import asyncio
from typing import Optional
from loguru import logger

from common.redis_client import RedisClient
from common.redpanda_client import RedpandaConsumer
from config import settings


class RedisConsumer:
    """Consumes messages from Redpanda and caches them in Redis.
    
    Topics:
        - orderbook.metrics: Caches real-time metrics (60s TTL)
        - orderbook.metrics.windowed: Caches aggregated statistics (300s TTL)
        - orderbook.alerts: Stores alerts (max 100 per symbol)
    
    TTL Settings:
        - Metrics: 60 seconds
        - Statistics: 300 seconds (5 minutes)
        - Alerts: 1 hour (managed in RedisClient.add_alert)
    
    Data Pipeline:
        orderbook.metrics (raw) → Flink → orderbook.metrics.windowed (aggregated)
    """

    # Topic name constants
    METRICS_TOPIC = settings.redpanda_topics['metrics']
    WINDOWED_TOPIC = settings.redpanda_topics['windowed']
    ALERTS_TOPIC = settings.redpanda_topics['alerts']
    
    # TTL constants
    METRICS_TTL_SECONDS = 60
    STATISTICS_TTL_SECONDS = 300
    MAX_ALERTS_PER_SYMBOL = 100

    def __init__(self):
        self.redis = RedisClient()
        self.consumer = RedpandaConsumer(
            topics=[
                self.METRICS_TOPIC,
                self.WINDOWED_TOPIC,
                self.ALERTS_TOPIC
            ],
            group_id='redis-writer',
            auto_commit=False,  # Manual commit after successful Redis write
            auto_offset_reset='latest'
        )

        # state
        self._running = False
        self._start_task: Optional[asyncio.Task] = None
        self._messages_processed = 0
        self._messages_failed = 0


    async def start(self):
        if self._running:
            logger.warning('RedisConsumer is already running')
            return

        try:
            logger.info("Starting RedisConsumer...")
            self._running = True

            await asyncio.gather(
                self.redis.connect(),
                self.consumer.connect()
            )

            logger.info(
                f'RedisConsumer started. Consuming from: '
                f'{self.METRICS_TOPIC}, {self.WINDOWED_TOPIC}, and {self.ALERTS_TOPIC}'
            )

            self._start_task = asyncio.create_task(self._consume_loop())
            
        
        except Exception as e:
            logger.error(f"Failed to start RedisConsumer: {e}")
            self._running = False
            raise

    async def stop(self):
        if not self._running:
            return
        
        logger.info("Stopping RedisConsumer...")
        self._running = False
        
        # Cancel the consume task if running
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            try:
                await self._start_task
            except asyncio.CancelledError:
                pass

        # Close connections (commits offsets)
        await asyncio.gather(
            self.consumer.close(),
            self.redis.close()
        )

        logger.info(
            f'RedisConsumer stopped. '
            f'Processed: {self._messages_processed}, Failed: {self._messages_failed}'
        )

    async def _consume_loop(self):
        """Main consumption loop that routes messages to handlers."""
        logger.info("Starting consume loop...")

        try:
            async for msg in self.consumer.consume(timeout_ms=1000):
                if not self._running:
                    break

                try:
                    # Route message based on topic
                    if msg.topic == self.METRICS_TOPIC:
                        await self._handle_cache_metrics(msg)
                    elif msg.topic == self.WINDOWED_TOPIC:
                        await self._handle_cache_statistics(msg)
                    elif msg.topic == self.ALERTS_TOPIC:
                        await self._handle_add_alert(msg)
                    else:
                        logger.warning(f'Unknown topic: {msg.topic}')
                        continue
                    
                    # Commit offset after successful processing
                    await self.consumer.commit()
                    self._messages_processed += 1

                except Exception as e:
                    self._messages_failed += 1
                    logger.error(f'Error processing message from {msg.topic}: {e}')
                    continue

        except asyncio.CancelledError:
            logger.info('Consume loop cancelled')
        except Exception as e:
            logger.error(f'Consume loop error: {e}')
            raise
        finally:
            logger.info("Consume loop exited")

    async def _handle_cache_metrics(self, msg):
        """Handle messages from the orderbook.metrics topic.
        
        Message format expected:
        {
            "symbol": "BTCUSDT",
            "timestamp": "2024-01-01T00:00:00Z",
            "metrics": {...}
        }
        
        Caches metrics with 60s TTL.
        """
        value = msg.value
        if not value:
            logger.warning('Empty message value for metrics')
            return

        symbol = value.get('symbol')
        if not symbol:
            logger.warning('Message missing "symbol" field')
            return

        metrics = value.get('metrics')
        if metrics:
            await self.redis.insert_metrics(
                symbol=symbol,
                metrics=metrics,
                ttl=self.METRICS_TTL_SECONDS
            )
            logger.debug(f'Cached metrics for {symbol} (TTL: {self.METRICS_TTL_SECONDS}s)')

    async def _handle_cache_statistics(self, msg):
        """Handle messages from the orderbook.metrics.windowed topic.
        
        Message format expected:
        {
            "symbol": "BTCUSDT",
            "timestamp": "2024-01-01T00:00:00Z",
            "avg_imb": 0.5,
            "min_imb": 0.3,
            "max_imb": 0.7,
            "avg_spread": 5.2,
            "avg_volume": 100000,
            "sample_count": 100,
            "window_type": '5m_sliding',
            "window_start": "2024-01-01T12:00:00Z",
            "window_end": "2024-01-01T12:05:00Z"
        }
        
        Caches statistics with 300s TTL.
        Statistics are computed by Flink window aggregations.
        """
        value = msg.value
        if not value:
            logger.warning('Empty message value for statistics')
            return

        symbol = value.get('symbol')
        if not symbol:
            logger.warning('Statistics message missing "symbol" field')
            return



        # Cache statistics with 300s TTL
        await self.redis.cache_statistics(
            symbol=symbol,
            stats=value,
            ttl=self.STATISTICS_TTL_SECONDS
        )
        logger.debug(f'Cached statistics for {symbol} (TTL: {self.STATISTICS_TTL_SECONDS}s)')

    async def _handle_add_alert(self, msg):
        """Handle messages from the orderbook.alerts topic.
        
        Message format expected:
        {
            "symbol": "BTCUSDT",
            "timestamp": "2024-01-01T00:00:00Z",
            "alert_type": "imbalance_high",
            "value": 0.75,
            "message": "..."
        }
        
        Stores alert in Redis list (max 100 per symbol)
        """
        value = msg.value
        if not value:
            logger.warning('Empty message value for alerts')
            return

        symbol = value.get('symbol')
        if not symbol:
            logger.warning('Alert message missing "symbol" field')
            return

        success = await self.redis.add_alert(
            symbol=symbol,
            alert=value,
            max_alerts=self.MAX_ALERTS_PER_SYMBOL
        )

        if success:
            logger.debug(f'Added alert for {symbol}')
        else:
            logger.error(f'Failed to add alert for {symbol}')

    def get_stats(self) -> dict:
        """Get consumer statistics."""
        return {
            'messages_processed': self._messages_processed,
            'messages_failed': self._messages_failed,
            'running': self._running
        }
