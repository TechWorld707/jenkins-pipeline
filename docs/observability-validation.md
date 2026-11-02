# Production observability review record

Date: 1 November 2026. Configuration implemented; no infrastructure applied and
no production release performed. Staging observability remains excluded.

## Validation completed

| Check | Result |
| --- | --- |
| Repository Ruff rules | Passed |
| Terraform Checkov security gate | 392 passed, zero failed, 67 skipped (existing suppressions plus documented retention/runtime/metadata exceptions) |
| Application/delivery unit and integration suite | 34 tests passed in isolated Python 3.10 environment |
| New telemetry tests in actual Python 3.12 application image | 7 tests passed |
| Disposable local PostgreSQL + FastAPI check | Database health HTTP 200 and enquiry HTTP 201; 22 spans received, including pool acquisition and database operations; metrics received |
| Request correlation and privacy | Response/log trace IDs present; test URL/customer values and SQL text absent from exported payloads |
| Mocked Terraform ECS tests | Three passed: idle launch boundary, production collector without automatic launch, and no staging collector |
| Terraform production/shared/staging configuration validation | Passed; final endpoint constraint additionally checked by mocked ECS tests |
| Terraform formatting and Git whitespace checks | Passed |
| Collector configuration | Upstream Contrib 0.123.0 validated file and Fargate `env:OTEL_CONFIG` loading; immutable image digest recorded in configuration |
| Nginx production configuration | `nginx -t` passed using existing frontend image |
| Prometheus alert rules | `promtool check rules` passed, three rules |
| Observability YAML/JSON, Bash and Python syntax | Passed |
| Jenkinsfile Groovy parsing | Passed using cached Jenkins image; full Jenkins runtime validation remains pending |

PostgreSQL validation used a temporary container with an in-memory data directory
and loopback-only port. It was stopped and automatically removed after validation.
No production request, database write, failure injection or deployment was used.

## Saved plans for review

| Stack | Managed actions | Saved plan |
| --- | --- | --- |
| Production | 123 creates, zero updates/deletes | `/tmp/webtech-production-observability.tfplan` |
| Shared | 17 creates, zero updates/deletes | `/tmp/webtech-shared-observability.tfplan` |

These are full stack creation plans, not small updates to a running application.
They include infrastructure baseline costs such as NAT, ALB and Multi-AZ RDS.
Terraform's tracked state did not provide existing application resources to update;
this was not a full audit of every AWS resource in the account.

The production plan has `collector_configured=false` and
`runtime_alarm_actions=false` because real production metric/trace endpoints and
an authentication secret ARN have not been provided. It must not be treated as a
complete metrics/tracing rollout plan. The saved plan includes the final encryption and endpoint-validation changes.
Regenerate it with the real backend inputs before any apply.

Plan files are private (mode 0600), contain potentially sensitive data and are
excluded from Git. Review locally with:

```bash
terraform -chdir=infra/terraform/environments/production show -no-color /tmp/webtech-production-observability.tfplan
terraform -chdir=infra/terraform/shared show -no-color /tmp/webtech-shared-observability.tfplan
```

Recorded SHA256 values:

```text
production 0b807c22b6b85fbfe902308cea9332f490baf8dd39b5e972b2abd27a3e12c1eb
shared     43b7e403e7f18a87b68dd959267a997eb3dbec3f4ae2a01f686c0141fe39b87b
```

AWS STS and package registries had intermittent TLS timeouts during validation;
successful results above were obtained after retries. No credential validation was
disabled. Do not substitute a failed refresh for a successful reviewed plan.

## Activation and live evidence still required

- Choose production backend hosting and supply authenticated HTTPS remote-write
  and Tempo OTLP HTTP URLs, plus the Secrets Manager ARN. Keep local/GitHub Terraform
  inputs consistent using the production repository variables documented in the guide.
- Review fresh plans with those real inputs, scoped IAM changes and the full stack
  budget. The guide includes an itemised partial CloudWatch cost estimate; external
  hosting and application baseline costs are not included in that estimate.
- After explicit apply approval, attach the additive Jenkins permissions, provision
  the alert subscriber and receiver, and enable the Jenkins production observability
  flag. Release only through the existing manual approval flow.
- Schedule the independent delivery observer, external functional checks and Grafana
  annotation sync with scoped credentials. These scripts were added but not installed
  as running services on a host. Do not depend on their heartbeats before scheduling.
- Confirm live Fargate → collector → Prometheus/Tempo export, CloudWatch native log/
  lifecycle delivery, dead-letter alarm routing, and Grafana queries/annotations.
  Hosted query authentication and bidirectional trace/log links need the chosen
  backend's configuration. Full-stack Grafana/Tempo UI operation was not exercised.
- Run the documented non-disruptive checks and drill fixtures, record evidence, then
  enable runtime alarm actions through another reviewed plan. Do not inject outages
  into production. Raw Jenkins/GitHub console log forwarding and Jira auto-creation
  are not implemented; structured delivery records and evidence links are available.

Implementation and permissions: [observability guide](../observability/README.md).
