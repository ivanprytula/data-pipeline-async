variable "project" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }

variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "sg_alb_id" { type = string }
variable "sg_app_id" { type = string }

variable "app_port" {
  type    = number
  default = 8000
}

variable "ecr_repository_url_ingestor" {
  description = "ECR URL for the ingestor image (from modules/ecr output)."
  type        = string
}

variable "image_tag" {
  description = "Image tag to deploy. Typically the git SHA or 'latest'."
  type        = string
  default     = "latest"
}

variable "msk_cluster_arn" {
  description = "MSK Serverless cluster ARN for IAM auth policy."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the HTTPS ALB listener. Required before apply."
  type        = string
}

variable "alb_access_log_bucket" {
  description = "S3 bucket name for ALB access logs. Empty string disables logging."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "Days to retain CloudWatch logs."
  type        = number
  default     = 30
}

# ── Ingestor sizing ────────────────────────────────────────────────────────────
variable "ingestor_cpu" {
  description = "Fargate CPU units (256 = 0.25 vCPU). Valid: 256, 512, 1024, 2048, 4096."
  type        = number
  default     = 256
}

variable "ingestor_memory" {
  description = "Fargate memory in MiB. Must be compatible with cpu setting."
  type        = number
  default     = 512
}

variable "ingestor_desired_count" {
  description = "Desired number of ingestor tasks."
  type        = number
  default     = 1
}
