# JIRA-002: Post-deployment enquiry performance regression

## Learner ticket

Priority: P2 — degraded performance in the WebTech learning environment.

Reporter: learning operator using the enquiry form and real telemetry.

Component: WebTech backend / webtech-production-postgres.

Environment: ECS Fargate and RDS PostgreSQL db.t3.micro, not the ticket example's EC2/MySQL installation.

Symptom to investigate after the drill release: enquiry submission becomes slow or returns HTTP 503 while the home page and database health checks can still return 200. Compare the onset with the backend deployment timestamp. A deployment correlation is evidence to investigate, not proof by itself.

Do not copy the example's 98% CPU, 24 connections, 450 slow queries/minute, 8.5-second latency or normal disk I/O into this ticket as observations. Record actual values. No continuous load generator is installed by this exercise.

## Instructor: implementation and boundaries

The learning image intentionally sets `QUERY_REGRESSION_DRILL=true`. Before saving an enquiry, it runs an unnecessary PostgreSQL aggregation over generated numbers, computing nested MD5 hashes. This burns real database CPU without reading customer data or scanning customer tables. The query does not sleep or fake a latency metric. The configured Docker image activates the drill; importing the module outside that image defaults to disabled.

Each SQL statement has an eight-second database-enforced timeout. A timed-out preflight causes the transaction to roll back and the existing error handler returns 503; a completed query adds latency before a normal 201 response. Each backend process allows only one drill query at a time and skips overlapping calls. The drill expires 30 minutes after each backend process starts. Scaling/restarting creates a new process and resets that window. Normal health routes do not execute the expensive query, so the existing pipeline smoke checks can succeed. Do not change the pipeline's security gates or manual deployment approval.

The regression logs `enquiry.preflight.started` and `enquiry.preflight.completed` with duration/outcome and a correlated trace. A custom `enquiry.preflight.aggregate` span encloses the SQL work. The existing telemetry redacts SQL text: do not expect SQL text in Tempo. Inspect the release source for the actual statement. RDS slow-query logging is not automatically enabled or altered.

The app remains healthy now: writing these files does not change the deployed image. Activation requires the normal build, scan and manually approved Jenkins deployment of the merged drill commit.

## Before approving deployment

The verified healthy pink release on 11 November used frontend revision 19 and backend revision 19, with two tasks each. The local snapshot is `.local-state/jira002/known-good.json`. If any other deployment occurs before this exercise, capture a fresh baseline rather than assuming 19 remains the intended rollback target:

```bash
aws ecs describe-services --cluster webtech-production \
  --services webtech-production-backend webtech-production-frontend \
  --region eu-west-2 \
  --query 'services[].{Service:serviceName,Revision:taskDefinition,Running:runningCount}'
```

Record the current backend image digest and UTC deployment time too. Use the ordinary production-only Jenkins job, observability enabled, BUILD_ONLY unchecked. Review scans and approve the explicit drill release. No Terraform apply, database parameter change or task-count increase is needed.

## Reproduce once, then investigate

First measure a single form submission on the healthy release as a baseline. After the drill release, submit once again. Use a synthetic name and email; these commands may create a labelled test enquiry if the transaction succeeds. Do not repeatedly run this command or use parallel load.

```bash
curl --connect-timeout 5 --max-time 15 -sS \
  -H 'Content-Type: application/json' \
  -d '{"name":"JIRA-002 Learning Test","email":"jira002@example.com"}' \
  -w '\nHTTP %{http_code} total=%{time_total}s\n' \
  https://d36rzp0gjk5fiq.cloudfront.net/api/enquiries
```

HTTP 201 means a test enquiry was saved; HTTP 503 means the database transaction failed. Record the result; do not claim a successful submission if it timed out. Any successfully saved synthetic rows remain clearly labelled for a separately reviewed cleanup; this drill performs no deletion.

Use Grafana Last 15 minutes (or the exact UTC window). Compare request p95 and errors with RDS CPUUtilization, DatabaseConnections and read/write IOPS. A single request may produce too little traffic for a useful histogram percentile or a visible one-minute CPU spike; the real per-request trace and log duration remain evidence. Two tasks and connection-pool sizes here differ from the original example.

Prometheus query:

```promql
histogram_quantile(0.95,
  sum by (le, route) (
    rate(webtech_http_request_duration_seconds_bucket{environment="production"}[5m])
  )
)
```

Grafana Explore → Production CloudWatch → CloudWatch Logs → Logs Insights QL. Select `/ecs/webtech-production/backend` before running:

```sql
fields @timestamp, event, duration_ms, outcome, error_type, trace_id, version
| filter event like /enquiry.preflight/ or event = "enquiry.database.failed"
| sort @timestamp desc
| limit 50
```

Open a returned trace ID in Production Tempo. Find `enquiry.preflight.aggregate` under `enquiry.save` and compare its duration with database connection acquisition. Distinguish long SQL execution after acquisition from JIRA-001's blocked network path. Record error types and current backend image/revision before choosing rollback. Do not raise the pool size merely because requests are slow.

## Roll back when you decide the new release is responsible

Restore the saved known-good backend revision. This is a live service update; run it when you are ready to end the incident. Use revision 19 only if it is still the verified baseline captured above.

```bash
aws ecs update-service --cluster webtech-production \
  --service webtech-production-backend \
  --task-definition webtech-production-backend:19 \
  --region eu-west-2 --query 'service.taskDefinition'
aws ecs wait services-stable --cluster webtech-production \
  --services webtech-production-backend --region eu-west-2
```

Recheck the actual service revision and repeat one labelled submission. Compare its status and duration with the drill request. Confirm `/api/health/db` returns HTTP 200. The pink frontend need not be rolled back because the regression is in the backend. Old slow traces remain historical evidence. Allow five-minute rate windows to clear; do not interpret old samples as new failures.

Rolling back ECS does not revert Git. Before a future deployment, revert the dedicated drill commit through the normal review workflow or explicitly disable `QUERY_REGRESSION_DRILL` in the image/source; otherwise the learning image will enable the drill again on task startup. If the 30-minute expiry resolved symptoms before rollback, record expiry as a confounding factor rather than falsely attributing recovery to rollback.
