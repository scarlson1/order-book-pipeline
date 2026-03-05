# Redpanda Infrastructure

This document describes the Redpanda (Kafka-compatible stream broker) infrastructure.

## Topics

### `orderbook.raw`

Raw order book data streamed from Binance WebSocket API.

| Field       | Type   | Description                                       |
| ----------- | ------ | ------------------------------------------------- |
| `symbol`    | string | Trading pair (e.g., "BTCUSDT", "ETHUSDT")         |
| `timestamp` | string | Millisecond-precision timestamp from Binance      |
| `bids`      | array  | Best bid orders: `[price, volume, order_id, ...]` |
| `asks`      | array  | Best ask orders: `[price, volume, order_id, ...]` |
| `update_id` | int    | Binance sequence number for deduplication         |

**Partition Strategy:**

- Partitioned by `symbol` field
- Enables parallel processing of different trading pairs
- Messages are ordered per symbol within each partition

---

### `orderbook.metrics`

Calculated imbalance metrics from the raw order book stream.

| Field                | Type   | Description                                            |
| -------------------- | ------ | ------------------------------------------------------ |
| `symbol`             | string | Trading pair                                           |
| `timestamp`          | string | Millisecond timestamp                                  |
| `mid_price`          | double | `(best_bid + best_ask) / 2`                            |
| `best_bid`           | double | Highest bid price                                      |
| `best_ask`           | double | Lowest ask price                                       |
| `spread_abs`         | double | `best_ask - best_bid`                                  |
| `spread_bps`         | double | Spread in basis points: `(spread / mid_price) * 10000` |
| `bid_volume`         | double | Total bid volume at top levels                         |
| `ask_volume`         | double | Total ask volume at top levels                         |
| `total_volume`       | double | Sum of bid + ask volumes                               |
| `imbalance_ratio`    | double | `(bid - ask) / (bid + ask)` in range `[-1, 1]`         |
| `weighted_imbalance` | double | Weighted imbalance using `1/i` decay                   |
| `vtob_ratio`         | double | Volume to Best Ask/Bid ratio                           |
| `best_bid_volume`    | double | Volume at best bid price                               |
| `best_ask_volume`    | double | Volume at best ask price                               |
| `depth_level`        | int    | Configured depth (default: 10)                         |
| `update_id`          | int    | Binance sequence number                                |

**Partition Strategy:**

- Partitioned by `symbol` field
- Maintains per-symbol metric stream
- Enables efficient consumption and alerting

---

### `orderbook.alerts`

Alert messages for threshold breaches.

_Currently commented out in the Flink job but infrastructure is ready._

| Field              | Type   | Description                                            |
| ------------------ | ------ | ------------------------------------------------------ |
| `symbol`           | string | Trading pair with alert                                |
| `timestamp`        | string | Alert timestamp                                        |
| `alert_type`       | string | "HIGH_IMBALANCE", "MEDIUM_IMBALANCE", "SPREAD_ANOMALY" |
| `severity`         | string | "HIGH" or "MEDIUM"                                     |
| `message`          | string | Human-readable alert description                       |
| `metrics_snapshot` | object | Snapshot of metrics at alert time                      |

**Threshold Configuration:**

- `ALERT_THRESHOLD_HIGH=0.70` → HIGH severity alerts
- `ALERT_THRESHOLD_MEDIUM=0.50` → MEDIUM severity alerts
- `SPREAD_ALERT_MULTIPLIER=2.0` → Spread anomaly threshold (2x normal)

---

## Consumer Groups

### `flink-orderbook-processor`

Primary consumer group for the PyFlink metrics calculation job.

| Property              | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Bootstrap Servers** | `{redpanda_bootstrap_servers}` (e.g., "localhost:29092")     |
| **Topic Consumed**    | `orderbook.raw`                                              |
| **Starting Offset**   | `latest-offset` (begins processing from most recent message) |
| **Checkpointing**     | Enabled every 10 seconds for exactly-once semantics          |

### `flink-orderbook-raw`

SQL-based source table consumer group (Flink SQL approach).

| Property              | Value                                                                |
| --------------------- | -------------------------------------------------------------------- |
| **Bootstrap Servers** | `{redpanda_bootstrap_servers}`                                       |
| **Topic Consumed**    | `orderbook.raw`                                                      |
| **Starting Offset**   | Configurable: `latest-offset`, `earliest-offset`, or specific offset |

### `flink-orderbook-metrics`

Consumer group for reading computed metrics (if separate consumption needed).

| Property              | Value                          |
| --------------------- | ------------------------------ |
| **Bootstrap Servers** | `{redpanda_bootstrap_servers}` |
| **Topic Consumed**    | `orderbook.metrics`            |
| **Starting Offset**   | Configurable                   |

### `flink-orderbook-alerts`

Consumer group for reading alerts (if enabled).

| Property              | Value                          |
| --------------------- | ------------------------------ |
| **Bootstrap Servers** | `{redpanda_bootstrap_servers}` |
| **Topic Consumed**    | `orderbook.alerts`             |
| **Starting Offset**   | Configurable                   |

