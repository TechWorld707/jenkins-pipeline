# Staging and production infrastructure

```text
infra/terraform/
├── bootstrap/                 # Existing protected state bucket
├── shared/                    # Shared ECR, CodeBuild, reports and build IAM
├── modules/
│   ├── network/               # VPC, two AZs, subnets, NAT and routes
│   ├── ecs/                   # Cluster, services, initial tasks and IAM
│   ├── database/              # Private RDS and managed credentials
│   ├── ingress/               # ALB, CloudFront, WAF and access logs
│   └── observability/         # Encrypted VPC flow logs
├── environments/
│   ├── staging/               # One task/service, Single-AZ RDS, 14-day logs
│   └── production/            # Two tasks/service, Multi-AZ RDS, 30-day logs
└── legacy/                    # Existing stack, unchanged remote state key
```

## Existing deployment and state

The former root configuration is preserved in `legacy/`. Its S3 state key remains
`jenkins-pipeline/app/terraform.tfstate`; moving files does not move or replace
AWS resources. The existing GitHub approved plan/apply workflow now uses that
folder. It also validates every new root. It does not automatically deploy the
new stacks. Do not run Terraform from the former root: local `.terraform/` data
there refers to the old stack; run from `legacy/` after initialising it instead.

The new stacks have separate state keys and distinct resource names. They are
new parallel environments, not an automatic adoption of the old stack. No state
was read, edited or migrated by this refactor. Deploying them while retaining the
legacy stack incurs additional costs. Inventory the existing state with
`terraform -chdir=infra/terraform/legacy state list` after initialising it. If you
want to reuse existing resources, design and review imports/state transfers
before applying; never import one resource into two active states. Keep legacy
until the new environments have passed testing and a separate retirement plan
has been reviewed. ALB/RDS deletion protection remains enabled.

## Provisioning order

1. Keep the existing bootstrap backend. Update each `backend.hcl` for your account
   before using a different account. Backend and deployment roles require access
   to each new state prefix and its `.tflock`, and to the state encryption key.
2. Initialise and plan shared resources:

   ```sh
   terraform -chdir=infra/terraform/shared init -backend-config=backend.hcl
   terraform -chdir=infra/terraform/shared plan -out=tfplan
   # Review before running: terraform -chdir=infra/terraform/shared apply tfplan
   ```

3. Configure CodeBuild GitHub authentication and update AWS roles for the new
   `webtech-shared-*` resources. Existing IAM policy JSON under `iam/` targets
   legacy names and is not sufficient for the new stacks. The new infrastructure
   also needs ECS, Cloud Map, NAT/EIP, IAM/PassRole, RDS, logging and edge permissions.
   No account IAM policies or Jenkins credentials are installed by this change.
4. Run the shared image-builder at the desired commit to publish the initial
   scanned frontend/backend images. This first build is done before the first
   Jenkins deployment because ECS services do not exist yet. Read both immutable
   image references from its release manifest. Do not use `latest`.
5. For each environment, supply `TF_VAR_cloudfront_origin_token` with a different
   random 32–128 character token and `TF_VAR_images` as a JSON object containing
   `frontend` and `backend` ECR references ending in `@sha256:<64 hex digits>`.
   These inputs have no defaults. Never commit tokens, credentials or state.

   ```sh
   terraform -chdir=infra/terraform/environments/staging init -backend-config=backend.hcl
   terraform -chdir=infra/terraform/environments/staging plan -out=tfplan
   # Review before running: terraform -chdir=infra/terraform/environments/staging apply tfplan
   terraform -chdir=infra/terraform/environments/staging output -json jenkins_parameters
   ```

   Repeat for `production` using its folder and its own origin token. Save initial
   image inputs securely for subsequent plans. Saved plans and state contain
   sensitive data. Production should initially use a release already verified in
   staging. New infrastructure applies remain explicit reviewed operations.
6. Set Jenkins CODEBUILD_PROJECT and REPORT_BUCKET from shared outputs. Set
   STAGING_* and PRODUCTION_* from each environment's `jenkins_parameters` output.
   Restrict Jenkins PassRole to the task and execution role ARNs in those outputs.
   Keep the existing required production approver configuration.

## Application deployment ownership

Jenkins builds/scans once, deploys digest references to staging, checks `/`,
`/healthz` and `/api/health/db`, then requires approval before deploying the same
manifest to production. `ci/deploy.sh` wraps the existing Python deployment code;
`ci/smoke-test.sh <url>` can independently check an environment.

Terraform creates initial task definitions and services. Services ignore changes
to `task_definition` so infrastructure applies do not roll back Jenkins releases.
When changing container settings, secrets or task roles in Terraform, coordinate
an explicit service deployment to the updated task definition; a Terraform apply
alone will not switch a service to that revision. Keep task settings identical
across both services' definitions and the live definitions Jenkins copies.

Frontend and backend remain separate services. Service Connect provides the
`backend:8000` alias expected by nginx. Both services use 0.5 vCPU / 1 GiB task
sizes to leave room for its proxy; measure memory before reducing sizes. Tasks
are private and use NAT for ECR, Secrets Manager and CloudWatch. Staging has one
NAT; production has one per AZ. NAT gateways have ongoing charges even when idle.

RDS owns the password; ECS injects its username/password fields into the backend.
The app still accepts DATABASE_URL for local Compose. RDS connections require TLS;
`sslmode=require` encrypts connections but does not verify the server certificate.
For stronger identity verification, package the RDS CA bundle and use verify-full.
Secret rotation requires a task restart. Master credentials and create-on-startup
tables remain learning shortcuts; production should use an application DB role
and explicit database migrations. CloudFront-to-ALB HTTP remains the existing
learning setup; use an origin domain/certificate for end-to-end HTTPS.

## Verification

```sh
terraform fmt -check -recursive infra/terraform
for root in bootstrap legacy shared environments/staging environments/production; do
  terraform -chdir="infra/terraform/$root" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="infra/terraform/$root" validate
done
ruff check .
python3 -m unittest discover -s ci -p 'test_*.py'
bash -n ci/deploy.sh ci/smoke-test.sh ci/build-images.sh
```

Security scanners still inspect the entire Terraform tree. Resource-scoped
exceptions explain short learning log retention, staging Single-AZ and Insights
settings, and module connections scanners cannot follow. Private tasks permit
outbound TCP 443 via NAT for public AWS APIs; that egress has a scoped Trivy
exception. No unrestricted inbound access is enabled. Review findings from
new modules against the required policies; existing resource-scoped exceptions
are retained with the legacy implementation. No scan gates have been disabled.
