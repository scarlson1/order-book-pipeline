# Flink

## Creating jobs

Jobs are located in `src/jobs`. New jobs can be created and added using the commands below (or following the pattern below)

To start docker compose with the jobs running, include `--profile auto-submit` (or `make up-submit`)

## Useful commands

### Submit Flink jobs

All of the current flink jobs are added to a service in the development and production docker compose files (`flink-job-submitter`)

```bash
# submit jobs using flink-job-submitter docker compose service
make flink-submit
# docker compose --profile auto-submit up -d --force-recreate flink-job-submitter

make flink-metrics # submit metrics job
# docker compose exec -e PYTHONPATH=/opt:/opt/src flink-jobmanager ./bin/flink run -py /opt/src/jobs/orderbook_metrics.py --pyFiles /opt/src -d

make flink-alerts # submit alerts job
#docker compose exec -e PYTHONPATH=/opt:/opt/src flink-jobmanager ./bin/flink run -py /opt/src/jobs/orderbook_alerts.py --pyFiles /opt/src -d

make flink-windows # submit windows job
#docker compose exec -e PYTHONPATH=/opt:/opt/src flink-jobmanager ./bin/flink run -py /opt/src/jobs/orderbook_windows.py --pyFiles /opt/src -d
```

### Health, monitoring & troubleshooting

```bash
make flink-ui
# open http://localhost:8081

make flink-logs
# docker compose logs -f flink-jobmanager flink-taskmanager

make flink-jobs
# docker compose exec flink-jobmanager flink list -a -m flink-jobmanager:8081
```
