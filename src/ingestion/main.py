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
import signal
from datetime import datetime, timezone
from loguru import logger

from src.common.redpanda_client import RedpandaProducer
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
        self.producer = RedpandaProducer()
        self.ws_client: BinanceWebSocketClient | None = None
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    # old ?? save raw data and process orderbook in Flink ??
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
            # Parse raw Binance data into standardized format
            snapshot = self.parser.parse(symbol, raw_data)
            
            if snapshot is None:
                logger.warning(f"Parser returned None for {symbol}")
                return
            
            # Add ingestion metadata
            message = {
                **snapshot.model_dump(),
                'ingested_at': datetime.now(timezone.utc).isoformat(),
                'source': 'binance_websocket',
            }
            
            # Publish to Redpanda
            # Key by symbol so all BTCUSDT messages go to same partition
            # This ensures ordered processing per symbol in Flink
            topic = settings.redpanda_topics['raw'] # 'orderbook.raw'
            
            success = await self.producer.publish(
                topic=topic,
                key=symbol,      # ← Partition by symbol for Flink ordering
                value=message
            )
            
            if success:
                logger.debug(
                    f'Published {symbol} to {topic} '
                    f'(bids: {len(snapshot.bids)}, asks: {len(snapshot.asks)})'
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
            stats = self.producer.get_stats()
            logger.info(
                f"Stats: sent={stats['messages_sent']} "
                f"failed={stats['messages_failed']} "
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
        
        try:
            # Connect to Redpanda
            await self.producer.connect()
            # self.producer = self._create_producer()
            
            # Create WebSocket client with our callback
            # The callback (handle_orderbook) connects webSocket client to the Redpanda publisher (after cleaning/validating)
            self.ws_client = BinanceWebSocketClient(
                callback=self.handle_orderbook
            )

            # run stats logging and websocket concurrently
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
        await self.producer.close()
        
        stats = self.producer.get_stats()
        logger.info(
            f"Ingestion service stopped. "
            f"Sent: {stats['messages_sent']}, "
            f"Failed: {stats['messages_failed']}"
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
