variable "aws_region" {
  type    = string
  default = "eu-west-2"
}
variable "image_uri" {
  description = "Immutable ECR image digest from the publish-only workflow."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/devops-lab@sha256:[a-f0-9]{64}$", var.image_uri))
    error_message = "Use a devops-lab ECR image pinned to its sha256 digest."
  }
}
variable "app_version" {
  description = "Full Git commit SHA used to build image_uri."
  type        = string
  validation {
    condition     = can(regex("^[a-f0-9]{40}$", var.app_version))
    error_message = "app_version must be a full Git commit SHA."
  }
}
variable "allowed_cidr" {
  description = "Public client CIDR permitted to reach the load balancer; use your IP/32."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.allowed_cidr)) && var.allowed_cidr != "0.0.0.0/0"
    error_message = "Supply a restricted IPv4 CIDR; unrestricted internet ingress is disallowed."
  }
}
variable "certificate_arn" {
  description = "Optional existing ACM certificate ARN in this region; enables HTTPS and HTTP redirect."
  type        = string
  default     = ""
}
variable "domain_name" {
  description = "DNS name covered by certificate_arn; point it to the ALB before smoke testing HTTPS."
  type        = string
  default     = ""
  validation {
    condition     = var.certificate_arn == "" || var.domain_name != ""
    error_message = "Provide the certificate's domain_name when enabling HTTPS."
  }
}
variable "alarm_email" {
  description = "Optional SNS email subscription; confirm the subscription before testing alerts."
  type        = string
  default     = ""
}
