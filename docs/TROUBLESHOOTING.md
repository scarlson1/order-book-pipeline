# Troubleshooting

A reference for debugging common issues across Flink, Consumer Service, Ingestion Service, Redpanda, and Redis.

---

## Table of Contents

- [General Utilities](#general-utilities)
- [Apache Flink](#apache-flink)
- [Consumer Service](#consumer-service)
- [Ingestion Service](#ingestion-service)
- [Redpanda](#redpanda)
- [Redis](#redis)
- [Network & Connectivity](#network--connectivity)

---

## General Utilities

```bash
# Check running processes
ps aux | grep <service-name>

# View system resource usage
top
htop

# Check disk usage
df -h
du -sh /var/log/*

# Tail logs in real time
tail -f /var/log/<service>.log

# Search logs for errors
grep -i "error\|exception\|fatal" /var/log/<service>.log

# Check open ports
ss -tlnp
netstat -tulnp

# Check environment variables for a running process
cat /proc/<PID>/environ | tr '\0' '\n'

# Inspect a Docker container
docker inspect <container_name>
docker logs <container_name> --tail 100 -f
docker exec -it <container_name> bash
```

---

## Apache Flink

### Job Management

```bash
# List all running Flink jobs
flink list

# List all jobs (including finished/failed)
flink list --all

# Get details on a specific job
flink info -j <job_id>

# Cancel a job
flink cancel <job_id>

# Cancel a job with a savepoint
flink cancel --withSavepoint /path/to/savepoint <job_id>

# Stop a job gracefully (drain + savepoint)
flink stop --savepointPath /path/to/savepoint <job_id>

# Trigger a manual savepoint
flink savepoint <job_id> /path/to/savepoint/dir

# Resume a job from a savepoint
flink run -s /path/to/savepoint /path/to/job.jar
```

### Cluster & TaskManager Health

```bash
# Check JobManager logs
tail -f $FLINK_HOME/log/flink-*-jobmanager-*.log

# Check TaskManager logs
tail -f $FLINK_HOME/log/flink-*-taskmanager-*.log

# Check Flink REST API - cluster overview
curl http://localhost:8081/overview

# List all jobs via REST API
curl http://localhost:8081/jobs

# Get job details via REST API
curl http://localhost:8081/jobs/<job_id>

# Check job exceptions
curl http://localhost:8081/jobs/<job_id>/exceptions

# Get TaskManager list
curl http://localhost:8081/taskmanagers

# Get TaskManager metrics
curl http://localhost:8081/taskmanagers/<taskmanager_id>/metrics

# Check job checkpoints
curl http://localhost:8081/jobs/<job_id>/checkpoints

# Get checkpoint config
curl http://localhost:8081/jobs/<job_id>/checkpoints/config
```

### Checkpoint & Backpressure Debugging

```bash
# Check backpressure on job vertices
curl "http://localhost:8081/jobs/<job_id>/vertices/<vertex_id>/backpressure"

# List job vertices
curl http://localhost:8081/jobs/<job_id>/vertices

# Get subtask details (latency, records in/out)
curl http://localhost:8081/jobs/<job_id>/vertices/<vertex_id>/subtasks/metrics

# Check for checkpoint failures in logs
grep -i "checkpoint" $FLINK_HOME/log/flink-*-jobmanager-*.log | grep -i "fail\|abort\|expire"

# Check RocksDB state backend size (if applicable)
du -sh /tmp/flink-*/job_*/
```

### Common Fixes

```bash
# Increase parallelism at submit time
flink run -p 8 /path/to/job.jar

# Set JobManager/TaskManager memory
flink run -Djobmanager.memory.process.size=2g \
          -Dtaskmanager.memory.process.size=4g \
          /path/to/job.jar

# Reset a stuck job by canceling and resubmitting from savepoint
flink cancel <job_id>
flink run -s /path/to/savepoint /path/to/job.jar
```

---

## Consumer Service

### Health & Status

```bash
# Check if consumer service is running
systemctl status consumer-service
# or
docker ps | grep consumer

# View consumer service logs
journalctl -u consumer-service -f
# or
docker logs consumer-service --tail 200 -f

# Check consumer service config
cat /etc/consumer-service/config.yaml
# or
env | grep CONSUMER_
```

### Lag & Offset Monitoring

```bash
# Check consumer group lag (Redpanda/Kafka CLI)
rpk group describe <consumer-group-name>

# List all consumer groups
rpk group list

# Check lag for all groups
rpk group list | xargs -I{} rpk group describe {}

# Reset offsets to earliest (use with caution)
rpk group seek <consumer-group-name> --to earliest --topics <topic-name>

# Reset offsets to latest
rpk group seek <consumer-group-name> --to latest --topics <topic-name>

# Reset offsets to specific timestamp
rpk group seek <consumer-group-name> --to 2024-01-01T00:00:00Z --topics <topic-name>
```

### Debugging Processing Issues

```bash
# Search for deserialization/processing errors
grep -i "deseri\|parse\|decode\|schema" /var/log/consumer-service.log

# Count error rate in logs
grep -c "ERROR" /var/log/consumer-service.log

# Check dead letter queue (DLQ) topic
rpk topic consume <dlq-topic-name> --num 10

# Check if consumer is stuck (no progress in offsets)
watch -n 5 "rpk group describe <consumer-group-name>"

# Inspect specific consumer threads/goroutines (if Go service)
kill -SIGQUIT <PID>   # dumps goroutine stack trace

# Check for OOM events related to consumer
dmesg | grep -i "oom\|killed" | grep consumer
```

### Restart & Recovery

```bash
# Restart consumer service
systemctl restart consumer-service
# or
docker restart consumer-service

# Force re-read from specific offset
rpk group seek <consumer-group-name> --to <offset> --topics <topic-name> --partitions 0,1,2
```

---

## Ingestion Service

### Health & Status

```bash
# Check ingestion service status
systemctl status ingestion-service
# or
docker ps | grep ingestion

# View ingestion service logs
journalctl -u ingestion-service -n 200 -f
# or
docker logs ingestion-service --tail 200 -f

# Check ingestion config/env
cat /etc/ingestion-service/config.yaml
env | grep INGESTION_
```

### Throughput & Performance

```bash
# Monitor ingestion rate from logs (records per second)
grep "ingested\|written\|produced" /var/log/ingestion-service.log | tail -100

# Check if ingestion is producing to the right topic
rpk topic describe <target-topic>

# Check topic high watermarks to verify data is flowing
rpk topic consume <target-topic> --num 5 --offset end

# Watch topic offset growth
watch -n 2 "rpk topic describe <target-topic>"

# Check for backpressure / slow acks
grep -i "timeout\|slow\|backpressure\|buffer full" /var/log/ingestion-service.log
```

### Data Quality Issues

```bash
# Sample recent messages from ingestion output topic
rpk topic consume <topic-name> --num 20 --offset end

# Check schema registry for schema mismatches (if applicable)
curl http://localhost:8081/subjects
curl http://localhost:8081/subjects/<topic-name>-value/versions/latest

# Search for validation/schema errors in logs
grep -i "schema\|validat\|invalid\|malformed" /var/log/ingestion-service.log

# Check dead letter queue
rpk topic consume <ingestion-dlq-topic> --num 10
```

### Restart & Recovery

```bash
# Restart ingestion service
systemctl restart ingestion-service
# or
docker restart ingestion-service

# Re-ingest from source (if supported) — check service-specific flags
ingestion-service --replay-from <timestamp>
```

---

## Redpanda

### Cluster Health

```bash
# Check cluster info
rpk cluster info

# Check broker status
rpk cluster health

# List all brokers
rpk redpanda admin brokers list

# Check cluster config
rpk cluster config get

# Check broker logs (Docker)
docker logs redpanda --tail 200 -f

# Check broker logs (systemd)
journalctl -u redpanda -f
```

### Topic Management

```bash
# List all topics
rpk topic list

# Describe a topic (partitions, replicas, offsets)
rpk topic describe <topic-name>

# Create a topic
rpk topic create <topic-name> --partitions 6 --replicas 3

# Delete a topic
rpk topic delete <topic-name>

# Consume messages from a topic
rpk topic consume <topic-name>

# Consume from the beginning
rpk topic consume <topic-name> --offset start

# Consume last N messages
rpk topic consume <topic-name> --num 10 --offset end

# Produce a test message
echo '{"test": "message"}' | rpk topic produce <topic-name>

# Check topic partition offsets
rpk topic describe <topic-name> -p
```

### Consumer Group Management

```bash
# List consumer groups
rpk group list

# Describe a consumer group (lag, offsets)
rpk group describe <group-name>

# Delete a consumer group
rpk group delete <group-name>

# Reset consumer group offset to earliest
rpk group seek <group-name> --to earliest

# Reset consumer group offset to latest
rpk group seek <group-name> --to latest
```

### Performance & Resource Monitoring

```bash
# Check Redpanda metrics (Prometheus format)
curl http://localhost:9644/metrics | grep -i "redpanda_"

# Check partition leadership balance
rpk cluster partitions balance status

# Check under-replicated partitions
curl http://localhost:9644/metrics | grep "under_replicated"

# Check request latency metrics
curl http://localhost:9644/metrics | grep "latency"

# Check broker disk usage
rpk redpanda admin storage local_mount_point list

# Check raft group health
curl http://localhost:9644/v1/raft/groups | python3 -m json.tool
```

### Configuration & Tuning

```bash
# View current broker config
rpk redpanda config print

# Set a cluster config value
rpk cluster config set log_retention_ms 86400000

# Check topic-level config
rpk topic describe <topic-name> --print-configs

# Alter topic retention
rpk topic alter-config <topic-name> --set retention.ms=3600000

# Check and set replication factor
rpk topic alter-config <topic-name> --set replication.factor=3
```

---

## Redis

### Connection & Health

```bash
# Connect to Redis CLI
redis-cli

# Connect to a remote Redis instance
redis-cli -h <host> -p <port> -a <password>

# Ping to check connectivity
redis-cli ping
# Expected: PONG

# Check Redis server info
redis-cli info

# Check only replication info
redis-cli info replication

# Check memory info
redis-cli info memory

# Check keyspace stats
redis-cli info keyspace

# Check connected clients
redis-cli info clients

# Check Redis config
redis-cli config get "*"
```

### Key Inspection

```bash
# Count total keys
redis-cli dbsize

# List keys matching a pattern (use with caution in production)
redis-cli keys "prefix:*"

# Safer: use SCAN instead of KEYS
redis-cli scan 0 match "prefix:*" count 100

# Get the type of a key
redis-cli type <key>

# Get TTL of a key (-1 = no expiry, -2 = key doesn't exist)
redis-cli ttl <key>

# Get value of a string key
redis-cli get <key>

# Get hash fields
redis-cli hgetall <key>

# Get list contents
redis-cli lrange <key> 0 -1

# Get set members
redis-cli smembers <key>

# Get sorted set members with scores
redis-cli zrange <key> 0 -1 withscores

# Check if key exists
redis-cli exists <key>
```

### Performance & Monitoring

```bash
# Monitor all commands in real time (use with caution in production)
redis-cli monitor

# Run latency analysis
redis-cli --latency

# Run latency history
redis-cli --latency-history

# Check slow log
redis-cli slowlog get 10

# Reset slow log
redis-cli slowlog reset

# Get memory usage of a specific key
redis-cli memory usage <key>

# Get a memory doctor report
redis-cli memory doctor

# Check for big keys
redis-cli --bigkeys

# Check stats (ops/sec, hit rate, etc.)
redis-cli info stats | grep -E "ops_per_sec|keyspace_hits|keyspace_misses|evicted"

# Check hit/miss ratio
redis-cli info stats | grep keyspace
```

### Replication & Cluster

```bash
# Check replication status
redis-cli info replication

# Check cluster status (if using Redis Cluster)
redis-cli cluster info

# Check cluster nodes
redis-cli cluster nodes

# Check for cluster errors
redis-cli cluster info | grep -v "^cluster_state:ok"

# Promote replica to primary (failover)
redis-cli replicaof no one

# Manually trigger Sentinel failover
redis-cli -p 26379 sentinel failover <master-name>

# Check Sentinel master status
redis-cli -p 26379 sentinel master <master-name>
```

### Troubleshooting Common Issues

```bash
# Check if Redis is out of memory
redis-cli info memory | grep "used_memory_human\|maxmemory_human\|mem_fragmentation_ratio"

# Check eviction policy
redis-cli config get maxmemory-policy

# Flush a specific database (use with extreme caution)
redis-cli select 0
redis-cli flushdb

# Flush all databases (DANGEROUS — use only in dev/test)
redis-cli flushall

# Check for blocked clients
redis-cli info clients | grep "blocked_clients"

# Check command stats for expensive operations
redis-cli info commandstats | sort -t= -k2 -rn | head -20

# Debug object internals
redis-cli debug object <key>

# Save snapshot manually
redis-cli bgsave

# Check last save time
redis-cli lastsave
```

---

## Network & Connectivity

```bash
# Test TCP connectivity to a service
nc -zv <host> <port>

# Trace route to a host
traceroute <host>

# DNS lookup
nslookup <hostname>
dig <hostname>

# Check DNS resolution from inside a container
docker exec -it <container> nslookup <hostname>

# Test HTTP endpoint health
curl -v http://<host>:<port>/health

# Check firewall rules
iptables -L -n -v

# Watch network traffic on a port (requires tcpdump)
tcpdump -i any port <port> -n

# Check active connections to a service port
ss -tnp | grep :<port>
```

---

## Quick Reference: Log Locations

| Service           | Default Log Location                                                  |
| ----------------- | --------------------------------------------------------------------- |
| Flink JobManager  | `$FLINK_HOME/log/flink-*-jobmanager-*.log`                            |
| Flink TaskManager | `$FLINK_HOME/log/flink-*-taskmanager-*.log`                           |
| Consumer Service  | `journalctl -u consumer-service` or `/var/log/consumer-service.log`   |
| Ingestion Service | `journalctl -u ingestion-service` or `/var/log/ingestion-service.log` |
| Redpanda          | `journalctl -u redpanda` or `docker logs redpanda`                    |
| Redis             | `/var/log/redis/redis-server.log`                                     |

---

## Quick Reference: Default Ports

| Service             | Default Port |
| ------------------- | ------------ |
| Flink REST API      | 8081         |
| Redpanda Kafka API  | 9092         |
| Redpanda Admin API  | 9644         |
| Redpanda Schema Reg | 8081         |
| Redis               | 6379         |
| Redis Sentinel      | 26379        |
