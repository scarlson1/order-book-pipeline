import json
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaSink,
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
)
from pyflink.common import WatermarkStrategy, Duration
from pyflink.common.serialization import SimpleStringSchema

from src.config import settings

def parse_orderbook(raw_message: str) -> dict:
    return json.loads(raw_message)

def check_alerts(metrics: dict) -> dict | None:
    """Check if metrics trigger any alerts.
    
    Args:
        metrics: Calculated metrics dictionary
        
    Returns:
        Alert dictionary or None
    """
    imbalance = abs(metrics.get('imbalance_ratio', 0))
    
    if imbalance >= settings.alert_threshold_high:
        return {
            'symbol': metrics['symbol'],
            'timestamp': metrics['timestamp'],
            'alert_type': 'EXTREME_IMBALANCE',
            'severity': 'CRITICAL' if imbalance >= 0.85 else 'HIGH',
            'message': f"Extreme imbalance detected: {imbalance:.2%}",
            'metric_value': imbalance,
            'threshold_value': settings.alert_threshold_high,
        }
    
    return None

def main():
    env = StreamExecutionEnvironment
    env.enable_checkpointing(10 * 1000)
    env.set_parallelism(2)

    # Configure Kafka/Redpanda source
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
        .set_topics(settings.redpanda_topics['metrics'])
        .set_group_id('flink-metrics-processor')
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
    metrics_stream = env.from_source(
        source=source,
        watermark_strategy=watermark_strategy,
        source_name='Redpanda OrderBook Metrics'
    )

    # Generate alerts from metrics
    alerts_stream = (
        metrics_stream
        .map(check_alerts)
        .filter(lambda x: x is not None)
    )

    # Configure Kafka/Redpanda sink for alerts
    alerts_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(settings.redpanda_topics['alerts'])
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )

    # Serialize and sink
    alerts_stream.map(json.dumps).sink_to(alerts_sink)

    # Execute
    env.execute('OrderBook Alerts Processor')


if __name__ == '__main__':
    main()