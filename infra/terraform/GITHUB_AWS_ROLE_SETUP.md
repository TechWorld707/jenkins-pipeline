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

Set repository Actions secrets `TF_STAGING_ORIGIN_TOKEN` and
`TF_PRODUCTION_ORIGIN_TOKEN` to separate stable random 32–128 character values.
Plans run before protected apply jobs, so environment-only secrets cannot supply
these inputs. Trusted same-repository PRs may use plan inputs; fork plans are excluded.
Protect branch/workflow writes and reviewers accordingly.

Image-map secrets are no longer used. Terraform creates zero-task ECS scaffolding
with an intentionally unpullable placeholder image and suspended autoscaling.
Jenkins chooses and deploys application image digests after approval. Remove obsolete
TF_STAGING_IMAGES/TF_PRODUCTION_IMAGES secrets and local `images` tfvars entries.
Saved plans still contain origin tokens; restrict artifact access (one-day retention).

## First deployment after teardown

1. Merge the code and configure GitHub roles, origin-token secrets and reviewers.
2. Run the workflow on main for shared; review and approve terraform-shared.
3. Enable staging/production via TF_STAGING_ENABLED / TF_PRODUCTION_ENABLED=true.
   Run, review and approve their infrastructure plans separately. Services start
   with zero tasks and autoscaling suspended; these applies do not launch the app.
4. Copy infrastructure outputs into Jenkins parameters for both environments.
5. Run Jenkins with BUILD_ONLY unchecked. Jenkins builds/scans/publishes images,
   then waits for staging application approval before starting staging tasks.
6. Jenkins verifies staging before requesting production approval; it deploys the
   same image digests there, then enables that environment's autoscaling after checks.

Full ownership, migration and Jenkins permissions:
[ci/DEPLOYMENT_FLOW.md](../../ci/DEPLOYMENT_FLOW.md). BUILD_ONLY is an optional
publication-only mode, not a provisioning prerequisite. Enabled stacks plan in
parallel; applying one does not automatically wait for the other stack. A main
push webhook may also trigger Jenkins, which needs both environments provisioned
and configured. GitHub completion does not automatically start local Jenkins.

## Review and approve a routine infrastructure change

1. Merge the reviewed change to main; open **Actions > WebTech CI and security scans**.
2. Open each **shared/staging/production infrastructure > Plan stack infrastructure** job. Read the
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

## Workflow graph

The workflow uses three explicitly named branches instead of a collapsed matrix:

- shared infrastructure → Plan shared infrastructure → Approve and apply shared infrastructure
- staging infrastructure → Plan staging infrastructure → Approve and apply staging infrastructure
- production infrastructure → Plan production infrastructure → Approve and apply production infrastructure

Expand each reusable workflow branch to view its jobs. Each plan has a separate
artifact and each changed main-branch plan has its own protected apply approval.
A disabled environment displays Setup required instead of running a plan; enable
its repository variable after providing its origin token. No-change plans skip
apply, and pull requests never apply.

## Credentials could not be loaded

If `configure-aws-credentials` reports that no credential providers are available,
check the role ARN input first. The plan job reads repository secret
`AWS_ROLE_TO_ASSUME`; each apply job reads `AWS_APPLY_ROLE_TO_ASSUME` from its own
protected environment. A production environment secret is unavailable to shared
or staging jobs. The workflow now checks missing role settings before authentication.

For a shared apply, open Settings > Environments > terraform-shared > Environment
secrets and add `AWS_APPLY_ROLE_TO_ASSUME` with the shared apply-role ARN. The
role must already exist and trust the exact `terraform-shared` OIDC subject from
the shared trust template. Adding the ARN does not create the AWS role, update
its trust, or grant permissions. Repeat for staging when enabling that stack.
Do not copy the production role ARN unless that role has explicitly reviewed
trust and permissions for the other environment. An STS AccessDenied after this
setting is supplied indicates a separate trust/permission issue.
