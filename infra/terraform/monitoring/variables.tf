variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
variable "backend_security_group_id" { type = string }
variable "log_kms_key_arn" { type = string }
variable "alert_topic_arn" { type = string }
variable "instance_type" {
  type    = string
  default = "t3.small"
}
variable "images" {
  description = "Reviewed linux/amd64 immutable images. No floating tags."
  type        = object({ prometheus = string, tempo = string, grafana = string, nginx = string })
  validation {
    condition     = alltrue([for image in values(var.images) : can(regex("@sha256:[0-9a-f]{64}$", image))])
    error_message = "Pin each image to a reviewed SHA256 digest."
  }
}
