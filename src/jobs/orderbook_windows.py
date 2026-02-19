# Windowed Aggregations

# - [ ] Tumbling 1-minute windows per symbol
#   - [ ] avg, min, max imbalance
#   - [ ] avg spread, avg volume
#   - [ ] sample count
# - [ ] Sliding 5-minute windows (every 30 seconds)
#   - [ ] Rolling statistics used by alert engine
# - [ ] Sink to `orderbook.metrics.windowed` topic

import json
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.common.time import Duration
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaSink,
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    DeliveryGuarantee
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream.window import SlidingEventTimeWindows, TumblingProcessingTimeWindows
from pyflink.datastream.functions import AggregateFunction, KeyedProcessFunction, KeyedCoProcessFunction

from src.common.models import Alert, AlertType, OrderBookMetrics, Severity
from src.config import settings
from jobs.orderbook_alert import parse_metrics

# TODO: where are agg windows saved ?? Don't appear to have a pydantic type / table created ??
# def calc_tumbling_vals(metrics: OrderBookMetrics) -> dict:

# ===== Aggregate Functions ===== #

#   - [ ] avg, min, max imbalance
#   - [ ] avg spread, avg volume
#   - [ ] sample count
class TumblingAggFunction(AggregateFunction):
    def create_accumulator(self) -> dict: # todo: type
        return {
            imbTotal: 0,
            imbMin: 0,
            imbMax: 0,
            spreadTotal: 0,
            volumeTotal: 0,
            sampleCount: 0
        }

    def add(self, value: OrderBookMetrics, acc: dict) -> dict:
        return {
            imbTotal: acc['imbTotal'] + value.imbalance_ratio,
            imbMin: min(acc['imbMin'], value.imbalance_ratio),
            imbMax: max(acc['imbMax'], value.imbalance_ratio),
            spreadTotal: acc['spreadTotal'] + value.spread_abs, # absolute or spread_bps ??
            volumeTotal: acc['volumeTotal'] + value.total_volume,
            sampleCount: acc['sampleCount'] + 1
        }
    
    def get_result(self, acc: dict) -> dict:
        return {
            avg_imb: acc['imbTotal'] / acc['sampleCount'],
            min_imb: acc['imbMin'],
            max_imb: acc['imbMax'],
            avg_spread: acc['spreadTotal'] / acc['sampleCount'],
            avg_volume: acc['volumeTotal'] / acc['sampleCount'],
            sample_count: acc['sampleCount']
        }

    def merge(self, a: dict, b: dict) -> dict:
        return {
            imbTotal: a['imbTotal'] + b['imbTotal'],
            imbMin: min(a['imbMin'], b['imbMin']),
            imbMax: max(a['imbMax'], b['imbMax']),
            spreadTotal: a['spreadTotal'] + b['spreadTotal'],
            volumeTotal: a['volumeTotal'] + b['volumeTotal'],
            sampleCount: a['sampleCount'] + b['sampleCount'],
        }

class SlidingAggFunction(AggregateFunction):
    def create_accumulator(self) -> dict: # todo: type
        return {
            imbTotal: 0,
            imbMin: 0,
            imbMax: 0,
            spreadTotal: 0,
            volumeTotal: 0,
            sampleCount: 0
        }

    def add(self, value: OrderBookMetrics, acc: dict) -> dict:
        return {
            imbTotal: acc['imbTotal'] + value.imbalance_ratio,
            imbMin: min(acc['imbMin'], value.imbalance_ratio),
            imbMax: max(acc['imbMax'], value.imbalance_ratio),
            spreadTotal: acc['spreadTotal'] + value.spread_abs, # absolute or spread_bps ??
            volumeTotal: acc['volumeTotal'] + value.total_volume,
            sampleCount: acc['sampleCount'] + 1
        }
    
    def get_result(self, acc: dict) -> dict:
        return {
            avg_imb: acc['imbTotal'] / acc['sampleCount'],
            min_imb: acc['imbMin'],
            max_imb: acc['imbMax'],
            avg_spread: acc['spreadTotal'] / acc['sampleCount'],
            avg_volume: acc['volumeTotal'] / acc['sampleCount'],
            sample_count: acc['sampleCount']
        }

    def merge(self, a: dict, b: dict) -> dict:
        return {
            imbTotal: a['imbTotal'] + b['imbTotal'],
            imbMin: min(a['imbMin'], b['imbMin']),
            imbMax: max(a['imbMax'], b['imbMax']),
            spreadTotal: a['spreadTotal'] + b['spreadTotal'],
            volumeTotal: a['volumeTotal'] + b['volumeTotal'],
            sampleCount: a['sampleCount'] + b['sampleCount'],
        }


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(10 * 1000)
    env.set_parallelism(settings.flink_parallelism)

    # Configure watermark strategy for event time processing
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/
    watermark_strategy = (
        WatermarkStrategy
            .for_bounded_out_of_orderness(Duration.of_seconds(5))
            .with_idleness(Duration.of_seconds(10))
    )

    

    try:
        source = (
            KafkaSource.builder()
                .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
                .set_topics(settings.redpanda_topics['metrics'])
                .set_group_id('flink-agg-processor')
                .set_start_offsets(KafkaOffsetsInitializer.latest())
                .set_value_only_deserializer(SimpleStringSchema())
                .build()
        )

        metrics_stream = (
            env.from_source(
                source=source,
                watermark_strategy=watermark_strategy,
                source_name="Redpanda OrderBook Metrics"
            )
                .map(parse_metrics)
                .filter(lambda x: x is not None)
                .key_by(lambda x: x['symbol'])
        )

        # tumbling 1 minute windows per symbol
        tumble_stream = (
            metrics_stream
                .window(TumblingProcessingTimeWindows.of(Duration.ofMinutes(1)))
                .aggregate(TumblingAggFunction())
                # .reduce()
        ) # need to group by window_start ?? need to create composite primary key in sink ??


        # sliding 5 minute windows every 30 seconds
        five_min_sliding_stream = (
            metrics_stream
                .window(SlidingEventTimeWindows.of(Duration.ofMinutes(5), Duration.ofSeconds(30)))
                .aggregate(SlidingAggFunction())
        )
        # https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/dev/datastream/operators/windows/#working-with-window-results

        all_windowed = tumble_stream.union(five_min_sliding_stream)


        aggregate_sink = (
            KafkaSink.builder()
                .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
                .set_record_serializer(
                    KafkaRecordSerializationSchema.builder()
                        .set_topic(settings.redpanda_topics['windowed'])
                        .set_value_serialization_schema(SimpleStringSchema())
                        .build()
                )
                .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
                .set_transactional_id_prefix('orderbook-windowed')
                .build()
        )

        # TEMPORARY UNTIL FINAL STREAM IS COMPLETE
        metrics_stream.map(lambda x: json.dumps(x.model_dump(mode='json'))).sink_to(aggregate_sink)

        env.execute("OrderBook Window Aggregate Processor")


    
    except Exception as e:
        print('writing records windowed from Kafka to JDBC failed: ', str(e))


if __name__ == '__main__':
    main()