"""Infrastructure metrics panel - free tier usage & performance overview."""
from __future__ import annotations

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.common.redpanda_client import _kafka_security_config
from dashboard.utils.async_runner import run_async


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_bytes(n: int | float | None, decimals: int = 2) -> str:
    if n is None:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.{decimals}f} {unit}"
        n /= 1024
    return f"{n:.{decimals}f} PB"


def _pct_bar(used: float, total: float, label: str = "") -> None:
    """Render a labelled progress bar showing used/total."""
    if total <= 0:
        st.caption("No quota data")
        return
    pct = min(used / total, 1.0)
    color = "🟢" if pct < 0.7 else "🟡" if pct < 0.9 else "🔴"
    st.progress(pct, text=f"{color} {label}  {_fmt_bytes(used)} / {_fmt_bytes(total)} ({pct*100:.1f}%)")


# ── data fetchers ─────────────────────────────────────────────────────────────

def _fetch_flink() -> dict:
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return {}
    try:
        return run_async(data_layer.flink.health_check(), timeout=8) or {}
    except Exception as e:
        return {"error": str(e)}


def _fetch_redis_infra() -> dict:
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return {}
    try:
        return run_async(_get_redis_infra(data_layer), timeout=8) or {}
    except Exception as e:
        return {"error": str(e)}


async def _get_redis_infra(data_layer) -> dict:
    """Pull extended Redis INFO sections."""
    client = data_layer.redis.redis.client
    if client is None:
        return {}
    raw = await client.info("all")
    return {
        # memory
        "used_memory": raw.get("used_memory"),
        "used_memory_human": raw.get("used_memory_human"),
        "used_memory_peak": raw.get("used_memory_peak"),
        "used_memory_peak_human": raw.get("used_memory_peak_human"),
        "maxmemory": raw.get("maxmemory"),
        # network
        "total_net_input_bytes": raw.get("total_net_input_bytes"),
        "total_net_output_bytes": raw.get("total_net_output_bytes"),
        # keyspace / ops
        "total_commands_processed": raw.get("total_commands_processed"),
        "instantaneous_ops_per_sec": raw.get("instantaneous_ops_per_sec"),
        "keyspace_hits": raw.get("keyspace_hits"),
        "keyspace_misses": raw.get("keyspace_misses"),
        "connected_clients": raw.get("connected_clients"),
        "uptime_in_seconds": raw.get("uptime_in_seconds"),
        # db0 key count
        "db0_keys": raw.get("db0", {}).get("keys") if isinstance(raw.get("db0"), dict) else None,
    }


def _fetch_cockroach() -> dict:
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return {}
    try:
        return run_async(_get_cockroach_stats(data_layer), timeout=10) or {}
    except Exception as e:
        return {"error": str(e)}


async def _get_cockroach_stats(data_layer) -> dict:
    """Query CockroachDB for storage and row counts.

    Storage size is probed via several approaches in order of reliability:
      1. crdb_internal.tenant_usage_details  (serverless / dedicated, CRDB ≥ v22.2)
      2. crdb_internal.ranges_no_leases      (self-hosted, needs VIEWCLUSTERMETADATA)
      3. information_schema.tables estimated row counts as a last resort indicator
    All failures are swallowed so partial data is always returned.
    """
    db = data_layer.db.db
    if db.pool is None:
        return {}

    async with db.pool.acquire() as conn:
        # ── row counts (reliable on all tiers) ───────────────────────────────
        counts: dict = {}
        for tbl in ("orderbook_metrics", "orderbook_alerts", "orderbook_metrics_windowed"):
            try:
                n = await conn.fetchval(f"SELECT count(*) FROM {tbl}")
                counts[tbl] = n
            except Exception:
                counts[tbl] = None

        # ── table-level estimated sizes from information_schema ───────────────
        table_sizes_bytes: dict = {}
        try:
            rows = await conn.fetch(
                """
                SELECT
                    table_name,
                    (data_length + index_length) AS size_bytes
                FROM information_schema.tables
                WHERE table_schema = current_database()
                  AND table_name IN (
                      'orderbook_metrics',
                      'orderbook_alerts',
                      'orderbook_metrics_windowed'
                  )
                """
            )
            for r in rows:
                if r["size_bytes"] is not None:
                    table_sizes_bytes[r["table_name"]] = int(r["size_bytes"])
        except Exception:
            pass

        # ── total DB size: try three escalating approaches ────────────────────
        total_size: int | None = None

        # Approach 1: serverless tenant usage (CRDB Serverless / v22.2+)
        if total_size is None:
            try:
                total_size = await conn.fetchval(
                    """
                    SELECT sql_instance_data_bytes
                    FROM crdb_internal.tenant_usage_details
                    LIMIT 1
                    """
                )
            except Exception:
                pass

        # Approach 2: sum across ranges (self-hosted, needs VIEWCLUSTERMETADATA)
        if total_size is None:
            try:
                total_size = await conn.fetchval(
                    """
                    SELECT sum(range_size)
                    FROM crdb_internal.ranges_no_leases
                    """
                )
            except Exception:
                pass

        # Approach 3: fall back to summing information_schema estimates
        if total_size is None and table_sizes_bytes:
            total_size = sum(table_sizes_bytes.values())

        # ── connection pool stats ─────────────────────────────────────────────
        pool_stats = {
            "size": db.pool.get_size(),
            "idle": db.pool.get_idle_size(),
            "max_size": db.pool.get_max_size(),
        }

        return {
            "total_size_bytes": int(total_size) if total_size is not None else None,
            "table_sizes_bytes": table_sizes_bytes,
            "row_counts": counts,
            "pool": pool_stats,
        }


