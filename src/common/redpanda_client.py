import asyncio
import json
from typing import Optional, Dict, List, Any, AsyncGenerator
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError, KafkaTimeoutError
from loguru import logger

from src.config import settings

class RedPandaProducer:
    """Async Redpanda/Kafka producer for publishing messages.
    
    Uses kafka-python-ng KafkaProducer under the hood but provides
    async interface by running sync operations in executor.
    
    Features:
    - JSON serialization
    - Message batching for efficiency
    - Automatic retries on failure
    - Compression (gzip)
    - Key-based partitioning
    
    Example:
        >>> async with RedpandaProducer() as producer:
        ...     await producer.publish(
        ...         topic='orderbook.raw',
        ...         key='BTCUSDT',
        ...         value={'price': 50000}
        ...     )
    
    Documentation:
    - KafkaProducer: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaProducer.html
    """
    def __init__(self) -> None:
        # self.producer: Optional[KafkaProducer] = None
        # self.bootstrap_server = settings.redpanda_bootstrap_servers
        self.producer: Optional[KafkaProducer] = None
        self._closed = False
        
        # Stats for monitoring
        self._messages_sent = 0
        self._messages_failed = 0

    # def _json_serializer(self, data):
    #     return json.dumps(data, default=str).encode("utf-8")

    async def connect(self) -> None:
        """
            Create a KafkaProducer with JSON serializer

            Ref: 
                - https://docs.redpanda.com/current/develop/produce-data/configure-producers/
                - Reference: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaProducer.html
        """
        if self.producer is not None:
            print(f'Redpanda producer already connected')
            return
        
        logger.info(f"Connecting to Redpanda at {settings.redpanda_bootstrap_servers}")
        try:
            # run sync KafkaProducer creation in executor (don't block event loop)
            self.producer = await asyncio.to_thread(
                lambda: KafkaProducer(
                    bootstrap_servers=[self.bootstrap_server],

                    # serialization
                    # JSON serializer: dict → JSON string → UTF-8 bytes
                    value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                    key_serializer=lambda k: k.encode('utf-8') if k else None,
                    
                    # reliability settings
                    acks='all',               # producer receives ack when majority/all replicas ack
                    retries=3,
                    retry_backoff_ms=300,     # Wait 300ms between retries
                    request_timeout_ms=30000, # 30 second request timeout
                    max_block_ms=10000,       # Max 10s to block on send
                    max_in_flight_requests_per_connection=5,  # Pipeline requests

                    # performance settings
                    batch_size=16384,       # Batch up to 16KB of data
                    linger_ms=100,          # Wait up to 100ms to accumulate messages
                    # buffer_memory=33554432,  # 32MB send buffer
                    # compression_type='gzip', # Compress messages with gzip

                    # metadata settings
                    metadata_max_age_ms=300000,  # Refresh metadata every 5 minutes
                )
            )

            logger.info("✓ Connected to Redpanda")
            self._closed = False
        
        except Exception as e:
            logger.error(f'Error connecting RedPanda producer: {e}')
            raise

    async def publish(
        self, 
        topic: str, 
        key: str, 
        value: Dict[str, Any], 
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """Publish a message to a Redpanda topic.
        
        Args:
            topic: Topic name (e.g., 'orderbook.raw')
            key: Message key for partitioning (e.g., 'BTCUSDT')
            value: Message value as dict (will be JSON serialized)
            headers: Optional message headers
            
        Returns:
            True if published successfully, False otherwise
            
        Reference: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaProducer.html#kafka.KafkaProducer.send
        
        Example:
            >>> await producer.publish(
            ...     topic='orderbook.raw',
            ...     key='BTCUSDT',
            ...     value={'timestamp': '2024-01-01T00:00:00Z', 'bids': [...]}
            ... )
        """
        if not self.producer or self._closed:
            logger.error('No Kafka producer. must call RedPandaProducer.connect()')
            return False

        try:
            kafka_headers = None
            if headers:
                kafka_headers = [(k, v.endcode('utf-8')) for k, v in headers.items()]
            
            # KafkaProducer.send() is synchronous but non-blocking
            # It returns a FutureRecordMetadata immediately
            future = asyncio.to_thread(
                lambda: self.producer.send(
                    topic=topic,
                    key=key,
                    value=value,
                    headers=kafka_headers
                )
            )
            self._messages_sent += 1
            return True
        
        except KafkaTimeoutError as e:
            logger.error(f'Timeout publishing to {topic}: {e}')
            self._messages_failed += 1
            return False
        except KafkaError as e:
            logger.error(f'Kafka error publishing to {topic}: {e}')
            self._messages_failed += 1
            return False
        except Exception as e:
            logger.error(f'Unexpected error publishing to {topic}: {e}')
            self._messages_failed += 1
            return False

    async def publish_batch(self, topic: str, msgs: List[Dict[str, Any]], key_field: str = 'symbol'):
        """Publish multiple messages efficiently.
        
        Args:
            topic: Topic name
            messages: List of message dicts
            key_field: Field to use as message key (default: 'symbol')
            
        Returns:
            Number of successfully published messages
            
        Example:
            >>> messages = [
            ...     {'symbol': 'BTCUSDT', 'price': 50000},
            ...     {'symbol': 'ETHUSDT', 'price': 3000}
            ... ]
            >>> count = await producer.publish_batch('orderbook.raw', messages)
        """
        success_count = 0

        for msg in msgs:
            key = msg.get(key_field)
            if not key: 
                logger.warning(f'message missing key field: {key_field}: {msg}')
                continue

            if await self.publish(topic,key, msg):
                success_count += 1
            
        logger.debug(f'Batch published {success_count}/{len(msgs)} messages to {topic}')
        return success_count

    async def flush(self, timeout: float = 10.0) -> None:
        """Flush all buffered messages.
        
        Ensures all messages are sent before returning.
        CRITICAL to call before closing to avoid data loss.
        
        Args:
            timeout: Max seconds to wait for flush
            
        Reference: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaProducer.html#kafka.KafkaProducer.flush
        """
        if not self.producer or self._closed:
            return

        try:
            logger.info('Flushing Redpanda producer...')
            await asyncio.wait_for(
                asyncio.to_thread(self.producer.flush),
                timeout=timeout
            )
            logger.info("Redpanda producer flushed")

        except asyncio.TimeoutError:
            logger.warning(f"Flush timed out after {timeout}s")
        except Exception as e:
            logger.error(f"Error flushing producer: {e}")

    async def close(self) -> None:
        """Close producer gracefully.
        
        Flushes buffered messages then closes connection.
        """
        if self._closed:
            logger.debug('RedPanda producer already closed')
            return

        if self.producer:
            try:
                await self.flush()

                await asyncio.to_thread(self.producer.close)

                logger.info(
                    f'Redpanda producer closed'
                    f'Sent: {self._messages_sent}; Failed: {self._messages_failed}'
                )

            except Exception as e:
                print(f'Error closing Redpanda producer: {e}')
            finally:
                self.producer = None
                self._closed = True

    def get_stats(self) -> Dict[str, int]:
        """Get producer statistics.
        
        Returns:
            Dict with sent and failed message counts
        """
        return {
            'messages_sent': self._messages_sent,
            'messages_failed': self._messages_failed,
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False

class RedPandaConsumer:

    def __init__(self, topic: str, group_id: str, auto_offset_reset: Optional[str] = 'latest') -> None:
        """
        Initializes the Redpanda Consumer.

        :param topic_name: The topic to subscribe to.
        :param bootstrap_servers: The Redpanda broker addresses (e.g., 'localhost:9092').
        :param group_id: The consumer group ID. Multiple consumers share work
        :param auto_offset_reset: Where to start consuming ('earliest' or 'latest').
        """
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=settings.redpanda_bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        print(f'Consumer initialized for topic: {topic}') # , group: {group_id}


    def connect(self):
        pass

    def close(self):
        pass

    async def consume(self):
        try:
            for msg in self.consumer:
                # message is a ConsumerRecord (topic, partition, offset, key, value, ...)
                print(f'TODO: handle message in consumer class {msg.value}')
                yield msg.value
        except KeyboardInterrupt:
            print("Consumption stopped by user.")
        finally:
            self.consumer.close()
            print("Consumer closed.")

    def __aenter__(self):
        pass

    def __aexit__(self):
        pass