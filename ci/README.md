# Jenkins image build and promotion

Jenkins owns this delivery pipeline. GitHub's existing security workflow, including
SonarQube, remains unchanged. CodeBuild runs image scans with Trivy only.

## Setup before the first run

1. Use a Jenkins Multibranch Pipeline with this repository's Jenkinsfile and a
   GitHub Branch Source webhook. Enable builds of main only for deployment; the
   Jenkinsfile also gates every deployment stage on branch main. Jenkins must
   execute trusted code: restrict Jenkinsfile/buildspec edits and main merges.
2. Install Pipeline, Git, GitHub Branch Source, and Credentials Binding plugins.
   The Linux agent needs Git, Bash, Python 3, and AWS CLI. No Docker is needed on
   Jenkins; Docker runs in privileged CodeBuild. Configure a Jenkins secret-text
   credential `github-checks-token` with read access to repository Actions runs.
3. Give the Jenkins agent an AWS IAM role (or configure short-lived credentials
   outside this Jenkinsfile). Scope CodeBuild StartBuild, BatchGetBuilds, StopBuild
   to webtech-image-builder; allow GetObject for the report prefix and the ECS
   operations below. Do not place AWS keys in source files.
4. Apply the reviewed Terraform changes through the existing PR workflow. They
   supply AWS_ACCOUNT_ID and SCAN_REPORT_BUCKET to CodeBuild and allow its service
   role PutObject only under reports/ and DescribeImages on the two ECR repos.
   CodeBuild GitHub source authentication must already be configured for cloning.
5. Supply the Jenkins build parameters. REPORT_BUCKET defaults to the existing
   private ALB log bucket. Set separate STAGING_* and PRODUCTION_* ECS clusters,
   frontend/backend service names, and environment base URLs. Set
   PRODUCTION_APPROVERS to Jenkins user/group IDs authorised to approve production.
   Blank settings fail before starting CodeBuild.

Staging/production services are prerequisites: this change does not create them.
Each service must use ECS rolling deployments and a task definition containing a
container named frontend or backend, respectively. Configure an ECS deployment
circuit breaker with rollback, load-balancer health checks, nonzero desired count,
networking, execution permissions, and environment-specific database/secrets.
The environment URL must route / to the frontend and /healthz to backend health.
Frontend currently proxies /healthz to backend:8000; configure that DNS/service
connectivity in each environment. Production and staging must not share writable
application data or secrets.

The Jenkins IAM role needs DescribeServices, DescribeTaskDefinition,
RegisterTaskDefinition, UpdateService, and PassRole limited to the task/execution
roles used by those services (PassedToService ecs-tasks.amazonaws.com).
RegisterTaskDefinition needs wildcard resource where no revision exists yet;
limit other writes to the intended services. Pipeline creation does not install
Jenkins credentials or AWS policies. The existing Terraform apply role's
CodeBuild inline-policy management is used to install build-role permissions.

## Gates and report folder

Jenkins checks the exact checkout SHA against the successful main push run of
security-scan.yml, including any Terraform deployment approval in that run. It
waits up to 30 minutes, then fails closed. CodeBuild must resolve and check out the
same SHA, or it refuses to build.

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
that ECS did not roll back to an old task definition, then checks / and /healthz.
These are smoke tests, not full end-to-end tests. Production requires manual
approval and reuses the same manifest without rebuilding. Services are updated
sequentially; a partial deployment failure stops the pipeline and needs operator
review. Existing ECS circuit-breaker rollback is recommended; this script does
not promise an atomic two-service rollback.

Jenkins has an overall 120-minute timeout, CodeBuild waits up to 40 minutes, and
production approval expires after 30 minutes. Configure Jenkins permissions so
only trusted users can change job parameters or approve production. Do not
approve an older release after a newer release has been deployed by another job.

## Local verification

    bash -n ci/build-images.sh
    python3 ci/test_image_gate.py
    python3 -m compileall -q ci
    terraform fmt -check -recursive infra/terraform
    terraform -chdir=infra/terraform validate

The failure-path test uses fake Docker/AWS commands and verifies frontend failure,
backend failure, and scanner errors cannot reach any AWS upload or push stage.
An actual Jenkins/CodeBuild/ECS run is still required for end-to-end validation.
