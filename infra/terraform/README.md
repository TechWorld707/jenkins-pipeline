# Terraform security settings

The network foundation uses eu-west-2a and eu-west-2b, disables automatic public
IPv4 assignment, denies all traffic through the default security group, and
records all VPC flows in a KMS-encrypted CloudWatch log group for 365 days.
Before changing the pinned zones in an existing deployment, review the plan for
subnet replacement.

CloudFront is the public website entry point, using its default HTTPS domain.
HTTP viewer requests redirect to HTTPS. AWS WAF on CloudFront uses the AWS Common,
Known Bad Inputs, and Amazon IP Reputation managed rule groups. WAF has ongoing
charges; CloudFront uses PriceClass_100. Caching is disabled to avoid caching API
responses or user sessions; query strings, headers, and cookies reach the origin.

The ALB is an internet-facing origin on HTTP port 80, restricted to the CloudFront
origin-facing managed prefix list. Its default response is 403; a listener rule
forwards only requests with the shared X-Origin-Verify header. CloudFront-to-ALB
traffic remains unencrypted for this learning setup. Frontend targets use port
8080. The ALB WAF exception now documents upstream protection, not omitted WAF.

Before planning in GitHub, create repository Actions secret
`CLOUDFRONT_ORIGIN_TOKEN` with a random 32-128 character value consisting of letters,
digits, underscores, or hyphens (for example, generate with `openssl rand -hex 32`).
For local plans supply it as `TF_VAR_cloudfront_origin_token`. Do not commit it.
Terraform stores this value in state and saved plans; sensitive marking only
redacts normal CLI output. Rotate the value in both origin and listener via Terraform.

The plan role needs CloudFront/WAF read permissions and
`ec2:DescribeManagedPrefixLists`. The apply role also needs CloudFront distribution
management/tagging, WAFv2 Web ACL management/tagging and association permissions,
and ALB listener-rule management. CloudFront-scoped WAF uses the aliased AWS
provider in us-east-1; policies restricted to eu-west-2 must account for this.
These AWS IAM permissions have not been installed by this change.

After deployment, `terraform output -raw frontend_url` gives the website address.
Verify normal pages/API requests through CloudFront and that direct ALB requests
are denied. AWS managed rules may block legitimate application inputs; review WAF
metrics and sampled requests before adjusting rules. CloudFront access-log storage
and a second origin for failover are deferred and documented with scoped scan
exceptions. A custom domain and origin certificate are needed to enable origin
HTTPS; the default CloudFront viewer certificate does not encrypt the origin hop.

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

## Logging and scan corrections

ALB access logs go to a private, versioned SSE-S3 bucket with 30-day retention.
SSE-S3 is required for ALB log delivery. Resource-scoped exceptions document the
terminal log bucket's lack of recursive access logging, customer-managed KMS,
and cross-region replication. EventBridge notifications are enabled without
consumers. ALB and RDS deletion protection must be disabled in a reviewed apply
before destroying them; the log bucket must also be emptied of versions before
removal.

WAF uses explicit managed rule blocks, including Known Bad Inputs and Anonymous
IP List, so Checkov can verify the protections. Anonymous IP List can block VPN,
proxy, or hosting-provider traffic. WAF request logs go to CloudWatch in us-east-1
with 365-day retention; authorization, cookie, and origin-verification headers
are redacted in those logs. Sampled requests are separate and are not covered by
logging redaction. WAF logs use CloudWatch service encryption with a documented
customer-key exception. CloudFront sets index.html as its default root object
and attaches security response headers. The ALB redirect exception reflects
HTTPS termination at CloudFront, and the geography exception intentionally allows
worldwide viewers. The default CloudFront certificate remains intentional.

The new learning RDS instance is pinned to PostgreSQL 18.3 with a postgres18
parameter group. AWS's orderable-instance API confirmed Performance Insights,
enhanced monitoring, and IAM authentication support for db.t3.micro in eu-west-2.
Multi-AZ is enabled for failover practice, with one-day automated backup
retention for point-in-time recovery. Seven-day retention was rejected by the
account Free plan; one day is the minimum nonzero setting and still needs AWS
deployment verification for this account. Restore creates a separate database instance;
it does not rewind the existing database. Final snapshots remain disabled. Performance Insights
uses a customer-managed KMS key and seven-day retention; enhanced monitoring runs
at 60-second intervals. PostgreSQL and upgrade logs are exported to KMS-encrypted
CloudWatch groups with 365-day retention. Query logging records all statements;
it can capture sensitive SQL values, so use test data and review log volume.
The parameter group explicitly requires SSL. Application database connections
must support TLS (prefer sslmode=verify-full with the RDS CA bundle). Enabling IAM
authentication does not replace password authentication automatically.

These resources require additional deployment-role permissions for S3 logging
configuration, WAF logging/CloudWatch log delivery in us-east-1, KMS key creation
and use, RDS parameter groups, monitoring-role creation/attachment, and PassRole
limited to the RDS monitoring role. Permissions must be reviewed before the next
apply; this change does not install IAM policies or apply infrastructure. Logging,
monitoring, and KMS incur AWS usage charges.


## GitHub apply permissions

The apply role retains inline policy `TerraformApplyStackAccess` (the base
`iam/github-terraform-apply-policy.json`) and now has three supplemental managed
policies: `GitHubTerraformApplyRdsAccess`, `GitHubTerraformApplyEdgeAccess`, and
`GitHubTerraformApplyLoggingAccess`. Their source JSON files are in `iam/`.
They cover the RDS instance/subnet group, project ALB/listeners, CloudFront,
WAF and its log delivery, the ALB log bucket, and application logging key.
The KMS key must carry `Project=webtech-application-logs`; key management is
restricted by that tag. Commit the application-logging.tf tag before retrying.
CloudFront creates use wildcard resources where resource IDs do not yet exist;
updates use account-specific resource ARNs. Policies are split to respect IAM
policy size limits. These permissions were installed in AWS separately from
Terraform; changing JSON files alone does not update AWS IAM.
