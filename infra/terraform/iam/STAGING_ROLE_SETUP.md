# Staging apply permissions — manual installation

Keep `GitHubTerraformStagingApplyRole`'s trust policy and
`TerraformStagingBackendAccess` inline policy unchanged. These files are proposed
permission sources, not installed policies. No Terraform plan/apply or AWS role
change was performed while preparing them.

Create the following **customer managed policies**, then attach them to that role.
Their combined size exceeds the per-role inline-policy limit. Each individual
policy is below the managed-policy size limit.

| Policy name | JSON source |
| --- | --- |
| TerraformStagingNetworkAccess | github-terraform-staging-network-policy.json |
| TerraformStagingRolesAccess | github-terraform-staging-roles-policy.json |
| TerraformStagingComputeAccess | github-terraform-staging-compute-policy.json |
| TerraformStagingEdgeAccess | github-terraform-staging-edge-policy.json |
| TerraformStagingLoggingAccess | github-terraform-staging-logging-policy.json |

For each file:

1. Open AWS IAM > Policies > Create policy > JSON.
2. Paste the entire file, select Next and enter the matching policy name above.
3. Create the policy. Repeat for the other four files.
4. Open IAM > Roles > GitHubTerraformStagingApplyRole > Permissions.
5. Choose Add permissions > Attach policies; find and select the five policy names.
6. Attach them. Keep the existing staging backend policy attached.

Confirm GitHub environment `terraform-staging` has secret
`AWS_APPLY_ROLE_TO_ASSUME` pointing to this staging role. Review a fresh staging
plan before approval; approving apply creates billable infrastructure. The
staging provider now adds `Environment=staging` to London resources; commit and
merge that provider change before using these policies, because KMS permissions
require that tag. The us-east-1 WAF provider does not manage staging KMS keys.

## Permission scope and limitations

These are learning deployment policies, not strict isolation between environments.
Regional EC2 networking mutations apply throughout eu-west-2, including resources
outside staging. CloudFront distribution and response-header operations cover the
account because generated IDs are not known until creation. Cloud Map operations
are regional. ECS task registration is regional; subsequent service and cluster management uses staging names. Task-definition
reads and deregistration require regional wildcard resource access. Some listing, log-delivery and scaling
operations also need wildcard resource scopes. The backend policy grants access
only to staging state; it does not isolate the wider service API operations.

IAM role management and PassRole target the four staging service roles. Editing
those roles' inline policies is privileged; keep GitHub reviewers and main-only
deployment restrictions enabled. KMS management targets keys tagged
`Environment=staging`; initial key creation requires that request tag. Managed
RDS secret access is metadata-only; passwords are not readable by these policies.
The policy does not manage shared ECR/CodeBuild or bootstrap infrastructure.

Access Analyzer validation checks action names, syntax and compatible resource
formats. It does not guarantee that every Terraform operation is authorised by
all account controls or prove strict isolation. No deployment was run to test it.
For production, replace regional/account-wide write scopes with reviewed tag/ID
conditions and resource-specific controls before reusing this approach.

## RDS PassRole and EIP refresh corrections

Update the existing customer managed policies (create a new default version):
`TerraformStagingRolesAccess` uses both `rds.amazonaws.com` and
`monitoring.rds.amazonaws.com` for the exact RDS monitoring role's PassRole
condition. This condition is separate from the monitoring role's trust principal;
keep its trust unchanged. `TerraformStagingNetworkAccess` includes
`ec2:DescribeAddressesAttribute`, used by the provider when reading an allocated
Elastic IP. The source corrections are not installed automatically.

After a partially failed apply, run a fresh plan against the current remote
state and review it before approving. Do not reuse the old saved binary plan,
delete state, or destroy successful resources to retry these permissions.

## ECS task definition read correction

`ecs:DescribeTaskDefinition` does not support resource-level permissions. The
compute policy grants this read API with Resource `*`, limited to eu-west-2.
Tag mutations remain restricted to staging task definitions. Deregistration is
regional as described below.
An apparently missing revision after registration can be a masked read-permission
denial. Check its existence and the IAM decision before recreating or deleting it.

## ECS task definition deregistration correction

AWS does not support resource-level permissions for `ecs:DeregisterTaskDefinition`.
The compute policy uses Resource `*`, restricted to eu-west-2, for this operation.
This permits deregistration of any task-definition family in that region, not
only staging families. Keep the GitHub approval gate protected. The provider's
family-only state ID is normal; its ARN attribute identifies the exact revision.
Do not edit state IDs or deregister revisions manually to fix this IAM denial.
