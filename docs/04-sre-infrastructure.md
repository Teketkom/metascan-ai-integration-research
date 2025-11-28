# SRE Инфраструктурный план для Metascan AI Integration

## Оглавление
- [Executive Summary](#executive-summary)
- [Текущее состояние](#текущее-состояние)
- [Целевая архитектура](#целевая-архитектура)
- [Инфраструктурный минимум](#инфраструктурный-минимум)
- [Инфраструктурный оптимум](#инфраструктурный-оптимум)
- [ML/AI инфраструктура](#mlai-инфраструктура)
- [Мониторинг и observability](#мониторинг-и-observability)
- [Security и compliance](#security-и-compliance)
- [План миграции](#план-миграции)
- [Cost estimation](#cost-estimation)

---

## Executive Summary

**Цель:** Спроектировать оптимальную SRE-инфраструктуру для Metascan с интеграцией AI/ML компонентов.

**Ключевые принципы:**
- 🎯 Cloud-native подход (Kubernetes-first)
- 📊 Observability по умолчанию (metrics, logs, traces)
- 🔒 Security by design (zero trust, least privilege)
- 💰 FinOps оптимизация (cost-aware infrastructure)
- 🚀 GitOps deployment (Infrastructure as Code)
- 🔄 Автомасштабирование (HPA, VPA, cluster autoscaler)

**Целевые SLO:**
```yaml
Availability:        99.9% (43.2 min downtime/month)
API Latency p95:     < 500ms
API Latency p99:     < 1000ms
Scan Throughput:     > 450K domains/day
ML Inference p95:    < 200ms
Error Rate:          < 1%
```

---

## Текущее состояние

### Существующая инфраструктура (предполагаемая)

```yaml
Compute:
  - 300+ scanning servers
  - Mixed environment (bare metal + cloud)
  - Manual scaling
  
Storage:
  - PostgreSQL (primary database)
  - Redis (cache)
  - File storage (reports)
  
Networking:
  - Nginx/HAProxy (load balancing)
  - Basic CDN
  
Monitoring:
  - Basic metrics
  - Log aggregation (limited)
  
Deployment:
  - Semi-manual
  - No CI/CD automation
```

### Проблемы и ограничения

❌ **Масштабирование:** Ручное, медленное  
❌ **Observability:** Фрагментированный мониторинг  
❌ **Deployment:** Долгий time-to-market  
❌ **Cost control:** Нет FinOps практик  
❌ **ML готовность:** Отсутствует ML инфраструктура  
❌ **DR:** Ограниченные возможности disaster recovery  

---

## Целевая архитектура

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     EDGE LAYER                                  │
├─────────────────────────────────────────────────────────────────┤
│  Cloudflare CDN + DDoS Protection                               │
│  ├─> WAF (Web Application Firewall)                            │
│  ├─> Rate Limiting                                              │
│  └─> SSL/TLS Termination                                        │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                  LOAD BALANCING LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│  AWS ALB / NLB + Istio Service Mesh                             │
│  ├─> L7 Load Balancing                                          │
│  ├─> Health Checks                                              │
│  ├─> Traffic Splitting (A/B, Canary)                           │
│  └─> mTLS Encryption                                            │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│               KUBERNETES CLUSTER (EKS)                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │  API Services    │  │  Scanning Workers│                    │
│  │  - REST API      │  │  - Nmap/Masscan  │                    │
│  │  - GraphQL       │  │  - Custom scanners│                   │
│  │  - WebSockets    │  │  - Lua NSE       │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ ML Inference     │  │ Data Processing  │                    │
│  │  - Triton Server │  │  - Spark Jobs    │                    │
│  │  - ONNX Runtime  │  │  - Kafka Streams │                    │
│  │  - GPU Nodes     │  │  - ETL Pipelines │                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ PostgreSQL  │  │ ClickHouse  │  │   Redis     │             │
│  │ (metadata)  │  │ (analytics) │  │  (cache)    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │    S3       │  │  OpenSearch │  │   Kafka     │             │
│  │  (storage)  │  │   (logs)    │  │  (events)   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│              OBSERVABILITY LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  Prometheus + Grafana + Loki + Tempo                            │
│  ├─> Metrics collection                                         │
│  ├─> Log aggregation                                            │
│  ├─> Distributed tracing                                        │
│  └─> Alerting (PagerDuty, Slack)                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Инфраструктурный минимум

### Minimum Viable Infrastructure (для старта)

#### Compute

```yaml
Kubernetes:
  Provider: AWS EKS / self-managed
  Nodes:
    - Control plane: 3 nodes (managed by EKS)
    - Worker nodes:
        General: 3x t3.xlarge (4 vCPU, 16 GB RAM)
        Scanning: 10x c6i.2xlarge (8 vCPU, 16 GB RAM)
  Auto-scaling:
    - HPA (Horizontal Pod Autoscaler)
    - Cluster Autoscaler
```

#### Storage

```yaml
Databases:
  PostgreSQL:
    Instance: db.t3.large (2 vCPU, 8 GB RAM)
    Storage: 500 GB SSD
    Backup: Daily snapshots
  
  Redis:
    Instance: cache.t3.medium (2 vCPU, 6.1 GB RAM)
    Replication: Single AZ
  
  Object Storage:
    S3: Standard tier
    Lifecycle: Archive to Glacier after 90 days
```

#### Networking

```yaml
Load Balancing:
  - AWS ALB (Application Load Balancer)
  - Internal: Kubernetes Ingress (Nginx)

CDN:
  - CloudFront (basic configuration)

DNS:
  - Route 53
```

#### Monitoring (Basic)

```yaml
Metrics:
  - Prometheus (in-cluster)
  - Grafana (basic dashboards)

Logs:
  - CloudWatch Logs
  - Retention: 30 days

Alerting:
  - Email notifications
  - Slack integration
```

### Стоимость минимума

```
Compute (EKS + EC2):      $2,500/month
Databases (RDS, Redis):   $800/month
Storage (S3, EBS):        $500/month
Networking (ALB, data):   $300/month
Monitoring:               $200/month
───────────────────────────────────────
ТОТАЛ:                    ~$4,300/month (~₽430K/month)
```

---

## Инфраструктурный оптимум

### Production-Grade Infrastructure

#### Compute

```yaml
Kubernetes:
  Provider: AWS EKS (Managed)
  Version: 1.28+
  
  Node Groups:
    General:
      - Type: t3.xlarge
      - Count: 5-20 (auto-scaled)
      - AZ: Multi-AZ (3 zones)
    
    Compute-Optimized (Scanning):
      - Type: c6i.4xlarge (16 vCPU, 32 GB)
      - Count: 10-50 (auto-scaled)
      - Spot instances: 60% savings
    
    Memory-Optimized (Data Processing):
      - Type: r6i.2xlarge (8 vCPU, 64 GB)
      - Count: 3-10 (auto-scaled)
    
    GPU (ML Inference):
      - Type: g4dn.xlarge (NVIDIA T4)
      - Count: 2-10 (auto-scaled)
      - Reserved instances: Cost savings
  
  Add-ons:
    - AWS VPC CNI
    - CoreDNS
    - kube-proxy
    - EBS CSI Driver
    - EFS CSI Driver
```

#### Storage

```yaml
Databases:
  PostgreSQL:
    Instance: db.r6i.2xlarge (8 vCPU, 64 GB)
    Storage: 2 TB SSD (io2, 10K IOPS)
    Multi-AZ: Yes
    Read replicas: 2
    Backup:
      - Automated daily
      - Point-in-time recovery (7 days)
      - Cross-region backup
  
  ClickHouse:
    Deployment: K8s StatefulSet
    Nodes: 3x r6i.4xlarge (16 vCPU, 128 GB)
    Storage: 10 TB NVMe SSD
    Replication: 2 replicas
  
  Redis:
    Instance: cache.r6g.xlarge (4 vCPU, 26 GB)
    Cluster mode: Enabled
    Shards: 3
    Replicas per shard: 2
    Multi-AZ: Yes
  
  Object Storage:
    S3:
      - Standard: Hot data (< 30 days)
      - Intelligent-Tiering: Warm data
      - Glacier: Cold data (> 180 days)
    MinIO (On-prem cache): 50 TB
```

#### Networking

```yaml
Load Balancing:
  External:
    - AWS ALB (Application Load Balancer)
    - AWS NLB (Network Load Balancer for TCP)
  
  Internal:
    - Istio Service Mesh
    - Envoy Proxy
  
  Features:
    - Traffic splitting (A/B, Canary)
    - Circuit breaking
    - Retry policies
    - Request mirroring

CDN:
  - CloudFront (global edge locations)
  - Custom cache behaviors
  - Lambda@Edge for dynamic content

DNS:
  - Route 53
  - Health checks
  - Geolocation routing
  - Failover policies

Security:
  - AWS WAF
  - Shield Standard (DDoS)
  - Shield Advanced (optional)
```

#### Message Queue

```yaml
Kafka:
  Deployment: AWS MSK (Managed Streaming for Kafka)
  Brokers: 3 (Multi-AZ)
  Instance: kafka.m5.xlarge
  Storage: 1 TB per broker
  
Alternative:
  NATS:
    Deployment: K8s StatefulSet
    Nodes: 3
    JetStream: Enabled
```

### Стоимость оптимума

```
Compute (EKS + EC2):
  - General nodes:        $1,500/month
  - Scanning nodes:       $4,000/month (with Spot)
  - Memory nodes:         $2,000/month
  - GPU nodes:            $3,000/month (Reserved)
  
Databases:
  - PostgreSQL RDS:       $2,500/month
  - ClickHouse:           $3,500/month
  - Redis cluster:        $1,200/month
  
Storage:
  - S3 (100 TB):          $2,300/month
  - EBS volumes:          $1,500/month
  
Networking:
  - ALB/NLB:              $500/month
  - Data transfer:        $2,000/month
  - CloudFront:           $1,000/month
  
Message Queue:
  - Kafka MSK:            $1,500/month
  
Monitoring:
  - Prometheus/Grafana:   $500/month
  - VictoriaMetrics:      $800/month
  - Loki:                 $600/month
  
Security:
  - WAF:                  $300/month
  - Secrets Manager:      $200/month
───────────────────────────────────────────
ТОТАЛ:                  ~$28,900/month (~₽2.9M/month)
```

---

## ML/AI инфраструктура

### ML Platform Components

#### Training Infrastructure

```yaml
Compute:
  GPU Cluster:
    - Nodes: 5-10x g5.12xlarge (NVIDIA A10G)
    - Spot instances for cost savings
    - Auto-scaling based on job queue
  
  Distributed Training:
    - Kubeflow
    - Horovod
    - Ray Cluster

Storage:
  Training Data:
    - S3: Raw datasets
    - EFS: Shared training workspace
    - FSx for Lustre: High-performance training
  
  Model Registry:
    - MLflow Model Registry
    - Artifact Store: S3
```

#### Inference Infrastructure

```yaml
Serving:
  Triton Inference Server:
    - Deployment: K8s Deployment
    - Replicas: 3-20 (HPA)
    - GPU: g4dn.xlarge (NVIDIA T4)
    - Features:
        - Model versioning
        - A/B testing
        - Dynamic batching
        - Multi-model serving
  
  ONNX Runtime:
    - CPU inference for lightweight models
    - Replicas: 5-50 (HPA)

API Gateway:
  - Kong / Apigee
  - Rate limiting
  - Authentication
  - Request transformation
```

#### MLOps Tools

```yaml
Experiment Tracking:
  - MLflow
  - Neptune.ai
  - Weights & Biases (optional)

Orchestration:
  - Kubeflow Pipelines
  - Airflow
  - Argo Workflows

Feature Store:
  - Feast
  - Tecton (optional)

Data Versioning:
  - DVC (Data Version Control)
  - LakeFS

Model Monitoring:
  - Evidently AI
  - Seldon Alibi Detect
  - Custom metrics (Prometheus)
```

### ML Infrastructure Diagram

```
┌─────────────────────────────────────────────────────────┐
│              DATA PREPARATION                           │
├─────────────────────────────────────────────────────────┤
│  S3 (Raw Data) → Spark → Feature Store → S3 (Features) │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              MODEL TRAINING                             │
├─────────────────────────────────────────────────────────┤
│  Kubeflow Pipeline                                      │
│  ├─> GPU Cluster (g5.12xlarge)                         │
│  ├─> Distributed Training (Horovod)                    │
│  ├─> Experiment Tracking (MLflow)                      │
│  └─> Model Registry                                     │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              MODEL VALIDATION                           │
├─────────────────────────────────────────────────────────┤
│  ├─> Offline metrics evaluation                        │
│  ├─> A/B testing framework                             │
│  └─> Model approval workflow                           │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              MODEL DEPLOYMENT                           │
├─────────────────────────────────────────────────────────┤
│  Triton Inference Server (K8s)                          │
│  ├─> Canary deployment                                  │
│  ├─> Auto-scaling (HPA)                                │
│  ├─> GPU nodes (g4dn.xlarge)                           │
│  └─> Load balancing (Istio)                            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              MODEL MONITORING                           │
├─────────────────────────────────────────────────────────┤
│  ├─> Data drift detection (Evidently)                  │
│  ├─> Model performance metrics (Prometheus)            │
│  ├─> Prediction latency (p95, p99)                     │
│  └─> Alerting (PagerDuty)                              │
└─────────────────────────────────────────────────────────┘
```

---

## Мониторинг и Observability

### Metrics Stack

```yaml
Prometheus:
  Deployment: K8s StatefulSet
  Retention: 15 days
  Storage: 500 GB SSD
  
  Scrapers:
    - Node Exporter (system metrics)
    - kube-state-metrics (K8s resources)
    - Custom app metrics (business KPIs)
  
VictoriaMetrics:
  Purpose: Long-term storage (1 year)
  Cluster mode: Yes
  Storage: 2 TB
  
Grafana:
  Deployment: K8s Deployment
  Dashboards:
    - Infrastructure overview
    - Application metrics
    - ML model performance
    - Business KPIs
    - SLO/SLI tracking
  
AlertManager:
  Integrations:
    - PagerDuty (critical)
    - Slack (warnings)
    - Email (informational)
```

### Logging Stack

```yaml
Loki:
  Deployment: K8s StatefulSet
  Retention: 30 days
  Storage: 1 TB SSD
  
Promtail:
  Deployment: DaemonSet (every node)
  Log sources:
    - Container logs
    - System logs
    - Audit logs
  
Alternative:
  OpenSearch:
    Nodes: 3x r6i.xlarge
    Storage: 2 TB
    Retention: 60 days
    Curator: Automated cleanup
```

### Tracing Stack

```yaml
Tempo:
  Deployment: K8s StatefulSet
  Backend: S3
  Retention: 7 days
  
OpenTelemetry:
  Collector: DaemonSet
  Instrumentation:
    - Automatic (Istio sidecars)
    - Manual (SDK in apps)
  
Alternative:
  Jaeger:
    Storage: OpenSearch
    Sampling: Adaptive
```

### Key Metrics to Track

```yaml
Infrastructure:
  - CPU/Memory utilization
  - Disk I/O
  - Network throughput
  - Node health
  
Application:
  - Request rate
  - Error rate
  - Response time (p50, p95, p99)
  - Throughput (domains/sec)
  
ML Models:
  - Inference latency
  - Prediction accuracy
  - Data drift
  - Model staleness
  
Business:
  - Active users
  - Scans completed
  - Vulnerabilities detected
  - Revenue metrics
```

---

## Security и Compliance

### Security Layers

#### Network Security

```yaml
Perimeter:
  - WAF (Web Application Firewall)
  - DDoS protection (Shield)
  - Rate limiting
  
Network Segmentation:
  - VPC with private/public subnets
  - Security groups
  - Network ACLs
  - PrivateLink for AWS services
  
Service Mesh:
  - mTLS between services (Istio)
  - Zero-trust networking
  - Network policies (Calico)
```

#### Identity & Access

```yaml
Authentication:
  - SSO (SAML/OIDC)
  - MFA required
  - Service accounts with IRSA
  
Authorization:
  - RBAC (Role-Based Access Control)
  - OPA (Open Policy Agent)
  - Least privilege principle
  
Secrets Management:
  - AWS Secrets Manager
  - HashiCorp Vault (alternative)
  - External Secrets Operator (K8s)
```

#### Runtime Security

```yaml
Container Security:
  - Image scanning (Trivy, Aqua)
  - Admission control (OPA Gatekeeper)
  - Pod Security Standards
  - Read-only root filesystem
  
Runtime Detection:
  - Falco (runtime security)
  - eBPF-based monitoring
  - Anomaly detection
  
Vulnerability Management:
  - Regular CVE scanning
  - Automated patching
  - Security advisories
```

#### Data Security

```yaml
Encryption:
  At Rest:
    - EBS encryption (KMS)
    - S3 encryption (SSE-KMS)
    - Database encryption (RDS)
  
  In Transit:
    - TLS 1.3
    - mTLS (service-to-service)
    - VPN for remote access
  
Data Classification:
  - PII identification
  - Data masking
  - Anonymization
  
Backup & DR:
  - Automated backups
  - Cross-region replication
  - Point-in-time recovery
  - RPO: < 1 hour
  - RTO: < 4 hours
```

### Compliance

```yaml
Standards:
  - ISO 27001
  - PCI DSS (if processing payments)
  - GDPR (data privacy)
  - Russian Federal Law 152-FZ (personal data)
  
Auditing:
  - CloudTrail (AWS API calls)
  - K8s audit logs
  - Database audit logs
  - Access logs retention: 1 year
  
Compliance Automation:
  - AWS Config
  - Prowler (security checks)
  - Compliance-as-Code (OPA policies)
```

---

## План миграции

### Фаза 1: Подготовка (Месяц 1-2)

```yaml
Инфраструктура:
  ✓ Создать AWS аккаунт и настроить Organizations
  ✓ Настроить VPC, subnets, security groups
  ✓ Развернуть EKS кластер (dev environment)
  ✓ Настроить CI/CD (GitHub Actions + ArgoCD)
  
Образование:
  ✓ Обучение команды Kubernetes
  ✓ Обучение команды GitOps
  ✓ SRE best practices
```

### Фаза 2: MVP Миграция (Месяц 3-4)

```yaml
Приложения:
  ✓ Контейнеризация основных сервисов
  ✓ Создание Helm charts
  ✓ Миграция stateless сервисов
  ✓ Настройка базового мониторинга
  
Данные:
  ✓ Миграция PostgreSQL в RDS
  ✓ Миграция Redis в ElastiCache
  ✓ Настройка S3 для файлов
  
Тестирование:
  ✓ Load testing
  ✓ Failover testing
  ✓ Performance benchmarking
```

### Фаза 3: Production Rollout (Месяц 5-6)

```yaml
Миграция:
  ✓ Canary deployment в production
  ✓ Постепенный перенос трафика (10% → 50% → 100%)
  ✓ Мониторинг SLO
  ✓ Готовность к rollback
  
Optimization:
  ✓ Auto-scaling настройка
  ✓ Cost optimization
  ✓ Performance tuning
```

### Фаза 4: ML Platform (Месяц 7-9)

```yaml
ML Infrastructure:
  ✓ Развертывание Kubeflow
  ✓ Настройка MLflow
  ✓ GPU node pools
  ✓ Feature store
  
ML Pipelines:
  ✓ Data preprocessing pipeline
  ✓ Training pipeline
  ✓ Inference deployment
  ✓ Model monitoring
```

### Фаза 5: Advanced Features (Месяц 10-12)

```yaml
Advanced:
  ✓ Service mesh (Istio) полное внедрение
  ✓ Advanced observability (distributed tracing)
  ✓ Chaos engineering (Chaos Mesh)
  ✓ Multi-region deployment
  ✓ Disaster recovery automation
```

---

## Cost Estimation

### Сравнение стоимости (месячная)

| Компонент | Минимум | Оптимум | Enterprise |
|-----------|---------|---------|------------|
| **Compute** | $2,500 | $10,500 | $25,000 |
| **Storage** | $1,300 | $7,200 | $15,000 |
| **Network** | $300 | $3,500 | $8,000 |
| **Databases** | $800 | $7,200 | $15,000 |
| **ML/AI** | - | $3,000 | $10,000 |
| **Monitoring** | $200 | $1,900 | $5,000 |
| **Security** | - | $500 | $2,000 |
| **Support** | - | $2,000 | $5,000 |
| **ИТОГО** | **$5,100** | **$35,800** | **$85,000** |
| **В рублях** | **₽510K** | **₽3.6M** | **₽8.5M** |

### Оптимизация стоимости

```yaml
Reserved Instances:
  - Savings: 30-50%
  - Commitment: 1-3 years
  
Spot Instances:
  - Savings: 60-90%
  - Use cases: Batch jobs, scanning workers
  
Savings Plans:
  - Compute savings: 20-40%
  - Flexible across services
  
Right-sizing:
  - Regular resource analysis
  - Automated recommendations
  - Savings: 10-30%
  
Storage Optimization:
  - S3 Intelligent-Tiering: Auto savings
  - EBS volume type optimization
  - Cleanup unused resources
```

---

## SRE Metrics & SLO

### Service Level Objectives

```yaml
Availability SLO:
  Target: 99.9%
  Error budget: 43.2 minutes/month
  Measurement: Uptime checks (external)
  
Latency SLO:
  API p95: < 500ms
  API p99: < 1000ms
  Measurement: Server-side metrics
  
Throughput SLO:
  Scans/day: > 450,000
  Measurement: Business metrics
  
Error Rate SLO:
  5xx errors: < 0.1%
  4xx errors: < 1%
  Measurement: HTTP status codes
```

### Error Budget Policy

```yaml
Error Budget > 80%:
  - Focus on features
  - Aggressive deployments
  - Innovation encouraged
  
Error Budget 50-80%:
  - Balanced approach
  - Standard deployment process
  - Monitor closely
  
Error Budget 20-50%:
  - Stability focus
  - Deployment freeze for non-critical
  - Post-mortem required
  
Error Budget < 20%:
  - Full deployment freeze
  - Emergency bug fixes only
  - All hands on stability
```

---

## Заключение

### Рекомендуемый путь

**Для начала (0-3 месяца):**
1. ✅ Развернуть **минимальную инфраструктуру** в AWS
2. ✅ Контейнеризировать критичные сервисы
3. ✅ Настроить базовый мониторинг
4. ✅ Внедрить CI/CD

**Для масштабирования (3-6 месяцев):**
1. ✅ Перейти на **оптимальную инфраструктуру**
2. ✅ Развернуть ML platform
3. ✅ Внедрить service mesh
4. ✅ Настроить advanced observability

**Для энтерпрайза (6-12 месяцев):**
1. ✅ Multi-region deployment
2. ✅ Full automation (GitOps)
3. ✅ Chaos engineering
4. ✅ Advanced ML capabilities

### KPI успеха

```yaml
Операционные:
  - Deployment frequency: Daily
  - Lead time: < 1 hour
  - MTTR: < 30 minutes
  - Change failure rate: < 5%
  
Бизнес:
  - Uptime: 99.9%+
  - Cost per scan: -40%
  - Time to market: -60%
  - Developer productivity: +50%
```

---

**Дата:** 28 ноября 2024  
**Автор:** Dmitriy Shalimov (Senior SRE / Cloud Architect)  
**Проект:** Metascan AI Integration Research
