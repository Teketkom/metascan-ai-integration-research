# AI Architecture For Metascan Platform

## 1. Архитектурная цель
Сделать всю платформу Metascan AI-assisted: сканирование, обогащение, анализ — через ML/LLM.

## 2. Обзор архитектуры (2025)
```
┌─────────────────────────────────────┐
│    Frontend (Web, API, CLI)         │
└─────────────────────────────────────┘
           │      │
       [User API, CLI]
           │      │
─────────────────────────────────────────
          ▼      ▼
┌─────────────────────────────────────┐
│   Backend Orchestration (K8s)       │
│   - API Gateway (Kong/Envoy)        │
│   - Auth+RBAC+Audit                 │
│   - ML Service API                  │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│        ML/LLM Layer:                │
│   — Feature extraction/ETL          │
│   — ML Model Serving (Triton/ONNX)  │
│   — Automated Lua/Script Generator  │
│   — Threat correlation (XGBoost)    │
│   — LLM Enrichment (OpenAI, Llama)  │
│   — AI postprocessing (Actions, triggers, alerts) │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Data Lake/Big Data (S3, ClickHouse, MinIO) │
│ — Итеративная обработка потоков         │
└─────────────────────────────────────┘
                                 
## 3. Ключевые узлы/Приложения
- **ML API:** Фреймворки FastAPI/Flask, TorchServe, Triton
- **Data Lake:** объектное S3, Datalake S3, ClickHouse (petabyte scale)
- **Batch Pipeline:** DVC + Kubeflow Pipelines
- **Serving pipeline:** MLflow, ONNX, FastAPI ML API

## 4. Запрос-ответ цепочки (AI pipeline)
User request (Analyze Domain) → API → ML Prediction+Lua Gen → Enrich+Threat Score → Response → Web/API

- Lua скрипты генерируются on-demand с помощью LLM модели и шаблонов.
- Тренировка ML/LLM моделей онлайн/офлайн.
- Интеграция внешних TI/XML feeds (Threat Intelligence).

## 5. Security/Isolation
- В каждом инстансе model-serving: sandbox (Firecracker/Kata)
- Ограничение на данные — data leakage контур и контроль доступа

## 6. Механизмы обновления/
- Rolling/blue-green updates моделей
- Monitoring input/output drift (Evidently, CLI tools)

## 7. Observability
- ML telemetry → Prometheus, Grafana, Loki
- Логи inference/предсказаний в отдельном log index

---
**Документ подготовлен:** 26.11.2025 (AI Architect)
# Metascan AI Integration Research
