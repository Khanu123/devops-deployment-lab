terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "devops-lab", ManagedBy = "Terraform" }
  }
}

variable "aws_region" {
  type    = string
  default = "eu-west-2"
}
variable "github_repository" {
  type    = string
  default = "Khanu123/devops-deployment-lab"
}
variable "existing_oidc_provider_arn" {
  description = "Reuse the account's GitHub OIDC provider if one already exists."
  type        = string
  default     = ""
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "state" {
  bucket        = "devops-lab-state-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  force_destroy = false
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Deny", Principal = "*", Action = "s3:*"
      Resource  = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}
resource "aws_ecr_repository" "app" {
  name                 = "devops-lab"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "AES256"
  }
}
# Images are retained deliberately: automatic pruning can remove rollback targets.
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.existing_oidc_provider_arn == "" ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}
locals {
  oidc_arn = var.existing_oidc_provider_arn != "" ? var.existing_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn
  account  = data.aws_caller_identity.current.account_id
}
resource "aws_iam_role" "github" {
  name = "devops-lab-github"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = local.oidc_arn }, Action = "sts:AssumeRoleWithWebIdentity"
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:environment:devops-lab"
      } }
    }]
  })
}
resource "aws_iam_role_policy" "github" {
  role = aws_iam_role.github.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages"], Resource = aws_ecr_repository.app.arn },
      { Effect = "Allow", Action = ["ecs:DescribeServices", "ecs:UpdateService"], Resource = "arn:aws:ecs:${var.aws_region}:${local.account}:service/devops-lab/devops-lab" },
      # These ECS actions do not support resource-level permissions.
      { Effect = "Allow", Action = ["ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition"], Resource = "*" },
      { Effect = "Allow", Action = ["iam:PassRole"], Resource = ["arn:aws:iam::${local.account}:role/devops-lab-execution", "arn:aws:iam::${local.account}:role/devops-lab-task"], Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } } }
    ]
  })
}
output "state_bucket" {
  value = aws_s3_bucket.state.id
}
output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}
output "github_role_arn" {
  value = aws_iam_role.github.arn
}
