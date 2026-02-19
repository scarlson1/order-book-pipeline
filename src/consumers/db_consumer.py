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
    """Consumes metrics and alerts from Redpanda and writes to TimescaleDB.
    
    Features:
    - Batch inserts for high-volume metrics (every 100 msgs OR 1 second)
    - Immediate inserts for low-volume alerts
    - Manual offset commit AFTER successful DB writes
    - Graceful shutdown with batch flush
    - Error handling for bad messages
    
    Message Flow:
        Redpanda (orderbook.metrics) ─┬─→ Batch → TimescaleDB → Commit offset
                                      │
        Redpanda (orderbook.alerts) -─┴─→ Immediate → TimescaleDB
    
    Expected Load:
    - 3 symbols × 600 messages/min = 1,800 metrics/min
    - Batching: 100 msgs/batch = ~18 batches/min
    """

    def __init__(self):
        self.consumer = RedpandaConsumer(
            topics=[
                settings.redpanda_topics['metrics'],
                settings.redpanda_topics['alerts']
            ],
            group_id='db-writer',
            auto_commit=False,  # Manual commit after successful DB write
            auto_offset_reset='latest'
        )
        self.db = DatabaseClient()
        
        # batch state
        self._batch: list[dict] = []
        self._batch_max_size = 100
        self._batch_timeout_seconds = 1.0
        self._last_flush_time = datetime.datetime.now(datetime.timezone.utc)
        
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
            f"DatabaseConsumer started - consuming from "
            f"{settings.redpanda_topics['metrics']} and "
            f"{settings.redpanda_topics['alerts']}"
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
        
        # Flush any remaining batch
        if self._batch:
            logger.info(f"Flushing final batch of {len(self._batch)} metrics")
            await self._flush_batch()
        
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
        
        Args:
            msg: ConsumerRecord from kafka-python-ng
        """
        topic = msg.topic
        value = msg.value
        
        if topic == settings.redpanda_topics['alerts']:
            # Alerts: insert immediately (low volume)
            await self._handle_alert(value)
            
        elif topic == settings.redpanda_topics['metrics']:
            # Metrics: add to batch
            self._add_to_batch(value)
            
            # Check if we should flush
            await self._check_flush()

    def _add_to_batch(self, value: dict) -> None:
        """Add metrics to batch.
        
        Args:
            value: Metric dict from Redpanda message
        """
        # Convert timestamp string to datetime
        # The metrics have 'timestamp' field - convert to proper datetime
        timestamp = value.get('timestamp')
        if isinstance(timestamp, str):
            try:
                dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                dt = datetime.datetime.now(datetime.timezone.utc)
        else:
            dt = datetime.datetime.now(datetime.timezone.utc)
        
        self._batch.append({
            **value,
            'time': dt,
            'timestamp': dt  # Use datetime for copy_records_to_table
        })
        
        logger.debug(f"Added to batch (size: {len(self._batch)})")

    async def _check_flush(self) -> None:
        """Check if batch should be flushed (size or timeout)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        time_since_flush = (now - self._last_flush_time).total_seconds()
        
        should_flush = (
            len(self._batch) >= self._batch_max_size or
            time_since_flush >= self._batch_timeout_seconds
        )
        
        if should_flush:
            await self._flush_batch()

    async def _flush_batch(self) -> None:
        """Write batch to database and commit offset.
        
        This is the critical section - we commit offsets ONLY after
        successful database write to ensure at-least-once delivery.
        """
        if not self._batch:
            return
        
        batch_size = len(self._batch)
        logger.info(f"Flushing batch of {batch_size} metrics")
        
        try:
            # Write to database
            await self.db.insert_batch_metrics(self._batch)
            
            # Commit offsets ONLY after successful write
            await self.consumer.commit()
            
            logger.info(f"Successfully inserted {batch_size} metrics and committed offset")
            
            # Clear batch and reset timer
            self._batch.clear()
            self._last_flush_time = datetime.datetime.now(datetime.timezone.utc)
            
        except Exception as e:
            logger.error(f"Failed to flush batch: {e}")
            # Don't commit - messages will be reprocessed on restart
            # Could implement retry logic here
            raise

    async def _handle_alert(self, value: dict) -> None:
        """Handle alert message - insert immediately.
        
        Args:
            value: Alert dict from Redpanda message
        """
        # Convert timestamp
        timestamp = value.get('timestamp')
        if isinstance(timestamp, str):
            try:
                dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                dt = datetime.datetime.now(datetime.timezone.utc)
        else:
            dt = datetime.datetime.now(datetime.timezone.utc)
        
        alert = {
            **value,
            'timestamp': dt
        }
        
        await self.db.insert_alert(alert)
        logger.debug(f"Inserted alert: {value.get('alert_type')} for {value.get('symbol')}")

    def get_stats(self) -> dict:
        """Get consumer statistics."""
        return {
            'current_batch_count': len(self._batch),
            '_last_flush_time': self._last_flush_time,
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
