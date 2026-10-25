variable "codebuild_compute_type" {
  description = "Compute size for the shared image builder."
  type        = string
  default     = "BUILD_GENERAL1_SMALL"
}

variable "build_log_retention_days" {
  description = "CloudWatch retention for shared image-builder logs."
  type        = number
  default     = 14
}
