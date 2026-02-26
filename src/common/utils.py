import asyncio
import signal
from config import settings
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

def apply_kafka_security(builder):
    protocol = settings.redpanda_security_protocol.upper()

    # Always set protocol explicitly (PLAINTEXT for local, SASL_SSL for serverless)
    builder = builder.set_property("security.protocol", protocol)

    if protocol in {"SASL_SSL", "SASL_PLAINTEXT"}:
        builder = builder.set_property("sasl.mechanism", settings.redpanda_sasl_mechanism)
        builder = builder.set_property(
            "sasl.jaas.config",
            f'org.apache.kafka.common.security.scram.ScramLoginModule required '
            f'username="{settings.redpanda_username}" '
            f'password="{settings.redpanda_password}";',
        )

    # Optional: disable hostname verification only if you explicitly configured that
    if protocol in {"SSL", "SASL_SSL"} and not settings.redpanda_ssl_check_hostname:
        builder = builder.set_property("ssl.endpoint.identification.algorithm", "")

    return builder
