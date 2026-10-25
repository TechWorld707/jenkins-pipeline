# GitHub infrastructure approvals and Jenkins application releases

| System | Responsibility | Approval location |
| --- | --- | --- |
| GitHub Actions | Shared Terraform infrastructure | `terraform-shared` |
| GitHub Actions | Staging Terraform infrastructure | `terraform-staging` |
| GitHub Actions | Production Terraform infrastructure | `terraform-production` |
| Jenkins | Build, scan, publish, deploy the same images to staging and production | Jenkins release input prompts |

Bootstrap remote-state infrastructure stays separate. Neither workflow runs
`terraform destroy`. No infrastructure is recreated by editing these files.

## GitHub approval settings

Open **Settings > Environments** and check all three environments above:

1. Set **Required reviewers** to your authorised infrastructure reviewers.
2. Restrict deployment branches to **main**, with no tag rule.
3. Store `AWS_APPLY_ROLE_TO_ASSUME` inside EACH environment, containing that
   stack's apply-role ARN. Do not put this credential setting at repository scope.
4. Protect main with required pull-request reviews and CI checks.

Shared and staging were configured with reviewer `TechWorld707` and main-only
branch rules during this change; production already had a reviewer. Verify all
three before merging. Self-review is allowed for this single-user learning setup;
enable prevention of self-review when a second reviewer is available. Required
reviewer support depends on the GitHub plan and repository visibility.

The environment gates stop the apply jobs before they obtain AWS credentials.
The plan itself runs before approval. YAML alone does not create reviewer rules.

## AWS role requirements

Account: `671662643382`; region: `eu-west-2`; repository:
`TechWorld707/jenkins-pipeline`. Use OIDC temporary credentials.

Keep the plan role separate from deployment roles:

- Repository secret `AWS_ROLE_TO_ASSUME`: existing plan-role ARN.
- Repository variables `TF_PLAN_ENABLED=true`, `AWS_REGION=eu-west-2`.
- Plan role: read infrastructure/state and manage only the three exact `.tflock`
  objects in [the lock policy](iam/github-terraform-plan-backend-policy.json).
  This file is a proposed expanded policy; AWS currently has only the previously
  installed shared-lock permission. Install the reviewed update before planning
  staging/production. Do not give the plan role state-file writes or deployment permissions.
- Prefer a separate apply role per stack. Exact environment-bound OIDC trust
  templates are in `iam/github-terraform-{shared,staging,production}-apply-trust.json`.
  This repository uses immutable OIDC subjects with owner/repository IDs; keep them.
- Each apply role needs read/write access to its own state object, its lock, bucket
  listing for that prefix, and the infrastructure operations used by its root.
  Shared manages ECR, CodeBuild, reports, IAM/logging/KMS. Environment roles manage
  their own network, ECS, RDS, ALB, CloudFront, WAF, logs, KMS and application IAM
  roles. Limit PassRole to that stack's service roles. WAF/CloudFront also require
  their global/us-east-1 operations. Never grant control over the bootstrap bucket
  or GitHub deployment roles themselves.
- Existing `iam/github-terraform-apply-*.json` files contain historical proposals
  and supplemental legacy permissions. They are not a complete three-stack role
  installation. Have their resource scopes reviewed before use; do not assume
  that attaching old policies grants new environment permissions.
- If backend objects use customer KMS encryption, grant access to the actual state
  key as well. Do not reuse a deleted application key for backend encryption.

No AWS IAM role/policy changes are installed by this code change. Trust templates
alone do not create roles or permissions. The old apply-role trust allowed only
`terraform-production`; it cannot assume credentials from shared or staging gates.

## Enable environment planning after setup

Staging and production planning are opt-in during a clean installation. Until
repository variables `TF_STAGING_ENABLED` and `TF_PRODUCTION_ENABLED` are `true`,
the workflow shows a **Setup required** summary and runs no Terraform for that
environment. Shared planning remains controlled by `TF_PLAN_ENABLED`.

In **Settings > Secrets and variables > Actions**, configure the secrets below,
then add each environment's enable variable on the **Variables** tab with value
`true`. Enable staging first and production when it is ready. Explicitly selecting
a disabled stack in Run workflow also shows the setup summary; it does not bypass
this setting. Once enabled, missing secrets remain a failure and block apply.

## Private inputs for staging and production plans

