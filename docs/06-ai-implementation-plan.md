# AI Implementation Plan / План внедрения ИИ для Metascan

## High-Level Roadmap
1. Инвентаризация big data: классификация данных, сбор схем, выгрузка исторических сканов
2. Подготовка инфраструктуры: развертывание ML storage (S3/MinIO), ClickHouse, ETL пайплайн
3. Быстрое создание sklearn/XGBoost baseline моделей (risk scoring, anomaly detection)
4. Построение feature store (Feast) и ML Registry (MLflow)
5. Интеграция триггеров (on-scan/update): запуск predictions, генерация Lua-скриптов
6. Автоматизация CI/CD ML: DVC/Kubeflow pipelines, мониторинг drift
7. Запуск автоматического Lua генератора из LLM с audit log
8. MVP пилот: тестирование на выборке заказчика
9. Пост-MVP: Обогащение моделей, доработка продуктового API

## Implementation Steps

### Data Engineering
- Сбор всей истории сканов: raw logs → data lake (S3/MinIO)
- Pre-processing (pandas, PySpark): очистка, dedupe, enrichment
- Схемы данных: OpenAPI spec, data catalog, DVC yaml
- Feature extraction автоматизация: auto-feature pipeline (детектор критичных портов, scoring TLS+headers)

### ML Ops
- MLflow + Kubeflow deployment (pipeline CI, model registry, versioning)
- Разделение моделей: risk scoring/XGBoost, anomaly/unsupervised, LLM enrichment/classification
- Версионирование моделей (prod/canary/test)
- Валидация через Evidently (drift, метрики)

### Inference/Serving
- Контейнеризация Triton/ONNX: GPU/CPU (TorchServe/TensorFlow Serving)
- Экспонирование REST, gRPC, batch jobs (FastAPI/Flask)
- Генерация Lua/PoC-скриптов в моменте (LLM prompt2Lua)

### Security/Compliance
- Sandbox для моделей (Firecracker, k8s PodSecurityPolicy)
- Реализация secrets/mTLS API gateway (OPA, Kyverno)
- Мониторинг и аудит inference pipeline

### Automation/Integration
- Полная интеграция с Metascan API (push notifications, webhooks)
- Autoscaling ML-Inference (KEDA, HPA metrics)
- Обогащение отчётов с помощью LLM
- Агент-интегратор для orchestration: реагирование на инциденты

## Цели/метрики успеха
- Время inference <500мс
- Уровень FP <8%
- ROI AI запуска >200%
- Полный drift monitoring

**Документ подготовлен:** 26.11.2025 (AI Architect)
# Metascan AI Integration Research
