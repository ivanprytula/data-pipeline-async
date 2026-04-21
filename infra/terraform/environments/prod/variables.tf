variable "aws_region" {
  type = string
  default = "us-east-1"
}

variable "aws_profile" {
  type = string
  default = "data-zoo-prod"
}
variable "vpc_cidr" {
  type = string
  default = "10.1.0.0/16"
}
variable "availability_zones" {
  type = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}
variable "github_repository" {
  type = string
  default = "ivanp/data-pipeline-async"
}
variable "redis_auth_token" {
  type = string
  sensitive = true
}
variable "acm_certificate_arn" {
  type = string
}
variable "image_tag" {
  type = string
  default = "latest"
}
