# Quick Answers to Your 10 Technical Questions

## Q1: Supabase 500MB with 3 symbols - how often truncate?

**Answer:** You'd need to truncate every 6 hours

- 3 symbols × 10 updates/sec = 30 inserts/second
- 30 × 86,400 = 2.6M rows/day = 1.96 GB/day
- 500MB fills in ~6 hours

**Better solution:** Use downsampling (1-min buckets)

- Reduces to 2.2 MB/day
- Lasts 115+ days
- NO truncation needed

---

## Q2: Will I hit ingress limits on Supabase free tier?

**Answer:** No for ingress, YES for storage

**Ingress:**

- 30 inserts/sec ✅ (under typical 100 RPS limit)
- 2.6M inserts/day (no hard limit on free tier)

**Storage:**

- 500MB limit ❌ (will fill in 6 hours)
- This is the real bottleneck, not ingress

---

## Q3: Would I have to change code switching from TimescaleDB to CockroachDB?

**Answer:** YES, but minimal changes

**Changes needed:**

1. Replace `time_bucket('1 hour', ts)` with `DATE_TRUNC('hour', ts)` (5-10 queries)
2. Remove `CREATE HYPERTABLE` calls (1-2 lines)
3. Remove compression settings (1-2 lines)

**Effort:** 30 min to 2 hours (depends on query count)

**Example:**

```sql
-- OLD (TimescaleDB):
SELECT time_bucket('5 min', timestamp) as bucket, AVG(imbalance)
FROM metrics GROUP BY bucket

-- NEW (CockroachDB/PostgreSQL):
SELECT DATE_TRUNC('minute', timestamp) as bucket, AVG(imbalance)
FROM metrics GROUP BY DATE_TRUNC('minute', timestamp)
```

---

## Q4: Why not use Supabase with TimescaleDB extension?

**Answer:** Only available on PAID tiers ($25+/month)

**Supabase pricing:**

- Free: PostgreSQL only
- Pro: $25/month - includes TimescaleDB
- Business: $199+/month

**Why choose CockroachDB instead:**

- FREE forever (Supabase Pro costs $25/month)
- Distributed database (more impressive for interviews)
- `DATE_TRUNC` works identically for 1-min aggregations
- Better for portfolio project

---

## Q5: Why wouldn't Render work to host everything free?

**Answer:** Render doesn't offer free PostgreSQL or Redis

**Render free offerings:**

- ✅ Web Services (Python apps) - FREE
- ✅ Background Workers - FREE
- ❌ PostgreSQL (minimum $7/month)
- ❌ Redis (minimum $10/month)

**Cost if using Render for all:**

- Web services: FREE
- PostgreSQL: $7/month
- Redis: $10/month
- **Total: $17+/month** (defeats "free" goal)

**Better approach:**

- Render services: FREE (web + worker)
- CockroachDB: FREE (external service)
- Upstash: FREE (external services)
- **Total: $0/month** ✅

---

## Q6: Redis elsewhere - speed issue? (Render backend + Upstash Redis)

**Answer:** NO, minimal speed impact (1-3ms latency)

**Latency breakdown:**

- Local Redis: 0.1ms
- Same region (Render US-East + Upstash US-East): 1-3ms ✅
- Different region: 50-200ms ❌

**Your setup:** Render US-East + Upstash US-East = 1-3ms latency

- Acceptable for cache operations
- Dashboard reads won't be noticeably slower

**Cost benefit:**

- Render Redis: $10/month
- Upstash Redis: $0/month
- **Save $10/month with negligible latency increase** ✅

---

## Q7: Docker Compose mapping to services

| Local Container | Production             | Type           |
| --------------- | ---------------------- | -------------- |
| timescaledb     | CockroachDB Serverless | Managed DB     |
| redis           | Upstash Redis          | Managed cache  |
| redpanda        | Upstash Kafka          | Managed broker |
| ingestion       | Render Web Service     | Python app     |
| consumers       | Render Worker          | Python app     |
| flink           | GCP Dataflow OR remove | Complex JVM    |
| dashboard       | Streamlit Cloud        | Python app     |
| grafana/pgadmin | DELETE                 | Dev tools only |

**Key insight:** Managed services replace containers in production

- NO Docker images needed for databases/caches
- Just configuration strings
- Python apps deploy same Dockerfile

---

## Q8: Is Terraform for single cloud or multi-cloud?

**Answer:** Can do both, but NOT needed for your setup

**Terraform capabilities:**

- ✅ Can manage AWS + GCP + DigitalOcean in one file
- ✅ Can manage multiple cloud providers
- ❌ But requires API keys for each provider

**For your setup:**

- CockroachDB: Manual web UI (5 min)
- Upstash: Manual web UI (5 min)
- Render: GitHub integration (no Terraform)
- Streamlit: GitHub integration (no Terraform)

**Verdict:** Skip Terraform for portfolio

- Takes 20 minutes manual setup
- Terraform adds unnecessary complexity
- Better to focus on code

---

## Q9: GCP e2-micro (2vCPU, 1GB) for backend?

**Answer:** YES, it works, but tight

**Resource usage:**

- Ingestion: 50-100 MB RAM, 5-10% CPU ✅
- Consumers: 100-200 MB RAM, 10-20% CPU ✅
- Dashboard: 200-400 MB RAM, 5-15% CPU ✅
- **Total under load:** 350-700 MB RAM (1GB limit) ⚠️

**Verdict:**

- ✅ Works for portfolio
- ⚠️ Tight memory margin
- Better: e2-small ($17/mo, 2GB RAM)
- Best: Use Render (FREE, handles scaling)

**Recommendation:** Use Render, not GCP VM

---

## Q10: Live Binance data + $0 = possible?

**Answer:** YES, with 1-minute downsampling

**The solution:**

```
Raw data: 30 ticks/sec → 2.6 GB/day ❌
Downsampled: 3 metrics/min → 2.2 MB/day ✅

1-minute buckets:
├─ 4,320 rows/day
├─ Uses 2.2 MB storage
├─ CockroachDB 250MB lasts 115+ days
└─ Everything FREE, data lasts months
```

**Implementation:**

1. Add provided `downsampling.py` to project
2. Buffer ticks for 60 seconds
3. Write 1 aggregated metric instead of 600 ticks
4. Everything else unchanged

**Cost with live data: $0/month** ✅

---

## Summary: Your Final Architecture

```
LIVE BINANCE DATA + $0 COST + PROFESSIONAL QUALITY

Binance (free, real-time)
↓ (30 ticks/sec)
Render Ingestion (free)
├─ Downsample to 1-min buckets
├─ CockroachDB (free) ← Store aggregates
├─ ~Upstash Kafka (free)~ ← Distribute events (deprecated)
└─ Upstash Redis (free) ← Cache
↓
Render Consumer (free)
├─ Read Kafka
├─ Calculate alerts
└─ Update DB
↓
Streamlit Cloud (free)
├─ Query DB
├─ Read cache
└─ Display dashboard

Total cost: $0/month
Data retention: 115+ days
Code changes: ~50 lines
Time to deploy: 3-5 hours
Interview quality: ⭐⭐⭐⭐⭐ Professional
```
