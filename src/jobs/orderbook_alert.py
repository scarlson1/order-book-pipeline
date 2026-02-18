"""Apache Flink job for order book alert detection.

This job:
1. Consumes processed metrics from Redpanda (orderbook.metrics topic)
2. Detects alert conditions (extreme imbalance, imbalance flip, spread widening, velocity spike)
3. Rate-limits / deduplicates alerts using keyed state + timers
4. Publishes triggered alerts to Redpanda (orderbook.alerts topic)

Documentation:
- PyFlink Overview:         https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/overview/
- Flink Kafka Connector:    https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
- Flink Keyed State:        https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/fault-tolerance/state/
- Flink ProcessFunction:    https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/
- Flink Windows:            https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/
- Flink Watermarks:         https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/
- Flink Timers:             https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#timers
"""

import json

from pydantic import ValidationError
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaSink,
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
)
from pyflink.common import WatermarkStrategy, Duration
from pyflink.common.serialization import SimpleStringSchema

from src.common.models import Alert, OrderBookMetrics, Severity
from src.config import settings


# ===== Parsing ===== #


def parse_metrics(raw_message: str) -> OrderBookMetrics | None:
    """Parse a JSON metrics message from the orderbook.metrics topic."""
    # return json.loads(raw_message)
    try:
        json_msg = json.loads(raw_message)
        orderBookMetric = OrderBookMetrics(**json_msg)
        return orderBookMetric
    except ValidationError as e:
        print(f"Validation Error:\n{e.json(indent=4)}")
        return None


# ===== Alert Checks ===== #


def check_extreme_imbalance(metrics: OrderBookMetrics) -> Alert | None:
    """Emit an alert when |imbalance_ratio| exceeds the HIGH threshold.

    Compares the absolute value of `imbalance_ratio` against
    `settings.alert_threshold_high` (default 0.70).  Returns a CRITICAL
    alert above 0.85, HIGH otherwise.

    Args:
        metrics: Parsed OrderBookMetrics dictionary.

    Returns:
        Alert dictionary, or None if the threshold is not breached.

    TODO:
        - Consider emitting both BID and ASK side context in the alert
              payload (best_bid / best_ask from metrics).
    """
    imbalance = abs(metrics.get("imbalance_ratio", 0))

    if imbalance >= settings.alert_threshold_medium:
        severity = (
            Severity.CRITICAL if imbalance >= 0.85 else
            Severity.HIGH if imbalance >= settings.alert_threshold_medium else 
            Severity.MEDIUM
        )
        vals = {
            "symbol": metrics["symbol"],
            "timestamp": metrics["timestamp"],
            "alert_type": "EXTREME_IMBALANCE",
            "severity": severity,
            "message": f"Extreme imbalance detected: {imbalance:.2%}",
            "metric_value": imbalance,
            "threshold_value": settings.alert_threshold_high,
        }
        alert = Alert(**vals)
        return alert

    return None


def check_imbalance_flip(metrics: dict) -> dict | None:
    """Detect a sign change in imbalance_ratio (buy pressure → sell pressure or vice-versa).

    A "flip" occurs when the sign of the current `imbalance_ratio` is
    opposite to the previously observed value for the same symbol.  Because
    this comparison is per-symbol it **must** run inside a keyed stream and
    use Flink ValueState to persist the previous value across invocations.

    Args:
        metrics: Parsed OrderBookMetrics dictionary.

    Returns:
        Alert dictionary on a sign change, or None.

    TODO:
        - [ ] Promote this function to a `KeyedProcessFunction` subclass so
              it has access to Flink's state backend.
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/
              Ref (Python API): https://nightlies.apache.org/flink/flink-docs-stable/api/python/reference/pyflink.datastream.html#pyflink.datastream.KeyedProcessFunction

        - [ ] Declare a `ValueState[float]` descriptor to store the previous
              imbalance per symbol key:
              ```python
              from pyflink.datastream.state import ValueStateDescriptor
              from pyflink.common.typeinfo import Types

              prev_imbalance_state = ValueStateDescriptor(
                  'prev_imbalance', Types.FLOAT()
              )
              ```
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/fault-tolerance/state/#using-managed-keyed-state
              Ref (Python): https://nightlies.apache.org/flink/flink-docs-stable/api/python/reference/pyflink.datastream.html#pyflink.datastream.state.ValueStateDescriptor

        - [ ] In `open()`, register the state descriptor via
              `self.prev_imbalance = runtime_context.get_state(prev_imbalance_state)`
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#the-keyedprocessfunction

        - [ ] In `process_element()`, read the previous value, compare signs,
              update state, and yield an alert on a flip:
              ```python
              prev = self.prev_imbalance.value()
              curr = metrics['imbalance_ratio']
              if prev is not None and (prev * curr < 0):   # sign change
                  yield alert_dict
              self.prev_imbalance.update(curr)
              ```

        - [ ] Key the upstream stream by symbol before applying this function:
              `metrics_stream.key_by(lambda m: m['symbol'])`
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/overview/#keyby
    """
    # TODO: implement — placeholder until KeyedProcessFunction is wired up
    pass


