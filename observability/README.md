# Production observability implementation

CloudWatch is the operational log store. Backend metrics use OTLP to a private
collector, then Prometheus remote write. Request/database spans use OTLP HTTP to
Tempo. Grafana reads all three. No staging exporters or monitoring resources are
enabled by these changes; existing release gates remain in place.

## Deployment map and ownership

The delivery path is GitHub checks/Terraform → Jenkins → shared CodeBuild/ECR →
manual staging gate and verification → manual production gate → production ECS.
The production request path is CloudFront/WAF → ALB → Nginx → FastAPI → PostgreSQL.
Terraform owns infrastructure and task templates; Jenkins owns active ECS service
revisions. The production task templates are published in the SSM String parameter
`/webtech-production/observability/task-templates`. An approved Jenkins deployment
reads those exact templates, sets release digests and commit SHA, and updates the
services. This avoids silently deploying an old task definition without a collector.

Existing ECS/CodeBuild/RDS/WAF/flow log groups are reused. ALB logs retain their
native S3 destination; forwarding ALB/CloudFront request logs into CloudWatch is
not part of this first implementation. Grafana dashboards are production only.

The initial live-state plans found no production/shared resources tracked for
update: they proposed full stack creation. Review `docs/observability-validation.md`
for the latest plan counts and verification results before proceeding.

## Required inputs before activation

1. Supply an authenticated HTTPS Prometheus **remote-write** endpoint (not the query
   URL) and Tempo **OTLP HTTP base** URL (without `/v1/traces`). AWS task egress
   currently allows HTTPS port 443 only. These must be reachable from private tasks
   through the existing NAT gateways.
2. Create a Secrets Manager JSON secret outside Terraform state containing
   `metrics_authorization` and `tempo_authorization`: complete HTTP Authorization
   header values. Use an AWS-managed Secrets Manager encryption key with this
   initial configuration; a customer-managed key also requires explicit scoped
   `kms:Decrypt` permission on the ECS execution role.
3. The default collector image is upstream OpenTelemetry Contrib `0.123.0`, pinned
   by immutable digest from its official GitHub registry mirror. It contains the
   validated remote-write and OTLP HTTP exporters. The image is configurable;
   check image security before release and validate any replacement distribution.
4. Set the following production-only Terraform object in a private tfvars file.
   These are illustrative endpoints/ARNs, not usable production inputs:

```hcl
production_telemetry = {
  metrics_url     = "https://metrics.example.invalid/api/v1/write"
  tempo_url       = "https://tempo.example.invalid"
  auth_secret_arn = "arn:aws:secretsmanager:eu-west-2:671662643382:secret:production-telemetry-REPLACE"
  # collector_image is optional; the default is the validated immutable digest.
}
monitoring_runtime_expected = false
```

Until this object is supplied, application exporters and the collector are
disabled. Plans without the object do **not** represent a complete telemetry rollout.
Never replace missing endpoints with public, unauthenticated lab listeners.

For GitHub-managed Terraform, set repository variable `PRODUCTION_TELEMETRY_JSON`
to the equivalent JSON object and `PRODUCTION_MONITORING_RUNTIME_EXPECTED` to
`false` initially. The reusable workflow writes a private production-only auto
tfvars file before planning; its reviewed saved plan retains those inputs for
apply. Keep local plan inputs consistent with these variables. Clearing the JSON
after activation would plan removal of collector resources and permissions.
Authorization header values belong only in Secrets Manager, never these variables.

## Review, apply and release sequence

Run Terraform formatting/validation, application/pipeline tests, collector `validate`,
Prometheus `promtool check rules`, and Nginx configuration checks. Generate saved
plans for production and shared infrastructure using the real private inputs.
Review costs, permissions and resource creation/replacement before any apply.
Saved plans contain sensitive values; keep them outside Git with restricted access.

After explicit approval, apply the reviewed infrastructure plans. Subscribe the
intended notification destination to the SNS topic returned by the production
`observability` output and confirm delivery. No subscription is created automatically.
Set Jenkins `PRODUCTION_OBSERVABILITY_ENABLED=true` only after the secret, templates
and log groups exist and permissions are attached. The flag enables shared build
events and production template use; it never bypasses either existing manual gate.
Release the application through the existing approved promotion flow.

Check collector logs and metrics/traces at the destination, then provision Grafana
using `grafana/provisioning/` and `grafana/dashboards/`. Supply separate query URLs
for `PROMETHEUS_QUERY_URL` and `TEMPO_QUERY_URL`; configure authentication for hosted
query backends in the deployment's secret-managed Grafana configuration. The sample
data sources assume local/internal backends without query authentication. Grafana's
CloudWatch source uses the default AWS credential chain, never hardcoded keys.
Set the dashboard's ALB/target-group suffix text variables from the production
`observability` Terraform output. The request-evidence table exposes `trace_id`
for lookup in Tempo Explore; automated bidirectional trace/log links remain a
Grafana correlation configuration step.

