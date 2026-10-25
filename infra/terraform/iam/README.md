# GitHub Terraform policy transition

Application deployment now uses shared, staging and production state keys.
The existing GitHub Terraform job targets shared infrastructure only.

The plan-role lock fix has been installed: its existing GetObject/PutObject/
DeleteObject permission now targets only the shared `.tflock` object, replacing
the retired app lock. It does not grant writes to Terraform state or locks for
staging/production. IAM simulation confirms shared lock access is allowed.

The three broader apply-role policy updates below remain **unapplied**. Automatic
approval review rejected that broader update because it changes access across
state prefixes and shared resources.

| Source | Intended AWS destination | Change |
| --- | --- | --- |
| github-terraform-plan-backend-policy.json | GitHubTerraformPlanRole / TerraformPlanBackendAccess | Shared state lock only (installed) |
| github-terraform-apply-policy.json | GitHubTerraformApplyRole / TerraformApplyStackAccess | New state keys and shared ECR repository names |
| github-terraform-apply-codebuild-policy.json | GitHubTerraformApplyCodebuildAccess | Shared CodeBuild role, project and log group |
| github-terraform-apply-logging-policy.json | GitHubTerraformApplyLoggingAccess | Shared report bucket |

Existing bootstrap/state encryption access must be preserved. The plan role's
existing ReadOnlyAccess attachment and the apply role's OIDC approval trust are
unchanged. Role and policy documents were backed up privately before preparing
changes. Only the narrow plan-role lock update has been installed.

The old RDS/edge policy files reflect still-attached historical supplemental
policies. They do not automatically authorise the new environment resources and
are not used by the shared-only apply job. Their future replacement or removal
requires a separate permission review. Creating the new environments with the
current provisioning identity does not prove the GitHub roles can manage them.

Do not rerun an old workflow revision that targets retired legacy configuration.
The shared plan job can now acquire its lock. Review/install the remaining
approved permissions before relying on infrastructure writes from the apply job.
