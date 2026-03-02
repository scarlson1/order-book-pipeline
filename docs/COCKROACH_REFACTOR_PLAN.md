# TimescaleDB -> CockroachDB Refactor Plan

## Query Performance Tradeoffs

Moving from TimescaleDB to CockroachDB changes the performance profile:

- TimescaleDB is typically faster for long-window time-series aggregations and specialized functions (`time_bucket`, `FIRST/LAST`, compression policies).
- CockroachDB is typically better for distributed availability, multi-region resilience, and operational simplicity at scale, but with higher write and query overhead per operation.
- For this pipeline, performance remains strong if dashboards and analytics read mostly from pre-aggregated Flink windowed tables instead of scanning high-volume raw ticks.

Recommended query posture after migration:

- Keep raw `orderbook_metrics` mainly for recent operational lookbacks.
- Use `orderbook_metrics_windowed` for charting and longer historical views by default.
- Prefer pre-aggregation in Flink over ad hoc heavy SQL aggregation in CockroachDB.
- Expect long-window historical analytics to be slower than TimescaleDB unless pre-aggregated.

## Objectives

- Replace Timescale-dependent schema and query patterns with Cockroach-compatible equivalents.
- Establish migration-driven schema management (no `init-db.sql` runtime bootstrap dependency).
- Integrate DB migration steps into deployment and CI workflows.
- Preserve existing ingestion, consumer, and dashboard behavior with minimal query regressions.

## Non-Goals (For This Refactor)

- Re-architecting the stream processing topology.
- Replacing Redis or Redpanda.
- Building a full warehouse/OLAP stack.

## Tooling and Process Recommendation

## Recommended Tool: SQL-First Migrations via `dbmate`

Why this is the best fit for this repo:

- Codebase already uses raw SQL and `asyncpg`.
- Migrations stay explicit, reviewable, and Cockroach-specific.
- Lower complexity than full ORM migration tooling for this project.

Alternative (valid) option:

- Alembic with raw SQL revisions is acceptable if you want Python-native migration tooling.

## Migration Process Model

- Store versioned migrations in a dedicated directory (for example, `db/migrations/`).
- Keep forward-only immutable migrations.
- Use expand/contract for breaking schema changes.
- Run migrations before deploying runtime services.
- Block deploy if migrations fail.
- Keep schema state in migration table managed by the migration tool.

## Rollout Strategy

1. Bootstrap migration framework and create Cockroach baseline schema migration.
2. Update application code for Cockroach compatibility and resilience.
3. Switch workflows to run migrations before deploy.
4. Remove Timescale-specific local/test assumptions.
5. Cut over documentation and operational runbooks.

## File-by-File Refactor Scope

