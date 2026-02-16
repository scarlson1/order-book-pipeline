# TODO: implement

"""Main ingestion service entry point."""
import asyncio
# import time
from loguru import logger

from src.config import settings

async def main():
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Monitoring symbols: {settings.symbol_list}")
    logger.info(f"Database: {settings.postgres_host}:{settings.postgres_port}")
    
    # Use settings throughout
    for symbol in settings.symbol_list:
        logger.info(f"Subscribing to {symbol}")

if __name__ == "__main__":
    asyncio.run(main())

# logger.info("Ingestion service starting...")
# logger.warning("This is a placeholder - implementation needed!")
# logger.info("Container will stay alive. Press Ctrl+C to stop.")

# # Keep container running indefinitely
# while True:
#     time.sleep(60)
#     logger.info("Still running... (waiting for implementation)")