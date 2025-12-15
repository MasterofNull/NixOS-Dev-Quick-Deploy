#!/usr/bin/env python3
"""
ML Engine - Integrated Machine Learning Capabilities
Replaces MindsDB with a lightweight, purpose-built ML system

Features:
- Time-series forecasting (stock prices, RF patterns)
- Anomaly detection (network traffic, signal analysis)
- Classification (threat detection, modulation types)
- Regression (trend analysis, prediction)

Co-authored by: Human & Claude 🚀
"""

from __future__ import annotations

import asyncio
import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

# ML libraries (lightweight, no heavy dependencies)
try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class MLEngine:
    """Integrated ML capabilities for AIDB MCP."""

    def __init__(self, engine: sa.Engine):
        self.engine = engine
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        if not ML_AVAILABLE:
            raise RuntimeError("scikit-learn not available - install with: pip install scikit-learn")

    async def train_forecast_model(
        self,
        model_name: str,
        table_name: str,
        target_column: str,
        feature_columns: List[str],
        lookback_hours: int = 24,
        forecast_horizon: int = 1,
    ) -> Dict[str, Any]:
        """
        Train a time-series forecasting model.

        Args:
            model_name: Unique name for the model
            table_name: Table containing time-series data (e.g., 'market_data')
            target_column: Column to predict (e.g., 'close')
            feature_columns: Columns to use as features
            lookback_hours: How many hours of history to use
            forecast_horizon: How many steps ahead to predict

        Returns:
            Training metrics and model info
        """
        def _train():
            session = self._session_factory()
            try:
                # Fetch training data
                query = f"""
                    SELECT time, {target_column}, {', '.join(feature_columns)}
                    FROM {table_name}
                    WHERE time >= NOW() - INTERVAL '{lookback_hours} hours'
                    ORDER BY time ASC
                """
                result = session.execute(sa.text(query))
                data = result.fetchall()

                if len(data) < 100:
                    raise ValueError(f"Insufficient data: need at least 100 rows, got {len(data)}")

                # Prepare features and target
                X = np.array([[row[i+2] for i in range(len(feature_columns))] for row in data[:-forecast_horizon]])
                y = np.array([row[1] for row in data[forecast_horizon:]])

                # Train/test split
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

                # Scale features
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)

                # Train model
                model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
                model.fit(X_train_scaled, y_train)

                # Evaluate
                train_score = model.score(X_train_scaled, y_train)
                test_score = model.score(X_test_scaled, y_test)

                # Serialize model and scaler
                model_artifact = pickle.dumps({'model': model, 'scaler': scaler})

                # Save to database
                stmt = sa.text("""
                    INSERT INTO ml_models (name, model_type, target_table, target_column, features, hyperparameters, model_artifact, metrics, status, last_trained_at)
                    VALUES (:name, :model_type, :target_table, :target_column, :features, :hyperparameters, :model_artifact, :metrics, :status, :last_trained_at)
                    ON CONFLICT (name) DO UPDATE SET
                        model_artifact = EXCLUDED.model_artifact,
                        metrics = EXCLUDED.metrics,
                        status = EXCLUDED.status,
                        last_trained_at = EXCLUDED.last_trained_at,
                        updated_at = NOW()
                """)

                session.execute(stmt, {
                    'name': model_name,
                    'model_type': 'forecast',
                    'target_table': table_name,
                    'target_column': target_column,
                    'features': json.dumps(feature_columns),
                    'hyperparameters': json.dumps({'lookback_hours': lookback_hours, 'forecast_horizon': forecast_horizon}),
                    'model_artifact': model_artifact,
                    'metrics': json.dumps({'train_r2': float(train_score), 'test_r2': float(test_score)}),
                    'status': 'ready',
                    'last_trained_at': datetime.now()
                })
                session.commit()

                return {
                    'model_name': model_name,
                    'status': 'trained',
                    'train_r2': float(train_score),
                    'test_r2': float(test_score),
                    'samples_trained': len(X_train),
                    'samples_tested': len(X_test)
                }
            finally:
                session.close()

        return await asyncio.to_thread(_train)

    async def train_anomaly_detector(
        self,
        model_name: str,
        table_name: str,
        feature_columns: List[str],
        contamination: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Train an anomaly detection model using Isolation Forest.

        Args:
            model_name: Unique name for the model
            table_name: Table containing data
            feature_columns: Columns to use as features
            contamination: Expected proportion of anomalies (0.0-0.5)

        Returns:
            Training metrics
        """
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            raise RuntimeError("scikit-learn required for anomaly detection")

        def _train():
            session = self._session_factory()
            try:
                query = f"SELECT {', '.join(feature_columns)} FROM {table_name} ORDER BY time DESC LIMIT 10000"
                result = session.execute(sa.text(query))
                data = np.array(result.fetchall())

                if len(data) < 100:
                    raise ValueError(f"Insufficient data: need at least 100 rows, got {len(data)}")

                # Scale features
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(data)

                # Train model
                model = IsolationForest(contamination=contamination, random_state=42)
                model.fit(X_scaled)

                # Detect anomalies in training set (for metrics)
                predictions = model.predict(X_scaled)
                anomaly_count = np.sum(predictions == -1)

                # Serialize
                model_artifact = pickle.dumps({'model': model, 'scaler': scaler})

                # Save
                stmt = sa.text("""
                    INSERT INTO ml_models (name, model_type, target_table, target_column, features, hyperparameters, model_artifact, metrics, status, last_trained_at)
                    VALUES (:name, :model_type, :target_table, :target_column, :features, :hyperparameters, :model_artifact, :metrics, :status, :last_trained_at)
                    ON CONFLICT (name) DO UPDATE SET
                        model_artifact = EXCLUDED.model_artifact,
                        metrics = EXCLUDED.metrics,
                        status = EXCLUDED.status,
                        last_trained_at = EXCLUDED.last_trained_at,
                        updated_at = NOW()
                """)

                session.execute(stmt, {
                    'name': model_name,
                    'model_type': 'anomaly_detection',
                    'target_table': table_name,
                    'target_column': 'anomaly_score',
                    'features': json.dumps(feature_columns),
                    'hyperparameters': json.dumps({'contamination': contamination}),
                    'model_artifact': model_artifact,
                    'metrics': json.dumps({'training_anomalies': int(anomaly_count), 'training_samples': len(data)}),
                    'status': 'ready',
                    'last_trained_at': datetime.now()
                })
                session.commit()

                return {
                    'model_name': model_name,
                    'status': 'trained',
                    'training_anomalies': int(anomaly_count),
                    'training_samples': len(data),
                    'contamination': contamination
                }
            finally:
                session.close()

        return await asyncio.to_thread(_train)

    async def predict(
        self,
        model_name: str,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Make predictions using a trained model.

        Args:
            model_name: Name of the trained model
            input_data: Feature values as dict

        Returns:
            Prediction results
        """
        def _predict():
            session = self._session_factory()
            try:
                # Load model
                query = sa.text("SELECT model_type, features, model_artifact FROM ml_models WHERE name = :name AND status = 'ready'")
                result = session.execute(query, {'name': model_name}).one_or_none()

                if not result:
                    raise ValueError(f"Model '{model_name}' not found or not ready")

                model_type, features_json, model_artifact = result
                features = json.loads(features_json)

                # Deserialize model
                model_data = pickle.loads(model_artifact)
                model = model_data['model']
                scaler = model_data['scaler']

                # Prepare input
                X = np.array([[input_data[f] for f in features]])
                X_scaled = scaler.transform(X)

                # Predict
                if model_type == 'forecast' or model_type == 'regression':
                    prediction = float(model.predict(X_scaled)[0])
                    confidence = None  # Could add prediction intervals
                elif model_type == 'anomaly_detection':
                    prediction = int(model.predict(X_scaled)[0])  # -1 for anomaly, 1 for normal
                    anomaly_score = float(model.score_samples(X_scaled)[0])
                    confidence = abs(anomaly_score)
                    prediction = {'is_anomaly': prediction == -1, 'anomaly_score': anomaly_score}
                elif model_type == 'classification':
                    prediction = int(model.predict(X_scaled)[0])
                    proba = model.predict_proba(X_scaled)[0]
                    confidence = float(max(proba))
                    prediction = {'class': prediction, 'probabilities': proba.tolist()}
                else:
                    raise ValueError(f"Unknown model type: {model_type}")

                # Store prediction
                stmt = sa.text("""
                    INSERT INTO ml_predictions (model_id, input_data, prediction, confidence)
                    SELECT id, :input_data, :prediction, :confidence
                    FROM ml_models WHERE name = :model_name
                """)
                session.execute(stmt, {
                    'input_data': json.dumps(input_data),
                    'prediction': json.dumps(prediction),
                    'confidence': confidence,
                    'model_name': model_name
                })
                session.commit()

                return {
                    'model_name': model_name,
                    'model_type': model_type,
                    'prediction': prediction,
                    'confidence': confidence,
                    'timestamp': datetime.now().isoformat()
                }
            finally:
                session.close()

        return await asyncio.to_thread(_predict)

    async def list_models(self) -> List[Dict[str, Any]]:
        """List all trained models."""
        def _list():
            session = self._session_factory()
            try:
                query = sa.text("""
                    SELECT name, model_type, target_table, target_column, metrics, status, last_trained_at, updated_at
                    FROM ml_models
                    ORDER BY updated_at DESC
                """)
                result = session.execute(query)
                return [
                    {
                        'name': row[0],
                        'model_type': row[1],
                        'target_table': row[2],
                        'target_column': row[3],
                        'metrics': json.loads(row[4]) if row[4] else {},
                        'status': row[5],
                        'last_trained_at': row[6].isoformat() if row[6] else None,
                        'updated_at': row[7].isoformat() if row[7] else None
                    }
                    for row in result
                ]
            finally:
                session.close()

        return await asyncio.to_thread(_list)

    async def get_model_metrics(self, model_name: str) -> Dict[str, Any]:
        """Get detailed metrics for a model."""
        def _get_metrics():
            session = self._session_factory()
            try:
                # Get model info
                query = sa.text("""
                    SELECT name, model_type, metrics, status, last_trained_at
                    FROM ml_models
                    WHERE name = :name
                """)
                result = session.execute(query, {'name': model_name}).one_or_none()

                if not result:
                    raise ValueError(f"Model '{model_name}' not found")

                # Get prediction count
                pred_query = sa.text("""
                    SELECT COUNT(*), AVG(confidence)
                    FROM ml_predictions mp
                    JOIN ml_models mm ON mp.model_id = mm.id
                    WHERE mm.name = :name
                """)
                pred_result = session.execute(pred_query, {'name': model_name}).one()

                return {
                    'model_name': result[0],
                    'model_type': result[1],
                    'training_metrics': json.loads(result[2]) if result[2] else {},
                    'status': result[3],
                    'last_trained_at': result[4].isoformat() if result[4] else None,
                    'prediction_count': pred_result[0],
                    'avg_confidence': float(pred_result[1]) if pred_result[1] else None
                }
            finally:
                session.close()

        return await asyncio.to_thread(_get_metrics)


class QuickMLHelpers:
    """Quick ML helpers for common use cases."""

    @staticmethod
    async def detect_rf_anomalies(ml_engine: MLEngine) -> Dict[str, Any]:
        """Detect anomalies in recent RF signals."""
        # Check if model exists
        models = await ml_engine.list_models()
        model_name = 'rf_anomaly_detector'

        if not any(m['name'] == model_name for m in models):
            # Train new model
            await ml_engine.train_anomaly_detector(
                model_name=model_name,
                table_name='rf_signals',
                feature_columns=['frequency', 'power_dbm', 'bandwidth'],
                contamination=0.05  # 5% expected anomalies
            )

        # Get recent signals and check for anomalies
        # (Implementation would query recent rf_signals and predict)
        return {'status': 'model_ready', 'model_name': model_name}

    @staticmethod
    async def forecast_stock_price(ml_engine: MLEngine, symbol: str, hours_ahead: int = 1) -> Dict[str, Any]:
        """Forecast stock price for given symbol."""
        model_name = f'stock_forecast_{symbol}'

        # Check if model exists
        models = await ml_engine.list_models()

        if not any(m['name'] == model_name for m in models):
            # Train new model
            await ml_engine.train_forecast_model(
                model_name=model_name,
                table_name='market_data',
                target_column='close',
                feature_columns=['open', 'high', 'low', 'volume'],
                lookback_hours=168,  # 1 week
                forecast_horizon=hours_ahead
            )

        # Make prediction (would need recent data)
        return {'status': 'model_ready', 'model_name': model_name}
