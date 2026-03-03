-- migrate:up transaction:false
ALTER TABLE orderbook_metrics
SET (
  ttl_expiration_expression = 'time + INTERVAL ''7 days''',
  ttl_job_cron = '@hourly'
);

ALTER TABLE orderbook_metrics_windowed
SET (
  ttl_expiration_expression = 'time + INTERVAL ''30 days''',
  ttl_job_cron = '@hourly'
);

-- migrate:down transaction:false
ALTER TABLE orderbook_metrics RESET (ttl_expiration_expression, ttl_job_cron);
ALTER TABLE orderbook_metrics_windowed RESET (ttl_expiration_expression, ttl_job_cron);
