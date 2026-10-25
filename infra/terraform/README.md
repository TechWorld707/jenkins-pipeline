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

## Deployed environments

| Environment | Application URL | Service size | Database |
| --- | --- | --- | --- |
| Staging | https://d1d5yx6wu274gs.cloudfront.net | One task per service | Single-AZ |
| Production | https://d3ayob9ayz3pqq.cloudfront.net | Two tasks per service | Multi-AZ |

Both initial deployments use the scanned release from shared CodeBuild run
`554447aa-c576-467b-a2a2-5b8f61a0f395`, commit
`ef52fe93cfd9ae157d3d2271a31e82d648adb118`. Subsequent Jenkins releases update
staging independently. Get current infrastructure outputs from each root.

## Remote state

All active application roots use separate objects in the existing backend bucket:

- `jenkins-pipeline/shared/terraform.tfstate`
- `jenkins-pipeline/staging/terraform.tfstate`
- `jenkins-pipeline/production/terraform.tfstate`

Each root has its own backend.hcl and lock file. Bootstrap is a separate protected
stack and is not included in application teardown. Do not destroy or replace the
backend bucket, its encryption key or access-log bucket.

## Build and deployment order

1. Initialise shared with `terraform -chdir=infra/terraform/shared init -backend-config=backend.hcl`.
2. Review a shared plan and apply it. Its outputs provide CodeBuild, ECR URLs and
   the report bucket.
3. Build and scan the application once in `webtech-shared-image-builder`. Jenkins
   or an explicit bootstrap build supplies EXPECTED_COMMIT and sourceVersion as
   the same full Git commit SHA. The successful build publishes both images and
   a release.json containing immutable digest references.
4. Supply each environment with its own random cloudfront_origin_token and the
   release manifest's frontend/backend images. Local `*.auto.tfvars.json` files
   are git-ignored, mode 0600, and must not be committed. Retain these inputs for
   later plans. Remote/CI execution must receive the same inputs securely.
5. Initialise and review staging, apply its plan, wait for ECS stability and check
   `/`, `/healthz` and `/api/health/db` through its CloudFront URL.
6. Review/apply production with the same release only after staging verification.

```sh
terraform -chdir=infra/terraform/environments/staging init -backend-config=backend.hcl
terraform -chdir=infra/terraform/environments/staging plan -out=tfplan
# Review the plan before applying it.
terraform -chdir=infra/terraform/environments/staging apply tfplan
terraform -chdir=infra/terraform/environments/staging output -json jenkins_parameters
```

Use the production folder for production commands. Saved binary and JSON plans
can contain secret inputs; keep them private and outside Git.

## Jenkins settings

- CODEBUILD_PROJECT: `webtech-shared-image-builder`
- REPORT_BUCKET: `webtech-shared-reports-671662643382`
- AWS_CREDENTIALS_ID: `jenkins-aws`
- STAGING_URL: `https://d1d5yx6wu274gs.cloudfront.net`
- STAGING_* service/cluster settings: staging's `jenkins_parameters` output
- STAGING_APPROVERS: authorised Jenkins user IDs/groups

Jenkins publishes scans and immutable images, then requests staging approval.
Approval records the user/time and deploys the same digests. Production deployment
is outside that Jenkins pipeline. Provisioning a fresh environment creates its
initial ECS services through Terraform; subsequent application releases use the
Jenkins approval flow. Do not rebuild an already-published SHA: ECR tags are
immutable. Reuse its release manifest when recovering a deployment-only failure.

Terraform ignores service task_definition changes so infrastructure applies do
not roll back Jenkins deployments. When changing task settings, coordinate an
explicit deployment of the new task revision. Service Connect supplies nginx's
`backend:8000` alias. Each Fargate task has 0.5 vCPU/1 GiB for the app and proxy.

## CI and permissions

The GitHub security workflow validates bootstrap, shared, staging and production.
Its approved Terraform plan/apply jobs target **shared** only; environment changes
require separate reviewed plans with their private inputs. The existing protected
`terraform-production` GitHub environment remains the approval gate for that shared
apply job; its name does not mean the production application is applied there.

The plan role now has GetObject/PutObject/DeleteObject access to the shared state
lock only, replacing its retired app-lock permission. IAM simulation confirms
that access. The broader apply-role policy changes in `iam/` remain proposals:
automatic approval review rejected their installation because they change access
across state prefixes/resources. They need explicit review before the GitHub
apply job can manage the new shared infrastructure. Application deployment via
the current provisioning identity is independent of that blocked role update.
Old edge/RDS policy sources in `iam/` describe previous supplemental permissions;
they do not grant the new environment deployment permissions automatically.

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
