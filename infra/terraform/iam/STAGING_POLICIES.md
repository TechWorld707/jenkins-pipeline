# Staging Terraform apply policies

This document contains all five policy documents for manual copying. Create five
separate customer managed policies in AWS IAM; do not paste this entire document
or combine the JSON blocks into one IAM policy. Attach all five to
`GitHubTerraformStagingApplyRole`, keeping `TerraformStagingBackendAccess`.

The combined policies exceed IAM policy size limits. Each JSON block below is a
complete, separate policy. See [STAGING_ROLE_SETUP.md](STAGING_ROLE_SETUP.md) for
installation, permission scope and the required staging provider tag change.
These files do not install permissions or create infrastructure.

## TerraformStagingNetworkAccess

Source: [github-terraform-staging-network-policy.json](github-terraform-staging-network-policy.json)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadNetworking",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeVpcs",
        "ec2:DescribeVpcAttribute",
        "ec2:DescribeInternetGateways",
        "ec2:DescribeSubnets",
        "ec2:DescribeRouteTables",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeSecurityGroupRules",
        "ec2:DescribeNetworkAcls",
        "ec2:DescribeFlowLogs",
        "ec2:DescribeTags",
        "ec2:DescribeAddresses",
        "ec2:DescribeNatGateways",
        "ec2:DescribeManagedPrefixLists",
        "ec2:GetManagedPrefixListEntries",
        "ec2:DescribeAddressesAttribute"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2"
        }
      }
    },
    {
      "Sid": "ManageNetworking",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateVpc",
        "ec2:DeleteVpc",
        "ec2:ModifyVpcAttribute",
        "ec2:CreateInternetGateway",
        "ec2:DeleteInternetGateway",
        "ec2:AttachInternetGateway",
        "ec2:DetachInternetGateway",
        "ec2:CreateSubnet",
        "ec2:DeleteSubnet",
        "ec2:ModifySubnetAttribute",
        "ec2:CreateRouteTable",
        "ec2:DeleteRouteTable",
        "ec2:CreateRoute",
        "ec2:DeleteRoute",
        "ec2:ReplaceRoute",
        "ec2:AssociateRouteTable",
        "ec2:DisassociateRouteTable",
        "ec2:ReplaceRouteTableAssociation",
        "ec2:CreateSecurityGroup",
        "ec2:DeleteSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress",
        "ec2:UpdateSecurityGroupRuleDescriptionsIngress",
        "ec2:UpdateSecurityGroupRuleDescriptionsEgress",
        "ec2:ModifySecurityGroupRules",
        "ec2:CreateFlowLogs",
        "ec2:DeleteFlowLogs",
        "ec2:CreateTags",
        "ec2:DeleteTags",
        "ec2:AllocateAddress",
        "ec2:ReleaseAddress",
        "ec2:CreateNatGateway",
        "ec2:DeleteNatGateway",
        "ec2:DisassociateAddress"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2"
        }
      }
    },
    {
      "Sid": "CreateServiceRole2",
      "Effect": "Allow",
      "Action": [
        "iam:CreateServiceLinkedRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/aws-service-role/ecs.amazonaws.com/AWSServiceRoleForECS",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": "ecs.amazonaws.com"
        }
      }
    },
    {
      "Sid": "CreateServiceRole3",
      "Effect": "Allow",
      "Action": [
        "iam:CreateServiceLinkedRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": "rds.amazonaws.com"
        }
      }
    },
    {
      "Sid": "CreateServiceRole4",
      "Effect": "Allow",
      "Action": [
        "iam:CreateServiceLinkedRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/aws-service-role/elasticloadbalancing.amazonaws.com/AWSServiceRoleForElasticLoadBalancing",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": "elasticloadbalancing.amazonaws.com"
        }
      }
    },
    {
      "Sid": "CreateServiceRole5",
      "Effect": "Allow",
      "Action": [
        "iam:CreateServiceLinkedRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/aws-service-role/wafv2.amazonaws.com/AWSServiceRoleForWAFV2Logging",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": "wafv2.amazonaws.com"
        }
      }
    },
    {
      "Sid": "CreateServiceRole6",
      "Effect": "Allow",
      "Action": [
        "iam:CreateServiceLinkedRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/aws-service-role/ecs.application-autoscaling.amazonaws.com/AWSServiceRoleForApplicationAutoScaling_ECSService",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": "ecs.application-autoscaling.amazonaws.com"
        }
      }
    }
  ]
}
```

## TerraformStagingRolesAccess

Source: [github-terraform-staging-roles-policy.json](github-terraform-staging-roles-policy.json)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ManageStagingRoles",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:UpdateRole",
        "iam:UpdateAssumeRolePolicy",
        "iam:DeleteRole",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:ListRoleTags",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:ListInstanceProfilesForRole",
        "iam:PutRolePolicy",
        "iam:GetRolePolicy",
        "iam:DeleteRolePolicy"
      ],
      "Resource": [
        "arn:aws:iam::671662643382:role/webtech-staging-ecs-execution",
        "arn:aws:iam::671662643382:role/webtech-staging-ecs-task",
        "arn:aws:iam::671662643382:role/webtech-staging-rds-monitoring",
        "arn:aws:iam::671662643382:role/webtech-staging-vpc-flow-logs"
      ]
    },
    {
      "Sid": "AttachExecutionPolicy",
      "Effect": "Allow",
      "Action": [
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy"
      ],
      "Resource": "arn:aws:iam::671662643382:role/webtech-staging-ecs-execution",
      "Condition": {
        "ArnEquals": {
          "iam:PolicyARN": "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
        }
      }
    },
    {
      "Sid": "AttachMonitoringPolicy",
      "Effect": "Allow",
      "Action": [
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy"
      ],
      "Resource": "arn:aws:iam::671662643382:role/webtech-staging-rds-monitoring",
      "Condition": {
        "ArnEquals": {
          "iam:PolicyARN": "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
        }
      }
    },
    {
      "Sid": "PassEcsexecution",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/webtech-staging-ecs-execution",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "ecs-tasks.amazonaws.com"
        }
      }
    },
    {
      "Sid": "PassEcstask",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/webtech-staging-ecs-task",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "ecs-tasks.amazonaws.com"
        }
      }
    },
    {
      "Sid": "PassRdsmonitoring",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/webtech-staging-rds-monitoring",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": [
            "rds.amazonaws.com",
            "monitoring.rds.amazonaws.com"
          ]
        }
      }
    },
    {
      "Sid": "PassVpcflowlogs",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::671662643382:role/webtech-staging-vpc-flow-logs",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "vpc-flow-logs.amazonaws.com"
        }
      }
    }
  ]
}
```

