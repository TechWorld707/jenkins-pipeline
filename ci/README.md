# Jenkins image publication and approved staging deployment

Merge into main → GitHub webhook → Jenkins → CodeBuild build/scan/report/push
→ manual staging approval → deploy the same image digests → smoke tests.

GitHub CI runs independently; Jenkins does not wait for the whole workflow or its
Terraform approval. Require the desired CI checks before merge using main branch
protection. This pipeline does not deploy production.

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
   in the infrastructure setup guide below. The existing GitHub plan/apply workflow
   still manages only legacy infrastructure. The shared stack supplies CodeBuild
   AWS_ACCOUNT_ID and SCAN_REPORT_BUCKET and grants its scoped ECR/report access.
   Configure CodeBuild GitHub source authentication before the initial build.
5. Supply CODEBUILD_PROJECT and REPORT_BUCKET from the shared Terraform outputs.
   Supply STAGING_CLUSTER, STAGING_FRONTEND_SERVICE, STAGING_BACKEND_SERVICE and
   STAGING_URL from staging outputs. Set STAGING_APPROVERS to comma-separated
   Jenkins user IDs or group names allowed to approve deployment. Staging settings
   are validated after image publication. Blank approval settings fail closed.
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
Jenkins credentials or AWS policies. Existing IAM policy JSON targets legacy resource names; update the deployment
roles for the new shared and environment resources before provisioning.

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
rebuilding. Production is outside this pipeline. Services are updated
sequentially; a partial deployment failure stops the pipeline and needs operator
review. Existing ECS circuit-breaker rollback is recommended; this script does
not promise an atomic two-service rollback.

Jenkins has an overall 120-minute timeout, CodeBuild waits up to 40 minutes, and
staging approval expires after 30 minutes. Configure Jenkins permissions so
only trusted users can change job parameters or approve staging. Do not
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
it only during CodeBuild and approved staging deployment; it checks the identity
with STS before each operation. Host AWS profiles are not automatically available
inside the container. See [local authentication setup](../jenkins/README.md#aws-authentication).
