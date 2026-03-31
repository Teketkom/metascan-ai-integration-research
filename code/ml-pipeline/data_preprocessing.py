#!/usr/bin/env python3
"""
Data Preprocessing Pipeline for Vulnerability Detection ML
Препроцессинг данных сканирования для обучения ML моделей

Author: Dmitriy Shalimov
Project: Metascan AI Integration
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import json
import logging
from datetime import datetime
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class VulnerabilityScanData:
    """Данные сканирования уязвимостей"""
    domain: str
    ip_address: str
    ports_open: List[int]
    services_detected: List[str]
    cve_detected: List[str]
    severity_scores: List[float]
    scan_timestamp: datetime
    response_headers: Dict[str, str]
    certificate_info: Optional[Dict]
    technology_stack: List[str]


class VulnerabilityDataPreprocessor:
    """
    Препроцессор данных уязвимостей для ML pipeline
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_names = []
        
    def load_scan_data(self, file_path: str, format: str = 'json') -> pd.DataFrame:
        """
        Загрузка данных сканирования
        
        Supported formats:
        - JSON: логи Metascan
        - CSV: экспортированные данные
        - Parquet: большие датасеты
        """
        logger.info(f"Loading scan data from {file_path} (format: {format})")
        
        if format == 'json':
            with open(file_path, 'r') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
        elif format == 'csv':
            df = pd.read_csv(file_path)
        elif format == 'parquet':
            df = pd.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Loaded {len(df)} records")
        return df
    
    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Извлечение признаков из сырых данных сканирования
        """
        logger.info("Extracting features...")
        
        features = pd.DataFrame()
        
        # 1. Числовые признаки
        features['num_open_ports'] = df['ports_open'].apply(lambda x: len(x) if isinstance(x, list) else 0)
        features['num_services'] = df['services_detected'].apply(lambda x: len(x) if isinstance(x, list) else 0)
        features['num_cves'] = df['cve_detected'].apply(lambda x: len(x) if isinstance(x, list) else 0)
        features['max_severity'] = df['severity_scores'].apply(
            lambda x: max(x) if isinstance(x, list) and len(x) > 0 else 0.0
        )
        features['avg_severity'] = df['severity_scores'].apply(
            lambda x: np.mean(x) if isinstance(x, list) and len(x) > 0 else 0.0
        )
        
        # 2. Порты (бинарные признаки для критичных портов)
        critical_ports = [21, 22, 23, 25, 80, 443, 3306, 3389, 5432, 8080, 8443]
        for port in critical_ports:
            features[f'port_{port}_open'] = df['ports_open'].apply(
                lambda x: 1 if isinstance(x, list) and port in x else 0
            )
        
        # 3. Технологический стек
        common_technologies = ['apache', 'nginx', 'php', 'python', 'java', 'nodejs', 'mysql', 'postgresql']
        for tech in common_technologies:
            features[f'tech_{tech}'] = df['technology_stack'].apply(
                lambda x: 1 if isinstance(x, list) and any(tech.lower() in str(t).lower() for t in x) else 0
            )
        
        # 4. SSL/TLS характеристики
        features['has_ssl'] = df['certificate_info'].apply(lambda x: 1 if x and isinstance(x, dict) else 0)
        features['ssl_expired'] = df['certificate_info'].apply(
            lambda x: 1 if x and x.get('expired', False) else 0
        )
        
        # 5. HTTP заголовки безопасности
        security_headers = ['X-Frame-Options', 'X-Content-Type-Options', 'Strict-Transport-Security', 'Content-Security-Policy']
        for header in security_headers:
            features[f'has_{header.lower().replace("-", "_")}'] = df['response_headers'].apply(
                lambda x: 1 if isinstance(x, dict) and header in x else 0
            )
        
        # 6. Временные признаки
        df['scan_timestamp'] = pd.to_datetime(df['scan_timestamp'])
        features['scan_hour'] = df['scan_timestamp'].dt.hour
        features['scan_day_of_week'] = df['scan_timestamp'].dt.dayofweek
        features['scan_month'] = df['scan_timestamp'].dt.month
        
        # 7. IP характеристики
        features['is_private_ip'] = df['ip_address'].apply(self._is_private_ip)
        features['ip_class'] = df['ip_address'].apply(self._get_ip_class)
        
        self.feature_names = features.columns.tolist()
        logger.info(f"Extracted {len(self.feature_names)} features")
        
        return features
    
    def _is_private_ip(self, ip: str) -> int:
        """Проверка, является ли IP приватным"""
        private_ranges = [
            r'^10\.',
            r'^172\.(1[6-9]|2[0-9]|3[01])\.',
            r'^192\.168\.'
        ]
        return 1 if any(re.match(pattern, ip) for pattern in private_ranges) else 0
    
    def _get_ip_class(self, ip: str) -> int:
        """Определение класса IP (A=0, B=1, C=2, D=3)"""
        try:
            first_octet = int(ip.split('.')[0])
            if first_octet < 128:
                return 0  # Class A
            elif first_octet < 192:
                return 1  # Class B
            elif first_octet < 224:
                return 2  # Class C
            else:
                return 3  # Class D/E
        except:
            return -1
    
    def create_target_labels(self, df: pd.DataFrame, target_column: str = 'is_vulnerable') -> np.ndarray:
        """
        Создание целевых меток для обучения
        
        Метка: 1 = уязвим, 0 = не уязвим
        """
        if target_column in df.columns:
            return df[target_column].values
        
        # Автоматическое определение по CVE
        labels = df['cve_detected'].apply(
            lambda x: 1 if isinstance(x, list) and len(x) > 0 else 0
        ).values
        
        logger.info(f"Created target labels: {np.sum(labels)} vulnerable, {len(labels) - np.sum(labels)} safe")
        return labels
    
    def normalize_features(self, features: pd.DataFrame, fit: bool = True) -> np.ndarray:
        """
        Нормализация признаков
        """
        logger.info("Normalizing features...")
        
        if fit:
            normalized = self.scaler.fit_transform(features)
        else:
            normalized = self.scaler.transform(features)
        
        return normalized
    
    def prepare_dataset(self, 
                       file_path: str, 
                       test_size: float = 0.2, 
                       val_size: float = 0.1,
                       random_state: int = 42) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Полный пайплайн подготовки датасета
        
        Returns:
            X_train, X_val, X_test, y_train, y_val, y_test
        """
        # 1. Загрузка
        df = self.load_scan_data(file_path)
        
        # 2. Извлечение признаков
        features = self.extract_features(df)
        
        # 3. Целевые метки
        labels = self.create_target_labels(df)
        
        # 4. Нормализация
        features_normalized = self.normalize_features(features, fit=True)
        
        # 5. Разбиение на тренировочную и тестовую выборки
        X_train_val, X_test, y_train_val, y_test = train_test_split(
            features_normalized, labels, test_size=test_size, random_state=random_state, stratify=labels
        )
        
        # 6. Разбиение тренировочной на train и validation
        val_size_adjusted = val_size / (1 - test_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val, y_train_val, test_size=val_size_adjusted, random_state=random_state, stratify=y_train_val
        )
        
        logger.info(f"Dataset split: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
        
        return X_train, X_val, X_test, y_train, y_val, y_test
    
    def save_preprocessor(self, file_path: str):
        """Сохранение препроцессора для инференса"""
        import joblib
        joblib.dump({
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'config': self.config
        }, file_path)
        logger.info(f"Preprocessor saved to {file_path}")


if __name__ == '__main__':
    # Пример использования
    preprocessor = VulnerabilityDataPreprocessor()
    
    # Генерация примера данных (для теста)
    sample_data = [
        {
            'domain': 'example.com',
            'ip_address': '192.168.1.100',
            'ports_open': [80, 443, 22],
            'services_detected': ['http', 'https', 'ssh'],
            'cve_detected': ['CVE-2024-1234'],
            'severity_scores': [7.5],
            'scan_timestamp': '2024-11-26T10:00:00',
            'response_headers': {'Server': 'Apache/2.4.41'},
            'certificate_info': {'expired': False},
            'technology_stack': ['Apache', 'PHP']
        }
    ]
    
    # Сохранение примера
    with open('/tmp/sample_scan_data.json', 'w') as f:
        json.dump(sample_data, f)
    
    # Обработка
    try:
        X_train, X_val, X_test, y_train, y_val, y_test = preprocessor.prepare_dataset('/tmp/sample_scan_data.json')
        print(f"\nDataset prepared successfully!")
        print(f"Features shape: {X_train.shape}")
        print(f"Feature names ({len(preprocessor.feature_names)}): {preprocessor.feature_names[:10]}...")
    except Exception as e:
        print(f"Error: {e}")
