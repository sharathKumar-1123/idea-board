variable "name" {
  description = "EKS cluster name."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes <major>.<minor> version. null lets EKS pick its current default."
  type        = string
  default     = null
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Private subnets for the control plane ENIs and worker nodes."
  type        = list(string)
}

variable "node_instance_type" {
  type    = string
  default = "t3.small"
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "tags" {
  type    = map(string)
  default = {}
}
