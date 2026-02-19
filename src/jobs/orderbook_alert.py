"""Apache Flink job for order book alert detection.

This job:
1. Consumes processed metrics from Redpanda (orderbook.metrics topic)
2. Detects alert conditions (extreme imbalance, imbalance flip, spread widening, velocity spike)
3. Rate-limits / deduplicates alerts using keyed state + timers
4. Publishes triggered alerts to Redpanda (orderbook.alerts topic)

Documentation:
- Flink Kafka Connector:    https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
- Flink Keyed State:        https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/fault-tolerance/state/
- Flink ProcessFunction:    https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/
- Flink Windows:            https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/
- Flink Watermarks:         https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/
- Flink Timers:             https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#timers
"""

import json
from typing import Tuple
from loguru import logger
from pydantic import ValidationError
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaSink,
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    DeliveryGuarantee
)
from pyflink.datastream.state import ValueStateDescriptor
from pyflink.datastream.window import SlidingEventTimeWindows
from pyflink.datastream.functions import AggregateFunction, KeyedProcessFunction, KeyedCoProcessFunction
from pyflink.common import WatermarkStrategy, Duration
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.time import Time
from pyflink.common.typeinfo import Types

from src.common.models import Alert, AlertType, OrderBookMetrics, Severity
from src.config import settings

# TODO: which parts need to be calculated from the windowed metrics ??


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

        alert = Alert(
            symbol=metrics.symbol,
            timestamp=metrics.timestamp,
            alert_type=AlertType.EXTREME_IMBALANCE,
            severity=severity,
            message=f"Extreme imbalance detected: {imbalance:.2%}",
            metric_value=imbalance,
            threshold_value=settings.alert_threshold_high,
        )
        return alert

    return None


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


# ===== KeyedProcessFunctions ===== #

"""
KeyedProcessFunction Explanation:

What is KeyedProcessFunction?
-----------------------------
KeyedProcessFunction is a low-level Flink operator that provides fine-grained
control over state and time in stream processing. Unlike simple transformations
like map() or filter(), KeyedProcessFunction allows you to:

1. **Maintain keyed state** - Store per-key information that persists across
   events for the same key. This is essential for comparisons (e.g., comparing
   current value to previous value).

2. **Use timers** - Register callbacks that fire at specific times (processing
   time or event time). This enables pattern detection, windowing, and rate
   limiting.

3. **Emit multiple outputs** - Unlike map() which emits one output per input,
   process_element() can emit zero, one, or multiple outputs.

Key Concepts:
- **Keyed Stream**: After keyBy(), all events with the same key are processed
  by the same parallel instance, guaranteeing state consistency.
- **ValueState**: Simple singleton state that holds a single value per key.
- **Processing Time Timers**: Fire at a specific wall-clock time.
- **Event Time Timers**: Fire when the watermark passes a specific timestamp.

When to use KeyedProcessFunction vs map():
- Use map() for stateless, element-by-element transformations
- Use KeyedProcessFunction when you need:
  * State (remembering previous values)
  * Timers (time-based triggers)
  * Multiple outputs per input
  * Complex conditional logic

References:
- Flink ProcessFunction: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/
- Flink Keyed State: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/fault-tolerance/state/
- Flink Timers: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#timers
- PyFlink KeyedProcessFunction: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/#the-keyedprocessfunction
"""