Set these as **repository Actions secrets**, since plans run before the protected
apply job. Environment-only secrets cannot supply the unapproved plan job.
Trusted same-repository PRs may use the plan role and these inputs; fork PR plans
are excluded. Limit who can push branches, and protect workflow changes with review.

| Secret | Value |
| --- | --- |
| `TF_STAGING_ORIGIN_TOKEN` | Stable random 32–128 character staging origin token |
| `TF_PRODUCTION_ORIGIN_TOKEN` | Different stable production origin token |
| `TF_STAGING_IMAGES` | JSON map with `frontend` and `backend` ECR digest references |
| `TF_PRODUCTION_IMAGES` | JSON map with `frontend` and `backend` ECR digest references |

Example image map shape (use real digests from Jenkins `release.json`):

```json
{"frontend":"671662643382.dkr.ecr.eu-west-2.amazonaws.com/webtech-shared-frontend@sha256:REPLACE_WITH_64_HEX_DIGEST","backend":"671662643382.dkr.ecr.eu-west-2.amazonaws.com/webtech-shared-backend@sha256:REPLACE_WITH_64_HEX_DIGEST"}
```

Copy only the `images` object, not the whole manifest. Keep stable bootstrap
image inputs for future plans; ECS service `task_definition` ignores Terraform
changes so later applies do not roll back Jenkins application releases.
Do not commit tokens or local `.auto.tfvars.json` files. Saved binary plans can
contain secrets even when text reports redact them. Artifacts expire after one day;
restrict repository access accordingly.

## First deployment after teardown

The previous images were deleted. ECS creation needs existing application images:

1. Commit/merge these changes, configure roles and secrets above.
2. In **Actions > WebTech CI and security scans > Run workflow**, select **main**,
   stack **shared**. Read its plan artifact, then approve **terraform-shared**.
3. In Jenkins **webtech-pipeline > main > Build with Parameters**, check
   **BUILD_ONLY**. This builds/scans/publishes images and skips all deployment
   configuration checks and approval/deployment stages. Set CodeBuild/report
   names from the new shared outputs. Download `release.json` after success.
4. Set both image-map secrets using that scanned release. Set the two origin tokens.
5. Set `TF_STAGING_ENABLED=true`. Run the GitHub workflow for **staging**, review its plan and approve
   **terraform-staging**. Copy its new `jenkins_parameters` output to Jenkins.
6. Set `TF_PRODUCTION_ENABLED=true`. Run it for **production**, review its plan and approve **terraform-production**.
   Copy the new production outputs to Jenkins.
7. For later application changes, run Jenkins with **BUILD_ONLY unchecked** and
   both URLs/approver lists configured. Jenkins deploys to staging after approval,
   verifies it, then asks for production approval and promotes the same digests.
   Use a new application commit for a new image build: ECR tags are immutable.

Merges to main and same-repository PRs plan all three stacks. PRs never apply.
Manual runs can select one stack or all. The three roots are independently
planned/applied; selecting all does not sequence provisioning dependencies. Use
shared → initial image build → staging → production for a clean installation.
A missing private input fails that environment's plan; other matrix entries
continue. An infrastructure merge may also trigger Jenkins via webhook, so during
initial provisioning use a manual build-only run until the services exist.

## Review and approve a routine infrastructure change

1. Merge the reviewed change to main; open **Actions > WebTech CI and security scans**.
2. Open each **Terraform (stack) > Plan stack infrastructure** job. Read the
   workflow summary and download its `terraform-plan-STACK-ATTEMPT` artifact.
3. Check additions, changes, replacements and deletions for that stack.
4. Select **Review deployments**, tick only the reviewed environment(s), and choose
   **Approve and deploy**. GitHub runs the corresponding apply jobs.
5. Check the apply job summary and outputs. Jenkins approvals remain separate.

A no-change plan skips apply and needs no approval. Applies use the exact saved
binary plan from that run, downloaded by artifact ID. They verify stack/commit,
reject a superseded main commit, use committed provider locks and retain S3 locking.
Per-stack concurrency covers planning through approval/apply. Approve or reject
old waiting runs so newer runs can proceed. GitHub may replace an older pending
run when another is queued; it does not cancel the active approval/apply run.
For an expired/stale plan, run the workflow again and review the new plan. Do not
force-unlock a running operation or disable locking to bypass an error.
