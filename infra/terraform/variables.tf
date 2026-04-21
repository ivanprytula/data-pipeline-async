variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Short project name used in resource naming."
  type        = string
  default     = "data-zoo"
}

variable "environment" {
  description = "Deployment environment (dev | prod)."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be 'dev' or 'prod'."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of AZs to use. Defaults to 2 for dev, 3 for prod."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "app_port" {
  description = "Port the ingestor container listens on."
  type        = number
  default     = 8000
}

variable "github_repository" {
  description = "GitHub repo in 'owner/repo' format, used for OIDC trust policy."
  type        = string
  default     = "ivanp/data-pipeline-async"
}