def check_spread_widening(metrics: dict) -> dict | None:
    """Emit an alert when the current spread exceeds N × its rolling average.

    Uses a sliding window to maintain a rolling average of `spread_bps` per
    symbol, then compares the latest value against
    `settings.spread_alert_multiplier` (default 2.0×).

    Args:
        metrics: Parsed OrderBookMetrics dictionary.

    Returns:
        Alert dictionary when spread is abnormally wide, or None.

    TODO:
        - [ ] Apply a sliding event-time window to compute the rolling average
              spread per symbol before this check runs.
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/#sliding-windows

        - [ ] Import and configure `SlidingEventTimeWindows`:
              ```python
              from pyflink.datastream.window import SlidingEventTimeWindows
              from pyflink.common.time import Time

              windowed = (
                  metrics_stream
                  .key_by(lambda m: m['symbol'])
                  .window(SlidingEventTimeWindows.of(
                      Time.minutes(5),   # window size
                      Time.seconds(30),  # slide interval
                  ))
                  .aggregate(SpreadAverageAggregateFunction())
              )
              ```
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/#window-functions
              Ref (Python): https://nightlies.apache.org/flink/flink-docs-stable/api/python/reference/pyflink.datastream.html#pyflink.datastream.window.SlidingEventTimeWindows

        - [ ] Implement `SpreadAverageAggregateFunction` (subclass of
              `AggregateFunction`) that accumulates (sum, count) and returns
              the mean spread_bps for the window.
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/#aggregatefunction
              Ref (Python): https://nightlies.apache.org/flink/flink-docs-stable/api/python/reference/pyflink.datastream.html#pyflink.datastream.functions.AggregateFunction

        - [ ] Join or connect the windowed average stream back to the raw
              metrics stream (e.g., via `CoProcessFunction` or broadcast state)
              so each event can be compared against its rolling baseline.
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#the-coprocessfunction

        - [ ] Threshold comparison:
              ```python
              if metrics['spread_bps'] > rolling_avg * settings.spread_alert_multiplier:
                  return { 'alert_type': 'SPREAD_WIDENING', ... }
              ```
    """
    # TODO: implement — placeholder until windowed rolling average is wired up
    pass


def check_velocity_spike(metrics: dict) -> dict | None:
    """Emit an alert when the rate of change of imbalance_ratio exceeds the threshold.

    Velocity = |current_imbalance − previous_imbalance| / Δt.  A sliding
    window is used to compute the rate of change over
    `settings.rolling_window_seconds` (default 60 s).

    Args:
        metrics: Parsed OrderBookMetrics dictionary.

    Returns:
        Alert dictionary on a velocity spike, or None.

    TODO:
        - [ ] Use a sliding event-time window (same pattern as
              `check_spread_widening`) to compute Δimbalance / Δt per symbol.
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/#sliding-windows

        - [ ] Alternatively, use `imbalance_velocity` if it is already
              populated by the upstream metrics job (see OrderBookMetrics in
              src/common/models.py).  If so, this check reduces to a simple
              threshold comparison and no window is needed here.

        - [ ] Implement a `VelocityAggregateFunction` (or reuse keyed state
              in a `KeyedProcessFunction`) that tracks the first and last
              imbalance values within the window and divides by elapsed time.
              Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/#aggregatefunction

        - [ ] Threshold comparison using `settings.velocity_threshold` (default 0.05):
              ```python
              if abs(velocity) > settings.velocity_threshold:
                  return { 'alert_type': 'VELOCITY_SPIKE', ... }
              ```
              Ref: src/config.py → Settings.velocity_threshold

        - [ ] Window size should be driven by `settings.rolling_window_seconds`:
              ```python
              Time.seconds(settings.rolling_window_seconds)
              ```
    """
    # TODO: implement — placeholder until velocity window is wired up
    pass


