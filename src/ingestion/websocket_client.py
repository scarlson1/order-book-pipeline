"""Binance WebSocket client for order book data.

Connects to Binance WebSocket API and streams real-time order book
data for configured symbols. Raw data is passed to a callback
function for processing by the rest of the pipeline.

Data Flow:
    Binance WebSocket
        ↓ (raw JSON message)
    BinanceWebSocketClient._handle_message()
        ↓ (parsed dict)
    callback() - provided by main.py
        ↓
    orderbook_parser.py → metrics_calculator.py → data_writer.py

Documentation:
- websockets library: https://websockets.readthedocs.io/en/stable/
- Binance WebSocket API: https://binance-docs.github.io/apidocs/spot/en/#diff-depth-stream
    - Binance US: https://docs.binance.us/?python#order-book-depth-diff-stream
- Binance Stream Formats: https://binance-docs.github.io/apidocs/spot/en/#partial-book-depth-streams
    - Binance US: https://docs.binance.us/?python#partial-order-book-depth-stream
- asyncio: https://docs.python.org/3/library/asyncio.html
- concurrent tasks: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
"""

from typing import Awaitable, Callable
import websockets
import asyncio
import json
from loguru import logger
from src.config import settings

# Rate limit docs: https://docs.binance.us/?python#general-information-on-rate-limits
# exchange information (status of symbols): https://docs.binance.us/?python#exchange-information-websocket
# market data requests: https://docs.binance.us/?python#market-data-requests

# wss://stream.binance.us:9443/ws/bnbbtc@depth
# Get a depth snapshot from https://www.binance.us/api/v1/depth?symbol=BNBBTC&limit=1000

# Type alias for the callback function signature
# The callback receives a symbol (str) and raw order book data (dict)
MessageCallback = Callable[[str, dict], Awaitable[None]]

class BinanceWebSocketClient:
    """Streams real-time order book data from Binance WebSocket API.
    
    Subscribes to partial book depth streams for each configured symbol.
    Raw messages are passed to a callback function for downstream processing.
    
    Binance Stream Format:
        wss://stream.binance.com:9443/ws/{symbol}@depth{levels}@{speed}
        
        Example:
            wss://stream.binance.com:9443/ws/btcusdt@depth20@100ms
    
    Raw Message Format from Binance:
        {
            "lastUpdateId": 160,
            "bids": [           <- Top 20 bid levels
                ["0.0024", "10"], <- [price, quantity]
                ...
            ],
            "asks": [           <- Top 20 ask levels
                ["0.0026", "100"],
                ...
            ]
        }
    
    Example:
        >>> async def handle_orderbook(symbol: str, data: dict):
        ...     print(f"{symbol}: {len(data['bids'])} bids")
        
        >>> client = BinanceWebSocketClient(callback=handle_orderbook)
        >>> await client.start()
    
    Documentation:
    - Partial Book Depth: https://docs.binance.us/?python#partial-order-book-depth-stream
    - websockets connect: https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html
    """

    def __init__(self, callback: MessageCallback) -> None:
        self.callback: Callable = callback

        self.symbols = settings.symbol_list       # ['BTCUSDT', 'ETHUSDT', ...]
        self.depth_levels = settings.depth_levels # 20
        self.update_speed = settings.update_speed # '100ms'
        self.base_url = settings.binance_ws_url   # 'wss://stream.binance.us:9443/ws'

        self._running = False
        self._tasks: list[asyncio.Task] = []

        # configurable settings
        self._max_retries = 5
        self._retry_delay = 1.0 # start with 1s delay
        self._max_retry_delay = 60.0 # cap at 60 seconds

    def _build_stream_url(self, symbol: str) -> str:
        """Build WebSocket URL for a symbol.
        
        Binance stream format:
            wss://stream.binance.us:9443/ws/{symbol}@depth{levels}@{speed}
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            WebSocket URL string
            
        Reference: https://binance-docs.github.io/apidocs/spot/en/#partial-book-depth-streams
        
        Example:
            >>> url = client._build_stream_url('BTCUSDT')
            >>> print(url)
            wss://stream.binance.com:9443/ws/btcusdt@depth20@100ms
        """
        stream = f'{symbol.lower()}@depth{self.depth_levels}@{self.update_speed}'
        return f'{self.base_url}/{stream}'

    async def _handle_message(self, symbol: str, raw_message: str) -> None:
        """Parse raw WebSocket message and pass to callback.
        
        This method:
        1. Parses the raw JSON string from Binance
        2. Validates it has the expected structure
        3. Passes it to the callback for further processing
        
        Args:
            symbol: Trading symbol this message is for
            raw_message: Raw JSON string from Binance WebSocket
            
        Raw Message Example from Binance:
            {
                "lastUpdateId": 160,
                "bids": [["50000.00", "1.500"], ["49999.00", "2.000"]],
                "asks": [["50001.00", "1.200"], ["50002.00", "1.800"]]
            }
        """
        try:
            data = json.loads(raw_message)

            if 'bids' not in data or 'asks' not in data:
                logger.warn(f'Unexpected message format for {symbol}: {data}')
                return

            await self.callback(symbol, data)

        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse message for {symbol}: {e}')
        except Exception as e:
            logger.error(f'Error handling message for {symbol}: {e}')

    async def _connect_symbol(self, symbol: str) -> None:
        """Maintain WebSocket connection for a single symbol.
        
        Handles connection, message receiving, and reconnection with
        exponential backoff on failures.
        
        Args:
            symbol: Trading symbol to subscribe to
            
        Reference:
        - websockets.connect: https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html
        - Exponential Backoff: https://websockets.readthedocs.io/en/stable/howto/reconnect.html
        """
        url = self._build_stream_url(symbol)
        retry_count = 0
        retry_delay = self._retry_delay

        while self._running:
            try:
                logger.info(f'Connecting to {url}')

                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ) as websocket:
                    logger.info(f'✓ Connected to {symbol} stream')
                    retry_count = 0
                    retry_delay = self._retry_delay

                    async for message in websocket:
                        if not self._running:
                            break

                        await self._handle_message(symbol, message)

            except websockets.exceptions.ConnectionClosedOK:
                # normal close (server restarted etc.)
                logger.info(f'{symbol}: Connection closed normally')
                if not self._running:
                    break

            except websockets.exceptions.ConnectionClosedError as e:
                logger.warning(f'{symbol}: Connection closed with error: {e}')

            except Exception as e:
                logger.error(f"{symbol}: Unexpected error: {e}")

            # reconnect with exponential backoff
            if self._running:
                retry_count += 1

                if retry_count > self._max_retries:
                    logger.error(f'{symbol}: Max retries ({self._max_retries}) reached --> giving up')
                    break

                logger.info(f'{symbol}: reconnecting in {retry_delay}s (attempt {retry_count}/{self._max_retries})')
                await asyncio.sleep(retry_delay)

                retry_delay = min(retry_delay * 2, self._max_retry_delay)

    
    async def start(self) -> None:
        """Start WebSocket connections for all configured symbols.
        
        Creates a separate async task for each symbol so they run
        concurrently and don't block each other.
        
        Reference:
        - asyncio.create_task: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
        """
        self._running = True
        logger.info(f"Starting WebSocket client for symbols: {self.symbols}")

        self._tasks = [
            asyncio.create_task(
                self._connect_symbol(symbol),
                name=f'ws_{symbol}'
            )
            for symbol in self.symbols
        ]

        logger.info(f'✓ Started {len(self._tasks)} WebSocket streams')

        await asyncio.gather(*self._tasks, return_exceptions=True)

    
    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.stop()
        return False