# Recover a production observability apply denied by IAM

The GitHub apply log identifies `GitHubTerraformApplyRole` in account
`671662643382`. Its existing permissions do not cover the new production monitoring
resources. This is an IAM authorization failure; it does not establish whether
the application is running.

The supplemental [policy](github-terraform-production-observability-policy.json)
covers the configured production queues, topic, EventBridge rules, event and
collector log groups, metric filters, alarms, dashboard, and optional task-template
SSM parameter. Keep the existing production policies, including KMS and execution
role policy management. This supplement does not grant secret-value access,
subscription management, or Jenkins/Grafana runtime permissions.

An IAM administrator must review and install the supplement on the actual apply
role. Do not give the workflow permission to expand its own IAM permissions.
Check managed-policy attachment and policy-size quotas first. For a new managed
policy, run from the repository root using the administrator's AWS profile:

```bash
aws sts get-caller-identity
aws iam create-policy \
  --policy-name GitHubTerraformProductionObservability \
  --policy-document file://infra/terraform/iam/github-terraform-production-observability-policy.json
aws iam attach-role-policy \
  --role-name GitHubTerraformApplyRole \
  --policy-arn arn:aws:iam::671662643382:policy/GitHubTerraformProductionObservability
```

If that managed policy already exists, review and publish a new policy version
instead of creating it again. Confirm the account before making changes. These
commands are instructions for an administrator; they have not been executed.

Most permissions are scoped to production resource ARNs. Dashboard ARNs omit the
region. CloudWatch Logs account-level discovery and resource-policy operations
require `Resource: "*"`; their statement is limited to `eu-west-2`, but permits
managing account-level Logs delivery policies in that region. Review that scope
explicitly. Existing KMS key permissions and the key's CloudWatch/Logs service
policy are still required for encrypted delivery.

After IAM propagation, run a **new production Terraform plan** against the same
remote state. A failed apply can leave successfully created resources recorded in
state, or a resource may exist despite its create call reporting an error. Refresh
and inspect the new plan; investigate/import an existing resource only if it is
missing from state. Do not delete resources or state to retry.

Review the entire new plan and obtain the existing manual production approval
before applying. Do not reuse the previously saved plan or rerun its apply job:
it may be stale after partial creation. Keep staging excluded and preserve the
manual application deployment approvals. After the reviewed apply, verify alarm
notification delivery, event targets and DLQs, and collector health separately.

References: [CloudWatch authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_cloudwatch.html),
[CloudWatch Logs authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html).
