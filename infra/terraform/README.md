# Terraform security settings

The network foundation uses eu-west-2a and eu-west-2b, disables automatic public
IPv4 assignment, denies all traffic through the default security group, and
records all VPC flows in a KMS-encrypted CloudWatch log group for 365 days.
Before changing the pinned zones in an existing deployment, review the plan for
subnet replacement.

The learning environment exposes the ALB over HTTP on port 80 using its AWS DNS
name, without a domain or ACM certificate. It forwards HTTP to private frontend
targets on port 8080. Resource-scoped Trivy and Checkov exceptions document this
intentional setup; use test data only. Enable HTTPS with a certificate before
using real credentials or sensitive data.

The bootstrap stack enables state-bucket access logging, EventBridge notifications,
a lifecycle rule to abort incomplete multipart uploads, and KMS encryption with
key rotation. Existing state versions are retained; changing default encryption
does not re-encrypt old objects. Backend users, including the CI role, need
kms:Encrypt, kms:Decrypt, and kms:GenerateDataKey on the state KMS key, alongside
their existing S3 permissions. Apply bootstrap changes before relying on these
settings in the application stack. New KMS keys and log storage incur AWS charges.

## Scoped Checkov exceptions

- CKV2_AWS_5 on the four application security groups: this checkout defines only
  network foundations. Remove each exception when adding its load balancer,
  frontend service, backend service, or database and attach the group there.
- CKV_AWS_144 on state and access-log buckets: this backend is single-region.
  Versioning protects prior state, but does not provide regional disaster
  recovery. Cross-region replication remains unimplemented and needs a replica
  bucket and replication role with appropriate KMS permissions.
- CKV_AWS_18 on the access-log destination: logging that bucket to itself would
  cause recursive logging.
- CKV_AWS_145 on the access-log destination: S3 server access-log delivery to S3
  requires SSE-S3 on the destination, per the
  [AWS documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html).

Trivy has the same resource-scoped exception for AVD-AWS-0132 on the access-log
bucket's encryption configuration in `bootstrap/logging.tf`. SSE-S3 remains
enabled; the state bucket continues to use its customer-managed KMS key. The
HIGH/CRITICAL scan gate remains enabled for all other findings.

EventBridge forwarding is enabled; add rules and consumers for any desired
alerting or automated responses.

## Local checks

```sh
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform/bootstrap validate
checkov -d infra/terraform --framework terraform
```

## GitHub plan review and approved apply

For console instructions, follow the [AWS role and GitHub setup guide](GITHUB_AWS_ROLE_SETUP.md).

The workflow plans `infra/terraform` after all CI checks pass. It runs on trusted
same-repository pull requests, main pushes, and manual runs. Fork pull requests
do not receive AWS credentials. The separate `bootstrap` stack is not applied
by this workflow; provision the backend and its access permissions first.

Configure these repository settings before enabling it:

1. Under **Settings > Environments**, create `terraform-production`. Configure
   **Required reviewers**, prevent self-review where appropriate, disable
   protection-rule bypass where available, and restrict deployment branches to
   `main`. An environment name in YAML alone does not require approval. Required
   reviewers availability depends on your GitHub plan and repository visibility;
   do not enable apply without an enforceable approval gate.
2. In that environment only, create secret `AWS_APPLY_ROLE_TO_ASSUME` containing
   the deployment role ARN. Its AWS OIDC trust must restrict the audience to
   `sts.amazonaws.com` and the subject to
   `repo:TechWorld707/jenkins-pipeline:environment:terraform-production`.
   Grant only the AWS write permissions needed by this stack, plus backend
   state, lock-file, and KMS permissions. Do not store this secret at repository
   level, and do not let the plan role assume the apply role.
3. Under **Settings > Secrets and variables > Actions**, set repository secret
   `AWS_ROLE_TO_ASSUME` to a separate plan role ARN. Give it resource-read
   permissions plus backend state/KMS read access and lock-file access; no
   infrastructure write access. Its OIDC trust should allow this repository's
   `pull_request` and `ref:refs/heads/main` subjects with audience
   `sts.amazonaws.com`. Only trusted collaborators should push branches in this
   repository: planning executes the submitted Terraform configuration.
4. Set repository variable `AWS_REGION=eu-west-2` and
   `TF_PLAN_ENABLED=true`. Manual deployment runs must select `main`.
5. Protect `main` with a ruleset requiring pull requests, approving reviews,
   dismissal of stale approvals, and successful CI checks including Terraform
   plan. Restrict bypasses and direct pushes. This enforces approval before merge;
   the workflow itself cannot enforce branch review rules.

Review a pull request under **Checks > Terraform plan > Details**, then open the
workflow summary or download `terraform-plan-report` for `terraform-plan.txt`.
Approve the PR after reviewing additions, updates, and deletions, then merge it.
The merge runs CI and creates a fresh plan against main and current AWS state.
Review this final report, then use **Actions > workflow run > Review deployments
> terraform-production > Approve and deploy**. The apply job uses the saved binary
plan from that same run; it does not generate an unreviewed replacement plan.
No-change plans do not request deployment approval. Apply jobs are serialized,
and a superseded main commit is rejected before applying. Terraform state locking
also prevents simultaneous state writes. If the saved plan becomes stale or its
one-day artifact expires, run the workflow again on main and review the new plan.

Plan artifacts can contain sensitive state values even when the text report
redacts them. Limit repository/Actions access and retain artifacts for one day.
GitHub report upload and AWS OIDC/apply require an actual configured workflow run
for end-to-end verification.
