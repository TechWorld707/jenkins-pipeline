variable "name" {
  type        = string
  description = "Environment resource prefix"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private database subnets"
}

variable "security_group_id" {
  type        = string
  description = "Database security group"
}

variable "multi_az" {
  type        = bool
  description = "Enable standby database"
}

variable "deletion_protection" {
  type        = bool
  description = "Protect database deletion"
  default     = true
}

variable "retention_days" {
  type        = number
  description = "Database log retention"
}
