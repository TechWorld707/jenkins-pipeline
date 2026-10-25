# Shared, staging and production infrastructure

```text
infra/terraform/
├── bootstrap/                 # Protected remote-state bucket, logging and KMS
├── shared/                    # ECR, CodeBuild and scan report storage
├── modules/                   # Network, ECS, database, ingress and observability
├── environments/
│   ├── staging/               # Single-AZ DB, one task per service
│   └── production/            # Multi-AZ DB, two tasks per service
└── iam/                       # GitHub deployment role policy sources
```

The original application stack has been retired. Its database was deleted without
a final snapshot at the owner's request, along with its ECR images and report
bucket. Its old state history remains in the protected backend. Do not recreate
resources from old configuration or old saved plans.

## Current deployment status

The shared, staging and production resources were destroyed on 25 October 2026.
Bootstrap remote-state storage and local Jenkins were retained. Old application
URLs and image digests are no longer valid. Follow the [GitHub approval setup](GITHUB_AWS_ROLE_SETUP.md)
to provision the stacks again; obtain new URLs from the approved applies.

## Remote state

All active application roots use separate objects in the existing backend bucket:

- `jenkins-pipeline/shared/terraform.tfstate`
- `jenkins-pipeline/staging/terraform.tfstate`
- `jenkins-pipeline/production/terraform.tfstate`

Each root has its own backend.hcl and lock file. Bootstrap is a separate protected
stack and is not included in application teardown. Do not destroy or replace the
backend bucket, its encryption key or access-log bucket.

## Build and deployment order

Use GitHub Actions for reviewed infrastructure applies:

1. Run the security workflow on main for **shared**; review its plan and approve
   the `terraform-shared` deployment.
2. Run Jenkins with `BUILD_ONLY=true` to build, scan and publish initial images.
3. Supply stable private origin tokens and image-map secrets to GitHub Actions.
4. Run/review/approve **staging**, then **production** infrastructure in GitHub.
5. Copy the new infrastructure outputs to Jenkins. Normal Jenkins releases use
   `BUILD_ONLY=false` and separate staging/production application approvals.

The [setup guide](GITHUB_AWS_ROLE_SETUP.md) lists the exact settings and sequence.
For local inspection, use each root's state/output commands; deployment approvals
belong in GitHub Actions. Plans and state can contain secrets; keep them private.

## Jenkins settings

- CODEBUILD_PROJECT: `webtech-shared-image-builder`
- REPORT_BUCKET: `webtech-shared-reports-671662643382`
- AWS_CREDENTIALS_ID: `jenkins-aws`
- STAGING_URL: new staging `jenkins_parameters.url` output
- STAGING_* service/cluster settings: staging's `jenkins_parameters` output
- STAGING_APPROVERS: authorised Jenkins user IDs/groups
- PRODUCTION_*: production outputs and its authorised PRODUCTION_APPROVERS

Jenkins publishes scans and immutable images, then requests staging approval.
Approval records the user/time and deploys the same digests to staging. Once
staging verification succeeds, a separate production approval promotes that exact
manifest, without another build. Production approval and result records are archived
with the Jenkins build. Provisioning a fresh environment creates its
initial ECS services through Terraform; subsequent application releases use the
Jenkins approval flow. Do not rebuild an already-published SHA: ECR tags are
immutable. Reuse its release manifest when recovering a deployment-only failure.

Terraform ignores service task_definition changes so infrastructure applies do
not roll back Jenkins deployments. When changing task settings, coordinate an
explicit deployment of the new task revision. Service Connect supplies nginx's
`backend:8000` alias. Each Fargate task has 0.5 vCPU/1 GiB for the app and proxy.

## CI and permissions

GitHub Actions owns infrastructure plans and approved applies for **shared**,
**staging** and **production**. Each stack has its own saved plan, report,
concurrency group and protected GitHub environment. Jenkins owns image builds,
scans, publication and application releases, with separate staging/production
application approvals. Bootstrap remains outside these workflows.

See [GITHUB_AWS_ROLE_SETUP.md](GITHUB_AWS_ROLE_SETUP.md) for environment reviewers,
OIDC roles, private Terraform inputs and the first-deployment sequence. GitHub
approval settings and AWS permissions are separate from committing workflow YAML.
Existing historical IAM policies do not automatically authorise all three stacks.

## Operational notes

- Staging uses Single-AZ RDS and one NAT; production uses Multi-AZ RDS and one NAT
  per AZ. NAT, ALB, WAF, Fargate, RDS, logging and KMS incur ongoing charges.
- Both environments have separate databases, secrets, VPCs and origin tokens.
- RDS-managed password fields are injected by ECS. Restart tasks after rotation.
- Database TLS uses sslmode=require; certificate validation needs an RDS CA bundle
  and verify-full. Master credentials and startup table creation remain learning
  shortcuts; use an app DB role and migrations for a hardened production system.
- CloudFront-to-ALB HTTP remains the learning configuration. An origin domain and
  certificate are required for end-to-end HTTPS.
- ALB/RDS deletion protections remain enabled in the new environments. Review and
  disable them explicitly before future destruction; final DB snapshots are on.
- Resource-scoped scan exceptions cover intentional short retention, staging
  availability choices, cross-module relationships and outbound HTTPS through NAT.

## Local checks

```sh
terraform fmt -check -recursive infra/terraform
for root in bootstrap shared environments/staging environments/production; do
  terraform -chdir="infra/terraform/$root" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="infra/terraform/$root" validate
done
ruff check .
python3 -m unittest discover -s ci -p 'test_*.py'
```

## ECS service autoscaling

Frontend and backend scale independently on Fargate. Staging runs 1–2 tasks per
service; production runs 2–6. `desired_count` is the initial/minimum count and
`max_task_count` is the upper limit in each environment's `terraform.tfvars`.
CPU target tracking uses 60% and memory uses 70%, with a 60-second scale-out
cooldown and 300-second scale-in cooldown. Either policy can request scale-out;
both must permit scale-in. These are service-average metrics, not per-request
latency guarantees. The database does not scale through these policies.

Terraform preserves runtime `desired_count` changes so later infrastructure
applies do not undo autoscaling. Change the target's min/max inputs to adjust
capacity bounds. AWS manages the target-tracking CloudWatch alarms.

Before applying, the provisioning role needs Application Auto Scaling target and
policy management/read permissions, including RegisterScalableTarget,
DeregisterScalableTarget, PutScalingPolicy, DeleteScalingPolicy,
DescribeScalableTargets, DescribeScalingPolicies, DescribeScalingActivities and
ListTagsForResource, plus the scoped CloudWatch alarm permissions used by target
tracking. On first use, AWS may need permission to create the ECS Application
Auto Scaling service-linked role (`ecs.application-autoscaling.amazonaws.com`).
No live IAM permissions or resources are changed by these source files.
