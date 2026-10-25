provider "aws" {
  region = "eu-west-2"
  default_tags { tags = { Project = "jenkins-pipeline", ManagedBy = "Terraform" } }
}
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
