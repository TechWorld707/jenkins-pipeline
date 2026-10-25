# Local Jenkins for this learning pipeline

Jenkins runs at http://localhost:8081 using the official LTS Java 21 image.
The container includes Git, Python 3, AWS CLI and the pipeline/GitHub plugins.
Docker builds run remotely in CodeBuild; Jenkins has no host Docker socket or
privileged mode. The Jenkins data directory uses a persistent named volume.

## Start and unlock

From the repository root:

```sh
docker compose -f jenkins/compose.yml up -d --build
docker compose -f jenkins/compose.yml ps
```

Open http://localhost:8081. Retrieve the unlock password in your own terminal:

```sh
docker compose -f jenkins/compose.yml exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Paste it into **Unlock Jenkins**. Complete the setup wizard, create your own
administrator account and set the Jenkins URL to http://localhost:8081/ for now.
The required project plugins are already baked into the image. You may install
suggested plugins in the wizard too. Do not paste passwords or AWS credentials
into this repository or chat.

## Create the Multibranch Pipeline job

1. From the dashboard choose **New Item** → name `webtech-pipeline` →
   **Multibranch Pipeline** → **OK**.
2. Under **Branch Sources**, select **Add source → GitHub**. Use owner
   `TechWorld707` and repository `jenkins-pipeline`. Configure repository-read
   credentials if required for private access or GitHub API rate limits.
3. Enable branch discovery; disable pull-request discovery for this deployment
   job. Add **Filter by name (with wildcards)** and set **Includes** to `main`.
4. Under **Build Configuration**, use **by Jenkinsfile**, script path `Jenkinsfile`.
5. Configure AWS authentication and permissions before scanning the job to avoid
   triggering a build that cannot access CodeBuild. Then save and select
   **Scan Multibranch Pipeline Now**. Open the resulting **main** job.
6. Configure the main job's parameters before the first full deployment run:
   CODEBUILD_PROJECT, REPORT_BUCKET, STAGING_CLUSTER, STAGING_FRONTEND_SERVICE,
   STAGING_BACKEND_SERVICE, STAGING_URL, STAGING_APPROVERS and corresponding
   PRODUCTION_* parameters. Both approver values are authorised Jenkins user IDs
   or groups. Some parameters appear only after Jenkins first loads the Jenkinsfile.
   Missing environment settings stop validation before image publication.

See [pipeline setup](../ci/README.md) for exact values, scoped IAM permissions,
scan reports, approval behaviour and deployment tracking.

## AWS authentication

The image includes the AWS Credentials plugin. Create a dedicated, scoped IAM
credential for this pipeline. In Jenkins go to **Manage Jenkins → Credentials →
System → Global credentials → Add Credentials**. Select **AWS Credentials**, set
ID `jenkins-aws`, and enter the access key ID and secret access key there. Keep
these values out of source control and chat. If using the plugin's Assume Role
setting, configure the target role and trust policy as well.

The Jenkinsfile uses AWS_CREDENTIALS_ID (default `jenkins-aws`) to bind credentials
only around CodeBuild and staging/production deployment operations. Approval does not hold
an AWS credential binding open. STS GetCallerIdentity verifies the bound identity
at the start of each AWS stage; it never prints the keys.

The local controller does not inherit host AWS profiles or an EC2 instance role.
A plain `docker compose exec jenkins aws sts get-caller-identity` therefore still
has no credentials: bindings exist only within the job's withCredentials block.
No host AWS files are mounted into the container.

The pipeline credential needs CodeBuild StartBuild/BatchGetBuilds/StopBuild for
the selected project, S3 report reads and staging/production ECS deployment
permissions plus PassRole restricted to both environments' task/execution roles. The CodeBuild service
role, not this Jenkins identity, performs the Docker builds, scans and ECR pushes.
Avoid using root or administrator credentials. Rotate stored access keys; for
hosted Jenkins prefer role-based short-lived authentication. The required AWS
resources must exist before the pipeline can use them.

After committing and merging the Jenkinsfile changes, reload the main job so it
reads the credential binding and AWS_CREDENTIALS_ID parameter.

## GitHub webhooks

GitHub cannot deliver webhooks to localhost. The container is intentionally bound
to loopback. For local learning, scan/build the job manually until a reachable
HTTPS endpoint is configured through a tunnel or a hosted Jenkins deployment.
Then configure the Jenkins root URL, the GitHub webhook URL ending in
`/github-webhook/`, and matching webhook secrets as described in the CI guide.
Starting this container alone does not activate the webhook.

## Maintenance

```sh
# Status and recent logs (initial startup logs can contain the unlock password)
docker compose -f jenkins/compose.yml ps
docker compose -f jenkins/compose.yml logs --tail=50 jenkins

# Stop while retaining Jenkins users, jobs and artifacts
docker compose -f jenkins/compose.yml down

# Rebuild to pick up base image/plugin updates
docker compose -f jenkins/compose.yml build --pull
docker compose -f jenkins/compose.yml up -d
```

Do not use `down -v` unless you intend to delete Jenkins data. Back up the named
volume before upgrades. This learning setup executes trusted pipeline code on
the controller; a hosted team setup should use separate build agents.
