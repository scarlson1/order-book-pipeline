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
# from pyflink.datastream.window import TumblingEventTimeWindows, SlidingEventTimeWindows
# from pyflink.common.time import Time
import json

from src.config import settings
from src.ingestion.metrics_calculator import calculate_metrics

# TODO: add notes to README about offset strategy ('latest' & run batch to fill gaps ??)
# parse with OrderBookMetrics to use built in calc methods (mid-price, spread, etc.) ??

# ===== Processing Functions ===== #

def parse_orderbook(raw_message: str) -> dict:
    """Parse raw JSON order book message.
    
    Args:
        raw_message: JSON string from Redpanda
        
    Returns:
        Parsed order book dictionary
    """
    return json.loads(raw_message)


# ===== Main Flink Job ===== #

def main():
    # Initialize Flink execution environment
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/datastream_tutorial/
    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(10 * 1000)
    env.set_parallelism(2)
    
    # Configure Kafka/Redpanda source
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
        .set_topics(settings.redpanda_topics['raw'])
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
        .map(calculate_metrics)
        .filter(lambda x: x is not None)
    )
    
    # Generate alerts from metrics (moved to orderbook_alert)
    # alerts_stream = (
    #     metrics_stream
    #     .map(check_alerts)
    #     .filter(lambda x: x is not None)
    # )
    
    # Configure Kafka/Redpanda sink for metrics
    metrics_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(settings.redpanda_topics['metrics'])
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )
    
    # Configure Kafka/Redpanda sink for alerts (moved to orderbook_alert)
    # alerts_sink = (
    #     KafkaSink.builder()
    #     .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
    #     .set_record_serializer(
    #         KafkaRecordSerializationSchema.builder()
    #         .set_topic(settings.redpanda_topics['alerts'])
    #         .set_value_serialization_schema(SimpleStringSchema())
    #         .build()
    #     )
    #     .build()
    # )
    
    # Serialize and sink
    metrics_stream.map(json.dumps).sink_to(metrics_sink)
    # alerts_stream.map(json.dumps).sink_to(alerts_sink) # (moved to orderbook_alert)
    
    # Execute
    env.execute('OrderBook Metrics Processor')


if __name__ == '__main__':
    main()

####################################
## ----- FLINK SQL APPROACH ----- ##
####################################

# requires the flink-sql-connector-kafka to be installed in Dockerfile.flink

# # Source: orderbook.raw (Kafka/Redpanda)
# def create_raw_source(t_env):
#     table_name = 'orderbook_raw'
#     source_ddl = f"""
#         CREATE TABLE {table_name} (
#             `timestamp` STRING,
#             symbol STRING,
#             bids ARRAY<ARRAY<STRING>>,
#             asks ARRAY<ARRAY<STRING>>,
#             update_id BIGINT,
#             ingested_at STRING,
#             source STRING,
#             proc_time AS PROCTIME()
#             watermark_timestamp AS TO_TIMESTAMP('timestamp'),
#             WATERMARK FOR watermark_timestamp AS watermark_timestamp - INTERVAL '5' SECOND
#         ) WITH (
#             'connector' = 'kafka',
#             'topic' = 'orderbook.raw',
#             'properties.bootstrap.servers' = '{settings.redpanda_bootstrap_servers}',
#             'properties.group.id' = 'flink-orderbook-raw',
#             'scan.startup.mode' = 'latest-offset',
#             'format' = 'json'
#         );
#         """
#     t_env.execute_sql(source_ddl)
#     return table_name
    

# # Sink: orderbook.metrics (Kafka/Redpanda)
# def create_metrics_sink(t_env):
#     table_name = 'orderbook_metrics'
#     source_ddl = f"""
#         CREATE TABLE {table_name} (
#             symbol STRING,
#             mid_price DOUBLE,
#             best_bid DOUBLE,
#             best_ask DOUBLE,
#             spread_bps DOUBLE,
#             event_time TIMESTAMP_LTZ(3)
#         ) WITH (
#             'connector' = 'kafka',
#             'topic' = 'orderbook.metrics',
#             'properties.bootstrap.servers' = '{settings.redpanda_bootstrap_servers}',
#             'format' = 'json'
#         );
#         """
#     t_env.execute_sql(source_ddl)
#     return table_name


# def process_metrics():
#     env = StreamExecutionEnvironment.get_execution_environment()
#     env.enable_checkpointing(10 * 1000)
#     # env.set_parallelism(1)

#     # Set up the table environment
#     settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
#     t_env = StreamTableEnvironment.create(env, environment_settings=settings)

#     try:
#         source_table = create_raw_source(t_env)
#         sink_table = create_metrics_sink(t_env)

#         # Insert computed metrics
#         t_env.execute_sql(
#             f"""
#                 INSERT INTO {sink_table}
#                 SELECT
#                     symbol,
#                     (CAST(asks[1][1] AS DOUBLE) + CAST(bids[1][1] AS DOUBLE)) / 2 AS mid_price,
#                     CAST(bids[1][1] AS DOUBLE) AS best_bid,
#                     CAST(asks[1][1] AS DOUBLE) AS best_ask,
#                     ((CAST(asks[1][1] AS DOUBLE) - CAST(bids[1][1] AS DOUBLE)) /
#                     ((CAST(asks[1][1] AS DOUBLE) + CAST(bids[1][1] AS DOUBLE)) / 2)) * 10000
#                         AS spread_bps,
#                     TO_TIMESTAMP_LTZ(CAST(`timestamp` AS BIGINT), 3) AS event_time
#                 FROM {source_table}
#                 WHERE cardinality(bids) > 0 AND cardinality(asks) > 0;
#             """
#         ).wait()
    
#     except Exception as e:
#         print(f'Failed writing records from Kafka to JDBC: {str(e)}')
