-- migrate:up transaction:false
ALTER TABLE orderbook_metrics_windowed
ADD COLUMN IF NOT EXISTS avg_mid_price FLOAT8;

DROP VIEW IF EXISTS latest_windowed_metrics;

CREATE VIEW IF NOT EXISTS latest_windowed_metrics AS
SELECT
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
FROM orderbook_metrics_windowed w
WHERE time = (
  SELECT MAX(time) FROM orderbook_metrics_windowed
  WHERE symbol = w.symbol AND window_type = w.window_type
);

-- migrate:down transaction:false
DROP VIEW IF EXISTS latest_windowed_metrics;

CREATE VIEW IF NOT EXISTS latest_windowed_metrics AS
SELECT
  symbol,
  window_type,
  time,
  window_start,
  window_end,
  avg_imbalance,
  avg_spread_bps,
  avg_total_volume,
  sample_count
FROM orderbook_metrics_windowed w
WHERE time = (
  SELECT MAX(time) FROM orderbook_metrics_windowed
  WHERE symbol = w.symbol AND window_type = w.window_type
);

ALTER TABLE orderbook_metrics_windowed
DROP COLUMN IF EXISTS avg_mid_price;
