# Dedicated project Prometheus

This is a separate local instance for WebTech production observability development.
It uses its own Compose project, network and persistent volume; it does not start
Grafana, Tempo, the application or any staging monitoring.

```bash
docker compose -f observability/prometheus/compose.yml up -d
```

- UI/query endpoint: http://127.0.0.1:19090
- Remote-write endpoint: http://127.0.0.1:19090/api/v1/write
- Readiness endpoint: http://127.0.0.1:19090/-/ready
- Retention: seven days or the 2 GB block limit, whichever is reached first.
- Storage: Compose volume `webtech-production-metrics_metrics-data`; retained on stop/down.

The local collector can reach the host endpoint using its configured host gateway,
or join this instance's Compose network and use `http://prometheus:9090/api/v1/write`.
Do not run the all-in-one `observability/compose.yml` stack on the same host port
at the same time. This instance is independent of that validation stack.

Application data arrives through the existing collector's remote-write exporter.
No additional FastAPI scrape endpoint is needed. The `up` metric initially shows
only Prometheus self-monitoring; it does not prove production is connected.

Production alert rules are mounted but disabled until production collection is
active and an alert receiver is configured. Enable them by changing `rule_files`
in `prometheus.yml` to `[/etc/prometheus/production-alerts.yml]`, validating with
`promtool check config`, then restarting this service. Configure Alertmanager
before relying on alert delivery.

This listener is loopback-only and has no ingestion authentication. AWS Fargate
cannot reach it directly. Production use requires durable reachable hosting and
an authenticated HTTPS ingestion endpoint before supplying it to Terraform.

```bash
docker compose -f observability/prometheus/compose.yml ps
docker compose -f observability/prometheus/compose.yml logs --tail=50 prometheus
docker compose -f observability/prometheus/compose.yml stop
```