# ===== Rate Limiting / Deduplication ===== #

# TODO: Implement an `AlertRateLimiter` KeyedProcessFunction that suppresses
#       duplicate alerts for the same (symbol, alert_type) pair within a
#       cooldown window.
#
#   Steps:
#   - [ ] Subclass `KeyedProcessFunction`; key the stream by
#         `(symbol, alert_type)` (use a tuple or composite string key).
#         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/
#         Ref (Python): https://nightlies.apache.org/flink/flink-docs-stable/api/python/reference/pyflink.datastream.html#pyflink.datastream.KeyedProcessFunction
#
#   - [ ] Declare a `ValueState[bool]` (or `ValueState[long]` for last-fired
#         timestamp) to track whether an alert is currently "suppressed":
#         ```python
#         from pyflink.datastream.state import ValueStateDescriptor
#         from pyflink.common.typeinfo import Types
#
#         suppressed_state = ValueStateDescriptor('suppressed', Types.BOOLEAN())
#         ```
#         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/fault-tolerance/state/#using-managed-keyed-state
#
#   - [ ] In `process_element()`, check the suppression flag; if not
#         suppressed, forward the alert, set the flag to True, and register
#         an event-time (or processing-time) timer for the cooldown duration:
#         ```python
#         ctx.timer_service().register_processing_time_timer(
#             ctx.timer_service().current_processing_time() + cooldown_ms
#         )
#         ```
#         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#timers
#
#   - [ ] In `on_timer()`, clear the suppression flag so the next alert for
#         this key can fire:
#         ```python
#         def on_timer(self, timestamp, ctx, out):
#             self.suppressed.clear()
#         ```
#         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#timers
#
#   - [ ] Make the cooldown duration configurable (e.g., add
#         `alert_cooldown_seconds: int = 60` to Settings in src/config.py).


# ===== Main Flink Job ===== #


