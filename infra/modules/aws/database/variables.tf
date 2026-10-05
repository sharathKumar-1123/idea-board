variable "name" {
  description = "Identifier for the RDS instance and related resources."
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Private subnets (at least two AZs) for the DB subnet group."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to connect on 5432 (the cluster's node security group)."
  type        = list(string)
}

variable "engine_version" {
  description = "PostgreSQL major version."
  type        = string
  default     = "16"
}

variable "instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Storage in GiB."
  type        = number
  default     = 20
}

variable "db_name" {
  type    = string
  default = "ideas"
}

variable "username" {
  type    = string
  default = "ideas"
}

variable "multi_az" {
  type    = bool
  default = false
}

variable "backup_retention_days" {
  type    = number
  default = 1
}

variable "deletion_protection" {
  description = "Protect against accidental deletion (also keeps a final snapshot on destroy)."
  type        = bool
  default     = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