def _fetch_redpanda() -> dict:
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return {}
    try:
        return run_async(_get_redpanda_stats(data_layer), timeout=8) or {}
    except Exception as e:
        return {"error": str(e)}

async def _get_redpanda_stats(data_layer) -> dict:
    """Fetch Redpanda topic + broker stats via Kafka AdminClient."""
    from kafka import KafkaAdminClient
    from kafka.errors import KafkaError
    from src.config import settings

    result: dict = {}

    try:
        admin = KafkaAdminClient(
            bootstrap_servers=settings.redpanda_bootstrap_server_list,
            **_kafka_security_config(),
            request_timeout_ms=5000,
            connections_max_idle_ms=10000,
        )

        # brokers
        # describe_cluster() returns dicts on kafka-python; some builds return
        # broker objects with attributes instead — handle both defensively.
        cluster_info = admin.describe_cluster()
        raw_brokers = cluster_info.get("brokers", [])
        normalised_brokers = []
        for b in raw_brokers:
            if isinstance(b, dict):
                node_id = b.get("node_id") or b.get("nodeId")
                host    = b.get("host")
                port    = b.get("port")
            else:
                # object with attributes (some kafka-python builds)
                node_id = getattr(b, "nodeId", None) or getattr(b, "node_id", None)
                host    = getattr(b, "host", None)
                port    = getattr(b, "port", None)
            normalised_brokers.append({"node_id": node_id, "host": host, "port": port})
        result["brokers"] = normalised_brokers
        result["cluster"] = {
            "controller_id": cluster_info.get("controller_id"),
            "cluster_id":    cluster_info.get("cluster_id"),
        }

        # topics - filter to our prefix
        prefix = settings.redpanda_topic_prefix
        all_topics = admin.list_topics()
        our_topics = [t for t in all_topics if prefix in t]
        result["topics"] = [{"name": t} for t in our_topics]

        # per-topic partition details
        if our_topics:
            topic_details = admin.describe_topics(our_topics)
            result["topic_details"] = {
                t["name"]: {
                    "partitions": [
                        {
                            "partition": p["partition"],
                            "leader":    p["leader"],
                            # replicas may be list[int] or list[dict] depending
                            # on kafka-python version — normalise to list[int]
                            "replicas": [
                                r if isinstance(r, int) else (
                                    r.get("node_id") or r.get("nodeId") or 0
                                )
                                for r in (p.get("replicas") or [])
                            ],
                        }
                        for p in t["partitions"]
                    ]
                }
                for t in topic_details
            }

        admin.close()

    except KafkaError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)

    return result


# async def _get_redpanda_stats(data_layer) -> dict:
#     """Fetch Redpanda topic + broker stats via Admin API."""
#     import aiohttp
#     from src.config import settings

#     base = settings.redpanda_admin_url
#     result: dict = {}

#     try:
#         async with aiohttp.ClientSession() as session:
#             # cluster health (already in health check; reuse)
#             health_resp = await session.get(
#                 f"{base}/v1/cluster/health_overview",
#                 timeout=aiohttp.ClientTimeout(total=5),
#             )
#             if health_resp.status == 200:
#                 result["cluster"] = await health_resp.json()

#             # brokers
#             brokers_resp = await session.get(
#                 f"{base}/v1/brokers",
#                 timeout=aiohttp.ClientTimeout(total=5),
#             )
#             if brokers_resp.status == 200:
#                 result["brokers"] = await brokers_resp.json()

#             # topics
#             topics_resp = await session.get(
#                 f"{base}/v1/topics",
#                 timeout=aiohttp.ClientTimeout(total=5),
#             )
#             if topics_resp.status == 200:
#                 all_topics = await topics_resp.json()
#                 # filter to our prefix
#                 prefix = settings.redpanda_topic_prefix
#                 result["topics"] = [t for t in all_topics if prefix in t.get("name", "")]