def main():
    # Initialize Flink execution environment
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/datastream_tutorial/
    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(10 * 1000)
    env.set_parallelism(settings.flink_parallelism)

    # -----------------------------------------------------------------
    # KafkaSource — orderbook.metrics
    # -----------------------------------------------------------------
    # TODO:
    #   - [ ] Confirm the consumer group ID is distinct from the metrics job
    #         ('flink-alerts-processor' vs 'flink-metrics-processor') to avoid
    #         offset conflicts.
    #   - [ ] Consider switching to `KafkaOffsetsInitializer.earliest()` during
    #         development so no events are missed on restart.
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/#starting-offset
    #   - [ ] For production, use `KafkaOffsetsInitializer.committed_offsets()`
    #         with a fallback to `earliest()` to resume from checkpointed offsets.
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/#consumer-offset-committing
    #   - [ ] Replace `SimpleStringSchema` with a typed deserializer (e.g., a
    #         custom `DeserializationSchema` that returns `OrderBookMetrics`)
    #         for end-to-end type safety.
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/#kafka-deserializationschema
    #
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
        .set_topics(settings.redpanda_topics['metrics'])
        .set_group_id('flink-alerts-processor')
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    # Configure watermark strategy for event time processing
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/
    watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(
        Duration.of_seconds(5)
    ).with_idleness(Duration.of_seconds(10))

    # Build processing pipeline
    # TODO: key the stream by symbol immediately after parsing so all
    #       stateful operators (imbalance flip, rate limiter) share the same
    #       key scope without an extra keyBy call.
    #       Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/overview/#keyby
    metrics_stream = (
        env.from_source(
            source=source,
            watermark_strategy=watermark_strategy,
            source_name="Redpanda OrderBook Metrics",
        )
        .map(parse_metrics)
        .filter(lambda x: x is not None)
    )

    # -----------------------------------------------------------------
    # check_extreme_imbalance()  — abs(imbalance) > HIGH threshold
    # -----------------------------------------------------------------
    # TODO:
    #   - [ ] Replace the plain `.map()` with a `KeyedProcessFunction` once
    #         the Alert model and keyed state are in place.
    #   - [ ] Add a `.key_by(lambda m: m['symbol'])` before this map so the
    #         stream is already partitioned for downstream stateful operators.
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/overview/#keyby
    
    extreme_imbalance_stream = metrics_stream \
        .key_by(lambda a: a['symbol']) \
        .map(check_extreme_imbalance) \
        .filter(lambda x: x is not None)
        

    # -----------------------------------------------------------------
    # check_imbalance_flip()  — sign change detection with keyed state
    # -----------------------------------------------------------------
    # TODO:
    #   - [ ] Wire up the `KeyedProcessFunction` described in the function
    #         docstring above.  Replace the placeholder below once implemented:
    #         ```python
    #         imbalance_flip_stream = (
    #             metrics_stream
    #             .key_by(lambda m: m['symbol'])
    #             .process(ImbalanceFlipDetector())
    #         )
    #         ```
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/
    #   - [ ] Union with other alert streams before the rate limiter:
    #         `all_alerts = extreme_imbalance_stream.union(imbalance_flip_stream, ...)`
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/api/python/reference/pyflink.datastream.html#pyflink.datastream.DataStream.union

    # -----------------------------------------------------------------
    # check_spread_widening()  — spread > N * rolling average
    # -----------------------------------------------------------------
    # TODO:
    #   - [ ] Build the sliding-window average stream (see function docstring).
    #   - [ ] Connect / join the windowed average back to the per-event stream.
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/joining/
    #   - [ ] Apply `check_spread_widening` after the join.

    # -----------------------------------------------------------------
    # check_velocity_spike()  — rate of change exceeds threshold
    # -----------------------------------------------------------------
    # TODO:
    #   - [ ] Build the sliding-window velocity stream (see function docstring).
    #   - [ ] Apply `check_velocity_spike` after the window aggregation.
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/#sliding-windows

    # -----------------------------------------------------------------
    # Rate limiting — deduplicate with keyed state + timer
    # -----------------------------------------------------------------
    # TODO:
    #   - [ ] Union all individual alert streams into one:
    #         ```python
    #         all_alerts = extreme_imbalance_stream.union(
    #             imbalance_flip_stream,
    #             spread_widening_stream,
    #             velocity_spike_stream,
    #         )
    #         ```
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/api/python/reference/pyflink.datastream.html#pyflink.datastream.DataStream.union
    #   - [ ] Apply the `AlertRateLimiter` KeyedProcessFunction (described in
    #         the module-level TODO block above) to deduplicate:
    #         ```python
    #         deduplicated_alerts = (
    #             all_alerts
    #             .key_by(lambda a: f"{a['symbol']}_{a['alert_type']}")
    #             .process(AlertRateLimiter(cooldown_ms=60_000))
    #         )
    #         ```
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#timers

    # Temporary: use extreme_imbalance_stream directly until all checks are implemented
    alerts_stream = extreme_imbalance_stream

    # -----------------------------------------------------------------
    # KafkaSink — orderbook.alerts
    # -----------------------------------------------------------------
    # TODO:
    #   - [ ] Add `.set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)`
    #         (or EXACTLY_ONCE with transactions) to match the checkpointing
    #         semantics of the job.
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/#fault-tolerance
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/api/python/reference/pyflink.datastream.html#pyflink.datastream.connectors.kafka.DeliveryGuarantee
    #   - [ ] Replace `SimpleStringSchema` with a typed serializer that
    #         accepts `Alert` objects directly.
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/#kafka-serializationschema
    #   - [ ] Set a `transactional_id_prefix` when using EXACTLY_ONCE delivery:
    #         `.set_transactional_id_prefix('orderbook-alerts')`
    #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/#fault-tolerance
    #
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
    alerts_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(settings.redpanda_topics["alerts"])
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )

    # Serialize and sink
    alerts_stream.map(lambda a: json.dumps(a.to_dict())).sink_to(alerts_sink)

    # Execute
    env.execute("OrderBook Alerts Processor")


if __name__ == "__main__":
    main()
