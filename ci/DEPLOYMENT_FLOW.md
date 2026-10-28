# Infrastructure approval and application approval are separate

GitHub Actions provisions shared/staging/production infrastructure after each
stack's plan review and approval. Terraform creates empty ECS Fargate services:
desired count zero, an intentionally unpullable placeholder task image and
suspended autoscaling with minimum zero. No application images or image-map
secrets are needed for these Terraform plans. Database, NAT, ALB and other
infrastructure still run and incur charges while the application services are idle.
The website returns an error until the first approved application deployment.

Jenkins performs this release sequence:

1. Check out the exact main commit and validate both environments' configuration.
2. Ask CodeBuild to build and scan frontend and backend, then publish passing
   reports, immutable ECR images and release.json. A blocking scan stops publication.
3. Archive the scan reports and release manifest before requesting staging approval.
4. Wait for the configured Jenkins staging approver; record identity/time.
5. Validate BOTH ECS services and capacity metadata before mutation. Register both
   new task revisions containing the release digests; update services. If a service
   is idle, start its configured minimum task count. Later releases preserve the
   current desired count, including extra tasks launched by autoscaling.
6. Wait for ECS stability; detect rollback; test /, /healthz and /api/health/db.
7. Only after those checks pass, set autoscaling minimum to the configured release
   minimum and resume scaling. A failed first release never enables autoscaling;
   its attempted tasks may remain running after failure for investigation.
8. Bind production approval to the SAME unchanged release manifest and successful
   staging evidence. Record production approver/time separately.
9. Deploy and verify the same digests in production, then activate its autoscaling.
   Production is never rebuilt during promotion.

AWS ECS Service Auto Scaling adds/removes Fargate tasks as service-average CPU or
memory demand changes. It is not an EC2 Auto Scaling Group. Staging defaults to
1–2 tasks per service after approval and production 2–6, targeting CPU 60% and
memory 70%, with 60-second scale-out and 300-second scale-in cooldowns. During
rolling deployments ECS can temporarily exceed the service scaling maximum under
its deployment surge settings. The database has separate capacity limits.

Terraform owns max capacity and the ReleaseMinCapacity target tag, derived from
`desired_count` in terraform.tfvars. Jenkins reads that tag for activation. Terraform
ignores live service desired counts, live service task revisions, activated minimum
capacity and suspension state, so later infrastructure applies preserve releases.
Changes to the runtime minimum tag take effect at the next approved Jenkins release.
Changing maximum capacity during an infrastructure apply can affect existing
running capacity; review it accordingly. Recreating a scalable target returns it
to the initial zero/suspended state and requires another approved Jenkins release.

## Fresh installation

1. Configure GitHub OIDC roles, state permissions and three protected environments.
2. Review/approve shared infrastructure in GitHub. Review/approve staging and
   production infrastructure with their own origin tokens. No image build is
   required before creating these empty services.
3. Read each root's `jenkins_parameters` Terraform output. Configure Jenkins with
   CodeBuild/report names, both clusters/services/URLs and both approver lists.
4. Run Jenkins with BUILD_ONLY unchecked. A reachable webhook can trigger it on
   pushes to main; local-only Jenkins requires a manual build or a configured
   reachable HTTPS endpoint. GitHub workflow completion does not start Jenkins.
5. Review scan reports, approve staging, verify staging, then approve production.

BUILD_ONLY remains optional: it publishes images and reports but skips all
application approvals/deployments and does not activate scaling. Never rebuild
an already-published SHA in immutable ECR repositories; use a new source commit
for a normal fresh build. Terraform infrastructure approvals do not replace
Jenkins application approvals, and a Jenkins build-only run deploys nothing.

## Existing deployment migration

These edits do not stop an already-running application. No live Terraform apply,
IAM update or ECS mutation was performed while preparing this change. Review a
fresh infrastructure plan before applying. Existing service desired counts,
service task definitions and active autoscaling state are preserved. Applying
adds ReleaseMinCapacity metadata required by the new deployment script and may
replace Terraform-owned bootstrap task definitions; review revision changes.
Wait for that apply before running the updated Jenkins deployment code.

If you want a fresh zero-task launch demonstration, use the new code when you
provision fresh environments; do not assume merging it stops existing services.
Do not delete databases, state or running resources merely to test this flow.

Remove obsolete TF_STAGING_IMAGES/TF_PRODUCTION_IMAGES repository secrets and the
`images` key from any local *.auto.tfvars.json inputs; Terraform no longer reads
image maps. Keep the origin-token secrets. Update environment enable variables
once their origin tokens and roles are ready. Both environment configurations
are currently required for a full Jenkins run; BUILD_ONLY bypasses those checks.

## Jenkins IAM addition

Jenkins already needs its CodeBuild, S3 report, ECS task/service and exact PassRole
permissions. It now also reads scalable targets/tags and updates existing ECS
scalable targets after verification. Review and manually attach
`infra/terraform/iam/jenkins-release-autoscaling-policy.json` to the Jenkins
identity if it lacks those operations. This policy addition is not installed by
these files. RegisterScalableTarget can change capacity; it is limited to ECS
DesiredCount, this region/account and the project's existing tagged targets.
Do not attach it to the CodeBuild image-builder role. The API permission is held
by the Jenkins identity; approval is enforced in the reviewed Jenkins pipeline,
not by IAM cryptographically recognising a Jenkins approval.

## Verification

Python unit tests mock AWS/network calls and cover absent approval, both-service
preflight, idle activation, preserved running capacity and blocked scaling after
failed health checks. Terraform native tests mock AWS and assert zero desired
counts, zero scaling minima, suspended scaling and placeholder images. These
checks do not exercise a live deployment. Validate a real approved release after
merging and applying the reviewed infrastructure changes.
