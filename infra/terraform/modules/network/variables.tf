variable "name" {
  type        = string
  description = "Environment resource prefix"
}

variable "cidr_block" {
  type        = string
  description = "Environment VPC CIDR"
}

variable "nat_per_az" {
  type        = bool
  description = "Use one NAT per AZ for availability"
  default     = false
}
