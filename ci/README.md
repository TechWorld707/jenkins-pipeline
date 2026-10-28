# Jenkins image publication and approved environment promotion

Merge into main → GitHub webhook → Jenkins → CodeBuild build/scan/report/push
→ staging approval → staging deploy/tests → production approval → production deploy/tests.

GitHub CI runs independently; Jenkins does not wait for the whole workflow or its
Terraform approval. Require the desired CI checks before merge using main branch
protection. Production is promoted only after verified staging and a separate manual approval.

Need a Jenkins server first? Follow the [local Docker setup](../jenkins/README.md).

## Setup before the first run

1. Use a Jenkins Multibranch Pipeline with this repository's Jenkinsfile and a
   GitHub Branch Source webhook. Enable builds of main only for deployment; the
   Jenkinsfile also gates every deployment stage on branch main. Jenkins must
   execute trusted code: restrict Jenkinsfile/buildspec edits and main merges.
2. Install Pipeline, Git, GitHub Branch Source, and Credentials Binding plugins.
   The Linux agent needs Git, Bash, Python 3, and AWS CLI. No Docker is needed on
   Jenkins; Docker runs in privileged CodeBuild. Install Pipeline: Input Step for
   manual approval. No github-checks-token credential is required.
3. Give the Jenkins agent an AWS IAM role (or configure short-lived credentials
   outside this Jenkinsfile). Scope CodeBuild StartBuild, BatchGetBuilds, StopBuild
   to webtech-shared-image-builder; allow GetObject for the report prefix and the ECS
   operations below. Do not place AWS keys in source files.
4. Provision the shared and environment stacks using the reviewed plans described
   in the infrastructure setup guide below. The GitHub plan/apply workflow now
   targets shared infrastructure. The shared stack supplies CodeBuild
   AWS_ACCOUNT_ID and SCAN_REPORT_BUCKET and grants its scoped ECR/report access.
   Configure CodeBuild GitHub source authentication before the initial build.
5. Supply CODEBUILD_PROJECT and REPORT_BUCKET from the shared Terraform outputs.
   Supply STAGING_CLUSTER, STAGING_FRONTEND_SERVICE, STAGING_BACKEND_SERVICE and
   STAGING_URL from staging outputs. Set STAGING_APPROVERS to comma-separated
   Jenkins user IDs or group names allowed to approve deployment. Both environment settings
   are validated before image publication and checked again before approval. Blank approval settings fail closed.
   Restrict who can edit job parameters. Jenkins administrators can also approve.

## Webhook configuration

Use the Multibranch job's GitHub Branch Source with a name filter including only
`main`; disable PR discovery for this job. In GitHub Settings → Webhooks, configure
`https://<jenkins-host>/github-webhook/` with application/json and push events.
Configure matching webhook secrets in GitHub and Jenkins, keep SSL verification
enabled, and ensure GitHub can reach the endpoint. Reuse an automatically managed
hook if one already exists. Scan the Multibranch job once to discover main.
Branch Source handles subsequent hooks; a duplicate Jenkinsfile trigger is not
needed. Direct pushes also trigger builds, so protect main to require PR merges.
Repository changes do not configure the live webhook or Jenkins job.

## Approval and event tracking

Both environments are checked before image publication so missing approvers
or a missing URL do not leave a published SHA that must be rebuilt on retry.

Scan reports and release.json are archived immediately after successful ECR
publication. Open **Approve staging deployment** in the Jenkins build, review the
reports and image digests, then select **Deploy to staging** or **Abort**.
Approval expires after 30 minutes. Rejecting or timing out leaves the images in
ECR and does not deploy staging. After approval, Jenkins deploys the exact digests
and checks frontend, backend and database health. No images are rebuilt.

Artifacts record the events:
- `codebuild-id.txt`: CodeBuild identifier.
- `release.json`: commit and published image digests.
- `staging-approval.txt`: approver, UTC approval time, target and manifest.
- `staging-result.txt`: overall pipeline result and staging status.

