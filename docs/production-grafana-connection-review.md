# Connect production to the private Grafana stack

Prepared 2026-11-06. Grafana already has healthy Prometheus, Tempo and CloudWatch
data sources. The remaining app path is production FastAPI → existing OTLP
collector sidecar → authenticated private HTTPS on `10.20.10.114` → Prometheus
metrics and Tempo traces. CloudWatch remains the central log store.

## Approved production Terraform plan

Saved plan: `/tmp/webtech-production-collector.tfplan`.
Readable plan: `/tmp/webtech-production-collector-plan.txt` (both mode 0600).

**7 adds, 1 update, 2 destroys**, consisting of:

- Replace the two Terraform-owned frontend/backend task-definition templates
  with revisions that include telemetry settings and the backend collector.
  These are template revisions, not running ECS task/service replacements.
  Before apply, Terraform owned revision 5 while running services used revision
  6. After the approved apply, templates are revision 7; running services remain
  at revision 6 with two tasks each.
- Add the collector CloudWatch log group, error metric filter and SNS alarm.
- Add a scoped execution-role policy to read the monitoring secret and decrypt
  its customer-managed key only through Secrets Manager.
- Add the SSM parameter holding exact Terraform-produced task-template ARNs.
- Update the existing ECS log key policy to permit the collector's log group.

**No ECS service update**, database change, new server, staging change, CloudFront
change or ALB change is proposed. The original local origin token was stale; it
was synchronized privately from the matching live CloudFront/ALB configuration
so this plan does not rotate it. No token/password was printed or committed.

The non-secret endpoints, secret ARN, KMS ARN and `use_private_ca: true` are stored
in the ignored local `observability.auto.tfvars.json`. Complete authorization
headers and the pinned public certificate stay in Secrets Manager. Neither
TLS verification nor authentication is bypassed. Runtime alarm actions stay
false until scheduled probes/observers are functioning; existing monitoring-host
alarms remain enabled independently.

Saved binary SHA256:
`8393887c0d7a6a09a91451f4654f2f78892261412bdf079be3a560e93cb22e28`.

## Application release is a separate approval

Applying this plan registers templates/permissions but deliberately preserves the
currently running service revisions. Use Jenkins `PRODUCTION_OBSERVABILITY_ENABLED`
for the next image release, preserving its manual staging and production approvals.
Do not update production services directly to bypass those gates. A new source
commit is needed for a new immutable image tag if the current SHA was already built.
The private-CA/KMS input support must also be committed before configuring those
inputs in GitHub's workflow, or a later plan could attempt to remove them.

Validate safe GET requests, application `webtech_*` metrics in Prometheus, sampled
trace IDs in Tempo, and correlated JSON request logs in CloudWatch. `up=1` alone
only proves self-scraping. An empty Grafana panel before this release is expected.

## Grafana work completed while awaiting plan approval

The production dashboard now has verified ALB and target-group suffix defaults,
so its CloudWatch panels no longer depend on manually filling blank variables.
Dashboard provisioning reload and its saved defaults were verified through the
Grafana API. Production deployment annotation sync is installed on EC2 and runs
every minute through systemd. It reads only structured deployment records from
CloudWatch and writes commit SHA/outcome annotations to the production dashboard.
The Grafana Editor service-account token is stored only on the encrypted host and
in the existing Secrets Manager record, never in repository settings or chat.
Revoke/rotate that service-account token in Grafana if access is no longer needed.

Annotation sync ran successfully; application deployment events will appear only
when the enabled delivery pipeline emits them. Synthetic checks and GitHub/Jenkins
observer scheduling are separate pending work, so runtime alarm actions stay off.
Publish the source changes and matching non-secret CI inputs before the next
Jenkins release so a future Terraform plan preserves this connection.

## Apply completed

The reviewed plan was approved and applied successfully: 7 additions, 1 key-policy
update, 2 retired template revisions. `/webtech-production/observability/task-templates`
now points to frontend/backend revision 7. Active production services were verified
unchanged at revision 6 with two running tasks each. Staging and the edge routing
configuration were untouched. The secret/KMS permissions and collector log/metric/
alarm resources are installed. The application exporter is not live until the
approved Jenkins release uses the new templates with observability enabled.

Final validation before source publication: 36 Python tests pass; repository-wide
Checkov reports 432 passed, 0 failed, 70 documented skips. An intentional delayed
import in the disposable-database validation script now has a targeted Ruff E402
annotation so the repository-wide lint gate can retain the required environment
setup order.