## Schema and Initialization

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/init-db.sql`
  - Replace Timescale-specific DDL with Cockroach-compatible baseline migration files.
  - Remove:
    - [x] `CREATE EXTENSION timescaledb`
    - [x] `create_hypertable(...)`
    - [x] `time_bucket(...)`
    - [x] `FIRST(...)`, `LAST(...)`
    - [x] `plpgsql` functions
  - [x] Replace `SERIAL` usage with Cockroach-safe identity strategy.

- New migration directory (to be created)
  - Example: `db/migrations/`
  - Include baseline schema for:
    - [x] `orderbook_metrics`
    - [x] `orderbook_alerts`
    - [x] `orderbook_metrics_windowed`
    - [x] Required indexes
    - [x] Cockroach-safe views used by dashboard

## Application Config

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/src/config.py`
  - [x] Add Cockroach connection settings:
    - [x] `POSTGRES_SSLMODE` (default `require` for production)
    - [x] Optional cert settings if needed.
  - [x] Build DB URL with SSL params for async and sync clients.
  - [x] Keep local dev defaults usable with Docker/local Postgres.

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/.env.example`
- `/Users/spencercarlson/Documents/dev/order-book-pipeline/.env.oci.example`
  - [x] Add Cockroach-specific env vars and secure defaults.
  - [x] Ensure examples reflect migration-first initialization flow.

## Database Client and Write Path

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/src/common/database.py`
  - [x] Remove Timescale extension detection and log messaging.
  - [x] Add Cockroach-friendly connection retry/backoff.
  - [x] Add handling strategy for transaction retry errors (`40001`).
  - [x] Validate `copy_records_to_table` behavior against Cockroach.
  - [x] Add fallback bulk insert path if COPY semantics are limited in target environment.
  - [x] Keep health checks and pool stats intact.

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/src/consumers/db_consumer.py`
  - [x] Update Timescale-specific docstrings/comments.
  - [x] Confirm batching sizes and commit behavior for Cockroach throughput.
  - [x] Optionally add idempotent insert patterns where at-least-once delivery can duplicate writes (best-effort in-memory dedupe in active batches).

## Dashboard Query Layer

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/dashboard/data/db_queries.py`
  - [x] Replace `time_bucket` usage with Cockroach-compatible query patterns (`date_trunc` or pre-aggregated reads).
  - [x] Shift historical chart queries toward `orderbook_metrics_windowed`.
  - [x] Ensure query shapes align with Cockroach indexes.

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/dashboard/data/data_layer.py`
  - [x] Update DB comments/terminology where needed.
  - [x] Keep health checks and fallback logic unchanged unless query API changes.

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/dashboard/components/services_health_status.py`
  - [x] Optional label update (`PostgreSQL` to `CockroachDB`) for clarity.

## Local Runtime and Compose

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/docker-compose.yml`
  - [x] Remove hard dependency on Timescale init script flow for schema.
  - [x] Decide local DB mode:
    - Option A: local Cockroach container (preferred for parity).
    - Option B: local Postgres for dev and Cockroach for prod only.
  - [x] Update service health checks and `depends_on` accordingly.

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/compose.oci.yml`
  - [x] Keep external Cockroach usage.
  - [x] Add migration execution hook/process before consumers run.

## Developer Tooling

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/Makefile`
- `/Users/spencercarlson/Documents/dev/order-book-pipeline/justfile`
  - [x] Replace `timescaledb` shell commands with DB-agnostic or Cockroach-aware commands.
  - [x] Add migration commands:
    - [x] create migration
    - [x] apply migration
    - [x] migration status

## CI/CD and GitHub Workflows

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/.github/workflows/deploy-oci.yml`
  - [x]Add migration step before `docker compose up`.
  - [x]Gate deployment on successful migration.

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/.github/workflows/test.yml`
  - [ ] Replace Timescale service image assumptions.
  - [ ] Ensure tests run against Cockroach-compatible schema setup.
  - [ ] Add migration application during CI setup.

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/.github/workflows/infra-apply.yml`
  - [ ] Keep infra provisioning.
  - [ ] Optionally add outputs/secret sync hooks if Cockroach endpoint/user material is managed there.

## Terraform Integration

- [ ] `/Users/spencercarlson/Documents/dev/order-book-pipeline/terraform/modules/cockroach/main.tf`
- [ ] `/Users/spencercarlson/Documents/dev/order-book-pipeline/terraform/modules/cockroach/outputs.tf`
- [ ] `/Users/spencercarlson/Documents/dev/order-book-pipeline/terraform/envs/prod/main.tf`
- [ ] `/Users/spencercarlson/Documents/dev/order-book-pipeline/terraform/envs/prod/outputs.tf`
  - [ ] Keep Terraform responsible for infrastructure lifecycle.
  - [ ] Expand outputs for DB connection metadata if provider supports it.
  - [ ] Do not manage application table DDL in Terraform.
  - [ ] Feed runtime endpoint/user secrets into deploy environment.

## Tests

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/tests/integration/test_database.py`
  - [ ] Update assumptions from Timescale bootstrapped schema to migration-managed schema.
  - [ ] Add coverage for Cockroach transaction retry behavior if retry logic is added.

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/tests/integration/test_ingestion_pipeline.py`
- `/Users/spencercarlson/Documents/dev/order-book-pipeline/tests/e2e/test_full_pipeline.py`
  - Ensure integration/e2e fixtures can bootstrap schema via migrations.

