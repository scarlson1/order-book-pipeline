"""Main ingestion service entry point.

This service:
1. Connects to Binance WebSocket API
2. Receives raw order book data
3. Parses into a standardized format
4. Publishes to Redpanda (orderbook.raw topic)

Everything AFTER publishing is handled by Flink:
    Redpanda (orderbook.raw)
        ↓
    Flink (metrics calculation, alerts, windowed aggregations)
        ↓
    Redpanda (orderbook.metrics / orderbook.alerts)
        ↓
    TimescaleDB + Redis + Dashboard

Documentation:
- kafka-python-ng: https://kafka-python.readthedocs.io/en/master/
- asyncio: https://docs.python.org/3/library/asyncio.html
- loguru: https://loguru.readthedocs.io/en/stable/
"""

import asyncio
import json
import signal
from datetime import datetime, timezone
from loguru import logger
from kafka import KafkaProducer
from kafka.errors import KafkaError

from src.config import settings
from src.ingestion.websocket_client import BinanceWebSocketClient
from src.ingestion.orderbook_parser import OrderBookParser


class IngestionService:
    """Ingestion service that publishes raw order book data to Redpanda.
    
    Responsibilities:
        - Manage WebSocket connection to Binance
        - Parse raw order book messages
        - Publish to Redpanda orderbook.raw topic
        - Handle graceful shutdown
    
    NOT responsible for:
        - Calculating metrics (Flink)
        - Checking alerts (Flink)
        - Writing to TimescaleDB (Flink consumer)
        - Writing to Redis (Flink consumer)
    
    Example:
        >>> service = IngestionService()
        >>> await service.start()
    """
    
    def __init__(self):
        """Initialize ingestion service."""
        self.parser = OrderBookParser()
        self.producer: KafkaProducer | None = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self.ws_client: BinanceWebSocketClient | None = None
        
        # Stats for monitoring
        self._messages_published = 0
        self._messages_failed = 0
    
    def _create_producer(self) -> KafkaProducer:
        """Create Redpanda/Kafka producer.
        
        Reference: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaProducer.html
        
        Returns:
            Configured KafkaProducer instance
        """
        logger.info(f"Connecting to Redpanda at {settings.redpanda_bootstrap_servers}")
        
        producer = KafkaProducer(
            bootstrap_servers=settings.redpanda_bootstrap_servers,
            
            # Serialize values as JSON bytes
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            
            # Serialize keys as UTF-8 bytes (we key by symbol for partitioning)
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            
            # Reliability settings
            acks='all',              # Wait for all replicas to acknowledge
            retries=3,               # Retry failed sends
            retry_backoff_ms=300,    # Wait 300ms between retries
            
            # Performance settings
            linger_ms=5,             # Batch messages for 5ms for efficiency
            batch_size=16384,        # 16KB batch size
            compression_type='gzip', # Compress messages
            
            # Timeout settings
            request_timeout_ms=30000,
            max_block_ms=10000,      # Max time to block on send
        )
        
        logger.info("✓ Connected to Redpanda")
        return producer
    
    async def _publish_to_redpanda(
        self,
        topic: str,
        key: str,
        data: dict
    ) -> bool:
        """Publish message to Redpanda topic.
        
        Args:
            topic: Redpanda topic name
            key: Message key (used for partitioning by symbol)
            data: Message data to publish
            
        Returns:
            True if published successfully, False otherwise
            
        Reference: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaProducer.html#kafka.KafkaProducer.send
        """
        try:
            # KafkaProducer.send() is synchronous but non-blocking
            # We run it in executor to avoid blocking the async event loop
            loop = asyncio.get_event_loop()
            
            future = await asyncio.to_thread(
                lambda: self.producer.send(
                    topic=topic,
                    key=key,
                    value=data
                )
            )
            
            # Optional: wait for acknowledgment
            # record_metadata = future.get(timeout=10)
            # logger.debug(f"Published to {topic}:{record_metadata.partition}:{record_metadata.offset}")
            
            self._messages_published += 1
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            self._messages_failed += 1
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error publishing to {topic}: {e}")
            self._messages_failed += 1
            return False
    
    async def handle_orderbook(self, symbol: str, raw_data: dict) -> None:
        """Handle raw order book message from WebSocket.
        
        This is the callback passed to BinanceWebSocketClient.
        It's called for every message received from Binance.
        
        Flow:
            BinanceWebSocketClient
                ↓ (symbol, raw_data)
            handle_orderbook()      ← This method
                ↓ Parse
            OrderBookParser
                ↓ Publish
            Redpanda (orderbook.raw)
                ↓ [Flink takes over from here]
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            raw_data: Raw order book dict from Binance WebSocket
        """
        try:
            # Step 1: Parse raw Binance data into standardized format
            snapshot = self.parser.parse(symbol, raw_data)
            
            if snapshot is None:
                logger.warning(f"Parser returned None for {symbol}")
                return
            
            # Step 2: Add ingestion metadata
            message = {
                **snapshot.model_dump(),
                'ingested_at': datetime.now(timezone.utc).isoformat(),
                'source': 'binance_websocket',
            }
            
            # Step 3: Publish to Redpanda
            # Key by symbol so all BTCUSDT messages go to same partition
            # This ensures ordered processing per symbol in Flink
            topic = settings.redpanda_topics['raw']
            
            await self._publish_to_redpanda(
                topic=topic,
                key=symbol,      # ← Partition by symbol
                data=message
            )
            
            logger.debug(
                f"Published {symbol} snapshot to {topic} "
                f"(bids: {len(snapshot.bids)}, asks: {len(snapshot.asks)})"
            )
            
        except Exception as e:
            logger.error(f"Error handling order book for {symbol}: {e}")
    
    async def _log_stats(self) -> None:
        """Log publishing statistics periodically."""
        while self._running:
            await asyncio.sleep(60)  # Log every minute
            logger.info(
                f"Stats: published={self._messages_published} "
                f"failed={self._messages_failed} "
                f"symbols={settings.symbol_list}"
            )
    
    async def start(self) -> None:
        """Start the ingestion service.
        
        Initializes the Redpanda producer and WebSocket client,
        then starts streaming data.
        """
        logger.info("=" * 50)
        logger.info(f"Starting {settings.app_name} Ingestion Service")
        logger.info(f"Environment:  {settings.environment}")
        logger.info(f"Symbols:      {settings.symbol_list}")
        logger.info(f"Depth:        {settings.depth_levels} levels")
        logger.info(f"Update Speed: {settings.update_speed}")
        logger.info(f"Redpanda:     {settings.redpanda_bootstrap_servers}")
        logger.info("=" * 50)
        
        self._running = True
        
        # Step 1: Connect to Redpanda
        self.producer = self._create_producer()
        
        # Step 2: Create WebSocket client with our callback
        # The callback (handle_orderbook) is what connects the
        # WebSocket client to the Redpanda publisher
        self.ws_client = BinanceWebSocketClient(
            callback=self.handle_orderbook
        )
        
        # Step 3: Run stats logging and WebSocket concurrently
        try:
            await asyncio.gather(
                self.ws_client.start(),
                self._log_stats(),
                return_exceptions=True
            )
        except asyncio.CancelledError:
            logger.info("Ingestion service cancelled")
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the ingestion service gracefully.
        
        Stops the WebSocket client and flushes/closes the Redpanda producer.
        """
        if not self._running:
            return
        
        logger.info("Stopping ingestion service...")
        self._running = False
        
        # Stop WebSocket client
        if self.ws_client:
            await self.ws_client.stop()
        
        # Flush and close Redpanda producer
        if self.producer:
            try:
                # Flush ensures all buffered messages are sent
                logger.info("Flushing Redpanda producer...")
                await asyncio.to_thread(self.producer.flush)
                
                # Close the producer
                await asyncio.to_thread(self.producer.close)
                logger.info("Redpanda producer closed")
                
            except Exception as e:
                logger.error(f"Error closing Redpanda producer: {e}")
        
        logger.info(
            f"Ingestion service stopped. "
            f"Published: {self._messages_published}, "
            f"Failed: {self._messages_failed}"
        )


def setup_signal_handlers(service: IngestionService) -> None:
    """Register OS signal handlers for graceful shutdown.
    
    Handles SIGTERM (Docker stop) and SIGINT (Ctrl+C).
    
    Args:
        service: IngestionService instance to stop on signal
        
    Reference: https://docs.python.org/3/library/signal.html
    """
    loop = asyncio.get_event_loop()
    
    def handle_signal():
        logger.info("Shutdown signal received")
        loop.create_task(service.stop())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)
    
    logger.info("Signal handlers registered (SIGTERM, SIGINT)")



async def main() -> None:
    """Main entry point for the ingestion service."""
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Monitoring symbols: {settings.symbol_list}")
    logger.info(f"Database: {settings.postgres_host}:{settings.postgres_port}")

    service = IngestionService()
    setup_signal_handlers(service)
    
    try:
        # creates instances of RedPanda producer and websocket connection to binance
        # publishes websocket to RedPanda topic
        await service.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await service.stop()

if __name__ == "__main__":
    # Configure loguru
    logger.add(
        settings.log_file,
        rotation="100 MB",
        retention="7 days",
        level=settings.log_level
    )
    
    asyncio.run(main())
