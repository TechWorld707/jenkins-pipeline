# Investigating production incidents

1. Check the intended runtime state and the external synthetic result. Separate
   an application outage from missing telemetry or an environment never released.
2. In Grafana, compare request errors, latency, pool occupancy/wait/timeouts and
   RDS connections with the latest deployment time. Use the commit SHA and exact
   release digests to identify the change.
3. Query production CloudWatch groups with the examples in
   `observability/queries/production.logs-insights`. Follow the request/trace ID to
   Tempo. An unsampled request may have logs but no stored trace.
4. For deployment failures, inspect `production-deployment.json`, service previous/
   requested/actual revisions and native ECS lifecycle events. `unknown` means the
   state could not be read, not that rollback succeeded. Verify both services and
   their running tasks before declaring recovery.
5. For build failures, use CodeBuild ID and stage outcome, then open native
   CloudWatch build logs. A failed security gate must not be bypassed to release.
6. For database timeouts, distinguish pool acquisition waits from server connection
   limits and failed networking/TLS/authentication. Check the maximum pool budget
   including worker count and deployment surge before changing limits.
7. For missing data, check exporter logs, backend reachability, collector memory,
   API observer heartbeat, probe scheduler and AWS log permissions. An empty
   dashboard does not establish health.
8. After a fix, verify external GET checks, an approved synthetic enquiry, expected
   service revisions, metrics/log ingestion and sampled traces. Record recovery
   evidence in the incident ticket.

Initial thresholds (CPU 85%, connections 50, free memory 128 MiB, free storage 2 GiB)
are lab starting points. Tune the connection threshold against actual RDS capacity
and memory against observed workload. Attach the SNS subscriber and configure a
Prometheus alert receiver before relying on notifications.
