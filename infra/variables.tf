# Copyright AnyCompany

variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (e.g. dev, prod)"
  type        = string
}

variable "project_name" {
  description = "Name of the project, used as a prefix for resource naming"
  type        = string
  default     = "customer-management"
}

variable "cognito_admin_group_name" {
  description = "Name of the Cognito user group granted admin (write) access"
  type        = string
  default     = "admin"
}