For deployment annotations, schedule `observability/sync-annotations.py` with
`GRAFANA_URL`, a secret `GRAFANA_TOKEN` authorised to write dashboard annotations,
and a writable `ANNOTATION_STATE` path. Its AWS role needs `logs:FilterLogEvents`
on the production pipeline event group. This uses Grafana's supported annotations
API; CloudWatch annotation queries themselves only support alarm history.

Schedule the external checker and delivery observer every minute on a persistent
host with independent uptime. Do not schedule them on an ephemeral Jenkins agent.
Protect their environment file; see `observer.env.example`. The observer polls
Jenkins build outcomes and GitHub production/shared job outcomes, omitting staging
jobs and raw console contents. Raw Jenkins/GitHub diagnostic logs remain at their
source; only their structured delivery records are centralised in this version.
This avoids copying unrestricted console output into CloudWatch. It does not yet
provide central full-text Jenkins/controller/GitHub logs.

```bash
python3 ci/production-functional-check.py --url https://YOUR-PRODUCTION-ORIGIN
python3 observability/observe-delivery.py
```

Run with `PRODUCTION_EVENT_LOG_GROUP=/webtech/production/pipeline-events` and a
scoped AWS identity so emitted records reach CloudWatch. Read checks are the safe
scheduled default. To verify a complete enquiry once, use `--submit-once
--cleanup-reference TICKET-OR-RUNBOOK`; this creates a synthetic record, so establish
an operator-approved SQL cleanup procedure before scheduling repeated writes.
There is no new public deletion endpoint.

Only after release, probes, observer and alert routing are healthy should a reviewed
plan set `monitoring_runtime_expected=true`. Until then runtime alarm actions are
disabled to respect intentionally idle services. The CodeBuild failure alarm is
independent of runtime state. Prometheus rules must likewise be enabled only when
production is expected to run. Prometheus needs an Alertmanager or equivalent rule
notification integration to deliver its alerts; the local validation stack does
not configure that notification destination.

## Signal and privacy choices

- FastAPI metrics cover route-template outcomes/durations, active requests and pool
  occupancy, acquisition duration, active acquisitions and timeouts. No public
  `/metrics` endpoint or second metrics scraping path is added. Built-in HTTP
  metric aggregation is dropped in favour of the custom canonical measurements.
- SQLAlchemy pool acquisition is measured around `_do_get`, including waiting
  before the checkout event. This boundary is covered by a real exhaustion test;
  keep that test when updating SQLAlchemy. Each worker has its own pool.
- Metrics carry a per-process instance ID so parallel tasks do not overwrite each
  other's cumulative series. Commit SHA stays in logs/traces, outside metric labels.
- Default production pool limit is two connections per process, zero overflow,
  five-second acquisition timeout. Budget for deployment surge: six backend tasks
  with 200% deployment capacity and one worker can demand 24 application connections,
  plus administrative/other clients and reserve. Verify the actual RDS limit.
- The collector is nonessential and uses 256 MiB inside the existing 1 GiB task
  allocation. This reduces application headroom; verify memory under realistic load.
  Queue/retry buffers are memory-only and bounded; they do not guarantee lossless
  delivery across task termination. Missing-metric and synthetic alarms expose gaps.
- JSON application logs omit exception messages, SQL text, request bodies and
  local variables. Sanitised stack frames retain file/function/line and error type.
  Uvicorn raw access logs are disabled in production. Trace exports allowlist safe
  attributes and drop exception events, URL/query data and SQL statement text.
- Nginx access logs use an allowlisted route and upstream timings, with backend
  trace ID and request ID. Production Nginx raw error logs are restricted to critical
  severity because ordinary error records can embed full URLs. Upstream failures
  remain visible through access status/timing records. Review rare critical records
  before broadening access to the log group.
- Production PostgreSQL disables statement/parameter/slow-statement logging and
  reduces verbose error details; locks still emit records. Use database metrics and
  sanitised query spans for performance diagnosis. Reassess privacy if adding SQL,
  constraints or database extensions that place user values in server messages.
- There is no migration job today: schema creation at startup emits start/success/
  failure records. A future migration stage must use the same event contract.
- Pipeline events contain identifiers and outcomes, never complete commands or
  arbitrary exception text. Failed scan evidence remains in native CodeBuild logs;
  failed builds still cannot publish a deployable release manifest.

## Permissions

Terraform adds a scoped CodeBuild `logs:CreateLogStream`/`logs:PutLogEvents` policy
for `/webtech/production/pipeline-events`. The production ECS execution role gains
`secretsmanager:GetSecretValue` only for the configured telemetry secret; it uses
existing log-delivery permissions. The ECS application task role needs no new
CloudWatch or backend access for HTTP export. The collector uses secret headers.

