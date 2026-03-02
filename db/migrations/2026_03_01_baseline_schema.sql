-- migrate:up
CREATE TABLE orderbook_metrics (
  time TIMESTAMPTZ NOT NULL,
  symbol STRING NOT NULL,
  mid_price FLOAT8 NOT NULL,
  best_bid FLOAT8 NOT NULL,
  best_ask FLOAT8 NOT NULL,
  imbalance_ratio FLOAT8,
  weighted_imbalance FLOAT8,
  bid_volume FLOAT8,
  ask_volume FLOAT8,
  total_volume FLOAT8,
  spread_bps FLOAT8,
  spread_abs FLOAT8,
  vtob_ratio FLOAT8,
  best_bid_volume FLOAT8,
  best_ask_volume FLOAT8,
  imbalance_velocity FLOAT8,
  depth_levels INT8,
  update_id INT8
);

CREATE INDEX idx_orderbook_symbol_time ON orderbook_metrics (symbol, time DESC);
CREATE INDEX idx_orderbook_time ON orderbook_metrics (time DESC);
CREATE INDEX idx_orderbook_imbalance ON orderbook_metrics (symbol, time DESC, weighted_imbalance);

CREATE TABLE orderbook_alerts (
  id INT8 PRIMARY KEY DEFAULT unique_rowid(),
  time TIMESTAMPTZ NOT NULL,
  symbol STRING NOT NULL,
  alert_type STRING NOT NULL,
  severity STRING NOT NULL,
  message STRING,
  metric_value FLOAT8,
  threshold_value FLOAT8,
  side STRING,
  mid_price FLOAT8,
  imbalance_ratio FLOAT8
);

CREATE INDEX idx_alerts_time ON orderbook_alerts (time DESC);
CREATE INDEX idx_alerts_symbol_time ON orderbook_alerts (symbol, time DESC);
CREATE INDEX idx_alerts_type ON orderbook_alerts (alert_type, time DESC);

CREATE TABLE orderbook_metrics_windowed (
  time TIMESTAMPTZ NOT NULL,
  symbol STRING NOT NULL,
  window_type STRING NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  window_duration_seconds INT8 NOT NULL,
  avg_imbalance FLOAT8,
  min_imbalance FLOAT8,
  max_imbalance FLOAT8,
  avg_spread_bps FLOAT8,
  min_spread_bps FLOAT8,
  max_spread_bps FLOAT8,
  avg_bid_volume FLOAT8,
  avg_ask_volume FLOAT8,
  avg_total_volume FLOAT8,
  total_bid_volume FLOAT8,
  total_ask_volume FLOAT8,
  total_volume FLOAT8,
  sample_count INT8 NOT NULL,
  window_velocity FLOAT8,
  CONSTRAINT pk_windowed PRIMARY KEY (time, symbol, window_type)
);

CREATE INDEX idx_windowed_symbol_time ON orderbook_metrics_windowed (symbol, time DESC);
CREATE INDEX idx_windowed_symbol_type_time ON orderbook_metrics_windowed (symbol, window_type, time DESC);
CREATE INDEX idx_windowed_type ON orderbook_metrics_windowed (window_type, time DESC);

CREATE VIEW latest_windowed_metrics AS
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

-- migrate:down
DROP VIEW IF EXISTS latest_windowed_metrics;
DROP TABLE IF EXISTS orderbook_metrics_windowed;
DROP TABLE IF EXISTS orderbook_alerts;
DROP TABLE IF EXISTS orderbook_metrics;