#             # per-topic partition metrics
#             topic_metrics: dict = {}
#             for topic in result.get("topics", []):
#                 tname = topic.get("name", "")
#                 try:
#                     tp_resp = await session.get(
#                         f"{base}/v1/topics/{tname}",
#                         timeout=aiohttp.ClientTimeout(total=5),
#                     )
#                     if tp_resp.status == 200:
#                         topic_metrics[tname] = await tp_resp.json()
#                 except Exception:
#                     pass
#             result["topic_details"] = topic_metrics

#     except Exception as e:
#         result["error"] = str(e)

#     return result


# ── sub-renderers ─────────────────────────────────────────────────────────────

def _render_flink_panel(data: dict) -> None:
    st.markdown("#### ⚡ Apache Flink")
    if "error" in data:
        st.error(f"Flink unreachable: {data['error']}")
        return

    jm = data.get("jobmanager", {})
    jobs = data.get("jobs", {})

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Task Managers", jm.get("task_managers", "—"))
    col2.metric("Slots Total", jm.get("slots_total", "—"))
    col3.metric("Slots Free", jm.get("slots_available", "—"))
    col4.metric("Jobs Running", jm.get("jobs_running", "—"))

    job_statuses = jobs.get("job_statuses", {})
    if job_statuses:
        st.markdown("**Jobs**")
        for job_id, status in job_statuses.items():
            icon = "🟢" if status == "RUNNING" else "🔴" if status == "FAILED" else "🟡"
            st.caption(f"{icon} `{job_id[:16]}…`  **{status}**")
    else:
        st.caption("No job data available")


def _render_cockroach_panel(data: dict) -> None:
    st.markdown("#### 🪳 CockroachDB")
    if "error" in data:
        st.error(f"CockroachDB query failed: {data['error']}")
        return

    FREE_TIER_BYTES = 10 * 1024 ** 3  # 10 GiB free tier

    total = data.get("total_size_bytes")
    if total is not None:
        _pct_bar(total, FREE_TIER_BYTES, "Storage used")
    else:
        st.caption("Storage size unavailable (needs SHOW RANGES or crdb_internal)")

    counts = data.get("row_counts", {})
    if counts:
        cols = st.columns(3)
        labels = {
            "orderbook_metrics": "Raw Metrics",
            "orderbook_alerts": "Alerts",
            "orderbook_metrics_windowed": "Windowed",
        }
        for i, (tbl, label) in enumerate(labels.items()):
            val = counts.get(tbl)
            cols[i].metric(label, f"{val:,}" if val is not None else "—")

    pool = data.get("pool", {})
    if pool:
        st.caption(
            f"Connection pool: {pool.get('size', '?')} active / "
            f"{pool.get('idle', '?')} idle / "
            f"{pool.get('max_size', '?')} max"
        )


# def _render_redis_panel(data: dict) -> None:
#     st.markdown("#### 🔴 Redis")
#     if "error" in data:
#         st.error(f"Redis query failed: {data['error']}")
#         return

#     FREE_TIER_MEMORY = 30 * 1024 ** 2   # 30 MB (Upstash free)
#     FREE_TIER_NETWORK = 256 * 1024 ** 2  # 256 MB/month (Upstash free)

#     used_mem = data.get("used_memory")
#     maxmem = data.get("maxmemory") or FREE_TIER_MEMORY
#     _pct_bar(used_mem, maxmem, "Memory")

#     net_in = data.get("total_net_input_bytes") or 0
#     net_out = data.get("total_net_output_bytes") or 0
#     net_total = net_in + net_out
#     _pct_bar(net_total, FREE_TIER_NETWORK, "Monthly Network (est.)")

#     col1, col2, col3, col4 = st.columns(4)
#     hits = data.get("keyspace_hits") or 0
#     misses = data.get("keyspace_misses") or 0
#     hit_rate = hits / (hits + misses) if (hits + misses) > 0 else None

#     col1.metric("Keys (db0)", data.get("db0_keys", "—"))
#     col2.metric("Clients", data.get("connected_clients", "—"))
#     col3.metric("Ops/sec", data.get("instantaneous_ops_per_sec", "—"))
#     col4.metric(
#         "Cache Hit Rate",
#         f"{hit_rate*100:.1f}%" if hit_rate is not None else "—",
#     )

