# Set up the AWS Terraform plan role and connect it to GitHub

> Rebuild note: the original application stack has been retired. The current
> GitHub plan/apply workflow targets `shared/`; see [the active infrastructure
> guide](README.md). Use the proposed policy sources under `iam/` for the new state
> keys. The shared-lock fix is installed for the plan role; broader apply-role
> updates are pending explicit security approval. State-key examples below target
> the shared stack.

This guide records the console steps used for this repository. It creates a
GitHub identity provider, a Terraform plan role, and its permission policies,
then connects the role to GitHub Actions. It does not create the apply role or
apply infrastructure.

## Values used in this project

| Item | Value |
| --- | --- |
| AWS account | `671662643382` |
| AWS region | `eu-west-2` (Europe/London) |
| GitHub repository | `TechWorld707/jenkins-pipeline` |
| Plan role | `GitHubTerraformPlanRole` |
| Managed policy | `ReadOnlyAccess` |
| Inline policy | `TerraformPlanBackendAccess` |
| State bucket | `techworld707-jenkins-pipeline-tfstate-671662643382` |
| State object | `jenkins-pipeline/shared/terraform.tfstate` |
| Lock object | `jenkins-pipeline/shared/terraform.tfstate.tflock` |

Confirm the AWS account and repository before copying the examples. You need
permission to manage IAM roles/providers in AWS and Actions secrets/variables in
GitHub. Reuse existing resources when following this guide again.

## 1. Add GitHub as an AWS identity provider

1. Sign in to the AWS console for the account above.
2. Search for **IAM** and open it.
3. In the left sidebar, select **Identity providers**.
4. If `token.actions.githubusercontent.com` exists, open it and verify its
   audience includes `sts.amazonaws.com`; reuse it.
5. Otherwise select **Add provider** and enter:

   | Field | Value |
   | --- | --- |
   | Provider type | OpenID Connect |
   | Provider URL | `https://token.actions.githubusercontent.com` |
   | Audience | `sts.amazonaws.com` |

6. Select **Add provider** to save.

OIDC lets a GitHub workflow obtain temporary AWS credentials. No AWS access key
or secret access key needs to be stored in GitHub for this workflow.

## 2. Create the plan role and its trust policy

A trust policy controls **who can assume the role**. Permission policies added
later control **what the role can do**.

1. Open **IAM > Roles > Create role**.
2. Under **Trusted entity type**, choose **Custom trust policy**.
3. Replace the editor contents with:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::671662643382:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": [
            "repo:TechWorld707@313882919/jenkins-pipeline@1424350875:pull_request",
            "repo:TechWorld707@313882919/jenkins-pipeline@1424350875:ref:refs/heads/main"
          ]
        }
      }
    }
  ]
}
```

4. Select **Next** to open **Add permissions**.

The two subject values allow PR plans and main-branch plans respectively. They
contain no wildcard. The PR subject does not encode the target branch: this
repository's workflow limits PRs to `main` and excludes forks. Only trusted
collaborators should be allowed to push branches in this repository, because
planning executes their Terraform configuration with the plan role's access.

This repository uses immutable OIDC subjects, confirmed through GitHub's API.
The owner ID is `313882919` and repository ID is `1424350875`. Name-only
subjects do not match its tokens and cause `sts:AssumeRoleWithWebIdentity`
to be denied. Keep both IDs in the subjects above. Do not widen the trust
to a wildcard to work around an error.

For an existing role, open **IAM > Roles > GitHubTerraformPlanRole > Trust
relationships > Edit trust policy**, replace the policy with the JSON above,
and select **Update policy**. Editing this document alone does not change AWS.

Verify the repository's subject format with:

```bash
gh api repos/TechWorld707/jenkins-pipeline/actions/oidc/customization/sub
```

The response should show `use_immutable_subject: true` and `sub_claim_prefix`
`repo:TechWorld707@313882919/jenkins-pipeline@1424350875`. Append
`:pull_request` or `:ref:refs/heads/main` as shown in the trust policy.

## 3. Attach ReadOnlyAccess and finish creating the role

1. Keep **Use existing policy** selected.
2. Search for `ReadOnlyAccess` and press Enter.
3. Tick the checkbox beside the exact AWS-managed policy **ReadOnlyAccess**.
4. Select **Next**.
5. Set **Role name** to `GitHubTerraformPlanRole`.
6. Review the trust policy and selected permissions.
7. Select **Create role**.

If the role already exists, open **IAM > Roles > GitHubTerraformPlanRole >
Permissions > Add permissions > Attach policies**, search for `ReadOnlyAccess`,
select its checkbox, and choose **Add permissions**. If it already appears in
the role's permissions table, it is already attached; the row checkbox is for
selecting it for actions, not for enabling it.

`ReadOnlyAccess` provides broad account-wide read access, including access to
some data. It is a starting point for this learning setup. For production,
replace it with narrower read permissions for the services/resources Terraform
needs. The plan role should not receive infrastructure deployment permissions
or permission to assume the apply role.

## 4. Check the deployed state bucket's encryption

1. Open **S3 > Buckets**.
2. Select `techworld707-jenkins-pipeline-tfstate-671662643382`.
3. Open **Properties**.
4. Find **Default encryption**; use Ctrl+F if needed.
5. Read **Encryption type**.

The console screenshot supplied during setup showed **SSE-S3**, so no
customer-managed KMS key ARN was shown. This is an observation from that setup,
not a live verification of AWS. The bucket is encrypted with S3-managed keys.
The bucket ARN (`arn:aws:s3:...`) and tag names are not KMS key ARNs.

The code in `bootstrap/main.tf` specifies customer-managed KMS encryption for
this state bucket. The observed deployment and the code therefore differ.
Review and apply bootstrap changes separately before relying on KMS, then grant
access to the actual key. The application workflow does not apply bootstrap.
Do not manually change encryption just to obtain an ARN.

## 5. Add the backend lock policy

For the observed SSE-S3 setup, the managed read policy supplies backend read
access, while this inline policy adds writes only to the temporary lock object.

1. Open **IAM > Roles > GitHubTerraformPlanRole**.
2. Select **Permissions > Add permissions > Create inline policy**.
3. Choose the **JSON** editor and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ManageTerraformLock",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::techworld707-jenkins-pipeline-tfstate-671662643382/jenkins-pipeline/shared/terraform.tfstate.tflock"
    }
  ]
}
```

