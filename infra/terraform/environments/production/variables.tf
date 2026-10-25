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
  description = "Tasks per service"
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
variable "images" {
  type        = map(string)
  description = "Bootstrap frontend and backend images, supplied through TF_VAR_images"
  validation {
    condition     = alltrue([for c in ["frontend", "backend"] : can(regex("^[0-9]{12}[.]dkr[.]ecr[.]eu-west-2[.]amazonaws[.]com/[^@]+@sha256:[0-9a-f]{64}$", var.images[c]))])
    error_message = "Supply frontend and backend ECR image digests."
  }
}
