# GitHub Terraform IAM policy sources

See [the setup guide](../GITHUB_AWS_ROLE_SETUP.md) for the three GitHub approval
environments and their separate apply-role requirements.

- `github-terraform-plan-backend-policy.json` proposes lock access for the exact
  shared, staging and production `.tflock` objects. Only shared lock access was
  previously installed. The source update does not change AWS automatically.
- `github-terraform-{shared,staging,production}-apply-trust.json` restrict each
  apply role to one protected GitHub environment using immutable OIDC subjects.
- The existing `github-terraform-apply-*.json` permission policies include
  historical legacy supplements and unapplied shared-policy proposals. They
  are not a complete, installed permission set for the new three-stack workflow.

AWS role changes were not performed in this change. Review deployment permissions
against each root, including exact state/lock objects, resource names, PassRole,
KMS and global edge operations, before installing policies. Preserve bootstrap
and exclude management of the GitHub roles themselves from deployment access.

An earlier attempt to install broad policy changes was rejected by automatic
approval review. That rejection did not install those permissions; these source
files must not be treated as evidence of live IAM access.
