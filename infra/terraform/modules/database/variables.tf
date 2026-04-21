variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the DB subnet group."
  type        = list(string)
}

variable "sg_db_id" {
  description = "Security group ID for the RDS instance."
  type        = string
}

variable "instance_class" {
  description = "RDS instance class. db.t3.micro for dev, db.t3.medium+ for prod."
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "Initial database name."
  type        = string
  default     = "data_pipeline"
}

variable "db_username" {
  description = "Master DB username."
  type        = string
  default     = "datazoo_admin"
}

variable "allocated_storage_gb" {
  type    = number
  default = 20
}

variable "max_allocated_storage_gb" {
  description = "Upper limit for storage autoscaling."
  type        = number
  default     = 100
}

variable "multi_az" {
  description = "Enable Multi-AZ for high availability (prod: true, dev: false)."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Days to retain automated backups. 0 disables backups."
  type        = number
  default     = 7
}
