from src.ingestion.websocket_client import BinanceWebSocketClient
from loguru import logger
import asyncio

# TODO: websocket tests

async def test_connection():
    """Test WebSocket connection with a simple callback."""
    
    message_count = 0
    
    async def print_callback(symbol: str, data: dict):
        """Simple callback that just prints what it receives."""
        nonlocal message_count
        message_count += 1
        
        best_bid = data['bids'][0][0] if data['bids'] else 'N/A'
        best_ask = data['asks'][0][0] if data['asks'] else 'N/A'
        
        logger.info(
            f"#{message_count} {symbol}: "
            f"bid={best_bid} ask={best_ask} "
            f"({len(data['bids'])} levels)"
        )
        
        # Stop after 5 messages
        if message_count >= 5:
            raise KeyboardInterrupt
    
    client = BinanceWebSocketClient(callback=print_callback)
    
    try:
        await client.start()
    except KeyboardInterrupt:
        await client.stop()
        logger.info(f"Received {message_count} messages")


if __name__ == "__main__":
    asyncio.run(test_connection())