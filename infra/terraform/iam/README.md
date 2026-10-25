# GitHub Terraform policy transition

Application deployment now uses shared, staging and production state keys.
The existing GitHub Terraform job targets shared infrastructure only.

These four policy sources are prepared for review and **have not been installed**
in the existing GitHub roles. Automatic approval review rejected the live update
because it changes access across state prefixes and shared resources.

| Source | Intended AWS destination | Change |
| --- | --- | --- |
| github-terraform-plan-backend-policy.json | GitHubTerraformPlanRole / TerraformPlanBackendAccess | Locks for shared, staging and production state keys |
| github-terraform-apply-policy.json | GitHubTerraformApplyRole / TerraformApplyStackAccess | New state keys and shared ECR repository names |
| github-terraform-apply-codebuild-policy.json | GitHubTerraformApplyCodebuildAccess | Shared CodeBuild role, project and log group |
| github-terraform-apply-logging-policy.json | GitHubTerraformApplyLoggingAccess | Shared report bucket |

Existing bootstrap/state encryption access must be preserved. The plan role's
existing ReadOnlyAccess attachment and the apply role's OIDC approval trust are
unchanged. Role and policy documents were backed up privately before preparing
changes; no live role-policy update was executed.

The old RDS/edge policy files reflect still-attached historical supplemental
policies. They do not automatically authorise the new environment resources and
are not used by the shared-only apply job. Their future replacement or removal
requires a separate permission review. Creating the new environments with the
current provisioning identity does not prove the GitHub roles can manage them.

Do not rerun an old workflow revision that targets retired legacy configuration.
Review/install the approved permission changes before relying on the migrated
shared plan/apply job.
