"""Database consumer - writes metrics and alerts from Redpanda to Postgres/CockroachDB."""

import asyncio
import datetime
from typing import Optional

from loguru import logger
from pydantic import ValidationError

from src.common.database import DatabaseClient
from src.common.models import OrderBookWindowedMetrics
from src.common.redpanda_client import RedpandaConsumer
from src.config import settings


class DatabaseConsumer:
    """Consumes metrics, alerts, and windowed data from Redpanda and writes to Postgres/CockroachDB.
    
    Features:
    - Batch inserts for high-volume metrics (every 200 msgs OR 1 second)
    - Batch inserts for windowed metrics (every 100 msgs OR 2 seconds)
    - Immediate inserts for low-volume alerts
    - Manual offset commit AFTER successful DB writes across buffered topics
    - Best-effort in-memory dedupe for duplicate deliveries in active batches
      (non-persistent; does not survive process restart)
    - Graceful shutdown with batch flush
    - Error handling for bad messages
    
    Message Flow:
        Redpanda (orderbook.metrics) ──────┬─→ Batch → CockroachDB → Commit
        Redpanda (orderbook.alerts) ───────┼─→ Immediate → CockroachDB → Commit
        Redpanda (orderbook.metrics.windowed) ─┴─→ Batch → CockroachDB → Commit
    
    Expected Load:
    - 3 symbols × 600 messages/min = 1,800 metrics/min
    - 3 symbols × 3 windows/min = 9 windowed/min
    - Variable alerts (~0-30/min)
    """

    def __init__(self):
        # Metrics + alerts consumer (high volume, frequent commits)
        self.consumer = RedpandaConsumer(
            topics=[settings.redpanda_topics['metrics'], settings.redpanda_topics['alerts']],
            group_id='db-writer-metrics',
            auto_commit=False,
            auto_offset_reset='latest'
        )
        # Windowed consumer (low volume, separate offset tracking)
        self.windowed_consumer = RedpandaConsumer(
            topics=[settings.redpanda_topics['windowed']],
            group_id='db-writer-windowed',
            auto_commit=False,
            auto_offset_reset='latest'
        )
        self.db = DatabaseClient()

        # Cockroach-oriented defaults: keep commit cadence low-latency,
        # while batching enough records to avoid very small transactions.
        # DatabaseClient handles deeper chunking/retries.
        # Metrics batch state
        self._metrics_batch: list[dict] = []
        self._metrics_batch_keys: set[tuple] = set()
        self._metrics_batch_max_size = 500 # 200 -> 500 to reduce DB credit use
        self._metrics_batch_timeout_seconds = 5.0 # 1.0 -> 5.0 to reduce DB credit use
        self._metrics_last_flush_time = datetime.datetime.now(datetime.timezone.utc)

        # Windowed batch state (separate batch for windowed data)
        self._windowed_batch: list[OrderBookWindowedMetrics] = []
        self._windowed_batch_keys: set[tuple] = set()
        self._windowed_batch_max_size = 100
        self._windowed_batch_timeout_seconds = 2.0
        self._windowed_last_flush_time = datetime.datetime.now(datetime.timezone.utc)

        # state
        self._running = False
        self._start_task: Optional[asyncio.Task] = None  # track running task state
        self._windowed_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the database consumer."""
        if self._running:
            logger.warning("DatabaseConsumer already running")
            return

        logger.info("Starting DatabaseConsumer...")
        self._running = True

        # Connect to both database and Redpanda
        await asyncio.gather(
            self.db.connect(),
            self.consumer.connect(),
            self.windowed_consumer.connect()
        )

        logger.info(f'DatabaseConsumer started - consuming from '
                    f"{settings.redpanda_topics['metrics']}, "
                    f"{settings.redpanda_topics['alerts']}, and "
                    f"{settings.redpanda_topics['windowed']}")

        # Start consumption in background task
        # Run metrics/alerts and windowed loops concurrently
        self._start_task = asyncio.create_task(self._consume_loop())
        self._windowed_task = asyncio.create_task(self._windowed_consume_loop())

    async def stop(self) -> None:
        """Stop the consumer gracefully."""
        if not self._running:
            return

        logger.info("Stopping DatabaseConsumer...")
        self._running = False

        # Cancel the consume task if running
        current_task = asyncio.current_task()
        if (self._start_task and self._start_task is not current_task
                and not self._start_task.done()):
            self._start_task.cancel()
            try:
                await self._start_task
            except asyncio.CancelledError:
                pass

        # Flush remaining writes first; consumer.close() performs final commit.
        await self._flush_pending_batches_without_commit()

        # Close connections (commits offsets)
        await asyncio.gather(
            self.consumer.close(),
            self.windowed_consumer.close(),
            self.db.close()
        )

        logger.info("DatabaseConsumer stopped")

    async def _consume_loop(self) -> None:
        """Main message processing loop."""
        try:
            async for msg in self.consumer.consume():
                if not self._running:
                    break

                try:
                    await self._process_message(msg)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Don't crash - log and continue
                    # Bad messages won't be committed, will be reprocessed

        except asyncio.CancelledError:
            logger.info("Consume loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in consume loop: {e}")
            raise
        finally:
            if self._running:
                await self.stop()

    async def _windowed_consume_loop(self) -> None:
        """Handles windowed topic independently with its own commit cadence."""
        try:
            async for msg in self.windowed_consumer.consume():
                if not self._running:
                    break
                try:
                    parsed = self._parse_windowed_message(msg.value)
                    if parsed is None:
                        logger.warning(f"Skipping malformed windowed message: {msg.value}")
                        # Commit and move on — don't block the consumer
                        await self.windowed_consumer.commit()
                        continue

                    self._add_to_windowed_batch(parsed)
                    await self._check_windowed_flush()

                except Exception as e:
                    logger.error(f"Error processing windowed message: {e}")
        except asyncio.CancelledError:
            logger.info("Windowed consume loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in windowed consume loop: {e}")
            raise

    async def _process_message(self, msg) -> None:
        """Process a single message from Redpanda.
        
            Args: msg: ConsumerRecord from kafka-python-ng
        """
        topic = msg.topic
        value = msg.value

        if topic == settings.redpanda_topics['alerts']:
            # Alerts: insert immediately (low volume)
            await self._handle_alert(value)

        elif topic == settings.redpanda_topics['metrics']:
            # Metrics: add to batch
            self._add_to_metrics_batch(value)
            await self._check_metrics_flush()

        else:
            logger.warning(f'Unexpected topic in metrics consumer: {topic}')
        # elif topic == settings.redpanda_topics['windowed']:
        #     parsed_windowed = self._parse_windowed_message(value)
        #     # Skip malformed legacy payloads so one poison-pill message
        #     # does not block the consumer group forever.
        #     if parsed_windowed is None:
        #         logger.warning(f"Skipping malformed windowed message: {value}")
        #         await self._flush_pending_batches_without_commit()
        #         await self.consumer.commit()
        #         return
        #     # Windowed: add to batch
        #     self._add_to_windowed_batch(parsed_windowed)
        #     await self._check_windowed_flush()

    def _parse_windowed_message(self, value: dict) -> Optional[OrderBookWindowedMetrics]:
        """Validate and normalize a windowed payload."""
        if not isinstance(value, dict):
            return None

        payload = {
            **value,
            'window_start': self._parse_timestamp(value.get('window_start')),
            'window_end': self._parse_timestamp(value.get('window_end'))
        }

        try:
            return OrderBookWindowedMetrics.model_validate(payload)
        except ValidationError as error:
            logger.warning(f'Invalid windowed payload (validation error): {error}')
            return None

    def _add_to_metrics_batch(self, value: dict) -> None:
        """Add metrics to batch."""
        timestamp = self._parse_timestamp(value.get('timestamp'))
        dedupe_key = (
            value.get('symbol'),
            timestamp,
            value.get('update_id'),
            value.get('mid_price'),
        )
        if dedupe_key in self._metrics_batch_keys:
            logger.debug(f"Skipping duplicate metric in active batch: {dedupe_key}")
            return

        self._metrics_batch.append({**value, 'time': timestamp, 'timestamp': timestamp})
        self._metrics_batch_keys.add(dedupe_key)

        logger.debug(f"Added to metrics batch (size: {len(self._metrics_batch)})")

    def _add_to_windowed_batch(self, value: OrderBookWindowedMetrics) -> None:
        """Add windowed metrics to batch."""
        dedupe_key = (
            value.symbol,
            value.window_type,
            value.window_start,
            value.window_end,
        )
        if dedupe_key in self._windowed_batch_keys:
            logger.debug(f"Skipping duplicate windowed record in active batch: {dedupe_key}")
            return

        self._windowed_batch.append(value)
        self._windowed_batch_keys.add(dedupe_key)

        logger.debug(f"Added to windowed batch (size: {len(self._windowed_batch)})")

    def _parse_timestamp(self, timestamp) -> datetime.datetime:
        """Parse timestamp string to datetime."""
        if isinstance(timestamp, str):
            try:
                return datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                pass
        return datetime.datetime.now(datetime.timezone.utc)

    async def _check_metrics_flush(self) -> None:
        """Check if batch should be flushed (size or timeout)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        time_since_flush = (now - self._metrics_last_flush_time).total_seconds()

        should_flush = (
            len(self._metrics_batch) >= self._metrics_batch_max_size
            or time_since_flush >= self._metrics_batch_timeout_seconds
        )

        if should_flush:
            await self._flush_metrics_batch()

    async def _check_windowed_flush(self) -> None:
        """Check if windowed batch should be flushed."""
        now = datetime.datetime.now(datetime.timezone.utc)
        time_since_flush = (now - self._windowed_last_flush_time).total_seconds()

        should_flush = (len(self._windowed_batch) >= self._windowed_batch_max_size
                        or time_since_flush >= self._windowed_batch_timeout_seconds)

        if should_flush:
            await self._flush_windowed_batch()

    async def _flush_pending_batches_without_commit(self) -> None:
        """Flush all pending batches without committing offsets."""
        if self._metrics_batch:
            logger.info(f"Flushing pending metrics batch of {len(self._metrics_batch)}")
            await self._flush_metrics_batch(commit_offsets=False, flush_other_batches=False)

        if self._windowed_batch:
            logger.info(f"Flushing pending windowed batch of {len(self._windowed_batch)}")
            await self._flush_windowed_batch(commit_offsets=False, flush_other_batches=False)

    async def _flush_metrics_batch(self,
                                   commit_offsets: bool = True,
                                   flush_other_batches: bool = True) -> None:
        """Write batch to database and commit offset.
        
        This is the critical section - we commit offsets ONLY after
        successful database write to ensure at-least-once delivery.
        """
        if not self._metrics_batch:
            return

        batch_size = len(self._metrics_batch)
        batch_records = list(self._metrics_batch)
        logger.info(f"Flushing batch of {batch_size} metrics")

        try:
            # Write to database
            await self.db.insert_batch_metrics(batch_records)
            # Clear batch eagerly to avoid duplicate writes on cross-batch errors.
            self._metrics_batch.clear()
            self._metrics_batch_keys.clear()
            self._metrics_last_flush_time = datetime.datetime.now(datetime.timezone.utc)

            # Commit offsets only after all previously buffered writes succeed.
            if commit_offsets:
                if flush_other_batches and self._windowed_batch:
                    await self._flush_windowed_batch(commit_offsets=False,
                                                     flush_other_batches=False)
                await self.consumer.commit()
                logger.info(f"✓ Inserted {batch_size} metrics and committed offset")
            else:
                logger.info(f"✓ Inserted {batch_size} metrics")

        except Exception as e:
            logger.error(f"Failed to flush metrics batch: {e}")
            raise

    async def _flush_windowed_batch(
        self,
        commit_offsets: bool = True,
        flush_other_batches: bool = True   # kept for signature compat, ignored
    ) -> None:
        if not self._windowed_batch:
            return

        batch_size = len(self._windowed_batch)
        batch_records = list(self._windowed_batch)
        logger.info(f"Flushing windowed batch of {batch_size}")

        try:
            await self.db.insert_batch_windowed_metrics(batch_records)
            self._windowed_batch.clear()
            self._windowed_batch_keys.clear()
            self._windowed_last_flush_time = datetime.datetime.now(datetime.timezone.utc)

            if commit_offsets:
                await self.windowed_consumer.commit()  # ← windowed consumer only
                logger.info(f"✓ Inserted {batch_size} windowed metrics and committed offset")
            else:
                logger.info(f"✓ Inserted {batch_size} windowed metrics")

        except Exception as e:
            logger.error(f"Failed to flush windowed batch: {e}")
            raise

    async def _handle_alert(self, value: dict) -> None:
        """Handle alert message - insert immediately.
        
        Flushes pending batches first so this commit cannot advance offsets
        for records that are still only in memory.
        """
        await self._flush_pending_batches_without_commit()
        timestamp = self._parse_timestamp(value.get('timestamp'))

        alert = {**value, 'timestamp': timestamp}

        await self.db.insert_alert(alert)
        await self.consumer.commit()  # commit immediately for alerts
        logger.debug(f"Inserted alert: {value.get('alert_type')} for {value.get('symbol')}")

    def get_stats(self) -> dict:
        """Get consumer statistics."""
        return {
            'metrics_batch_count': len(self._metrics_batch),
            'windowed_batch_count': len(self._windowed_batch),
            'metrics_batch_unique_keys': len(self._metrics_batch_keys),
            'windowed_batch_unique_keys': len(self._windowed_batch_keys),
            'running': self._running
        }


async def main():
    """Main entry point for testing."""
    consumer = DatabaseConsumer()

    try:
        await consumer.start()

        # Run for a bit then stop
        await asyncio.sleep(60)

    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
