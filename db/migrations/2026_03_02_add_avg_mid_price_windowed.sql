-- migrate:up
ALTER TABLE orderbook_metrics_windowed
ADD COLUMN avg_mid_price FLOAT8;

DROP VIEW IF EXISTS latest_windowed_metrics;
CREATE VIEW latest_windowed_metrics AS
SELECT DISTINCT ON (symbol, window_type)
  symbol,
  window_type,
  time,
  window_start,
  window_end,
  avg_mid_price,
  avg_imbalance,
  avg_spread_bps,
  avg_total_volume,
  sample_count
FROM orderbook_metrics_windowed
ORDER BY symbol, window_type, time DESC;

-- migrate:down
DROP VIEW IF EXISTS latest_windowed_metrics;
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

ALTER TABLE orderbook_metrics_windowed
DROP COLUMN avg_mid_price;
