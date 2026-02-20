"""Database consumer - writes metrics and alerts from Redpanda to TimescaleDB."""

import asyncio
import datetime
from typing import Optional
from loguru import logger

from src.common.database import DatabaseClient
from src.common.redpanda_client import RedpandaConsumer
from src.config import settings

# creating duplicate alerts if commits are sent only after batch is flushed ??
# alerts idempotent ??

class DatabaseConsumer:
    """Consumes metrics, alerts, and windowed data from Redpanda and writes to TimescaleDB.
    
    Features:
    - Batch inserts for high-volume metrics (every 100 msgs OR 1 second)
    - Batch inserts for windowed metrics (every 50 msgs OR 2 seconds)
    - Immediate inserts for low-volume alerts
    - Manual offset commit AFTER successful DB writes
    - Graceful shutdown with batch flush
    - Error handling for bad messages
    
    Message Flow:
        Redpanda (orderbook.metrics) ──────┬─→ Batch → TimescaleDB → Commit
        Redpanda (orderbook.alerts) ───────┼─→ Immediate → TimescaleDB → Commit
        Redpanda (orderbook.metrics.windowed) ─┴─→ Batch → TimescaleDB → Commit
    
    Expected Load:
    - 3 symbols × 600 messages/min = 1,800 metrics/min
    - 3 symbols × 3 windows/min = 9 windowed/min
    - Variable alerts (~0-30/min)
    """

    def __init__(self):
        self.consumer = RedpandaConsumer(
            topics=[
                settings.redpanda_topics['metrics'],
                settings.redpanda_topics['alerts'],
                settings.redpanda_topics['windowed']
            ],
            group_id='db-writer',
            auto_commit=False,  # Manual commit after successful DB write
            auto_offset_reset='latest'
        )
        self.db = DatabaseClient()
        
        # Metrics batch state
        self._metrics_batch: list[dict] = []
        self._metrics_batch_max_size = 100
        self._metrics_batch_timeout_seconds = 1.0
        self._metrics_last_flush_time = datetime.datetime.now(datetime.timezone.utc)
        
        # Windowed batch state (separate batch for windowed data)
        self._windowed_batch: list[dict] = []
        self._windowed_batch_max_size = 50  # Smaller batch (less frequent)
        self._windowed_batch_timeout_seconds = 2.0
        self._windowed_last_flush_time = datetime.datetime.now(datetime.timezone.utc)
        
        # state
        self._running = False
        self._start_task: Optional[asyncio.Task] = None # track running task state

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
            self.consumer.connect()
        )
        
        logger.info(
            f'DatabaseConsumer started - consuming from '
            f"{settings.redpanda_topics['metrics']}, "
            f"{settings.redpanda_topics['alerts']}, and "
            f"{settings.redpanda_topics['windowed']}"
        )
        
        # Start consumption in background task
        self._start_task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Stop the consumer gracefully."""
        if not self._running:
            return
        
        logger.info("Stopping DatabaseConsumer...")
        self._running = False
        
        # Cancel the consume task if running
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            try:
                await self._start_task
            except asyncio.CancelledError:
                pass
        
        # Flush any remaining batches
        if self._metrics_batch:
            logger.info(f"Flushing final metrics batch of {len(self._metrics_batch)}")
            await self._flush_metrics_batch()
        
        if self._windowed_batch:
            logger.info(f"Flushing final windowed batch of {len(self._windowed_batch)}")
            await self._flush_windowed_batch()
        
        # Close connections (commits offsets)
        await asyncio.gather(
            self.consumer.close(),
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
            await self.stop()

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

        elif topic == settings.redpanda_topics['windowed']:
            # Windowed: add to batch
            self._add_to_windowed_batch(value)
            await self._check_windowed_flush()

    def _add_to_metrics_batch(self, value: dict) -> None:
        """Add metrics to batch."""
        timestamp = self._parse_timestamp(value.get('timestamp'))
        
        self._metrics_batch.append({
            **value,
            'time': timestamp,
            'timestamp': timestamp
        })
        
        logger.debug(f"Added to metrics batch (size: {len(self._metrics_batch)})")

    def _add_to_windowed_batch(self, value: dict) -> None:
        """Add windowed metrics to batch."""
        # Parse timestamps
        window_start = self._parse_timestamp(value.get('window_start'))
        window_end = self._parse_timestamp(value.get('window_end'))
        
        self._windowed_batch.append({
            **value,
            'window_start': window_start,
            'window_end': window_end
        })
        
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
            len(self._metrics_batch) >= self._metrics_batch_max_size or
            time_since_flush >= self._metrics_batch_timeout_seconds
        )
        
        if should_flush:
            await self._flush_metrics_batch()

    async def _check_windowed_flush(self) -> None:
        """Check if windowed batch should be flushed."""
        now = datetime.datetime.now(datetime.timezone.utc)
        time_since_flush = (now - self._windowed_last_flush_time).total_seconds()
        
        should_flush = (
            len(self._windowed_batch) >= self._windowed_batch_max_size or
            time_since_flush >= self._windowed_batch_timeout_seconds
        )
        
        if should_flush:
            await self._flush_windowed_batch()

    async def _flush_metrics_batch(self) -> None:
        """Write batch to database and commit offset.
        
        This is the critical section - we commit offsets ONLY after
        successful database write to ensure at-least-once delivery.
        """
        if not self._metrics_batch:
            return
        
        batch_size = len(self._metrics_batch)
        logger.info(f"Flushing batch of {batch_size} metrics")
        
        try:
            # Write to database
            await self.db.insert_batch_metrics(self._metrics_batch)
            # Commit offsets ONLY after successful write
            await self.consumer.commit()
            
            logger.info(f"✓ Inserted {batch_size} metrics and committed offset")
            
            # Clear batch and reset timer
            self._metrics_batch.clear()
            self._metrics_last_flush_time = datetime.datetime.now(datetime.timezone.utc)
            
        except Exception as e:
            logger.error(f"Failed to flush metrics batch: {e}")
            raise

    async def _flush_windowed_batch(self) -> None:
        """Write windowed batch to database and commit offset."""
        if not self._windowed_batch:
            return
        
        batch_size = len(self._windowed_batch)
        logger.info(f"Flushing windowed batch of {batch_size}")
        
        try:
            await self.db.insert_batch_windowed_metrics(self._windowed_batch)
            await self.consumer.commit()
            
            logger.info(f"✓ Inserted {batch_size} windowed metrics")
            
            self._windowed_batch.clear()
            self._windowed_last_flush_time = datetime.datetime.now(datetime.timezone.utc)
            
        except Exception as e:
            logger.error(f"Failed to flush windowed batch: {e}")
            raise

    async def _handle_alert(self, value: dict) -> None:
        """Handle alert message - insert immediately."""
        timestamp = self._parse_timestamp(value.get('timestamp'))
        
        alert = {
            **value,
            'timestamp': timestamp
        }
        
        await self.db.insert_alert(alert)
        await self.consumer.commit() # commit immediately for alerts
        logger.debug(f"Inserted alert: {value.get('alert_type')} for {value.get('symbol')}")

    def get_stats(self) -> dict:
        """Get consumer statistics."""
        return {
            'metrics_batch_count': len(self._metrics_batch),
            'windowed_batch_count': len(self._windowed_batch),
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
