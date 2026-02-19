import asyncio
import signal
from loguru import logger
from typing import Protocol, runtime_checkable

# 1. Define the Protocol
# @runtime_checkable allows you to use isinstance() checks at runtime, 
# although static type checkers don't strictly require it.
@runtime_checkable
class Stoppable(Protocol):
    """Represents any object that has a stop method."""
    def stop(self) -> None:
        ...  # Ellipsis indicates an abstract method for typing purposes


def setup_signal_handlers(service: Stoppable) -> None:
    """Register OS signal handlers for graceful shutdown.
    
    Handles SIGTERM (Docker stop) and SIGINT (Ctrl+C).
    
    Args:
        service: IngestionService instance to stop on signal
        
    Reference: https://docs.python.org/3/library/signal.html
    """
    loop = asyncio.get_event_loop()
    name = type(service).__name__
    
    def handle_signal():
        logger.info(f'{name}: Shutdown signal received')
        loop.create_task(service.stop())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)
    
    logger.info(f'{name}: Signal handlers registered (SIGTERM, SIGINT)')