4. Select **Next**.
5. Name the policy `TerraformPlanBackendAccess`.
6. Select **Create policy**.
7. Confirm that the role's permissions table contains both `ReadOnlyAccess` and
   `TerraformPlanBackendAccess`.

The `.tflock` file prevents conflicting Terraform operations. These write
permissions apply to the lock file, not to the state object or infrastructure.
Other controls, including explicit bucket-policy or organisation-policy denies,
can still block access.

### When the backend uses KMS

If state objects or new lock objects use KMS, add key access as well. Default
bucket encryption alone does not identify how every existing object is
encrypted. After bootstrap enables KMS, existing objects are not automatically
re-encrypted.

Find the actual key under **S3 > state bucket > Properties > Default encryption**
or inspect the individual object's encryption properties. Open the key in KMS
and copy its ARN. Add this statement to the inline policy's `Statement` array,
separated from the existing statement by a comma:

```json
{
  "Sid": "UseStateEncryptionKey",
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt",
    "kms:Encrypt",
    "kms:GenerateDataKey"
  ],
  "Resource": "arn:aws:kms:eu-west-2:671662643382:key/REPLACE-WITH-ACTUAL-KEY-ID"
}
```

Replace the placeholder before saving. These permissions support reading state
and writing encrypted locks. The key policy must also permit the role's access,
directly or through account IAM delegation. If existing objects use different
keys, access to those keys may also be needed.

## 6. Copy the role ARN

1. Return to the top of **IAM > Roles > GitHubTerraformPlanRole**.
2. Copy the **ARN** displayed in the role summary.
3. With no custom role path, it should be:

```text
arn:aws:iam::671662643382:role/GitHubTerraformPlanRole
```

Copy the value AWS displays rather than constructing one if the role has a path.
This ARN identifies a role; it is not an access key or password.

## 7. Save the ARN in GitHub

1. Open `https://github.com/TechWorld707/jenkins-pipeline`.
2. Select **Settings**.
3. In the sidebar, select **Secrets and variables > Actions**.
4. On the **Secrets** tab, select **New repository secret**.
5. Enter:

   | Field | Value |
   | --- | --- |
   | Name | `AWS_ROLE_TO_ASSUME` |
   | Secret | The plan role ARN copied from AWS |

6. Select **Add secret**.

If that name already exists, edit it instead. GitHub stores the ARN as a workflow
input; the OIDC provider and role trust policy are what establish AWS trust.
Browser spell-check underlines in this field do not indicate an AWS error.

## 8. Add the GitHub Actions variables

1. Stay under **Settings > Secrets and variables > Actions**.
2. Select the **Variables** tab, beside **Secrets**.
3. Select **New repository variable**.
4. Enter name `AWS_REGION` and value `eu-west-2`, then select **Add variable**.
5. Select **New repository variable** again.
6. Enter name `TF_PLAN_ENABLED` and value `true`, then select **Add variable**.

Use lowercase `true` without quotation marks. These are repository variables,
not secrets. The workflow reads them through `vars`, and the role ARN through
`secrets`.

Expected settings:

| Location | Name | Value |
| --- | --- | --- |
| Repository secret | `AWS_ROLE_TO_ASSUME` | Plan role ARN |
| Repository variable | `AWS_REGION` | `eu-west-2` |
| Repository variable | `TF_PLAN_ENABLED` | `true` |

## 9. Run the workflow and review the plan

1. Ensure `.github/workflows/security-scan.yml` is committed and pushed to GitHub.
2. Open **Actions > WebTech CI and security scans**.
3. Select **Run workflow**, choose branch **main**, and select **Run workflow**.
4. Open the new run. **Queued** means it is waiting for a runner.
5. Wait for application lint, Trivy, Checkov, SonarQube, and Terraform checks.
6. If they all succeed, **Terraform plan** runs. Open it to inspect step logs.
7. Return to the run's summary to read the Terraform plan report.
8. Under **Artifacts**, download `terraform-plan-report` for the complete
   `terraform-plan.txt` and saved binary plan.
