variable "name" {
  type        = string
  description = "Environment resource prefix"
}

variable "vpc_id" {
  type        = string
  description = "VPC to monitor"
}

variable "retention_days" {
  type        = number
  description = "CloudWatch retention days"
}
