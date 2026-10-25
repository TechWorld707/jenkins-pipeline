variable "name" {
  type        = string
  description = "Environment prefix"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private app subnets"
}

variable "security_group_ids" {
  type        = map(string)
  description = "Task security groups"
}

variable "images" {
  type        = map(string)
  description = "Initial frontend and backend immutable image references"
}

variable "db_host" {
  type        = string
  description = "Database host"
}

variable "db_name" {
  type        = string
  description = "Database name"
}

variable "db_secret_arn" {
  type        = string
  description = "RDS managed credential secret"
}

variable "desired_count" {
  type        = number
  description = "Tasks per service"
}

variable "retention_days" {
  type        = number
  description = "Log retention"
}

variable "target_group_arn" {
  type        = string
  description = "Frontend target group"
}

variable "container_insights" {
  type        = bool
  description = "Enable ECS Container Insights"
}