9. Review additions, updates, replacements, and deletions before approving any
   deployment. Plan artifacts can contain sensitive state values; restrict
   access. This workflow retains them for one day.

To rerun the same commit, open a previous run and select **Re-run jobs > Re-run
all jobs**. To test newly pushed workflow changes, start a new run on main;
rerunning an older run uses its original commit.

For a pull request, open **Checks > Terraform plan > Details** to reach the report.
After an approved PR is merged, the workflow generates a fresh main-branch plan
against current state. Review that final plan again before approving apply.

## 10. Understand the separate apply setup

This guide completes the plan-role connection only. Automatic resource creation
requires a separate apply role and GitHub approval configuration:

1. Create environment **terraform-production** under **Settings > Environments**.
2. Configure **Required reviewers** and restrict deployment branches to `main`.
   Verify your GitHub plan/repository visibility supports required reviewers.
   An environment name in YAML alone does not enforce approval.
3. Create a separate AWS deployment role with permissions for the application
   stack and backend, using an environment-restricted OIDC trust policy.
4. Store its ARN as `AWS_APPLY_ROLE_TO_ASSUME` **inside that environment**.
5. Protect main with required PR reviews and successful CI checks.
6. Review the final main plan, then use **Review deployments >
   terraform-production > Approve and deploy** in the workflow run.

The apply job executes the saved plan from that run after approval. It is skipped
when no changes are needed. See [the Terraform README](README.md#github-plan-review-and-approved-apply)
for deployment requirements. These settings are not created by this document.

### Attach the apply role permissions

After creating `GitHubTerraformApplyRole` and saving its ARN as the environment
secret `AWS_APPLY_ROLE_TO_ASSUME`:

1. Open **AWS IAM > Roles > GitHubTerraformApplyRole > Permissions**.
2. Select **Add permissions > Create inline policy**, then choose **JSON**.
3. Paste the complete contents of
   [github-terraform-apply-policy.json](iam/github-terraform-apply-policy.json).
4. Select **Next**, name it `TerraformApplyStackAccess`, and create the policy.

The policy was checked with IAM Access Analyzer with no findings. It has not
been tested through a changed infrastructure apply. It permits the networking
API operations used by this stack across `eu-west-2`; those EC2 permissions are
region-scoped, not restricted to this project's individual VPC resources. IAM
management and PassRole are limited to `jenkins-pipeline-vpc-flow-logs`, logs to
the project log group, and state writes to the configured state and lock objects.
It does not grant permission to edit the GitHub plan or apply roles.

The KMS permissions target the existing flow-log key
`b0848b64-e1e1-4015-8310-2a1636d43cf5`. Creating a new key or recreating this
stack after destroying that key requires a reviewed policy update; this policy
does not grant `kms:CreateKey`. On 22 October 2026, both the deployed state
bucket default and the state object were verified as SSE-S3 (`AES256`). If the
backend moves to KMS, add the actual state-key permissions before applying.
Bootstrap resources are managed separately and are not covered by this policy.

Keep required reviewers and the `main` deployment branch restriction enabled
on `terraform-production`. A no-change plan will still skip apply; the next
intended change on main will wait for approval when the environment rules are
configured correctly. Attaching this policy does not deploy any resources.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Plan skipped | `TF_PLAN_ENABLED` is a variable with exact value `true`; all prerequisite jobs passed; fork PRs are excluded. |
| OIDC assumption denied | Provider URL/audience, account ID, role ARN, exact repository subject, and actual OIDC subject format. Manual plan runs should select main. |
| Yellow underline in trust editor | Read the exact warning. Confirm the policy has exact repository subjects, not broad wildcards; do not remove restrictions blindly. |
| S3 AccessDenied | Managed read policy, exact bucket/object paths, lock policy, and bucket/organisation restrictions. |
| KMS AccessDenied | Encryption of existing objects and locks, actual key ARN, role permissions, and the KMS key policy. |
| Cannot find a KMS key | Check Default encryption. SSE-S3 does not show a customer-managed key; tag keys and bucket ARNs are unrelated. |
| State lock error | Check for an active operation and lock permissions. Do not force-unlock an active operation. |
| Apply credentials missing | Configure the separate environment-scoped apply role secret. The plan role cannot deploy. |
| Plan expired, stale, or superseded | Start a new main workflow run and review the newly generated plan. |

## Official references

- [GitHub: configure AWS OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [AWS: connect GitHub Actions using IAM roles](https://aws.amazon.com/blogs/security/use-iam-roles-to-connect-github-actions-to-actions-in-aws/)
- [AWS: ReadOnlyAccess managed policy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/ReadOnlyAccess.html)
- [HashiCorp: S3 backend permissions and locking](https://developer.hashicorp.com/terraform/language/backend/s3)
- [GitHub: use Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [GitHub: deployment environments and protection](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
