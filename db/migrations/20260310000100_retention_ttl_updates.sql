-- migrate:up transaction:false
ALTER TABLE orderbook_alerts
SET (
  ttl_expiration_expression = 'time + INTERVAL ''7 days''',
  ttl_job_cron = '@hourly'
);

ALTER TABLE orderbook_metrics
SET (ttl_expiration_expression = 'time + INTERVAL ''24 hours''');

-- migrate:down transaction:false
ALTER TABLE orderbook_alerts RESET (ttl_expiration_expression, ttl_job_cron);
ALTER TABLE orderbook_metrics RESET (ttl_expiration_expression, ttl_job_cron);