# RichFunction -> provided open() and close() methods
class ImbalanceFlipDetector(KeyedProcessFunction[str, OrderBookMetrics, Alert | None]):
    """Detects sign changes in imbalance_ratio (buy pressure → sell pressure or vice-versa).
    
    This KeyedProcessFunction maintains keyed state to track the previous imbalance
    value for each symbol. When a sign change is detected (positive to negative or
    vice versa), an alert is emitted.
    
    How it works:
    1. The stream is keyed by symbol (e.g., "BTCUSDT")
    2. For each incoming metrics event, we:
       - Read the previous imbalance from ValueState
       - Check if there's a sign change (prev * curr < 0)
       - If sign changed, emit an IMBALANCE_FLIP alert
       - Update the state with the current imbalance
    
    Why KeyedProcessFunction is needed:
    - We need per-symbol state to compare current vs previous imbalance
    - Simple map() cannot maintain state across events
    - The comparison requires remembering the last value per symbol
    
    State:
    - prev_imbalance: ValueState[float] - stores previous imbalance_ratio
    
    Timers: None needed for flip detection (stateless comparison)
    
    Example:
        Input: [{symbol: "BTCUSDT", imbalance_ratio: 0.5}, 
                {symbol: "BTCUSDT", imbalance_ratio: -0.3}]
        Output: Alert(IMBALANCE_FLIP) - sign changed from positive to negative
    """
    
    def __init__(self):
        """Initialize the detector."""
        # State descriptor for storing previous imbalance per key (symbol). Declared here but initialized in open()
        self.prev_imbalance_state = None
        
    def open(self, runtime_context):
        """Called when the function is initialized.
        This is where we register our state descriptors with the runtime context.
        The runtime_context provides access to keyed state backend.
        """
        # Create a ValueStateDescriptor for storing float values
        # 'prev_imbalance' is the name used to identify this state
        # Types.FLOAT() specifies the type of values stored
        state_descriptor = ValueStateDescriptor(
            'prev_imbalance',  # State name - must be unique per function
            Types.FLOAT()      # Type info for serialization
        )
        # Register the state with the runtime context
        self.prev_imbalance_state = runtime_context.get_state(state_descriptor)
    
    def process_element(self, value, ctx):
        """Process each incoming metrics element.
        
        This is the main processing function called for each element in the
        keyed stream. All events with the same key are processed sequentially
        by this function, guaranteeing consistency of state.
        
        Args:
            value: The incoming OrderBookMetrics object
            ctx: KeyedProcessFunction.Context providing:
                 - timer_service(): access to time services
                 - timestamp(): event timestamp
                 - output(): collector for emitting results
        
        Yields:
            Alert if a sign change is detected, None otherwise
        """
        curr_imbalance = value.get('imbalance_ratio') if isinstance(value, dict) else value.imbalance_ratio
        
        # Retrieve previous imbalance from keyed state (None if no previous value exists)
        prev_imbalance = self.prev_imbalance_state.value()
        
        # Check for sign change: if both exist and have opposite signs
        if prev_imbalance is not None and (prev_imbalance * curr_imbalance < 0):
            # Determine direction: prev was positive = buy pressure, now negative = sell
            direction = "BUY→SELL" if prev_imbalance > 0 else "SELL→BUY"
            
            alert = Alert(
                symbol=value.get('symbol') if isinstance(value, dict) else value.symbol,
                alert_type=AlertType.IMBALANCE_FLIP,
                severity=Severity.MEDIUM,
                message=f"Imbalance flip detected: {direction}",
                metric_value=curr_imbalance,
                threshold_value=0.0,  # Any sign change triggers this
                imbalance_ratio=curr_imbalance
            )
            yield alert
        
        # Update state with current imbalance for next comparison
        self.prev_imbalance_state.update(curr_imbalance)


class AlertRateLimiter(KeyedProcessFunction):
    """Rate-limits alerts to prevent alert storms for the same condition.
    
    This KeyedProcessFunction suppresses duplicate alerts for the same
    (symbol, alert_type) pair within a configurable cool down window.
    
    How it works:
    1. The stream is keyed by composite key: "{symbol}_{alert_type}"
    2. For each incoming alert:
       - Check if this key is currently "suppressed" in state
       - If NOT suppressed:
         * Forward the alert to output
         * Set suppressed = True in state
         * Register a timer for cooldown_ms milliseconds from now
       - If suppressed:
         * Drop the alert (don't forward)
    3. When the timer fires (after cooldown period):
       - Clear the suppressed flag
       - The next alert for this key will be allowed through
    
    Why KeyedProcessFunction is needed:
    - We need per-(symbol, alert_type) state to track suppression
    - We need timers to automatically clear suppression after cooldown
    - This would be impossible with simple map()
    
    State:
    - suppressed: ValueState[bool] - True if alerts are currently suppressed
    
    Timers:
    - Processing-time timer registered for cooldown duration
    - on_timer() clears the suppression flag
    
    Example:
        Input: 5 alerts for "BTCUSDT_EXTREME_IMBALANCE" within 10 seconds
        Output: Only the first alert is emitted, next 4 are suppressed
        After 60 seconds: Suppression clears, next alert can fire
    """
    
    def __init__(self, cooldown_ms: int = 60_000):
        self.cooldown_ms = cooldown_ms
        self.suppressed_state = None # State descriptor will be initialized in open()
        
    def open(self, runtime_context):
        """Initialize state backend. Registers the suppressed state descriptor with the runtime context."""
        self.suppressed_state = runtime_context.get_state(ValueStateDescriptor(
            'suppressed',
            Types.BOOLEAN() 
        ))
    
    def process_element(self, value, ctx):
        """Process incoming alert with rate limiting logic.
        
        Checks if alerts for this key are currently suppressed. If not,
        forwards the alert and registers a timer to clear suppression.
        
        Args:
            value: The incoming Alert object
            ctx: KeyedProcessFunction.Context providing timer service
            
        Yields:
            Alert if not suppressed, None if suppressed
        """
        is_suppressed = self.suppressed_state.value()
        
        # rate limiting step: drop if alert is suppressed
        if is_suppressed:
            return
        
        # Not suppressed - forward the alert
        yield value
        
        # Mark as suppressed to prevent future alerts until timer fires
        self.suppressed_state.update(True)
        
        # Register a processing-time timer to clear suppression after cooldown
        timer_timestamp = ctx.timer_service().current_processing_time() + self.cooldown_ms
        ctx.timer_service().register_processing_time_timer(timer_timestamp)
    
    def on_timer(self, timestamp: int, ctx: 'KeyedProcessFunction.OnTimerContext', out):
        """
        This is the timer callback that clears the suppression flag,
        allowing new alerts to pass through for this key.
        
        Args:
            timestamp: When the timer fired (processing time in ms)
            ctx: OnTimerContext providing additional timer-specific methods
            out: Output collector for emitting results (not used here)
        """
        self.suppressed_state.clear()
        
        logger.info(f'Alert suppression ended for {ctx.getCurrentKey()}')