## TerraformStagingComputeAccess

Source: [github-terraform-staging-compute-policy.json](github-terraform-staging-compute-policy.json)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ManageStagingCluster",
      "Effect": "Allow",
      "Action": [
        "ecs:CreateCluster",
        "ecs:DeleteCluster",
        "ecs:DescribeClusters",
        "ecs:UpdateCluster",
        "ecs:UpdateClusterSettings",
        "ecs:TagResource",
        "ecs:UntagResource",
        "ecs:ListTagsForResource"
      ],
      "Resource": "arn:aws:ecs:eu-west-2:671662643382:cluster/webtech-staging"
    },
    {
      "Sid": "ManageStagingServices",
      "Effect": "Allow",
      "Action": [
        "ecs:CreateService",
        "ecs:UpdateService",
        "ecs:DeleteService",
        "ecs:DescribeServices",
        "ecs:TagResource",
        "ecs:UntagResource",
        "ecs:ListTagsForResource"
      ],
      "Resource": "arn:aws:ecs:eu-west-2:671662643382:service/webtech-staging/webtech-staging-*"
    },
    {
      "Sid": "RegisterTaskDefinitions",
      "Effect": "Allow",
      "Action": [
        "ecs:RegisterTaskDefinition"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2"
        }
      }
    },
    {
      "Sid": "ManageStagingTaskDefinitions",
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeTaskDefinition",
        "ecs:DeregisterTaskDefinition",
        "ecs:TagResource",
        "ecs:UntagResource",
        "ecs:ListTagsForResource"
      ],
      "Resource": [
        "arn:aws:ecs:eu-west-2:671662643382:task-definition/webtech-staging-frontend:*",
        "arn:aws:ecs:eu-west-2:671662643382:task-definition/webtech-staging-backend:*"
      ]
    },
    {
      "Sid": "ManageServiceDiscovery",
      "Effect": "Allow",
      "Action": [
        "servicediscovery:CreateHttpNamespace",
        "servicediscovery:GetNamespace",
        "servicediscovery:DeleteNamespace",
        "servicediscovery:GetOperation",
        "servicediscovery:ListTagsForResource",
        "servicediscovery:TagResource",
        "servicediscovery:UntagResource"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2"
        }
      }
    },
    {
      "Sid": "ManageStagingRds",
      "Effect": "Allow",
      "Action": [
        "rds:CreateDBInstance",
        "rds:ModifyDBInstance",
        "rds:DeleteDBInstance",
        "rds:CreateDBSubnetGroup",
        "rds:ModifyDBSubnetGroup",
        "rds:DeleteDBSubnetGroup",
        "rds:CreateDBParameterGroup",
        "rds:ModifyDBParameterGroup",
        "rds:DeleteDBParameterGroup",
        "rds:AddTagsToResource",
        "rds:RemoveTagsFromResource",
        "rds:ListTagsForResource"
      ],
      "Resource": [
        "arn:aws:rds:eu-west-2:671662643382:db:webtech-staging-postgres",
        "arn:aws:rds:eu-west-2:671662643382:subgrp:webtech-staging-db-subnets",
        "arn:aws:rds:eu-west-2:671662643382:pg:webtech-staging-*",
        "arn:aws:rds:eu-west-2:671662643382:snapshot:webtech-staging-postgres-final"
      ]
    },
    {
      "Sid": "ReadRds",
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBSubnetGroups",
        "rds:DescribeDBParameterGroups",
        "rds:DescribeDBParameters",
        "rds:DescribeDBEngineVersions"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2"
        }
      }
    },
    {
      "Sid": "ReadRdsSecretMetadata",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:eu-west-2:671662643382:secret:rds!db-*"
    },
    {
      "Sid": "RdsCreatesManagedSecret",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:TagResource"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2",
          "aws:CalledViaLast": "rds.amazonaws.com"
        }
      }
    },
    {
      "Sid": "DescribeRdsManagedEncryptionKey",
      "Effect": "Allow",
      "Action": [
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:eu-west-2:671662643382:key/*",
      "Condition": {
        "ForAnyValue:StringEquals": {
          "kms:ResourceAliases": [
            "alias/aws/rds",
            "alias/aws/secretsmanager"
          ]
        }
      }
    },
    {
      "Sid": "ManageEcsScaling",
      "Effect": "Allow",
      "Action": [
        "application-autoscaling:RegisterScalableTarget",
        "application-autoscaling:DeregisterScalableTarget",
        "application-autoscaling:PutScalingPolicy",
        "application-autoscaling:DeleteScalingPolicy",
        "application-autoscaling:DescribeScalableTargets",
        "application-autoscaling:DescribeScalingPolicies",
        "application-autoscaling:DescribeScalingActivities"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2",
          "application-autoscaling:service-namespace": "ecs"
        }
      }
    },
    {
      "Sid": "ReadScalingTags",
      "Effect": "Allow",
      "Action": [
        "application-autoscaling:ListTagsForResource"
      ],
      "Resource": "arn:aws:application-autoscaling:eu-west-2:671662643382:scalable-target/*"
    },
    {
      "Sid": "ManageScalingAlarms",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DeleteAlarms",
        "cloudwatch:DescribeAlarms"
      ],
      "Resource": "arn:aws:cloudwatch:eu-west-2:671662643382:alarm:TargetTracking-service/webtech-staging/*"
    }
  ]
}
```

## TerraformStagingEdgeAccess

Source: [github-terraform-staging-edge-policy.json](github-terraform-staging-edge-policy.json)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadAlb",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeLoadBalancerAttributes",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetGroupAttributes",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeListenerAttributes",
        "elasticloadbalancing:DescribeRules",
        "elasticloadbalancing:DescribeTags"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2"
        }
      }
    },
    {
      "Sid": "ManageAlb",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:CreateLoadBalancer",
        "elasticloadbalancing:DeleteLoadBalancer",
        "elasticloadbalancing:ModifyLoadBalancerAttributes",
        "elasticloadbalancing:SetSecurityGroups",
        "elasticloadbalancing:SetSubnets",
        "elasticloadbalancing:SetIpAddressType",
        "elasticloadbalancing:CreateTargetGroup",
        "elasticloadbalancing:ModifyTargetGroup",
        "elasticloadbalancing:ModifyTargetGroupAttributes",
        "elasticloadbalancing:DeleteTargetGroup",
        "elasticloadbalancing:CreateListener",
        "elasticloadbalancing:ModifyListener",
        "elasticloadbalancing:DeleteListener",
        "elasticloadbalancing:ModifyListenerAttributes",
        "elasticloadbalancing:CreateRule",
        "elasticloadbalancing:ModifyRule",
        "elasticloadbalancing:DeleteRule",
        "elasticloadbalancing:SetRulePriorities",
        "elasticloadbalancing:AddTags",
        "elasticloadbalancing:RemoveTags"
      ],
      "Resource": [
        "arn:aws:elasticloadbalancing:eu-west-2:671662643382:loadbalancer/app/webtech-staging-alb/*",
        "arn:aws:elasticloadbalancing:eu-west-2:671662643382:targetgroup/webtech-staging-frontend/*",
        "arn:aws:elasticloadbalancing:eu-west-2:671662643382:listener/app/webtech-staging-alb/*/*",
        "arn:aws:elasticloadbalancing:eu-west-2:671662643382:listener-rule/app/webtech-staging-alb/*/*/*"
      ]
    },
    {
      "Sid": "ReadPrefixLists",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeManagedPrefixLists",
        "ec2:GetManagedPrefixListEntries"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2"
        }
      }
    },
    {
      "Sid": "CreateCloudFront",
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateDistribution",
        "cloudfront:CreateResponseHeadersPolicy"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ManageCloudFront",
      "Effect": "Allow",
      "Action": [
        "cloudfront:GetDistribution",
        "cloudfront:GetDistributionConfig",
        "cloudfront:UpdateDistribution",
        "cloudfront:DeleteDistribution",
        "cloudfront:TagResource",
        "cloudfront:UntagResource",
        "cloudfront:ListTagsForResource"
      ],
      "Resource": "arn:aws:cloudfront::671662643382:distribution/*"
    },
    {
      "Sid": "ManageResponseHeaders",
      "Effect": "Allow",
      "Action": [
        "cloudfront:GetResponseHeadersPolicy",
        "cloudfront:GetResponseHeadersPolicyConfig",
        "cloudfront:UpdateResponseHeadersPolicy",
        "cloudfront:DeleteResponseHeadersPolicy"
      ],
      "Resource": "arn:aws:cloudfront::671662643382:response-headers-policy/*"
    },
    {
      "Sid": "ManageWaf",
      "Effect": "Allow",
      "Action": [
        "wafv2:CreateWebACL",
        "wafv2:GetWebACL",
        "wafv2:UpdateWebACL",
        "wafv2:DeleteWebACL",
        "wafv2:TagResource",
        "wafv2:UntagResource",
        "wafv2:ListTagsForResource",
        "wafv2:PutLoggingConfiguration",
        "wafv2:GetLoggingConfiguration",
        "wafv2:DeleteLoggingConfiguration"
      ],
      "Resource": [
        "arn:aws:wafv2:us-east-1:671662643382:global/webacl/webtech-staging-waf/*",
        "arn:aws:wafv2:us-east-1:671662643382:global/managedruleset/*/*"
      ]
    },
    {
      "Sid": "ReadManagedRules",
      "Effect": "Allow",
      "Action": [
        "wafv2:DescribeManagedRuleGroup",
        "wafv2:ListAvailableManagedRuleGroups",
        "wafv2:ListAvailableManagedRuleGroupVersions",
        "wafv2:CheckCapacity"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    }
  ]
}
```

## TerraformStagingLoggingAccess

Source: [github-terraform-staging-logging-policy.json](github-terraform-staging-logging-policy.json)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ManageStagingAlbLogBucket",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketAcl",
        "s3:GetBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:GetBucketTagging",
        "s3:PutBucketTagging",
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetEncryptionConfiguration",
        "s3:PutEncryptionConfiguration",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetLifecycleConfiguration",
        "s3:PutLifecycleConfiguration",
        "s3:GetBucketNotification",
        "s3:PutBucketNotification",
        "s3:GetBucketLogging",
        "s3:GetBucketWebsite",
        "s3:GetAccelerateConfiguration",
        "s3:GetBucketRequestPayment",
        "s3:GetBucketCORS",
        "s3:GetReplicationConfiguration",
        "s3:GetBucketObjectLockConfiguration",
        "s3:GetBucketOwnershipControls"
      ],
      "Resource": "arn:aws:s3:::webtech-staging-alb-logs-671662643382"
    },
    {
      "Sid": "ManageStagingLogGroups",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:PutRetentionPolicy",
        "logs:DeleteRetentionPolicy",
        "logs:AssociateKmsKey",
        "logs:DisassociateKmsKey",
        "logs:ListTagsForResource",
        "logs:TagResource",
        "logs:UntagResource",
        "logs:ListTagsLogGroup",
        "logs:TagLogGroup",
        "logs:UntagLogGroup"
      ],
      "Resource": [
        "arn:aws:logs:eu-west-2:671662643382:log-group:/ecs/webtech-staging/*",
        "arn:aws:logs:eu-west-2:671662643382:log-group:/aws/rds/instance/webtech-staging-postgres/*",
        "arn:aws:logs:eu-west-2:671662643382:log-group:/webtech-staging/vpc-flow-logs",
        "arn:aws:logs:eu-west-2:671662643382:log-group:/webtech-staging/vpc-flow-logs:*",
        "arn:aws:logs:us-east-1:671662643382:log-group:aws-waf-logs-webtech-staging",
        "arn:aws:logs:us-east-1:671662643382:log-group:aws-waf-logs-webtech-staging:*"
      ]
    },
    {
      "Sid": "ReadLogGroups",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": [
            "eu-west-2",
            "us-east-1"
          ]
        }
      }
    },
    {
      "Sid": "WafLogDelivery",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeResourcePolicies",
        "logs:PutResourcePolicy",
        "logs:CreateLogDelivery",
        "logs:UpdateLogDelivery",
        "logs:DeleteLogDelivery",
        "logs:GetLogDelivery",
        "logs:ListLogDeliveries"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "CreateApplicationKey",
      "Effect": "Allow",
      "Action": [
        "kms:CreateKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2",
          "aws:RequestTag/Environment": "staging"
        }
      }
    },
    {
      "Sid": "ManageApplicationKey",
      "Effect": "Allow",
      "Action": [
        "kms:DescribeKey",
        "kms:GetKeyPolicy",
        "kms:PutKeyPolicy",
        "kms:GetKeyRotationStatus",
        "kms:EnableKeyRotation",
        "kms:DisableKeyRotation",
        "kms:UpdateKeyDescription",
        "kms:ListResourceTags",
        "kms:TagResource",
        "kms:UntagResource",
        "kms:ScheduleKeyDeletion",
        "kms:CancelKeyDeletion",
        "kms:CreateGrant",
        "kms:ListGrants",
        "kms:RevokeGrant",
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:eu-west-2:671662643382:key/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2",
          "aws:ResourceTag/Environment": "staging"
        }
      }
    },
    {
      "Sid": "TagApplicationKeyOnCreation",
      "Effect": "Allow",
      "Action": "kms:TagResource",
      "Resource": "arn:aws:kms:eu-west-2:671662643382:key/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2",
          "aws:RequestTag/Environment": "staging"
        }
      }
    }
  ]
}
```
