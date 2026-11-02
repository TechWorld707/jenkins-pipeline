# Controlled production observability validation

Do not inject outages into production. Use local tests and sanitised fixture replay
for disruptive cases. Existing manual approvals remain required for releases.

| Exercise | Where | Evidence to verify |
| --- | --- | --- |
| Read-only functional checks | Released production HTTPS origin | Successful synthetic events; HTTP logs/metrics; a sampled database-health trace |
| One approved enquiry | Production, after cleanup procedure exists | HTTP 201, enquiry-save query trace, correlated request record; clean up synthetic row |
| Pool exhaustion | `ci/test_observability.py` local SQLite QueuePool | Real acquisition timeout, measured waiting duration, timeout counter, zero acquisitions left active |
| URL/privacy probe | Local FastAPI and OTLP receiver test | URL/customer values absent from exported spans, metrics and application logs |
| Security gate failure | Isolated build-only test | Failed gate cannot upload release artifacts or push images; native build logs retain findings |
| Agent/controller unavailable | Mock observer API or sanitised fixture | Observer failure and heartbeat-missing alert path; no shutdown of a live agent |
| ECS deployment failure | Sanitised lifecycle fixture in a test log group | Correct failure filter and notification route; verify rollback interpretation separately |
| Collector unavailable | Local test collector | Application remains responsive; missing-metric detection fires after the configured window |

Run tests with the application requirements and `httpx` installed:

```bash
python3 -m unittest discover -s ci -p 'test_*.py'
```

For event replay, use a dedicated test group and copied metric filters/alarms,
with names/namespace prefixed `WebTech/Drill`. Do not publish replay events into
the production SLO or page route. Fixture replay proves filter/routing logic,
not that a real ECS outage has been captured. Record unexecuted exercises as
pending; do not represent configuration validation as live end-to-end evidence.

Each drill ticket must include the time limit, fixture or injection, expected
signals, cleanup action, actual results and recovery evidence.
