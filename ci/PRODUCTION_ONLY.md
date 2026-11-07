# Separate production-only Jenkins job

Use `Jenkinsfile.production` for a second job named `webtech-production-only`.
The original `Jenkinsfile` retains staging verification and both environment
approvals. This separate job deliberately has no staging deployment or evidence.

Flow: checkout main → validate settings → CodeBuild build/scan/publish (or reuse a
verified release for the same commit) → manual production approval → deploy and
verify production. Existing production deployment helpers provide health checks,
rollback evidence, autoscaling activation and telemetry.

## Create the job after these files are available on main

1. Jenkins → **New Item** → `webtech-production-only` → **Multibranch Pipeline**.
2. Add the same GitHub repository and credential used by `webtech-pipeline`.
3. Discover branches, include only `main`, and disable pull request discovery.
4. Under **Build Configuration**, set **Script Path** to `Jenkinsfile.production`.
5. For this manual job, enable **Suppress automatic SCM triggering** for all
   branches under branch properties (suppress both indexing and event-triggered
   builds). Do not add periodic build triggers. Save, scan once to discover main,
   then open its main branch job to build manually.
6. Before using this job, disable the original `webtech-pipeline` job through its
   UI so a webhook cannot start its staging-to-production flow. Its Jenkinsfile
   remains unchanged. Run only one production deployment job at a time:
   `disableConcurrentBuilds` serializes within a job, not across different jobs.
7. Configure **Build with Parameters** with shared CodeBuild/report outputs,
   `AWS_CREDENTIALS_ID=jenkins-aws`, production cluster/services and the **new**
   production HTTPS URL. Set `PRODUCTION_APPROVERS` to your actual authorised
   Jenkins user IDs/groups. Blank approvers fail closed. Restrict job configuration
   and parameter editing to trusted release operators.
8. Keep `PRODUCTION_OBSERVABILITY_ENABLED=false` until the new monitoring host and
   reviewed collector connection are ready. Then enable it for the approved
   application release. `BUILD_ONLY=true` publishes images without deployment.
9. Review archived scans and release digests, then approve **Deploy to production**.
   Approval expires after 30 minutes. Abort/timeout prevents deployment.

This job can use shared + production infrastructure without staging resources.
Creating these files does not create a live Jenkins job, publish them to GitHub,
apply Terraform or deploy the application. The Jenkins UI script path must point
to this file on main; do not paste it over the existing job's Jenkinsfile.

## Release checks

A separate readiness helper checks the manifest hash recorded after build, the
checked-out commit, immutable ECR tags/digests in the current account/region, and
archived scan JSON before approval and again before deployment. The production
manual approver and timestamp remain mandatory in the shared deployment helper.
A reused release uses archived scan results, not a fresh vulnerability database.
The existing staging promotion gate is not modified or bypassed in its job.

Production approval/result files and deployment/rollback telemetry are archived.
Infrastructure reviews and approvals remain separate from the application gate.

## Validation

Run `python3 -m unittest discover -s ci -p 'test_*.py'` with the repository's test
dependencies and `ruff check ci/production-only-ready.py ci/test_production_only_gate.py`.
A live Jenkins Declarative syntax check and job run require the restarted Jenkins
server and published files; those are not implied by Python tests.
