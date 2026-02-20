# Windowed Aggregations

# Creates per symbol:
#   - 1m Tumbling windows
#   - 5m Sliding windows

import json
from datetime import datetime, timedelta, timezone
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.common.time import Duration, Time
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaSink,
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    DeliveryGuarantee
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream.window import SlidingEventTimeWindows, TumblingProcessingTimeWindows
from pyflink.datastream.functions import AggregateFunction

from common.models import OrderBookMetrics
from config import settings
from jobs.orderbook_alerts import parse_metrics

# ===== Aggregate Functions ===== #


def get_symbol(metric: OrderBookMetrics | dict) -> str:
    """Extract symbol from either model or dict payload."""
    return metric["symbol"] if isinstance(metric, dict) else metric.symbol


def to_json_record(record) -> str:
    """Serialize model/dict results for Kafka string sink."""
    if isinstance(record, dict):
        return json.dumps(record)
    if hasattr(record, "model_dump"):
        return json.dumps(record.model_dump(mode="json"))
    return json.dumps(record)

class WindowAggFunction(AggregateFunction):
    """Aggregate metrics into payload compatible with DB windowed schema."""

    def __init__(self, window_type: str, window_duration_seconds: int):
        self.window_type = window_type
        self.window_duration_seconds = window_duration_seconds

    def create_accumulator(self) -> dict:
        return {
            'symbol': '',
            'imb_total': 0.0,
            'imb_min': None,
            'imb_max': None,
            'spread_bps_total': 0.0,
            'spread_bps_min': None,
            'spread_bps_max': None,
            'bid_volume_total': 0.0,
            'ask_volume_total': 0.0,
            'total_volume_total': 0.0,
            'sample_count': 0,
        }

    def add(self, value: OrderBookMetrics, acc: dict) -> dict:
        imbalance = float(value.imbalance_ratio or 0.0)
        spread_bps = float(value.spread_bps or 0.0)
        bid_volume = float(value.bid_volume or 0.0)
        ask_volume = float(value.ask_volume or 0.0)
        total_volume = float(value.total_volume or 0.0)

        return {
            'symbol': value.symbol or acc['symbol'],
            'imb_total': acc['imb_total'] + imbalance,
            'imb_min': imbalance if acc['imb_min'] is None else min(acc['imb_min'], imbalance),
            'imb_max': imbalance if acc['imb_max'] is None else max(acc['imb_max'], imbalance),
            'spread_bps_total': acc['spread_bps_total'] + spread_bps,
            'spread_bps_min': spread_bps if acc['spread_bps_min'] is None else min(acc['spread_bps_min'], spread_bps),
            'spread_bps_max': spread_bps if acc['spread_bps_max'] is None else max(acc['spread_bps_max'], spread_bps),
            'bid_volume_total': acc['bid_volume_total'] + bid_volume,
            'ask_volume_total': acc['ask_volume_total'] + ask_volume,
            'total_volume_total': acc['total_volume_total'] + total_volume,
            'sample_count': acc['sample_count'] + 1,
        }

    def get_result(self, acc: dict) -> dict:
        count = acc['sample_count']
        if count == 0:
            return {
                'symbol': acc['symbol'],
                'window_type': self.window_type,
                'window_start': None,
                'window_end': None,
                'window_duration_seconds': self.window_duration_seconds,
                'sample_count': 0,
            }

        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(seconds=self.window_duration_seconds)

        return {
            'symbol': acc['symbol'],
            'window_type': self.window_type,
            'window_start': window_start.isoformat(),
            'window_end': window_end.isoformat(),
            'window_duration_seconds': self.window_duration_seconds,
            'avg_imbalance': acc['imb_total'] / count,
            'min_imbalance': acc['imb_min'],
            'max_imbalance': acc['imb_max'],
            'avg_spread_bps': acc['spread_bps_total'] / count,
            'min_spread_bps': acc['spread_bps_min'],
            'max_spread_bps': acc['spread_bps_max'],
            'avg_bid_volume': acc['bid_volume_total'] / count,
            'avg_ask_volume': acc['ask_volume_total'] / count,
            'avg_total_volume': acc['total_volume_total'] / count,
            'total_bid_volume': acc['bid_volume_total'],
            'total_ask_volume': acc['ask_volume_total'],
            'total_volume': acc['total_volume_total'],
            'sample_count': count,
            'window_velocity': None,
        }

    def merge(self, a: dict, b: dict) -> dict:
        return {
            'symbol': a['symbol'] or b['symbol'],
            'imb_total': a['imb_total'] + b['imb_total'],
            'imb_min': (
                b['imb_min'] if a['imb_min'] is None
                else a['imb_min'] if b['imb_min'] is None
                else min(a['imb_min'], b['imb_min'])
            ),
            'imb_max': (
                b['imb_max'] if a['imb_max'] is None
                else a['imb_max'] if b['imb_max'] is None
                else max(a['imb_max'], b['imb_max'])
            ),
            'spread_bps_total': a['spread_bps_total'] + b['spread_bps_total'],
            'spread_bps_min': (
                b['spread_bps_min'] if a['spread_bps_min'] is None
                else a['spread_bps_min'] if b['spread_bps_min'] is None
                else min(a['spread_bps_min'], b['spread_bps_min'])
            ),
            'spread_bps_max': (
                b['spread_bps_max'] if a['spread_bps_max'] is None
                else a['spread_bps_max'] if b['spread_bps_max'] is None
                else max(a['spread_bps_max'], b['spread_bps_max'])
            ),
            'bid_volume_total': a['bid_volume_total'] + b['bid_volume_total'],
            'ask_volume_total': a['ask_volume_total'] + b['ask_volume_total'],
            'total_volume_total': a['total_volume_total'] + b['total_volume_total'],
            'sample_count': a['sample_count'] + b['sample_count'],
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
                .set_starting_offsets(KafkaOffsetsInitializer.latest())
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
                .key_by(get_symbol)
        )

        # tumbling 1 minute windows per symbol
        tumble_stream = (
            metrics_stream
                .window(TumblingProcessingTimeWindows.of(Time.minutes(1)))
                .aggregate(WindowAggFunction('1m_tumbling', 60))
                # .window(TumblingProcessingTimeWindows.of(Duration.of_minutes(1)))
                # .aggregate(TumblingAggFunction())
                # .reduce()
        ) # need to group by window_start ?? need to create composite primary key in sink ??


        # sliding 5 minute windows every 30 seconds
        five_min_sliding_stream = (
            metrics_stream
                .window(SlidingEventTimeWindows.of(Time.minutes(5), Time.seconds(30)))
                .aggregate(WindowAggFunction('5m_sliding', 300))
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
        all_windowed.map(
            to_json_record,
            output_type=Types.STRING()
        ).sink_to(aggregate_sink)

        env.execute("OrderBook Window Aggregate Processor")


    
    except Exception as e:
        print('writing records windowed from Kafka to JDBC failed: ', str(e))


if __name__ == '__main__':
    main()