def _render_redis_panel(data: dict) -> None:
    st.markdown("#### 🔴 Redis")
    if "error" in data:
        st.error(f"Redis query failed: {data['error']}")
        return

    # Redis Cloud free tier hard limits
    FREE_TIER_MEMORY = 30 * 1024 ** 2  # 30 MB
    FREE_TIER_MAX_CONNS = 30           # 30 connections
    FREE_TIER_MAX_OPS = 100            # 100 ops/sec throughput cap

    # -- memory ---------------------------------------------------------------
    used_mem = data.get("used_memory")
    maxmem = data.get("maxmemory") or FREE_TIER_MEMORY
    _pct_bar(used_mem, maxmem, "Memory (30 MB limit)")

    # -- throughput vs cap ----------------------------------------------------
    ops = data.get("instantaneous_ops_per_sec") or 0
    ops_pct = min(ops / FREE_TIER_MAX_OPS, 1.0)
    ops_color = "🟢" if ops_pct < 0.7 else "🟡" if ops_pct < 0.9 else "🔴"
    st.progress(ops_pct, text=f"{ops_color} Throughput  {ops} / {FREE_TIER_MAX_OPS} ops/sec ({ops_pct*100:.1f}%)")

    # -- connections vs cap ---------------------------------------------------
    clients = data.get("connected_clients") or 0
    conn_pct = min(clients / FREE_TIER_MAX_CONNS, 1.0)
    conn_color = "🟢" if conn_pct < 0.7 else "🟡" if conn_pct < 0.9 else "🔴"
    st.progress(conn_pct, text=f"{conn_color} Connections  {clients} / {FREE_TIER_MAX_CONNS} ({conn_pct*100:.1f}%)")

    # -- network transfer (cumulative since last restart) ---------------------
    net_in = data.get("total_net_input_bytes") or 0
    net_out = data.get("total_net_output_bytes") or 0
    uptime = data.get("uptime_in_seconds") or 1

    hits = data.get("keyspace_hits") or 0
    misses = data.get("keyspace_misses") or 0
    hit_rate = hits / (hits + misses) if (hits + misses) > 0 else None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Keys (db0)", data.get("db0_keys", "—"))
    col2.metric("Net In (since restart)", _fmt_bytes(net_in))
    col3.metric("Net Out (since restart)", _fmt_bytes(net_out))
    col4.metric("Cache Hit Rate", f"{hit_rate*100:.1f}%" if hit_rate is not None else "—")

    st.caption(
        f"ℹ️ Network counters reset on restart "
        f"(uptime {uptime // 3600}h {(uptime % 3600) // 60}m). "
        "Monthly bandwidth quota is not exposed via Redis INFO — monitor via the Redis Cloud console."
    )



def _render_redpanda_panel(data: dict) -> None:
    st.markdown("#### 🐼 Redpanda")
    if "error" in data:
        st.error(f"Redpanda Admin API unavailable: {data['error']}")
        return

    cluster = data.get("cluster", {})
    brokers = data.get("brokers", [])
    topics = data.get("topics", [])
    topic_details = data.get("topic_details", {})

    col1, col2, col3 = st.columns(3)
    col1.metric("Brokers", len(brokers) if isinstance(brokers, list) else "—")
    col2.metric("App Topics", len(topics))
    healthy = cluster.get("is_healthy")
    col3.metric("Cluster Health", "✅ Healthy" if healthy else ("❌ Unhealthy" if healthy is False else "—"))

    if topic_details:
        st.markdown("**Topic partitions**")
        rows = []
        for tname, detail in topic_details.items():
            partitions = detail.get("partitions", []) if isinstance(detail, dict) else []
            rows.append({
                "Topic": tname.split(".")[-1],  # short name
                "Partitions": len(partitions),
                "Replicas": partitions[0].get("replicas", []) if partitions else [],
            })
        for row in rows:
            replicas = len(row["Replicas"])
            st.caption(f"`{row['Topic']}`  — {row['Partitions']} partition(s), {replicas} replica(s)")
    elif not topics:
        st.caption("No topics found for configured prefix")


# ── main component ────────────────────────────────────────────────────────────

@st.fragment()
def render_infra_metrics(refresh_rate: int = 60_000) -> None:
    """Render infrastructure / free-tier usage panel."""
    st_autorefresh(interval=refresh_rate, key="infra_metrics_refresh")

    with st.expander("🖥️ Infrastructure Usage & Metrics", expanded=False):
        st.caption("Refreshes every 60 s — click to expand")

        tab_flink, tab_crdb, tab_redis, tab_rp = st.tabs(
            ["Flink", "CockroachDB", "Redis", "Redpanda"]
        )

        with tab_flink:
            with st.spinner("Fetching Flink metrics…"):
                flink_data = _fetch_flink()
            _render_flink_panel(flink_data)

        with tab_crdb:
            with st.spinner("Fetching CockroachDB metrics…"):
                crdb_data = _fetch_cockroach()
            _render_cockroach_panel(crdb_data)

        with tab_redis:
            with st.spinner("Fetching Redis metrics…"):
                redis_data = _fetch_redis_infra()
            _render_redis_panel(redis_data)

        with tab_rp:
            with st.spinner("Fetching Redpanda metrics…"):
                rp_data = _fetch_redpanda()
            _render_redpanda_panel(rp_data)