Timestamped console logs also show the stages and approving user. Records follow
Jenkins artifact retention; these are not immutable external audit logs.
Concurrent builds are serialized, so approval pauses also delay queued builds.
Avoid competing staging deployments from other jobs during approval.

Staging/production services are provisioned by `infra/terraform/environments/`.
See [the infrastructure setup guide](../infra/terraform/README.md) for bootstrap
images, environment plans and Jenkins output values.
The ECS module creates separate frontend/backend services with rolling deployments,
circuit-breaker rollback, private networking and environment-specific credentials.
Service Connect supplies the backend:8000 alias used by nginx. The environment URL
routes / to the frontend, /healthz to backend health, and /api/health/db to a
PostgreSQL connectivity check. Production and staging must not share writable
application data or secrets.

The Jenkins IAM role needs DescribeServices, DescribeTaskDefinition,
RegisterTaskDefinition, UpdateService, and PassRole limited to the task/execution
roles used by those services (PassedToService ecs-tasks.amazonaws.com).
RegisterTaskDefinition needs wildcard resource where no revision exists yet;
limit other writes to the intended services. Pipeline creation does not install
Jenkins credentials or AWS policies. The proposed GitHub role policy updates target the new shared resources; their
installation in AWS remains pending explicit security approval.

## Gates and report folder

Jenkins passes its exact checkout SHA to CodeBuild. The build refuses to proceed
unless its resolved source and checkout match the requested commit. Jenkins also
checks the completed build and release manifest SHA before offering approval.

Both images are built first. Trivy scans frontend then backend for HIGH/CRITICAL
package vulnerabilities. A blocking finding or scanner error stops immediately.
The first failing image prevents subsequent scans. Neither image is pushed and
no S3 upload occurs on a scan failure; findings remain in CodeBuild logs. Local
JSON files on the temporary build host are not uploaded after failure. This
pipeline does not run a duplicate SonarQube scan.

Only after both scans pass are HTML/JSON reports uploaded:

    s3://<REPORT_BUCKET>/reports/<commit-sha>/<codebuild-run-uuid>/
      frontend-trivy.html
      frontend-trivy.json
      backend-trivy.html
      backend-trivy.json

That bucket's existing 30-day lifecycle also expires reports. Each image is then
pushed with its full commit SHA tag. A release.json manifest records the remote
ECR digests after BOTH pushes succeed. Jenkins downloads the manifest and reports
only after CodeBuild succeeds, and archives them as build artifacts. HTML files
can be downloaded and opened locally; HTML Publisher is not required.

Images use immutable ECR tags. Rebuilding a previously published SHA can fail on
push, rather than overwrite an existing image. A push/network failure can leave
one image published, but no deployment proceeds without a successful build and
complete release manifest. No failed-scan report is uploaded to S3; reports of
passing scans can exist if a later push/deployment fails.

Staging task definitions are copied from their existing environment-specific
services, changing only image digests. Jenkins waits for service stability, checks
that ECS did not roll back to an old task definition, then checks /, /healthz and /api/health/db.
These are smoke tests, not full end-to-end tests. Staging requires manual approval and uses the published manifest without
rebuilding. Production promotes the exact manifest verified in staging. Services are updated
sequentially; a partial deployment failure stops the pipeline and needs operator
review. Existing ECS circuit-breaker rollback is recommended; this script does
not promise an atomic two-service rollback.

Jenkins has an overall 180-minute timeout, CodeBuild waits up to 40 minutes, and
each environment approval expires after 30 minutes. Configure Jenkins permissions so
only trusted users can change job parameters or approve staging/production. Do not
approve an older release after a newer release has been deployed by another job.

## Local verification

    bash -n ci/build-images.sh
    python3 -m unittest discover -s ci -p 'test_*.py'
    python3 -m compileall -q ci
    terraform fmt -check -recursive infra/terraform
    terraform -chdir=infra/terraform/environments/staging validate

The failure-path test uses fake Docker/AWS commands and verifies frontend failure,
backend failure, and scanner errors cannot reach any AWS upload or push stage.
An actual Jenkins/CodeBuild/ECS run is still required for end-to-end validation.

