variable "environment" {
  type        = string
  description = "Environment name"
}

variable "cidr_block" {
  type        = string
  description = "Isolated environment CIDR"
}

variable "desired_count" {
  type        = number
  description = "Minimum tasks per service after the first approved Jenkins release"
}

variable "multi_az" {
  type        = bool
  description = "Enable RDS Multi-AZ"
}

variable "retention_days" {
  type        = number
  description = "Log retention"
}

variable "cloudfront_origin_token" {
  type        = string
  description = "Unique secret origin token for this environment"
  sensitive   = true
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{32,128}$", var.cloudfront_origin_token))
    error_message = "Supply a random 32-128 character origin token."
  }
}
variable "max_task_count" {
  type        = number
  description = "Maximum Fargate tasks per service; desired_count is the minimum"
  validation {
    condition     = var.max_task_count >= var.desired_count && var.desired_count >= 1 && floor(var.desired_count) == var.desired_count && floor(var.max_task_count) == var.max_task_count
    error_message = "Task limits must be positive integers, with max_task_count >= desired_count."
  }
}
