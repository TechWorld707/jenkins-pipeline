terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
  backend "s3" {}
}
provider "aws" {
  region = "eu-west-2"
  default_tags {
    tags = { Project = "jenkins-pipeline", ManagedBy = "Terraform", Environment = "production", Component = "monitoring" }
  }
}
