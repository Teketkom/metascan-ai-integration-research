# Terraform Configuration for Metascan AI Infrastructure
# Провизионинг облачной инфраструктуры для ML/AI

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
  
  backend "s3" {
    bucket         = "metascan-terraform-state"
    key            = "ml-infrastructure/terraform.tfstate"
    region         = "eu-central-1"
    encrypt        = true
    dynamodb_table = "terraform-lock"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "Metascan AI Integration"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Team        = "SRE"
    }
  }
}

# ===========================
# VPC и сеть
# ===========================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  
  name = "${var.project_name}-vpc"
  cidr = var.vpc_cidr
  
  azs             = data.aws_availability_zones.available.names
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs
  
  enable_nat_gateway   = true
  single_nat_gateway   = var.environment == "dev" ? true : false
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_iam_role  = true
  create_flow_log_cloudwatch_log_group = true
  
  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# ===========================
# EKS Cluster
# ===========================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"
  
  cluster_name    = "${var.project_name}-eks"
  cluster_version = "1.28"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  # Управление доступом
  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true
  
  # Encryption
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }
  
  # Node Groups
  eks_managed_node_groups = {
    # Основные рабочие ноды
    general = {
      name           = "general-workers"
      instance_types = ["t3.xlarge"]
      
      min_size     = 3
      max_size     = 10
      desired_size = 3
      
      labels = {
        role = "general"
      }
      
      taints = []
    }
    
    # ML ноды с GPU
    ml_gpu = {
      name           = "ml-gpu-workers"
      instance_types = ["g4dn.xlarge"]  # NVIDIA T4 GPU
      ami_type       = "AL2_x86_64_GPU"
      
      min_size     = 0
      max_size     = 5
      desired_size = 1
      
      labels = {
        role     = "ml-inference"
        hardware = "gpu"
      }
      
      taints = [
        {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NoSchedule"
        }
      ]
    }
    
    # Вычислительно интенсивные ноды (для обучения)
    compute_optimized = {
      name           = "compute-workers"
      instance_types = ["c6i.4xlarge"]
      
      min_size     = 0
      max_size     = 10
      desired_size = 2
      
      labels = {
        role = "ml-training"
      }
    }
  }
  
  # Cluster add-ons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }
}

# ===========================
# S3 Buckets
# ===========================

# Bucket для ML моделей
resource "aws_s3_bucket" "ml_models" {
  bucket = "${var.project_name}-ml-models-${var.environment}"
  
  tags = {
    Name = "ML Models Storage"
  }
}

resource "aws_s3_bucket_versioning" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
  }
}

# Bucket для данных сканирования
resource "aws_s3_bucket" "scan_data" {
  bucket = "${var.project_name}-scan-data-${var.environment}"
  
  tags = {
    Name = "Scan Data Storage"
  }
}

# ===========================
# RDS PostgreSQL (для MLflow)
# ===========================

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"
  
  identifier = "${var.project_name}-mlflow-db"
  
  engine               = "postgres"
  engine_version       = "15.4"
  family               = "postgres15"
  major_engine_version = "15"
  instance_class       = "db.t3.medium"
  
  allocated_storage     = 100
  max_allocated_storage = 500
  
  db_name  = "mlflow"
  username = "mlflow"
  port     = 5432
  
  multi_az               = var.environment == "prod" ? true : false
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]
  
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  
  deletion_protection = var.environment == "prod" ? true : false
  skip_final_snapshot = var.environment == "dev" ? true : false
  
  tags = {
    Name = "MLflow Database"
  }
}

# ===========================
# ElastiCache Redis (кеш)
# ===========================

module "redis" {
  source  = "terraform-aws-modules/elasticache/aws"
  version = "~> 1.0"
  
  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t3.medium"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  
  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.redis.id]
  
  snapshot_retention_limit = 5
  snapshot_window         = "03:00-05:00"
  
  tags = {
    Name = "ML Inference Cache"
  }
}

# ===========================
# KMS Keys
# ===========================

resource "aws_kms_key" "eks" {
  description             = "EKS Secret Encryption Key"
  deletion_window_in_days = 10
  enable_key_rotation     = true
  
  tags = {
    Name = "${var.project_name}-eks-key"
  }
}

resource "aws_kms_key" "s3" {
  description             = "S3 Bucket Encryption Key"
  deletion_window_in_days = 10
  enable_key_rotation     = true
  
  tags = {
    Name = "${var.project_name}-s3-key"
  }
}

# ===========================
# Security Groups
# ===========================

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "redis" {
  name        = "${var.project_name}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ===========================
# Outputs
# ===========================

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "rds_endpoint" {
  value = module.rds.db_instance_endpoint
}

output "redis_endpoint" {
  value = module.redis.configuration_endpoint
}

output "s3_ml_models_bucket" {
  value = aws_s3_bucket.ml_models.id
}