---

## Consumer Group Inspection Commands

### List all consumer groups

```bash
# List all active and inactive consumer groups
rpk group list --state any
```

### Get consumer group details

```bash
# Get full details of a specific consumer group
rpk group describe flink-orderbook-processor --topics orderbook.raw

# Output includes:
# - Members (assigned partitions)
# - Last stable offset (LSO)
# - Log end offset (LEO)
# - Uncommitted offsets
```

### Get offsets for a topic

```bash
# Get current offsets for all consumer groups on a topic
rpk group offsets orderbook.raw --group flink-orderbook-processor
```

---

## Topic Management Commands

### Create topics

```bash
# Create the raw topic with 6 partitions and replication factor 3
rpk topic create orderbook.raw --partitions 6 --replication-factor 3

# Create metrics topic
rpk topic create orderbook.metrics --partitions 6 --replication-factor 3

# Create alerts topic
rpk topic create orderbook.alerts --partitions 6 --replication-factor 3
```

### List topics

```bash
# List all topics with partition count and replication factor
rpk topic list --verbose
```

### Delete topics (use with caution)

```bash
# Delete a topic and all its data
rpk topic delete orderbook.alerts --if-exists
```

---

## Partition Management Commands

### Get partition leader information

```bash
# Get partition leaders for a topic
rpk topic describe orderbook.raw --json

# Output format:
# {
#   "topic": "orderbook.raw",
#   "partitions": [
#     {"leader": 0, "replicas": [1, 2, 3], "isr": [1, 2, 3]},
#     ...
#   ]
# }
```

### Alter topic configuration

```bash
# Increase retention for raw topic (e.g., 7 days)
rpk topic alter config orderbook.raw \
  --config "retention.ms=604800000" \
  --config "retention.bytes=-1"

# Set log segment size (default is typically 1GB)
rpk topic alter config orderbook.raw \
  --config "log.segment.bytes=1073741824"
```

### Compaction (optional, for stateful processing)

```bash
# Enable compaction for metrics topic (last-value semantics)
rpk topic alter config orderbook.metrics \
  --config "cleanup.policy=compact,delete" \
  --config "retention.bytes=-1"
```

---

## Offset Management Commands

### Seek to specific offset (manual restart)

```bash
# Reset a consumer group to earliest offset
rpk group seek flink-orderbook-processor orderbook.raw --offset -1
  # -1 = earliest, 0+ = absolute offset

# Set specific offset for a partition (requires JSON input)
rpk group seek flink-orderbook-processor orderbook.raw \
  --offset "{\"orderbook.raw:0\":[0]}"
```

### Commit offsets manually

```bash
# Write custom offset to consumer group state
rpk group seek flink-orderbook-processor orderbook.raw \
  --offset "${OFFSET_VALUE}"
```

---

## Data Validation Commands

### Check message counts

```bash
# Get offsets (end offset - log start offset) to estimate message count
rpk group offsets orderbook.raw --group flink-orderbook-processor

# Alternatively, use kafka-console-consumer for sample messages
echo "Piping consumer here..." \
  | rpk consume orderbook.raw \
    --from-beginning \
    --max-messages 10
```

### Sample raw messages

```bash
# Stream last 10 messages from a topic
rpk consume orderbook.raw \
  --max-messages 10 \
  --print-time | head -n 10
```

---

## Monitoring and Troubleshooting

### Check consumer lag

```bash
# List consumer groups with lag information
rpk group list --state any --json | jq '.[] | {name, state, topics: [.topics[] | {topic: .topic, partition, current_offset: .current_offset, log_end_offset: .log_end_offset, lag: (.log_end_offset - .current_offset)}]}'
```

### Restart consumer from latest

```bash
# Update topic config to seek latest (requires Flink restart after config change)
rpk topic alter config orderbook.raw --config "cleanup.policy=delete"

# In Flink job, set starting_offsets to KafkaOffsetsInitializer.latest()
```

### Check for stuck consumer groups

```bash
# Look for consumer groups with no members
rpk group list --state inactive

# Investigate why group is inactive (broker issues, authentication, etc.)
rpk group describe <group-name> --topics <topic>
```

---

## Production Recommendations

| Setting                | Recommended Value                                   | Rationale                                     |
| ---------------------- | --------------------------------------------------- | --------------------------------------------- |
| **Partitions**         | 6-12 per topic                                      | Balances parallelism with consumer throughput |
| **Replication Factor** | 3 (or cluster size)                                 | Ensures high availability                     |
| **Retention**          | `orderbook.raw`: 1 day, `orderbook.metrics`: 7 days | Raw is ephemeral; metrics need audit trail    |
| **Log Segment Size**   | 1GB                                                 | Default, allows efficient log compaction      |

---

## Security Configuration

Redpanda can be configured with:

- **SASL/SCRAM** authentication for broker access
- **TLS encryption** in-flight data protection
- **ACLs** for topic-level access control

See `docs/ENV_VARS.md` and Redpanda documentation for security configuration details.
