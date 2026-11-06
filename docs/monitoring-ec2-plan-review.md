# Beginner EC2 monitoring plan review

Prepared 2026-11-06 for account `671662643382`, London (`eu-west-2`).
This revision uses **t3.small: 2 vCPU, 2 GiB RAM**. The revised plan was approved and applied successfully: seven resources added,
zero changed and zero destroyed. The monitoring server is now running.

## What happened and what this plan changes

The previously approved t3.medium launch was rejected by AWS as not Free Tier
eligible for the current account. Twelve supporting resources were created before
that failure and remain in the separate monitoring Terraform state. AWS lists
t3.small as eligible; eligibility does not guarantee free usage.

**The new plan creates 7 resources, updates 0, and deletes 0.** It reuses all twelve
existing resources rather than recreating their storage or permissions:

| Remaining resource | Count | Purpose |
|---|---:|---|
| EC2 instance | 1 | Runs Prometheus, Tempo, Grafana and private HTTPS ingress |
| Existing data-volume attachment | 1 | Attaches the existing encrypted 20 GiB data disk |
| CloudWatch alarms | 5 | CPU, instance status, data disk, service readiness and TLS expiry |

The existing resources are the security group/two rules, private network interface,
20 GiB data disk, encryption key, secret metadata, log group, and EC2 IAM
role/profile/permission policy/SSM attachment. They can incur storage/key/secret
charges even while no server is running. No application release has been triggered.

## Smaller learning configuration

- Container RAM limits: Prometheus 384 MiB, Tempo 512 MiB, Grafana 384 MiB,
  Nginx 64 MiB; **1,344 MiB total**, leaving about 704 MiB for host services.
- A **2 GiB swap file** on the encrypted root disk cushions memory spikes. Each
  container also has a bounded RAM-plus-swap limit. Swap is slower than RAM.
- Prometheus Go memory target 300 MiB and query concurrency 2; Tempo Go memory
  target 384 MiB. Both Go processes use one scheduler CPU for this light workload.
- **20 GiB persistent data disk plus 20 GiB OS disk: 40 GiB provisioned total**.
  The swap file uses existing OS-disk space; it is not another disk.
- Three-day metrics/trace retention, 5 GB Prometheus block cap, and an 80% disk alarm.
- **No snapshots or backup roles**. Data volume retains `prevent_destroy`, which
  is protection against ordinary Terraform deletion, not a recovery backup.
- Private subnet; no public IP, SSH access or public Grafana ports. Backend ECS
  security group alone may ingest over HTTPS. Browser access uses an SSM tunnel.
- **No purchased TLS certificate/domain needed**: the host generates a private
  certificate and the collector pins/verifies it. There is no insecure TLS bypass.

This is intended for occasional learning requests and small dashboards. Sustained
traffic, large trace searches or many concurrent queries may exhaust resources;
monitor readiness and disk/memory metrics and increase capacity if needed.

## Cost

AWS Pricing API checked on 2026-11-06: Linux t3.small in London costs
**USD 0.0236/hour**, approximately **USD 17.23 for 730 hours of compute**.
Initial total budget is roughly **USD 25–40/month**, varying with usage and account
credits, for compute, 40 GiB gp3, one KMS key, a secret, alarms, custom metrics,
CloudWatch logs/queries and NAT processing. There is no snapshot charge from this
configuration. Existing application/NAT baseline, tax and discounts are excluded.
Stopping EC2 reduces compute costs; retained storage/key/secret/alarms still bill.

## Plan and validation

Separate Terraform root: `infra/terraform/monitoring`; state key:
`jenkins-pipeline/monitoring/terraform.tfstate` in the existing state bucket.

New saved binary plan: `/tmp/webtech-monitoring-small.tfplan`.
Readable complete plan: `/tmp/webtech-monitoring-small-plan.txt`.
Both are mode 0600. Saved binary SHA256:
`a23361ca501681834bb7e30d8b09893439665ee873f7dd754d60cda45e671dd9`. The previous `/tmp/webtech-monitoring-ec2.tfplan` is stale
following partial creation and must not be applied again.

Terraform validation, Compose rendering, bootstrap Bash/embedded Python syntax,
and the container-memory budget check passed. Checkov: **46 passed, 0 failed,
3 documented exceptions** (30-day logs, coordinated manual credential rotation,
five-minute native EC2 metrics instead of paid detailed metrics).

Earlier validation of unchanged components covered the exact pinned Tempo,
Nginx and collector configuration, four mocked ECS trust/approval/isolation tests,
and input-contract/promotion tests. The small-instance bootstrap ran with two corrected issues, documented below.
No end-to-end production application telemetry or image CVE scan is claimed complete.

## Next: production collector approval

The replacement monitoring plan was approved and applied. Do not reuse its saved
plan after this successful apply. A separate reviewed production plan must connect ECS
collector endpoints and secret/KMS access. Application releases still retain the
manual staging and production approvals. Publish the integration source before the next Jenkins release.

See the [full runbook](../observability/ec2/README.md) for permissions, SSM access,
TLS trust, validation and remaining alert receiver setup.

## Applied result and runtime verification

Instance: `i-042305efaf481f6fb` (`t3.small`), private IP `10.20.10.114`.
Data volume: `vol-0e41502c911cbb7f2` (20 GiB). All nineteen monitoring resources
now exist in the separate state; no application service or staging resource was
changed. No automated snapshots were created.

Bootstrap initially failed on the nonexistent `awscli2` package name; the selected
AMI already includes AWS CLI v2. The install command was corrected and resumed
on the same instance through SSM. Nginx worker access to the password hash/public
certificate was also corrected; the private key/plaintext credential file remain
root-only. The source bootstrap includes both fixes. Historical cloud-init status
still records the initial failure; the repair service completed and the actual
monitoring service is active. Do not rely on the historical cloud-init status
alone to assess current runtime health.

Verified from the running instance:

- Prometheus, Tempo, Grafana and Nginx containers are running.
- Grafana, Prometheus datasource, Tempo datasource and CloudWatch datasource
  health endpoints all return HTTP 200.
- HTTPS ingestion verifies the generated private certificate: invalid auth gives
  401; authenticated empty remote write reaches Prometheus and gives the expected
  400 payload error; an empty OTLP trace envelope is accepted with HTTP 200.
- Independent health probe reports 1 (healthy) and successfully publishes metrics.
- CloudWatch lists disk, memory, readiness and certificate-expiry metrics, plus
  container and bootstrap log streams in the central host log group.
- Root disk is approximately 31% used and data disk 3% at this initial check.
- SSM port forwarding to local 13000 returns Grafana health HTTP 200 from the laptop.
  The official Session Manager plugin was installed in `~/.local/bin`.

Open Grafana using `bash observability/ec2/open-grafana.sh`; then browse
http://127.0.0.1:13000. Username: `admin`. Retrieve only `grafana_admin_password`
from Secrets Manager secret `webtech-production-monitoring/credentials` in your
own secure terminal/console. Passwords have not been printed in this chat.

The bootstrap source repairs differ from the EC2's initially stored user-data.
Because `user_data_replace_on_change` is true, a future Terraform plan can propose
an instance replacement. Review that change deliberately; do not blindly rerun an
old saved plan or apply a replacement just to refresh bootstrap metadata. The data
volume and stable ENI are separate resources. There is no automatic monitoring
apply workflow.

Production application metrics/traces are **not yet connected**. A separate reviewed
production plan and the existing Jenkins approvals are still required for that
activation. The private-CA source and workflow settings must accompany the next Jenkins release.
