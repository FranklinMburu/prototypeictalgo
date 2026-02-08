Monitoring and Alerts
=====================

DLQ (dead-letter queue) monitoring
----------------------------------

Metric: `dlq_size`

- Purpose: the number of entries currently in the decision DLQ (either Redis-backed or in-memory fallback). A sustained non-zero value indicates persistent persistence failures or backpressure.
- Alert: `ReasonerServiceDLQHigh` fires when `dlq_size` is greater than zero for 5 minutes.

Suggested runbook
------------------

1. Inspect the DLQ via admin endpoints (`/admin/dlq`) or the `scripts/dlq_inspect.py` CLI.
2. Check storage availability (database) and any error logs from the reasoner service.
3. If Redis is configured and used as DLQ, check Redis health and memory usage.
4. If entries are safe to requeue, use the admin requeue endpoints or manually requeue after resolving underlying errors.

Why this alert
---------------

A transient DLQ item is expected in case of short-lived outages. This alert focuses on sustained problems (5m) to avoid noisy paging for short blips.