## Jenkins AWS credential binding

Install the AWS Credentials plugin (included in `jenkins/plugins.txt`) and add an
**AWS Credentials** entry with ID `jenkins-aws` in the Jenkins credential store.
The AWS_CREDENTIALS_ID build parameter selects this entry. The Jenkinsfile binds
it only during CodeBuild and approved staging/production deployment; it checks the identity
with STS before each operation. Host AWS profiles are not automatically available
inside the container. See [local authentication setup](../jenkins/README.md#aws-authentication).


## Active shared build resources

Use CODEBUILD_PROJECT `webtech-shared-image-builder` and REPORT_BUCKET
`webtech-shared-reports-671662643382`. The old build project, ECR repositories and
report bucket have been deleted. Update saved Jenkins build parameters as well
as merging the Jenkinsfile defaults. Use staging Terraform outputs for its URL
and service settings. GitHub Terraform role policy updates remain pending
separate security approval; see the infrastructure guide.

## Production promotion

Set the following parameters before starting the pipeline. Defaults match the
currently deployed production infrastructure; PRODUCTION_APPROVERS is deliberately
blank and must contain authorised Jenkins user IDs or group names.

| Parameter | Default/value |
| --- | --- |
| PRODUCTION_CLUSTER | webtech-production |
| PRODUCTION_FRONTEND_SERVICE | webtech-production-frontend |
| PRODUCTION_BACKEND_SERVICE | webtech-production-backend |
| PRODUCTION_URL | https://d3ayob9ayz3pqq.cloudfront.net |
| PRODUCTION_APPROVERS | Your authorised Jenkins user/group IDs |

Both STAGING_APPROVERS and PRODUCTION_APPROVERS are required before image
publication. For this learning setup, the same user may approve both; Jenkins
administrators can approve regardless of the configured submitter list. Restrict
who may edit job parameters. Production must have a different configured cluster
and URL from staging.

After staging smoke tests succeed, Jenkins archives `staging-verification.txt`
with the tested release manifest's SHA256. Open **Paused for Input** for **Approve
production deployment**, review the scan reports and staging evidence, then choose
**Deploy to production** or **Abort**. Approval times out after 30 minutes. Abort
or timeout leaves staging deployed and skips production. No second CodeBuild
build or image push occurs during promotion.

The production gate requires staging status VERIFIED in this same run and checks
the release manifest's hash and commit before approval and again before deployment.
It rejects a changed manifest. Production copies its own current task definitions,
changing only image digests, preserving its database configuration, secrets,
roles and task settings. It waits for ECS and checks /, /healthz and /api/health/db.

Jenkins archives `production-approval.txt` (approver, UTC time, target and manifest)
and `production-result.txt` (status and pipeline result). Both environment result
files include the overall pipeline result: production rejection/failure can mark
the run aborted/failed while staging status remains VERIFIED. Approval artifacts
and scan reports are in Jenkins; only scan reports and release.json are uploaded
to S3 by the current pipeline.

The AWS credential must allow production ECS reads, task registration and service
updates, plus PassRole limited to production task/execution roles, as well as its
existing staging permissions. This code change does not modify AWS IAM policies.
Updates to two services are not atomic, and smoke-test failure does not itself
roll back both services. Keep competing deployers out of these environments while
approval is pending. Live production promotion must be verified after merge.


## Infrastructure and approved application deployment

Terraform provisions empty ECS Fargate services and suspended autoscaling. Jenkins
builds/scans/publishes image digests, waits for staging approval, deploys and tests
staging, then requests production approval to promote the same images. Scaling
activates after each environment passes verification. BUILD_ONLY publishes only.

See [the deployment flow](../ci/DEPLOYMENT_FLOW.md) for the exact sequence,
existing-service migration and the additional Jenkins autoscaling permissions.
Both environment configurations are required for a full run. No initial image
map is needed for Terraform. Use fresh infrastructure outputs for the URLs.