class SpreadWideningJoinFunction(KeyedCoProcessFunction):
    """Joins raw metrics with windowed average to detect spread widening

        Stream and aggregate are keyed by same field (symbol) - this join state/class is also partitioned by the same key
    """

    def __init__(self):
        self.avg_spread_state = None

    def open(self, runtime_context):
        # store the latest windowed average spread per symbol
        self.avg_spread_state = runtime_context.get_state(
            ValueStateDescriptor('avg_spread', Types.DOUBLE())
        )

    # process metrics stream (left input)
    def process_element1(self, value, ctx):
        current_spread = value.spread_bps # value.get('spread_bps') if isinstance(value, dict) else value.spread_bps

        avg_spread = self.avg_spread_state.value()

        # compare is we have an average to compare against
        if avg_spread is not None and avg_spread > 0:
            threshold = settings.spread_alert_multiplier # e.g. 2.0
            if current_spread > avg_spread * threshold:
                yield Alert(
                    symbol=value.symbol,
                    alert_type=AlertType.SPREAD_WIDENING,
                    severity=Severity.HIGH,
                    message=f'Spread {current_spread:.2f} bps > {threshold}× avg ({avg_spread:.2f})',
                    metric_value=current_spread,
                    threshold_value=avg_spread * threshold
                )

    # process windowed average stream (right input)
    def process_element2(self, value, ctx):
        # The windowed stream outputs (symbol, average_spread)
        symbol = value[0] if isinstance(value, tuple) else value.get('symbol')
        avg_spread = value[1] if isinstance(value, tuple) else value

        # update state for this symbol
        self.avg_spread_state.update(avg_spread)


class VelocitySpikeDetector(KeyedProcessFunction):
    """Detects rapid changes in imbalance_ratio"""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self.prev_state = None
        self.prev_timestamp_state = None

    def open(self, runtime_context):
        self.prev_state = runtime_context.get_state(
            ValueStateDescriptor('prev_imbalance', Types.FLOAT())
        )
        self.prev_timestamp_state = runtime_context.get_state(
            ValueStateDescriptor('prev_timestamp', Types.LONG())
        )

    def process_element(self, value, ctx):
        """Iterate through each item, calc delta imbalance / delta time -> create alert if above threshold"""
        curr_imbalance = value.imbalance_ratio
        curr_timestamp = ctx.timestamp()

        prev_imbalance = self.prev_state.value()
        prev_timestamp = self.prev_timestamp_state.value()

        # only compute velocity if we have previous event
        if prev_imbalance is not None and prev_timestamp is not None:
            dt = (curr_timestamp - prev_timestamp) / 1000.0 # ms -> seconds

            if dt > 0:
                velocity = abs(curr_imbalance - prev_imbalance) / dt

                # check against threshold
                if velocity > settings.velocity_threshold:
                    severity = Severity.HIGH if velocity > 0.1 else Severity.MEDIUM
                    yield Alert(
                        symbol=value.symbol,
                        alert_type=AlertType.VELOCITY_SPIKE,
                        severity=severity,
                        message=f'Velocity {velocity:.3f}/s exceeds threshold {settings.velocity_threshold}',
                        metric_value=velocity,
                        threshold_value=settings.velocity_threshold,
                        imbalance_ratio=curr_imbalance
                    )

        # update state
        self.prev_state.update(curr_imbalance)
        self.prev_timestamp_state.update(curr_timestamp)


# ===== Aggregate Functions ===== #

class SpreadAverageAggregateFunction(AggregateFunction):
    def create_accumulator(self) -> Tuple[float, int]:
        return 0.0, 0 # [spread_bps, count]

    def add(self, value: OrderBookMetrics, accumulator: Tuple[float, int]) -> Tuple[float, int]:
        spread_bps = value.spread_bps
        return accumulator[0] + spread_bps, accumulator[1] + 1

    def get_result(self, accumulator: Tuple[int, int]) -> float:
        return accumulator[0] / accumulator[1]

    def merge(self, a: Tuple[float, int], b: Tuple[float, int]) -> Tuple[float, int]:
        return a[0] + b[0], a[1] + b[1]