## Documentation

- `/Users/spencercarlson/Documents/dev/order-book-pipeline/README.md`
- `/Users/spencercarlson/Documents/dev/order-book-pipeline/DEPLOYMENT.md`
- `/Users/spencercarlson/Documents/dev/order-book-pipeline/DEVELOPMENT.md`
- `/Users/spencercarlson/Documents/dev/order-book-pipeline/QUICKSTART.md`
- `/Users/spencercarlson/Documents/dev/order-book-pipeline/docs/TROUBLESHOOTING.md`
  - Remove Timescale-specific operational instructions.
  - Document migration workflow and Cockroach performance posture.
  - Add “query by windowed table first” guidance.

## Database Initialization and Management Workflow

## Local Development

- Start local services.
- Run migration apply command once environment is ready.
- Run app services.
- Use migration create/apply commands for all schema changes.

## CI

- Provision test database service.
- Apply migrations.
- Run tests.
- Fail pipeline on schema drift or migration errors.

## Production (OCI)

- Pull latest code.
- Apply migrations against Cockroach target.
- Start or restart runtime containers.
- Verify health checks and row freshness.

## Migration Safety Practices

- One logical change per migration file.
- Avoid destructive changes in single-step deploys.
- Use expand/contract for renames and type changes.
- Keep migration SQL idempotent when practical.
- Test migrations against staging with production-like data volume.

## Query and Indexing Guidelines for Cockroach

- Primary access patterns:
  - latest per symbol
  - recent range by symbol and time
  - recent alerts by symbol and time
  - latest windowed aggregates by symbol and window type

- Required index posture:
  - `(symbol, time DESC)` on metrics
  - `(symbol, time DESC)` and `(alert_type, time DESC)` on alerts
  - `(symbol, window_type, time DESC)` on windowed table

- Query posture:
  - Prefer narrow time ranges on raw metrics.
  - Prefer windowed table for dashboards beyond short lookbacks.
  - Keep long-window analytical scans out of request-time dashboard paths.

## Proposed Execution Phases

## Phase 0: Prep

- Choose migration tool (`dbmate` recommended).
- Add migration command wrappers.
- Define baseline schema migration.

## Phase 1: Schema Cutover

- Apply baseline migration in non-prod.
- Validate all writer paths and dashboard reads.
- Remove runtime dependency on `init-db.sql`.

## Phase 2: App Compatibility

- Update config and DB client.
- Replace Timescale SQL and comments.
- Tune batch write behavior for Cockroach.

## Phase 3: Pipeline Integration

- Add migration step to deploy workflow.
- Update CI DB service and migration bootstrap.
- Update Terraform outputs/secrets wiring as needed.

## Phase 4: Documentation and Runbooks

- Rewrite setup and troubleshooting docs.
- Add migration rollback/roll-forward playbook.

## Cutover Acceptance Criteria

- Migrations apply cleanly in staging and production.
- Consumers ingest and persist metrics/alerts/windowed rows continuously.
- Dashboard loads without SQL errors and key charts render.
- Health checks pass for Redis, DB, Redpanda, and Flink.
- No Timescale-specific SQL remains in runtime paths.

## Risks and Mitigations

- Risk: Dashboard regressions from changed aggregate queries.
  - Mitigation: prefer windowed table reads and validate query latency before cutover.

- Risk: Duplicate writes from at-least-once consumer commit behavior.
  - Mitigation: evaluate idempotent keys/upsert strategy for high-value tables.

- Risk: Migration drift between environments.
  - Mitigation: migration-only schema changes and CI validation.

- Risk: Cockroach retryable transaction errors under write bursts.
  - Mitigation: add retry with backoff in DB write path.

## Decision Needed Before Implementation

- Confirm migration tool choice:
  - `dbmate` (recommended) or Alembic.
- Confirm local DB parity strategy:
  - local Cockroach container or local Postgres with Cockroach-only production.
