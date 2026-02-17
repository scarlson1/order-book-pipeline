# Flink Jobs

This directory contains Apache Flink stream processing jobs.

## Jobs

### orderbook_metrics.py

Consumes raw order book data from Redpanda, calculates metrics,
and publishes processed results back to Redpanda.

Topics consumed:

- `orderbook.raw`

Topics produced:

- `orderbook.metrics`
- `orderbook.alerts`

## Running Jobs

```bash
# Start Flink + Redpanda
make up-streaming

# Submit a job
docker-compose exec flink-jobmanager flink run /opt/flink/jobs/orderbook_metrics.py

# View running jobs
make flink-jobs

# Open Flink Web UI
make flink-ui
# Visit: http://localhost:8081
```

## Documentation

- Apache Flink: https://nightlies.apache.org/flink/flink-docs-stable/
- PyFlink: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/overview/
- Flink Kafka Connector: https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/