# ===== Main Flink Job ===== #


def main():
    # Initialize Flink execution environment
    # Reference: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/datastream_tutorial/
    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(10 * 1000)
    env.set_parallelism(settings.flink_parallelism)

    try:

        # -----------------------------------------------------------------
        # KafkaSource — orderbook.metrics
        # -----------------------------------------------------------------
        # TODO:
        #   - [ ] For production, use `KafkaOffsetsInitializer.committed_offsets()`
        #         with a fallback to `earliest()` to resume from checkpointed offsets.
        #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/#consumer-offset-committing
        #   - Replace `SimpleStringSchema` with a typed deserializer (e.g., a
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
        # TODO: key the stream by symbol immediately after parsing so all stateful operators (imbalance flip, rate limiter) share the same key scope without an extra keyBy call.
        #       Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/overview/#keyby
        metrics_stream = (
            env.from_source(
                source=source,
                watermark_strategy=watermark_strategy,
                source_name="Redpanda OrderBook Metrics",
            )
            .map(parse_metrics)
            .filter(lambda x: x is not None)
            .key_by(lambda a: a['symbol'])
        )

        # -----------------------------------------------------------------
        # check_extreme_imbalance()  — abs(imbalance) > HIGH threshold
        # -----------------------------------------------------------------
        extreme_imbalance_stream = metrics_stream \
            .map(check_extreme_imbalance) \
            .filter(lambda x: x is not None)
            

        # -----------------------------------------------------------------
        # check_imbalance_flip()  — sign change detection with keyed state
        # -----------------------------------------------------------------
        imbalance_flip_stream = (
            metrics_stream
                .process(ImbalanceFlipDetector()) # class in order to extend KeyedProcessFunction
                .filter(lambda x: x is not None)
        )

        # -----------------------------------------------------------------
        # check_spread_widening()  — spread > N * rolling average
        # -----------------------------------------------------------------
        # Uses a sliding window to maintain a rolling average of `spread_bps` per
        # symbol, then compares the latest value against
        # `settings.spread_alert_multiplier` (default 2.0×).
        windowed = (
            metrics_stream
                .window(SlidingEventTimeWindows.of(
                    Time.minutes(5),   # window size
                    Time.seconds(30),  # slide interval
                ))
                .aggregate(
                    SpreadAverageAggregateFunction(),
                    accumulator_type=Types.TUPLE([Types.DOUBLE(), Types.INTEGER()]),
                    output_type=Types.DOUBLE()
                )
        )

        raw_keyed = metrics_stream
        windowed_keyed = windowed.key_by(lambda x: x[0] if isinstance(x, tuple) else x.get('symbol'))

        connected = raw_keyed.connect(windowed_keyed) 

        spread_widening_stream = connected.process(SpreadWideningJoinFunction()).filter(lambda x: x is not None)

        # -----------------------------------------------------------------
        # check_velocity_spike()  — rate of change exceeds threshold
        # -----------------------------------------------------------------
        velocity_spike_stream = (
            metrics_stream
                .process(VelocitySpikeDetector(window_seconds=settings.rolling_window_seconds))
                .filter(lambda x: x is not None)
        )

        # -----------------------------------------------------------------
        # Rate limiting — deduplicate with keyed state + timer
        # -----------------------------------------------------------------

        all_alerts = extreme_imbalance_stream.union(
            imbalance_flip_stream,
            spread_widening_stream,
            velocity_spike_stream
        )

        # remove alerts by symbol+type that occurred in the last minute (key_by partitions the suppression state)
        deduped_alerts = (
            all_alerts
                .key_by(lambda a: f'{a['symbol']}_{a['alert_type']}')
                .process(AlertRateLimiter(cooldown_ms=60_000))
        )

        # -----------------------------------------------------------------
        # KafkaSink — orderbook.alerts
        # -----------------------------------------------------------------
        #   - [ ] Replace `SimpleStringSchema` with a typed serializer that
        #         accepts `Alert` objects directly.
        #         Ref: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/#kafka-serializationschema
        alerts_sink = (
            KafkaSink.builder()
                .set_bootstrap_servers(settings.redpanda_bootstrap_servers)
                .set_record_serializer(
                    KafkaRecordSerializationSchema.builder()
                        .set_topic(settings.redpanda_topics["alerts"])
                        .set_value_serialization_schema(SimpleStringSchema())
                        .build()
                )
                .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
                .set_transactional_id_prefix('orderbook-alerts')
                .build()
        )

        # Serialize and sink
        deduped_alerts.map(lambda a: json.dumps(a.to_dict())).sink_to(alerts_sink)

        # Execute
        env.execute("OrderBook Alerts Processor")

    except Exception as e:
        print('writing alert records from Kafka to JDBC failed: ', str(e))


if __name__ == "__main__":
    main()