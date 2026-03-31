#!/usr/bin/env python3
"""
ML Model Training for Vulnerability Detection
Обучение ML моделей для детектирования уязвимостей

Author: Dmitriy Shalimov
Project: Metascan AI Integration
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging
import json
from pathlib import Path

# ML Libraries
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, f1_score
import xgboost as xgb
import lightgbm as lgb

# MLOps
import mlflow
import mlflow.sklearn
import mlflow.xgboost
import mlflow.lightgbm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VulnerabilityDetectionModel:
    """
    Модель детектирования уязвимостей на основе данных сканирования
    """
    
    SUPPORTED_MODELS = {
        'random_forest': RandomForestClassifier,
        'gradient_boosting': GradientBoostingClassifier,
        'xgboost': xgb.XGBClassifier,
        'lightgbm': lgb.LGBMClassifier,
        'logistic_regression': LogisticRegression
    }
    
    def __init__(self, model_type: str = 'xgboost', config: Optional[Dict] = None):
        """
        Инициализация модели
        
        Args:
            model_type: Тип модели (random_forest, xgboost, lightgbm, etc.)
            config: Конфигурация гиперпараметров
        """
        self.model_type = model_type
        self.config = config or self._get_default_config(model_type)
        self.model = None
        self.metrics = {}
        
    def _get_default_config(self, model_type: str) -> Dict:
        """Конфигурации по умолчанию"""
        configs = {
            'random_forest': {
                'n_estimators': 200,
                'max_depth': 15,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': 42,
                'n_jobs': -1
            },
            'gradient_boosting': {
                'n_estimators': 200,
                'learning_rate': 0.1,
                'max_depth': 5,
                'random_state': 42
            },
            'xgboost': {
                'n_estimators': 200,
                'learning_rate': 0.1,
                'max_depth': 7,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'objective': 'binary:logistic',
                'eval_metric': 'logloss',
                'random_state': 42,
                'n_jobs': -1
            },
            'lightgbm': {
                'n_estimators': 200,
                'learning_rate': 0.1,
                'max_depth': 7,
                'num_leaves': 31,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'objective': 'binary',
                'metric': 'binary_logloss',
                'random_state': 42,
                'n_jobs': -1
            },
            'logistic_regression': {
                'max_iter': 1000,
                'random_state': 42,
                'n_jobs': -1
            }
        }
        return configs.get(model_type, {})
    
    def train(self, 
              X_train: np.ndarray, 
              y_train: np.ndarray, 
              X_val: Optional[np.ndarray] = None,
              y_val: Optional[np.ndarray] = None,
              mlflow_tracking: bool = True) -> None:
        """
        Обучение модели
        """
        logger.info(f"Training {self.model_type} model...")
        
        if mlflow_tracking:
            mlflow.start_run(run_name=f"{self.model_type}_vulnerability_detection")
            mlflow.log_params(self.config)
        
        # Инициализация модели
        model_class = self.SUPPORTED_MODELS[self.model_type]
        self.model = model_class(**self.config)
        
        # Обучение
        if self.model_type in ['xgboost', 'lightgbm'] and X_val is not None:
            # Early stopping для gradient boosting
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        else:
            self.model.fit(X_train, y_train)
        
        logger.info("Training completed.")
        
        # Валидация
        if X_val is not None and y_val is not None:
            self.evaluate(X_val, y_val, dataset_name='validation', mlflow_tracking=mlflow_tracking)
        
        if mlflow_tracking:
            # Сохранение модели в MLflow
            if self.model_type == 'xgboost':
                mlflow.xgboost.log_model(self.model, "model")
            elif self.model_type == 'lightgbm':
                mlflow.lightgbm.log_model(self.model, "model")
            else:
                mlflow.sklearn.log_model(self.model, "model")
            
            mlflow.end_run()
    
    def evaluate(self, 
                 X_test: np.ndarray, 
                 y_test: np.ndarray, 
                 dataset_name: str = 'test',
                 mlflow_tracking: bool = True) -> Dict:
        """
        Оценка модели
        """
        logger.info(f"Evaluating on {dataset_name} set...")
        
        # Предсказания
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        
        # Метрики
        metrics = {
            'accuracy': np.mean(y_pred == y_test),
            'f1_score': f1_score(y_test, y_pred),
            'roc_auc': roc_auc_score(y_test, y_pred_proba),
        }
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        metrics['confusion_matrix'] = cm.tolist()
        metrics['true_positives'] = int(cm[1, 1])
        metrics['false_positives'] = int(cm[0, 1])
        metrics['true_negatives'] = int(cm[0, 0])
        metrics['false_negatives'] = int(cm[1, 0])
        
        # Precision, Recall
        if metrics['true_positives'] + metrics['false_positives'] > 0:
            metrics['precision'] = metrics['true_positives'] / (metrics['true_positives'] + metrics['false_positives'])
        else:
            metrics['precision'] = 0.0
        
        if metrics['true_positives'] + metrics['false_negatives'] > 0:
            metrics['recall'] = metrics['true_positives'] / (metrics['true_positives'] + metrics['false_negatives'])
        else:
            metrics['recall'] = 0.0
        
        self.metrics[dataset_name] = metrics
        
        # Логирование в MLflow
        if mlflow_tracking:
            for key, value in metrics.items():
                if key != 'confusion_matrix':
                    mlflow.log_metric(f"{dataset_name}_{key}", value)
        
        # Вывод
        logger.info(f"\n{dataset_name.upper()} Metrics:")
        logger.info(f"  Accuracy:  {metrics['accuracy']:.4f}")
        logger.info(f"  Precision: {metrics['precision']:.4f}")
        logger.info(f"  Recall:    {metrics['recall']:.4f}")
        logger.info(f"  F1 Score:  {metrics['f1_score']:.4f}")
        logger.info(f"  ROC AUC:   {metrics['roc_auc']:.4f}")
        logger.info(f"  Confusion Matrix:\n{cm}")
        
        return metrics
    
    def get_feature_importance(self, feature_names: list) -> pd.DataFrame:
        """
        Получение важности признаков
        """
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            df = pd.DataFrame({
                'feature': feature_names,
                'importance': importances
            }).sort_values('importance', ascending=False)
            return df
        else:
            logger.warning("Model does not support feature importances")
            return pd.DataFrame()
    
    def save_model(self, file_path: str):
        """Сохранение модели"""
        import joblib
        joblib.dump({
            'model': self.model,
            'model_type': self.model_type,
            'config': self.config,
            'metrics': self.metrics
        }, file_path)
        logger.info(f"Model saved to {file_path}")


if __name__ == '__main__':
    # Пример использования
    from data_preprocessing import VulnerabilityDataPreprocessor
    
    # 1. Подготовка данных
    preprocessor = VulnerabilityDataPreprocessor()
    
    # Генерация примера данных
    np.random.seed(42)
    X_train = np.random.randn(1000, 50)
    y_train = np.random.randint(0, 2, 1000)
    X_val = np.random.randn(200, 50)
    y_val = np.random.randint(0, 2, 200)
    X_test = np.random.randn(200, 50)
    y_test = np.random.randint(0, 2, 200)
    
    # 2. Обучение модели
    model = VulnerabilityDetectionModel(model_type='xgboost')
    model.train(X_train, y_train, X_val, y_val, mlflow_tracking=False)
    
    # 3. Оценка
    metrics = model.evaluate(X_test, y_test, mlflow_tracking=False)
    
    print("\nTraining completed successfully!")
