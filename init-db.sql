-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create main orderbook metrics table
CREATE TABLE IF NOT EXISTS orderbook_metrics (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- Price data
    mid_price DOUBLE PRECISION NOT NULL,
    best_bid DOUBLE PRECISION NOT NULL,
    best_ask DOUBLE PRECISION NOT NULL,
    
    -- Imbalance metrics
    imbalance_ratio DOUBLE PRECISION,
    weighted_imbalance DOUBLE PRECISION,
    
    -- Volume metrics
    bid_volume DOUBLE PRECISION,
    ask_volume DOUBLE PRECISION,
    total_volume DOUBLE PRECISION,
    
    -- Spread metrics
    spread_bps DOUBLE PRECISION,
    spread_abs DOUBLE PRECISION,
    
    -- Top of book metrics
    vtob_ratio DOUBLE PRECISION,
    best_bid_volume DOUBLE PRECISION,
    best_ask_volume DOUBLE PRECISION,
    
    -- Velocity and derivatives
    imbalance_velocity DOUBLE PRECISION,
    
    -- Metadata
    depth_levels INTEGER,
    update_id BIGINT
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('orderbook_metrics', 'time', if_not_exists => TRUE);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_orderbook_symbol_time 
    ON orderbook_metrics (symbol, time DESC);

CREATE INDEX IF NOT EXISTS idx_orderbook_time 
    ON orderbook_metrics (time DESC);

CREATE INDEX IF NOT EXISTS idx_orderbook_imbalance 
    ON orderbook_metrics (symbol, time DESC, weighted_imbalance);

-- Create alerts table
CREATE TABLE IF NOT EXISTS orderbook_alerts (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT,
    metric_value DOUBLE PRECISION,
    threshold_value DOUBLE PRECISION,
    side VARCHAR(10),
    
    -- Additional context
    mid_price DOUBLE PRECISION,
    imbalance_ratio DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_alerts_time 
    ON orderbook_alerts (time DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_symbol_time 
    ON orderbook_alerts (symbol, time DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_type 
    ON orderbook_alerts (alert_type, time DESC);

-- Create materialized view for 1-minute aggregates
CREATE MATERIALIZED VIEW IF NOT EXISTS orderbook_metrics_1m AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    
    -- Price statistics
    FIRST(mid_price, time) as open_price,
    MAX(mid_price) as high_price,
    MIN(mid_price) as low_price,
    LAST(mid_price, time) as close_price,
    
    -- Imbalance statistics
    AVG(weighted_imbalance) as avg_imbalance,
    STDDEV(weighted_imbalance) as stddev_imbalance,
    MAX(weighted_imbalance) as max_imbalance,
    MIN(weighted_imbalance) as min_imbalance,
    
    -- Volume statistics
    AVG(total_volume) as avg_volume,
    MAX(total_volume) as max_volume,
    
    -- Spread statistics
    AVG(spread_bps) as avg_spread_bps,
    MAX(spread_bps) as max_spread_bps,
    MIN(spread_bps) as min_spread_bps,
    
    -- Count
    COUNT(*) as sample_count
FROM orderbook_metrics
GROUP BY bucket, symbol;

-- Create continuous aggregate policy (auto-refresh)
-- This will be set up in application code after first data arrives

-- Create retention policy (optional - keep data for 7 days)
-- Uncomment to enable automatic data cleanup
-- SELECT add_retention_policy('orderbook_metrics', INTERVAL '7 days');
-- SELECT add_retention_policy('orderbook_alerts', INTERVAL '30 days');

-- Create function to calculate statistics for a symbol
CREATE OR REPLACE FUNCTION get_symbol_statistics(
    p_symbol VARCHAR(20),
    p_interval INTERVAL DEFAULT '1 hour'
)
RETURNS TABLE (
    symbol VARCHAR(20),
    avg_imbalance DOUBLE PRECISION,
    stddev_imbalance DOUBLE PRECISION,
    avg_spread_bps DOUBLE PRECISION,
    avg_volume DOUBLE PRECISION,
    sample_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        om.symbol,
        AVG(om.weighted_imbalance)::DOUBLE PRECISION,
        STDDEV(om.weighted_imbalance)::DOUBLE PRECISION,
        AVG(om.spread_bps)::DOUBLE PRECISION,
        AVG(om.total_volume)::DOUBLE PRECISION,
        COUNT(*)::BIGINT
    FROM orderbook_metrics om
    WHERE om.symbol = p_symbol
        AND om.time >= NOW() - p_interval
    GROUP BY om.symbol;
END;
$$ LANGUAGE plpgsql;

-- Create function to get recent alerts
CREATE OR REPLACE FUNCTION get_recent_alerts(
    p_limit INTEGER DEFAULT 100,
    p_symbol VARCHAR(20) DEFAULT NULL
)
RETURNS TABLE (
    id INTEGER,
    alert_time TIMESTAMPTZ,
    symbol VARCHAR(20),
    alert_type VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    metric_value DOUBLE PRECISION
) AS $$
BEGIN
    IF p_symbol IS NULL THEN
        RETURN QUERY
        SELECT 
            oa.id,
            oa.time,
            oa.symbol,
            oa.alert_type,
            oa.severity,
            oa.message,
            oa.metric_value
        FROM orderbook_alerts oa
        ORDER BY oa.time DESC
        LIMIT p_limit;
    ELSE
        RETURN QUERY
        SELECT 
            oa.id,
            oa.time,
            oa.symbol,
            oa.alert_type,
            oa.severity,
            oa.message,
            oa.metric_value
        FROM orderbook_alerts oa
        WHERE oa.symbol = p_symbol
        ORDER BY oa.time DESC
        LIMIT p_limit;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO orderbook_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO orderbook_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO orderbook_user;

-- Insert sample configuration (optional)
CREATE TABLE IF NOT EXISTS config (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO config (key, value) VALUES 
    ('alert_threshold_high', '0.70'),
    ('alert_threshold_medium', '0.50'),
    ('spread_alert_multiplier', '2.0'),
    ('calculation_depth', '10'),
    ('retention_days', '7')
ON CONFLICT (key) DO NOTHING;

-- Create windowed metrics table for Flink window aggregates
CREATE TABLE IF NOT EXISTS orderbook_metrics_windowed (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- Window metadata
    window_type VARCHAR(20) NOT NULL,  -- '1m_tumbling' or '5m_sliding'
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    window_duration_seconds INTEGER NOT NULL,
    
    -- Imbalance statistics
    avg_imbalance DOUBLE PRECISION,
    min_imbalance DOUBLE PRECISION,
    max_imbalance DOUBLE PRECISION,
    
    -- Spread statistics
    avg_spread_bps DOUBLE PRECISION,
    min_spread_bps DOUBLE PRECISION,
    max_spread_bps DOUBLE PRECISION,
    
    -- Volume statistics
    avg_bid_volume DOUBLE PRECISION,
    avg_ask_volume DOUBLE PRECISION,
    avg_total_volume DOUBLE PRECISION,
    total_bid_volume DOUBLE PRECISION,
    total_ask_volume DOUBLE PRECISION,
    total_volume DOUBLE PRECISION,
    
    -- Metadata
    sample_count INTEGER NOT NULL,
    window_velocity DOUBLE PRECISION,
    
    -- Use window_end as the time column (represents when window completed)
    CONSTRAINT pk_windowed PRIMARY KEY (time, symbol, window_type)
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('orderbook_metrics_windowed', 'time', if_not_exists => TRUE);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_windowed_symbol_time 
    ON orderbook_metrics_windowed (symbol, time DESC);

CREATE INDEX IF NOT EXISTS idx_windowed_symbol_type_time 
    ON orderbook_metrics_windowed (symbol, window_type, time DESC);

CREATE INDEX IF NOT EXISTS idx_windowed_type 
    ON orderbook_metrics_windowed (window_type, time DESC);

-- Create view for latest windowed metrics per symbol
CREATE OR REPLACE VIEW latest_windowed_metrics AS
SELECT DISTINCT ON (symbol, window_type)
    symbol,
    window_type,
    time,
    window_start,
    window_end,
    avg_imbalance,
    avg_spread_bps,
    avg_total_volume,
    sample_count
FROM orderbook_metrics_windowed
ORDER BY symbol, window_type, time DESC;

-- Create view for dashboard
CREATE OR REPLACE VIEW dashboard_summary AS
SELECT
    symbol,
    LAST(mid_price, time) as current_price,
    LAST(weighted_imbalance, time) as current_imbalance,
    LAST(spread_bps, time) as current_spread,
    LAST(total_volume, time) as current_volume,
    LAST(time, time) as last_update,
    COUNT(*) as updates_last_hour
FROM orderbook_metrics
WHERE time >= NOW() - INTERVAL '1 hour'
GROUP BY symbol;

COMMIT;
