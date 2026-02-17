"""Apache Flink job for order book metrics processing.

This job:
1. Consumes raw order book data from Redpanda (orderbook.raw topic)
2. Calculates imbalance metrics using windowed aggregations
3. Detects alert conditions
4. Publishes processed metrics to Redpanda (orderbook.metrics topic)
5. Publishes alerts to Redpanda (orderbook.alerts topic)

Documentation:
- PyFlink Overview: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/overview/
- Flink Kafka Connector: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
- Flink Windows: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/
- Flink Watermarks: https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/
"""

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaSink,
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
)
from pyflink.common import WatermarkStrategy, Duration
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream.window import TumblingEventTimeWindows, SlidingEventTimeWindows
from pyflink.common.time import Time
import json
import os


# ===== Configuration ===== #

REDPANDA_BROKERS = os.getenv('REDPANDA_BOOTSTRAP_SERVERS', 'redpanda:9092')

TOPIC_RAW = 'orderbook.raw'             # Input: raw order book snapshots
TOPIC_METRICS = 'orderbook.metrics'     # Output: calculated metrics
TOPIC_ALERTS = 'orderbook.alerts'       # Output: generated alerts

ALERT_THRESHOLD_HIGH = float(os.getenv('ALERT_THRESHOLD_HIGH', '0.70'))


# ===== Processing Functions ===== #

def parse_orderbook(raw_message: str) -> dict:
    """Parse raw JSON order book message.
    
    Args:
        raw_message: JSON string from Redpanda
        
    Returns:
        Parsed order book dictionary
    """
    return json.loads(raw_message)


def calculate_imbalance(data: dict) -> dict:
    """Calculate order book imbalance metrics.
    
    Args:
        data: Parsed order book dictionary
        
    Returns:
        Dictionary with calculated metrics
    """
    bids = data.get('bids', [])[:10]
    asks = data.get('asks', [])[:10]
    
    bid_volume = sum(float(vol) for _, vol in bids)
    ask_volume = sum(float(vol) for _, vol in asks)
    total_volume = bid_volume + ask_volume
    
    if total_volume == 0:
        return None
    
    imbalance_ratio = (bid_volume - ask_volume) / total_volume
    
    best_bid = float(bids[0][0]) if bids else 0
    best_ask = float(asks[0][0]) if asks else 0
    mid_price = (best_bid + best_ask) / 2
    spread_bps = ((best_ask - best_bid) / mid_price * 10000) if mid_price > 0 else 0
    
    return {
        'symbol': data['symbol'],
        'timestamp': data['timestamp'],
        'mid_price': mid_price,
        'best_bid': best_bid,
        'best_ask': best_ask,
        'imbalance_ratio': imbalance_ratio,
        'bid_volume': bid_volume,
        'ask_volume': ask_volume,
        'total_volume': total_volume,
        'spread_bps': spread_bps,
    }


def check_alerts(metrics: dict) -> dict | None:
    """Check if metrics trigger any alerts.
    
    Args:
        metrics: Calculated metrics dictionary
        
    Returns:
        Alert dictionary or None
    """
    imbalance = abs(metrics.get('imbalance_ratio', 0))
    
    if imbalance >= ALERT_THRESHOLD_HIGH:
        return {
            'symbol': metrics['symbol'],
            'timestamp': metrics['timestamp'],
            'alert_type': 'EXTREME_IMBALANCE',
            'severity': 'CRITICAL' if imbalance >= 0.85 else 'HIGH',
            'message': f"Extreme imbalance detected: {imbalance:.2%}",
            'metric_value': imbalance,
            'threshold_value': ALERT_THRESHOLD_HIGH,
        }
    
    return None


# ===== Main Flink Job ===== #

def main():
    """Main Flink job entry point."""
    
    # Initialize Flink execution environment
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/datastream_tutorial/
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(2)
    
    # Configure Kafka/Redpanda source
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(REDPANDA_BROKERS)
        .set_topics(TOPIC_RAW)
        .set_group_id('flink-orderbook-processor')
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )
    
    # Configure watermark strategy for event time processing
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/
    watermark_strategy = (
        WatermarkStrategy
        .for_bounded_out_of_orderness(Duration.of_seconds(5))
        .with_idleness(Duration.of_seconds(10))
    )
    
    # Build processing pipeline
    raw_stream = env.from_source(
        source=source,
        watermark_strategy=watermark_strategy,
        source_name='Redpanda OrderBook Raw'
    )
    
    # Parse → Calculate → Filter
    metrics_stream = (
        raw_stream
        .map(parse_orderbook)
        .filter(lambda x: x is not None)
        .map(calculate_imbalance)
        .filter(lambda x: x is not None)
    )
    
    # Generate alerts from metrics
    alerts_stream = (
        metrics_stream
        .map(check_alerts)
        .filter(lambda x: x is not None)
    )
    
    # Configure Kafka/Redpanda sink for metrics
    metrics_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(REDPANDA_BROKERS)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(TOPIC_METRICS)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )
    
    # Configure Kafka/Redpanda sink for alerts
    alerts_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(REDPANDA_BROKERS)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(TOPIC_ALERTS)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )
    
    # Serialize and sink
    metrics_stream.map(json.dumps).sink_to(metrics_sink)
    alerts_stream.map(json.dumps).sink_to(alerts_sink)
    
    # Execute
    env.execute('OrderBook Metrics Processor')


if __name__ == '__main__':
    main()