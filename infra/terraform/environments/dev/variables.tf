variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_profile" {
  description = "AWS named profile to use. Set via TF_VAR_aws_profile or CLI."
  type        = string
  default     = "data-zoo-dev"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "github_repository" {
  type    = string
  default = "ivanp/data-pipeline-async"
}

variable "redis_auth_token" {
  description = "Redis AUTH token. Source from SSM or pass via TF_VAR_redis_auth_token."
  type        = string
  sensitive   = true
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the HTTPS ALB listener."
  type        = string
  default     = ""  # Must be set before applying compute module
}

variable "image_tag" {
  description = "Docker image tag to deploy."
  type        = string
  default     = "develop"
}
