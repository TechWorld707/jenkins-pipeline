# Terraform security settings

The network foundation uses eu-west-2a and eu-west-2b, disables automatic public
IPv4 assignment, denies all traffic through the default security group, and
records all VPC flows in a KMS-encrypted CloudWatch log group for 365 days.
Before changing the pinned zones in an existing deployment, review the plan for
subnet replacement.

The load-balancer security group accepts HTTPS on port 443. When adding the
load balancer, configure an HTTPS listener with an ACM certificate; its frontend
targets can continue to use HTTP on port 80 inside the VPC.

The bootstrap stack enables state-bucket access logging, EventBridge notifications,
a lifecycle rule to abort incomplete multipart uploads, and KMS encryption with
key rotation. Existing state versions are retained; changing default encryption
does not re-encrypt old objects. Backend users, including the CI role, need
kms:Encrypt, kms:Decrypt, and kms:GenerateDataKey on the state KMS key, alongside
their existing S3 permissions. Apply bootstrap changes before relying on these
settings in the application stack. New KMS keys and log storage incur AWS charges.

## Scoped Checkov exceptions

- CKV2_AWS_5 on the four application security groups: this checkout defines only
  network foundations. Remove each exception when adding its load balancer,
  frontend service, backend service, or database and attach the group there.
- CKV_AWS_144 on state and access-log buckets: this backend is single-region.
  Versioning protects prior state, but does not provide regional disaster
  recovery. Cross-region replication remains unimplemented and needs a replica
  bucket and replication role with appropriate KMS permissions.
- CKV_AWS_18 on the access-log destination: logging that bucket to itself would
  cause recursive logging.
- CKV_AWS_145 on the access-log destination: S3 server access-log delivery to S3
  requires SSE-S3 on the destination, per the
  [AWS documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html).

EventBridge forwarding is enabled; add rules and consumers for any desired
alerting or automated responses.

## Local checks

```sh
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform/bootstrap validate
checkov -d infra/terraform --framework terraform
```
