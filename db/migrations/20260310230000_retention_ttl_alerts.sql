-- migrate:up transaction:false
ALTER TABLE orderbook_alerts
SET (
  ttl_expiration_expression = 'time + INTERVAL ''7 days''',
  ttl_job_cron = '@hourly'
);

-- migrate:down transaction:false
ALTER TABLE orderbook_alerts RESET (ttl_expiration_expression, ttl_job_cron);