The Jenkins identity additionally needs `ssm:GetParameter` on the exact task-template
parameter plus log writes to the event group. Existing ECS describe/register/update,
PassRole and autoscaling permissions remain necessary. A sample additive policy is
in `permissions/jenkins-observability.json`; it is not attached automatically.

The external observer/probe identity needs log stream creation/writes to the event
group only. Jenkins observer credentials need read access to the selected job;
GitHub credentials need repository Actions read access. Neither should trigger or
approve deployments. Grafana needs scoped CloudWatch log reads and AWS metric
read/list APIs for production and relevant shared sources, including `us-east-1`
for CloudFront-scoped WAF. See `permissions/grafana-cloudwatch.json`.

Terraform apply permissions must cover the planned Logs groups/metric filters/
resource policy, EventBridge rules/targets, SNS topic, CloudWatch alarms/dashboard,
SSM parameter, task definitions and scoped role policies. Reconcile these against
the plan and existing apply-role policy before attaching permissions. No AWS role
permission policy has been attached by this implementation session.

## Cost model

The configuration adds 19 metric alarms (10 AWS metrics including two NAT gateways,
seven event/heartbeat alarms and two dead-letter queue alarms), seven custom metric
filters, one CloudWatch dashboard, two event/probe groups, two encrypted dead-letter
queues and an SNS topic. Native ECS/CodeBuild/RDS groups are reused;
collector logs add one group only when configured. Metric filters incur metric
charges when matching data is published; log queries charge for data scanned.
Configuring the collector also adds one collector-error metric filter and alarm.
Disabling alarm actions suppresses notifications, not alarm charges.
Container Insights and existing logs are existing baseline costs.

Use the AWS calculator for **eu-west-2**, and **us-east-1** where applicable:

`monthly monitoring = alarm count × alarm rate + active custom metrics × metric rate + ingested GB × ingestion rate + retained GB-month × storage rate + query GB × query rate + dashboard + SNS + backend hosting/storage/egress`

Example sizing for review: 730 hours/month, 2 backend collectors normally running
(up to 12 during surge), 1 GB/month additional logs, 30-day CloudWatch retention,
7-day local metric/trace retention and 10% production trace sampling. Collector CPU
is reserved within existing task size, so it does not alone increase billed task
size; pressure may cause more tasks or require larger task sizing. The Docker lab
uses existing host compute but still consumes disk/memory. Hosted backend prices
and log volume are unknown, so this is a sizing model, not a fixed dollar quote.

London list-price example, checked 1 November 2026: standard alarms $0.10/month,
first-tier custom metrics $0.30/month, Standard log ingestion $0.5985/GB, log storage
$0.0315/GB-month, and Logs Insights $0.0059/GB scanned. Assuming 20 alarms and all
eight custom metrics active for a full month, 1 GB additional ingestion, 1 GB-month
retention and 10 GB scanned, those components total **about $5.09/month**. With the
collector disabled, 19 alarms/seven metrics give **about $4.69/month**. These are
partial incremental estimates, before free-tier credits and tax, and exclude
dashboard/API, KMS requests, SNS/SQS, network, backend hosting and the whole application baseline.
Rates: [AWS London CloudWatch price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/eu-west-2/index.json).

Production event logs and SNS reuse the existing observability customer-managed KMS
key, adding no separate key-month charge. The key grants CloudWatch only the
notification operations needed by production alarms, and Logs only the production
log encryption context. Staging retains the original key policy. See
[AWS SNS key management](https://docs.aws.amazon.com/sns/latest/dg/sns-key-management.html).

The current saved plans recreate the application infrastructure, including NAT
gateways, ALB and Multi-AZ RDS; their baseline costs are separate and materially
larger than the observability additions. Confirm the full baseline budget before
applying. References: [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/),
[Fargate pricing](https://aws.amazon.com/fargate/pricing/),
[VPC/NAT pricing](https://aws.amazon.com/vpc/pricing/).

## Local validation backends

`compose.yml` provides Prometheus, Tempo, collector and Grafana with persistent
volumes and loopback-only published ports. Supply `GRAFANA_ADMIN_PASSWORD`, then
run `docker compose -f observability/compose.yml up -d`. Grafana is on local port
13000, Prometheus on 19090, Tempo on 13200 and OTLP HTTP ingestion on 14318.
For a local instrumented backend test set `OTEL_EXPORTER_OTLP_ENDPOINT` to
`http://127.0.0.1:14318`. This stack labels test traffic as production to exercise
the dashboards; never connect it to the real production alert route.

The Compose stack is a local test fixture, not internet-ready production hosting.
Authenticated TLS ingestion and a durable, reachable backend location still need
to be supplied before AWS collection can be activated.
