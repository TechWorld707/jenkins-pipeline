variable "name" {
  type        = string
  description = "Environment prefix"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "ALB subnets"
}

variable "alb_security_group_id" {
  type        = string
  description = "ALB security group"
}

variable "deletion_protection" {
  type        = bool
  description = "Protect ALB deletion"
  default     = true
}

variable "retention_days" {
  type        = number
  description = "WAF log retention"
}
