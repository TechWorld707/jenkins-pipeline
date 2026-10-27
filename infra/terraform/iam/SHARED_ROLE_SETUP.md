# Attach shared infrastructure permissions manually

Role: **GitHubTerraformSharedApplyRole**. Keep the existing trust policy and
`TerraformSharedBackendAccess` permission policy unchanged.

1. Open AWS IAM > Roles > GitHubTerraformSharedApplyRole > Permissions.
2. Select Add permissions > Create inline policy > JSON.
3. Paste the entire `github-terraform-shared-resources-policy.json` file.
4. Select Next; name it `TerraformSharedResourceAccess`; create the policy.
5. Confirm both backend and resource policies appear under Permissions.

This resource policy covers only the shared root: two named ECR repositories,
the image-builder project and service role, report bucket, CodeBuild log group,
and the tagged application-log encryption key. It contains no permission to
modify the GitHub deployment roles or bootstrap bucket. Deployment authority over
the CodeBuild service role includes editing its inline permissions, so access to
the GitHub shared approval environment remains privileged and must be reviewed.

CloudWatch DescribeLogGroups uses a regional wildcard because it is a listing
operation. KMS CreateKey requires a wildcard plus the configured Project tag;
subsequent key management is restricted by that tag. ECR uses its AWS-managed
key and receives only grant-retirement permission through ECR for deletion.
The policy does not start builds, push images, or delete stored report objects.

The JSON is a prepared policy source, not an installed AWS policy. IAM Access
Analyzer checks syntax/action/resource compatibility; it does not prove a complete
Terraform deployment will succeed. No apply or infrastructure creation was run.
After installation, review a current shared Terraform plan before approving apply.
A successful apply creates billable resources. No Git push is needed merely to
attach the policy in AWS; commit the file separately to retain its source history.
