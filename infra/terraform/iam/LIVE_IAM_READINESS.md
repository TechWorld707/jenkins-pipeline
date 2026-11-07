# Live IAM preparation — 28 October 2026

The following permission changes were installed at the user's explicit request.
No Terraform plan/apply, image build, ECS service update or application
infrastructure creation was performed during this IAM preparation.

| Identity | Preparation |
| --- | --- |
| GitHubTerraformPlanRole | Existing shared/staging locks retained; exact production lock access added |
| GitHubTerraformSharedApplyRole | Existing shared trust/backend/resource policies retained |
| GitHubTerraformStagingApplyRole | Existing five policies retained; scaling Describe APIs moved to regional read scope |
| GitHubTerraformApplyRole | Production-only trust retained; production backend inline policy and five production resource policies added |
| Terraform-user-001 (identity used by recent Jenkins builds) | Existing AdministratorAccess already covers deployment/scaling operations; no extra grant added |
| webtech-shared-codebuild-image-builder | Existing working build/scan/report/ECR policy retained; no new deployment access added |

Production policy sources are `github-terraform-production-{network,roles,compute,edge,logging}-policy.json`.
They use the same documented regional/account-level scopes as staging. The
existing production role's legacy permissions were not removed or narrowed;
this preparation is not a least-privilege cleanup. Its production-only trust
remains bound to the protected terraform-production GitHub environment.

The Jenkins autoscaling supplemental policy is available as a source for a
future scoped Jenkins identity, but was not attached redundantly to the current
administrator identity. No Jenkins credentials were read or replaced.

GitHub production origin-token secret was created privately. The production
AWS_APPLY_ROLE_TO_ASSUME environment secret now identifies the audited existing
production apply role. Production execution remains disabled until the new code
is merged and the operator is ready to review its plan. Existing origin tokens
and staging/shared environment settings were preserved.

## Required deployment sequence

1. Merge the code change, including zero-task services, suspended initial scaling,
   ReleaseMinCapacity metadata, updated deployment script, and Environment=production
   provider default tag. Production KMS permissions require that tag.
2. Review/apply the infrastructure updates in GitHub. Existing running services
   are not automatically stopped. The metadata must exist before running the new
   Jenkins deployment script.
3. Set TF_PRODUCTION_ENABLED=true when ready, review/approve its first plan, and
   obtain its real URL/cluster/service outputs. Its new application services stay
   at zero tasks until the approved Jenkins release.
4. Configure Jenkins with BOTH environments' URLs/services and authorised Jenkins
   approver IDs. The current normal pipeline validates production configuration
   before building; missing settings will still fail that preflight.
5. Run the approved Jenkins release flow. A configured reachable webhook can
   trigger it; a local-only controller needs a manual run or reachable endpoint.

IAM validation/simulation cannot guarantee absence of live deployment failures.
AWS capacity, runtime health, registry availability, newly reported vulnerabilities,
account restrictions and unknown application errors still require real deployment
validation. Builds and infrastructure applies were deliberately not run here.
Policy-version backups and simulation results are private under
`/tmp/jenkins-live-iam-audit/`; source files in Git record intended permissions.

## Production rebuild repair — 7 November 2026

Terraform's task-template parameter refresh failed because the production apply
role lacked `ssm:DescribeParameters`. Added `ProductionTaskTemplateDiscovery` to
`github-terraform-production-observability-policy.json`, with `Resource: "*"`
and `aws:RequestedRegion=eu-west-2`. AWS does not support parameter resource
scoping for this metadata-list action. Existing parameter value/write permissions
remain scoped to `/webtech-production/observability/task-templates`.

The live `GitHubTerraformProductionObservability` managed policy was minimally
updated to default version `v2`, preserving its existing statements. IAM simulation
for `GitHubTerraformApplyRole` returned `allowed` for London DescribeParameters.
The previous policy version remains available for rollback.

The GitHub `PRODUCTION_TELEMETRY_JSON` variable still referred to the destroyed
monitoring host, secret and key. It was removed, and local production telemetry
inputs were disabled until monitoring is rebuilt. Neither Jenkinsfile changed.
At the time of the repair, both production services had desired/running counts
of zero. No Terraform apply or application deployment was performed in this repair.

Start a **new** GitHub Actions workflow run from current main with `stack=production`
to refresh partial state and generate a new reviewed plan; do not reuse the failed
run's saved plan. Approve only after reviewing the new diff. A later monitoring
connection needs a fresh endpoint/secret/key configuration and its own plan.
