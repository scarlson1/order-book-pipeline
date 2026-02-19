import asyncio
import json
from typing import Optional, Dict, List, Any, AsyncGenerator
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError, KafkaTimeoutError
from loguru import logger

from src.config import settings

class RedpandaProducer:
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
                    bootstrap_servers=[settings.redpanda_bootstrap_servers],

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
                kafka_headers = [(k, v.encode('utf-8')) for k, v in headers.items()]
            
            # KafkaProducer.send() is synchronous but non-blocking
            # returns a FutureRecordMetadata immediately
            future = await asyncio.to_thread(
                lambda: self.producer.send(
                    topic=topic,
                    key=key,        # ← Partition by symbol
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

class RedpandaConsumer:
    """Async Redpanda/Kafka consumer for consuming messages.
    
    Uses kafka-python-ng KafkaConsumer under the hood but provides
    async interface via async generator.
    
    Features:
    - JSON deserialization
    - Consumer group management
    - Automatic offset tracking
    - Configurable commit strategy
    
    Example:
        >>> async with RedpandaConsumer(
        ...     topics=['orderbook.metrics'],
        ...     group_id='db-writer'
        ... ) as consumer:
        ...     async for message in consumer.consume():
        ...         print(f"{message.key}: {message.value}")
    
    Documentation:
    - KafkaConsumer: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html
    """
    def __init__(self, topics: List[str], group_id: str, auto_commit: bool = True, auto_offset_reset: Optional[str] = 'latest') -> None:
        """Initialize Redpanda consumer.
        
        Args:
            topics: List of topics to consume from
            group_id: Consumer group ID (shared processing across group)
            auto_commit: Auto-commit offsets (default: True)
            auto_offset_reset: Where to start if no offset ('earliest' or 'latest')
        """
        self.topics = topics
        self.group_id = group_id
        self.auto_commit = auto_commit
        self.auto_offset_reset = auto_offset_reset
        
        self.consumer: Optional[KafkaConsumer] = None
        self._closed = False
        self._messages_consumed = 0

    async def connect(self) -> None:
        
        if self.consumer is not None:
            return
        
        logger.info(
            f'Connecting consumer `{self.group_id}` to Redpanda'
            f'topics: {self.topics}'
        )
        try:
            self.consumer = await asyncio.to_thread(
                lambda: KafkaConsumer(
                    *self.topics,
                    bootstrap_servers=settings.redpanda_bootstrap_servers,

                    # consumer group settings
                    group_id=self.group_id,
                    auto_offset_reset=self.auto_offset_reset, # 'earliest' or 'latest'
                    enable_auto_commit=self.auto_commit,
                    auto_commit_interval_ms=500, # Commit every 5 seconds

                    # deserialization
                    value_deserializer=lambda v: json.loads(v.decode('utf-8')) if v else None,
                    key_deserializer=lambda k: k.decode('utf-8') if k else None,

                    #fetch settings
                    fetch_min_bytes=1,      # Return immediately if any data
                    fetch_max_wait_ms=500,  # Wait max 500ms for min_bytes
                    max_partition_fetch_bytes= 1048576,  # 1MB per partition

                    # session settings
                    session_timeout_ms=30000,    # 30s session timeout
                    heartbeat_interval_ms=3000,  # Send heartbeat every 3s

                    # processing settings
                    max_poll_records=500,        # Process up to 500 messages per poll
                    max_poll_interval_ms=300000, # 5 minute max between polls
                )
            )

            logger.info(
                f"✓ Consumer '{self.group_id}' connected to topics: {self.topics}"
            )
            self._closed = False
        
        except Exception as e:
            logger.error(f'Failed to connect consumer: {e}')
            raise

    async def consume(self, timeout_ms: int = 1000) -> AsyncGenerator[Any, None]:
        """Consume messages as an async generator.
        
        Args:
            timeout_ms: Poll timeout in milliseconds
            
        Yields:
            ConsumerRecord objects with .key, .value, .topic, .partition, .offset
            
        Reference: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html#kafka.KafkaConsumer.poll
        
        Example:
            >>> async for message in consumer.consume():
            ...     print(f"Received from {message.topic}: {message.value}")
            ...     # message.key      - message key (string)
            ...     # message.value    - message value (dict)
            ...     # message.topic    - topic name
            ...     # message.partition - partition number
            ...     # message.offset   - message offset
        """
        if not self.consumer or self._closed:
            logger.error('Redpanda consumer not connected')
            return

        try:
            # poll for messages without blocking event loop
            message_batch = await asyncio.to_thread(
                lambda: self.consumer.poll(timeout_ms=timeout_ms)
            )
            # message_batch is dict: {TopicPartition: [messages]}
            for topic_partition, msgs in message_batch.items():
                for msg in msgs:
                    self._messages_consumed += 1
                    yield msg

            if not message_batch:
                await asyncio.sleep(0.01)

        except KeyboardInterrupt:
            print("Consumption stopped by user.")
        except Exception as e:
            logger.error(f"Error consuming messages: {e}")
            raise
        finally:
            self.consumer.close()
            print("Consumer closed.")

    async def commit(self) -> None:
        """Manually commit current offsets.
        
        Only needed if auto_commit=False.
        
        Reference: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html#kafka.KafkaConsumer.commit
        """
        if not self.consumer or self._closed:
            return
        
        try:
            await asyncio.to_thread(self.consumer.commit)
            logger.debug('committed offsets')

        except Exception as e:
            logger.error(f'Error committing offsets: {e}')

    async def close(self) -> None:
        """Close consumer gracefully.
        
        Commits offsets (if auto_commit=False) then closes connection.
        """
        if self._closed:
            logger.debug('Redpanda consumer already closed')
            return

        if self.consumer:
            try:
                if not self.auto_commit:
                    await self.commit()

                await asyncio.to_thread(self.consumer.close)

                logger.info(
                    f'Redpanda consumer closed `{self.group_id}` ',
                    f'Consumed: {self._messages_consumed} messages'
                )
            
            except Exception as e:
                logger.error(f'Error closing Redpanda consumer: {e}')
            finally:
                self.consumer = None
                self._closed = True

    def get_stats(self) -> Dict[str, int]:
        """Get consumer statistics.
        
        Returns:
            Dict with consumed message count
        """
        return {
            'messages_consumed': self._messages_consumed,
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False

#############################
# ===== USAGE EXAMPLE ===== #
#############################

# async def example_producer():
#     """Example: Publishing messages to Redpanda."""
    
#     async with RedpandaProducer() as producer:
#         # Publish single message
#         await producer.publish(
#             topic='orderbook.raw',
#             key='BTCUSDT',
#             value={
#                 'symbol': 'BTCUSDT',
#                 'timestamp': '2024-01-01T00:00:00Z',
#                 'bids': [[50000.0, 1.5], [49999.0, 2.0]],
#                 'asks': [[50001.0, 1.2], [50002.0, 1.8]]
#             }
#         )
        
#         # Publish batch
#         messages = [
#             {'symbol': 'BTCUSDT', 'price': 50000},
#             {'symbol': 'ETHUSDT', 'price': 3000},
#             {'symbol': 'SOLUSDT', 'price': 100}
#         ]
#         count = await producer.publish_batch('orderbook.raw', messages)
#         logger.info(f"Published {count} messages")
        
#         # Check stats
#         stats = producer.get_stats()
#         logger.info(f"Stats: {stats}")


# async def example_consumer():
#     """Example: Consuming messages from Redpanda."""
    
#     async with RedpandaConsumer(
#         topics=['orderbook.metrics'],
#         group_id='example-consumer',
#         auto_offset_reset='latest'
#     ) as consumer:
        
#         # Consume messages
#         async for message in consumer.consume():
#             logger.info(
#                 f"Received: {message.key} from "
#                 f"{message.topic}:{message.partition}:{message.offset}"
#             )
#             logger.info(f"Value: {message.value}")
            
#             # Process message here...
            
#             # Break after 10 messages for demo
#             if consumer.get_stats()['messages_consumed'] >= 10:
#                 break


# async def example_manual_commit():
#     """Example: Manual offset commit for exactly-once processing."""
    
#     async with RedpandaConsumer(
#         topics=['orderbook.metrics'],
#         group_id='db-writer',
#         auto_commit=False  # Manual commit
#     ) as consumer:
        
#         batch = []
        
#         async for message in consumer.consume():
#             batch.append(message.value)
            
#             # Process in batches of 100
#             if len(batch) >= 100:
#                 # Write to database
#                 # await db.insert_batch(batch)
                
#                 # Commit offset AFTER successful write
#                 await consumer.commit()
                
#                 logger.info(f"Processed and committed batch of {len(batch)}")
#                 batch = []

# if __name__ == "__main__":
#     # Run producer example
#     asyncio.run(example_producer())
    
#     # Run consumer example
#     # asyncio.run(example_consumer())