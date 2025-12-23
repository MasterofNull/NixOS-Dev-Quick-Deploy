"""
MindsDB Integration Client for AIDB MCP
Provides interface to MindsDB AI data platform for predictive analytics and ML workflows
"""

import logging
import httpx
import asyncio
import os
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MindsDBModelStatus(Enum):
    """MindsDB model training status"""
    GENERATING = "generating"
    TRAINING = "training"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class MindsDBModel:
    """MindsDB predictive model"""
    name: str
    status: MindsDBModelStatus
    accuracy: Optional[float] = None
    predict_column: Optional[str] = None
    training_time: Optional[float] = None


@dataclass
class MindsDBPrediction:
    """Prediction result from MindsDB model"""
    prediction: Any
    confidence: Optional[float] = None
    explanation: Optional[Dict[str, Any]] = None


class MindsDBClient:
    """
    Client for interacting with MindsDB AI data platform

    Integrates with:
    - AIDB PostgreSQL database
    - Local llama.cpp runtime for AI-enhanced predictions
    - CodeMachine workflows
    - Redis for caching

    Provides:
    - Automated ML model creation
    - Time-series forecasting
    - Classification and regression
    - AI-enhanced data queries
    - MCP protocol support
    """

    def __init__(
        self,
        http_url: str = "http://mindsdb:47334",
        postgres_url: str = "postgresql://mindsdb@mindsdb:47336",
        mcp_url: str = "http://mindsdb:47337"
    ):
        self.http_url = http_url
        self.postgres_url = postgres_url
        self.mcp_url = mcp_url
        self.http_client = httpx.AsyncClient(timeout=300.0)

    async def health_check(self) -> Dict[str, bool]:
        """Check if MindsDB services are available"""
        health_status = {}

        # Check HTTP API
        try:
            response = await self.http_client.get(f"{self.http_url}/api/status")
            health_status["http"] = response.status_code == 200
        except Exception as e:
            logger.error(f"MindsDB HTTP health check failed: {e}")
            health_status["http"] = False

        # Check MCP API
        try:
            response = await self.http_client.get(f"{self.mcp_url}/health")
            health_status["mcp"] = response.status_code == 200
        except Exception as e:
            logger.error(f"MindsDB MCP health check failed: {e}")
            health_status["mcp"] = False

        return health_status

    async def execute_sql(self, query: str) -> Dict[str, Any]:
        """
        Execute MindsDB SQL query via HTTP API

        Args:
            query: MindsDB SQL query

        Returns:
            Query results as dict
        """
        try:
            response = await self.http_client.post(
                f"{self.http_url}/api/sql/query",
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"MindsDB SQL execution failed: {e}")
            raise

    async def create_database_connection(
        self,
        name: str,
        engine: str,
        parameters: Dict[str, Any]
    ) -> bool:
        """
        Create database connection in MindsDB

        Args:
            name: Connection name
            engine: Database engine (postgres, mysql, etc.)
            parameters: Connection parameters (host, port, user, password, database)

        Returns:
            True if successful
        """
        params_str = ", ".join([f'"{k}": "{v}"' for k, v in parameters.items()])

        query = f"""
        CREATE DATABASE {name}
        WITH ENGINE = '{engine}',
        PARAMETERS = {{ {params_str} }};
        """

        try:
            await self.execute_sql(query)
            logger.info(f"Created MindsDB database connection: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create database connection {name}: {e}")
            return False

    async def connect_to_aidb_postgres(self) -> bool:
        """
        Connect MindsDB to AIDB PostgreSQL database

        Creates a connection to access workflow data, agent metrics, etc.
        """
        parameters = {
            "host": os.getenv("AIDB_POSTGRES_HOST", "postgres"),
            "port": os.getenv("AIDB_POSTGRES_PORT", "5432"),
            "database": os.getenv("AIDB_POSTGRES_DB", "mcp"),
            "user": os.getenv("AIDB_POSTGRES_USER", "mcp"),
            "password": os.getenv("AIDB_POSTGRES_PASSWORD", "mcp_dev_password_change_me"),
            "schema": "public"
        }

        return await self.create_database_connection(
            name="aidb_postgres",
            engine="postgres",
            parameters=parameters
        )

    async def create_predictor(
        self,
        name: str,
        from_data: str,
        predict_column: str,
        using_params: Optional[Dict[str, Any]] = None
    ) -> MindsDBModel:
        """
        Create ML predictor (model) in MindsDB

        Args:
            name: Predictor name
            from_data: Source table (e.g., 'aidb_postgres.codemachine_workflows')
            predict_column: Column to predict
            using_params: Optional training parameters

        Returns:
            MindsDBModel object
        """
        using_clause = ""
        if using_params:
            params_str = ", ".join([f"{k}='{v}'" for k, v in using_params.items()])
            using_clause = f"USING {params_str}"

        query = f"""
        CREATE MODEL {name}
        FROM {from_data}
        PREDICT {predict_column}
        {using_clause};
        """

        try:
            await self.execute_sql(query)
            logger.info(f"Created MindsDB predictor: {name}")

            # Wait for training to complete
            return await self.wait_for_model(name)

        except Exception as e:
            logger.error(f"Failed to create predictor {name}: {e}")
            raise

    async def get_model_status(self, name: str) -> MindsDBModel:
        """Get status of a MindsDB model"""
        query = f"SELECT * FROM models WHERE name = '{name}';"

        try:
            result = await self.execute_sql(query)
            data = result.get("data", [])[0] if result.get("data") else {}

            return MindsDBModel(
                name=name,
                status=MindsDBModelStatus(data.get("STATUS", "error").lower()),
                accuracy=data.get("ACCURACY"),
                predict_column=data.get("PREDICT"),
                training_time=data.get("TRAINING_TIME")
            )

        except Exception as e:
            logger.error(f"Failed to get model status for {name}: {e}")
            raise

    async def wait_for_model(
        self,
        name: str,
        poll_interval: int = 5,
        timeout: int = 600
    ) -> MindsDBModel:
        """Wait for model training to complete"""
        elapsed = 0

        while elapsed < timeout:
            model = await self.get_model_status(name)

            if model.status == MindsDBModelStatus.COMPLETE:
                logger.info(f"Model {name} training complete (accuracy: {model.accuracy})")
                return model
            elif model.status == MindsDBModelStatus.ERROR:
                raise Exception(f"Model {name} training failed")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Model {name} training timeout after {timeout}s")

    async def predict(
        self,
        model_name: str,
        input_data: Dict[str, Any]
    ) -> MindsDBPrediction:
        """
        Make prediction using trained model

        Args:
            model_name: Name of trained model
            input_data: Input features for prediction

        Returns:
            MindsDBPrediction with result and confidence
        """
        where_clause = " AND ".join([f"{k} = '{v}'" for k, v in input_data.items()])

        query = f"""
        SELECT *
        FROM {model_name}
        WHERE {where_clause};
        """

        try:
            result = await self.execute_sql(query)
            data = result.get("data", [])[0] if result.get("data") else {}

            # Extract prediction and confidence
            prediction_value = None
            confidence = None

            for key, value in data.items():
                if "predict" in key.lower() or "forecast" in key.lower():
                    prediction_value = value
                elif "confidence" in key.lower():
                    confidence = value

            return MindsDBPrediction(
                prediction=prediction_value,
                confidence=confidence,
                explanation=data
            )

        except Exception as e:
            logger.error(f"Prediction failed for model {model_name}: {e}")
            raise

    async def query_with_ai(
        self,
        natural_language_query: str,
        context_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute natural language query using AI

        Leverages MindsDB's AI capabilities to interpret and execute queries

        Args:
            natural_language_query: Query in natural language
            context_data: Optional context table/view

        Returns:
            Query results
        """
        # MindsDB supports natural language queries via AI
        query = f"""
        SELECT *
        FROM {context_data or 'aidb_postgres'}
        WHERE '{natural_language_query}';
        """

        return await self.execute_sql(query)

    async def create_time_series_forecast(
        self,
        name: str,
        source_table: str,
        target_column: str,
        time_column: str,
        horizon: int = 7,
        window: Optional[int] = None
    ) -> MindsDBModel:
        """
        Create time-series forecasting model

        Args:
            name: Model name
            source_table: Source data table
            target_column: Column to forecast
            time_column: Time/date column
            horizon: Forecast horizon (periods ahead)
            window: Historical window size

        Returns:
            Trained time-series model
        """
        using_params = {
            "timeseries_settings": {
                "order_by": time_column,
                "horizon": horizon
            }
        }

        if window:
            using_params["timeseries_settings"]["window"] = window

        return await self.create_predictor(
            name=name,
            from_data=source_table,
            predict_column=target_column,
            using_params=using_params
        )

    async def list_models(self) -> List[MindsDBModel]:
        """List all MindsDB models"""
        query = "SELECT * FROM models;"

        try:
            result = await self.execute_sql(query)
            models = []

            for data in result.get("data", []):
                models.append(MindsDBModel(
                    name=data.get("NAME"),
                    status=MindsDBModelStatus(data.get("STATUS", "error").lower()),
                    accuracy=data.get("ACCURACY"),
                    predict_column=data.get("PREDICT"),
                    training_time=data.get("TRAINING_TIME")
                ))

            return models

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def drop_model(self, name: str) -> bool:
        """Delete a MindsDB model"""
        query = f"DROP MODEL {name};"

        try:
            await self.execute_sql(query)
            logger.info(f"Dropped MindsDB model: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to drop model {name}: {e}")
            return False

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


# ============================================================================
# Integration Use Cases for AIDB MCP
# ============================================================================

async def predict_workflow_success_rate(
    mindsdb: MindsDBClient,
    workflow_spec: Dict[str, Any]
) -> float:
    """
    Predict CodeMachine workflow success rate using historical data

    Args:
        mindsdb: MindsDB client
        workflow_spec: Workflow specification

    Returns:
        Predicted success rate (0-1)
    """
    # Create predictor if not exists
    model_name = "workflow_success_predictor"

    try:
        await mindsdb.get_model_status(model_name)
    except:
        # Train new model
        await mindsdb.create_predictor(
            name=model_name,
            from_data="aidb_postgres.codemachine_workflows",
            predict_column="status",
            using_params={"model": "lightgbm"}
        )

    # Predict success
    prediction = await mindsdb.predict(
        model_name=model_name,
        input_data={
            "engines": workflow_spec.get("engines"),
            "parallel_execution": workflow_spec.get("parallel")
        }
    )

    return prediction.confidence or 0.5


async def forecast_agent_performance(
    mindsdb: MindsDBClient,
    agent_name: str,
    periods_ahead: int = 7
) -> List[float]:
    """
    Forecast llama.cpp inference performance metrics

    Args:
        mindsdb: MindsDB client
        agent_name: Name of agent (qwen-coder or deepseek-r1)
        periods_ahead: Number of periods to forecast

    Returns:
        List of forecasted performance scores
    """
    model_name = f"{agent_name}_performance_forecast"

    try:
        await mindsdb.get_model_status(model_name)
    except:
        # Create time-series model
        await mindsdb.create_time_series_forecast(
            name=model_name,
            source_table="aidb_postgres.agent_performance_metrics",
            target_column="success_rate",
            time_column="timestamp",
            horizon=periods_ahead
        )

    # Generate forecast
    result = await mindsdb.execute_sql(f"""
        SELECT success_rate
        FROM {model_name}
        WHERE agent_name = '{agent_name}'
        LIMIT {periods_ahead};
    """)

    return [row["success_rate"] for row in result.get("data", [])]


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example of using MindsDB with AIDB MCP"""

    client = MindsDBClient()

    # Health check
    health = await client.health_check()
    print(f"MindsDB health: {health}")

    # Connect to AIDB PostgreSQL
    await client.connect_to_aidb_postgres()

    # Create workflow success predictor
    model = await client.create_predictor(
        name="workflow_predictor",
        from_data="aidb_postgres.codemachine_workflows",
        predict_column="execution_time",
        using_params={"model": "lightgbm"}
    )
    print(f"Model trained: {model.name}, Accuracy: {model.accuracy}")

    # Make prediction
    prediction = await client.predict(
        model_name="workflow_predictor",
        input_data={
            "engines": "['qwen-coder']",
            "parallel_execution": "false"
        }
    )
    print(f"Predicted execution time: {prediction.prediction}s (confidence: {prediction.confidence})")

    # Natural language query
    result = await client.query_with_ai(
        natural_language_query="What are the top 5 fastest code generation agents?",
        context_data="aidb_postgres.agent_metrics"
    )
    print(f"AI query result: {result}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(example_usage())
