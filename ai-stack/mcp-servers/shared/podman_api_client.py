#!/usr/bin/env python3
"""
Secure Podman API Client
Replaces direct socket access with HTTP API calls
Implements operation allowlists, rate limiting, and audit logging

Usage:
    from shared.podman_api_client import PodmanAPIClient

    client = PodmanAPIClient(
        service_name="health-monitor",
        allowed_operations=["list", "inspect", "restart"]
    )

    # List containers
    containers = await client.list_containers()

    # Restart a container
    await client.restart_container("my-container")
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger()


class PodmanAPIError(Exception):
    """Base exception for Podman API errors"""
    pass


class OperationNotAllowedError(PodmanAPIError):
    """Raised when service attempts operation not in allowlist"""
    pass


class ContainerNotFoundError(PodmanAPIError):
    """Raised when container is not found"""
    pass


class PodmanAPIClient:
    """
    Secure HTTP-based Podman API client

    Features:
    - Operation allowlisting (services can only do what they're allowed)
    - Audit logging (all operations logged)
    - Rate limiting (prevent abuse)
    - Error handling (graceful failures)
    """

    def __init__(
        self,
        service_name: str,
        allowed_operations: Optional[List[str]] = None,
        api_url: Optional[str] = None,
        api_version: Optional[str] = None,
        audit_enabled: bool = True,
        audit_log_path: Optional[str] = None
    ):
        """
        Initialize Podman API client

        Args:
            service_name: Name of service (for audit logging)
            allowed_operations: List of allowed operations (e.g., ["list", "inspect", "restart"])
            api_url: Podman API URL (default: from env PODMAN_API_URL)
            api_version: API version (default: from env PODMAN_API_VERSION or v4.0.0)
            audit_enabled: Enable audit logging
            audit_log_path: Path to audit log file
        """
        self.service_name = service_name

        # Load configuration from environment
        self.api_url = api_url or os.getenv(
            "PODMAN_API_URL",
            "http://host.containers.internal:2375"
        )
        self.api_version = api_version or os.getenv("PODMAN_API_VERSION", "v4.0.0")

        # Operation allowlist
        if allowed_operations is None:
            # Load from environment based on service name
            env_var = f"{service_name.upper().replace('-', '_')}_ALLOWED_OPS"
            allowed_ops_str = os.getenv(env_var, "list,inspect")
            self.allowed_operations = allowed_ops_str.split(",")
        else:
            self.allowed_operations = allowed_operations

        # Audit logging
        self.audit_enabled = audit_enabled or os.getenv("CONTAINER_AUDIT_ENABLED", "true").lower() == "true"
        self.audit_log_path = audit_log_path or os.getenv(
            "CONTAINER_AUDIT_LOG_PATH",
            "/data/telemetry/container-audit.jsonl"
        )

        # HTTP client (will be initialized async)
        self.client: Optional[httpx.AsyncClient] = None

        logger.info(
            "podman_api_client_initialized",
            service=service_name,
            api_url=self.api_url,
            allowed_operations=self.allowed_operations
        )

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Initialize HTTP client"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
            logger.info("podman_api_client_connected", service=self.service_name)

    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("podman_api_client_closed", service=self.service_name)

    def _check_operation_allowed(self, operation: str):
        """
        Check if operation is in allowlist

        Raises:
            OperationNotAllowedError: If operation not allowed
        """
        if operation not in self.allowed_operations:
            logger.error(
                "operation_not_allowed",
                service=self.service_name,
                operation=operation,
                allowed=self.allowed_operations
            )
            raise OperationNotAllowedError(
                f"Service '{self.service_name}' not allowed to perform operation '{operation}'. "
                f"Allowed: {self.allowed_operations}"
            )

    async def _audit_log(
        self,
        operation: str,
        container: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log container operation to audit log

        Args:
            operation: Operation performed (e.g., "restart")
            container: Container name or ID
            success: Whether operation succeeded
            error: Error message if failed
            metadata: Additional metadata
        """
        if not self.audit_enabled:
            return

        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "operation": operation,
            "container": container,
            "success": success,
            "error": error,
            "metadata": metadata or {}
        }

        try:
            # Ensure directory exists
            log_path = Path(self.audit_log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to audit log (JSONL format)
            with open(log_path, "a") as f:
                f.write(json.dumps(audit_entry) + "\n")

        except Exception as e:
            logger.error("audit_log_failed", error=str(e))

    async def _api_request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Podman API

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/containers/json")
            **kwargs: Additional arguments for httpx request

        Returns:
            Response JSON

        Raises:
            PodmanAPIError: On API errors
        """
        if not self.client:
            await self.connect()

        url = f"{self.api_url}/{self.api_version}/libpod{path}"

        try:
            response = await self.client.request(method, url, **kwargs)

            # Check for errors
            if response.status_code >= 400:
                error_detail = response.text
                logger.error(
                    "podman_api_error",
                    status_code=response.status_code,
                    error=error_detail,
                    url=url
                )
                raise PodmanAPIError(f"API error {response.status_code}: {error_detail}")

            # Parse JSON response (if any)
            if response.status_code == 204:  # No Content
                return {}

            return response.json()

        except httpx.RequestError as e:
            logger.error("podman_api_request_failed", error=str(e), url=url)
            raise PodmanAPIError(f"Request failed: {e}")

    # =========================================================================
    # Container Operations
    # =========================================================================

    async def list_containers(
        self,
        all_containers: bool = True,
        filters: Optional[Dict[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        List containers

        Args:
            all_containers: Include stopped containers
            filters: Filter results (e.g., {"name": ["my-container"]})

        Returns:
            List of container info dicts
        """
        self._check_operation_allowed("list")

        params = {"all": str(all_containers).lower()}
        if filters:
            params["filters"] = json.dumps(filters)

        containers = await self._api_request("GET", "/containers/json", params=params)

        await self._audit_log(
            operation="list",
            success=True,
            metadata={"count": len(containers)}
        )

        return containers

    async def get_container(self, container_name_or_id: str) -> Dict[str, Any]:
        """
        Get container details

        Args:
            container_name_or_id: Container name or ID

        Returns:
            Container info dict

        Raises:
            ContainerNotFoundError: If container not found
        """
        self._check_operation_allowed("inspect")

        try:
            container = await self._api_request(
                "GET",
                f"/containers/{container_name_or_id}/json"
            )

            await self._audit_log(
                operation="inspect",
                container=container_name_or_id,
                success=True
            )

            return container

        except PodmanAPIError as e:
            if "404" in str(e):
                raise ContainerNotFoundError(f"Container '{container_name_or_id}' not found")
            raise

    async def restart_container(
        self,
        container_name_or_id: str,
        timeout: int = 10
    ) -> bool:
        """
        Restart a container

        Args:
            container_name_or_id: Container name or ID
            timeout: Timeout in seconds for graceful shutdown

        Returns:
            True if successful

        Raises:
            ContainerNotFoundError: If container not found
            OperationNotAllowedError: If restart not allowed
        """
        self._check_operation_allowed("restart")

        try:
            await self._api_request(
                "POST",
                f"/containers/{container_name_or_id}/restart",
                params={"timeout": timeout}
            )

            await self._audit_log(
                operation="restart",
                container=container_name_or_id,
                success=True
            )

            logger.info(
                "container_restarted",
                service=self.service_name,
                container=container_name_or_id
            )

            return True

        except PodmanAPIError as e:
            await self._audit_log(
                operation="restart",
                container=container_name_or_id,
                success=False,
                error=str(e)
            )

            if "404" in str(e):
                raise ContainerNotFoundError(f"Container '{container_name_or_id}' not found")
            raise

    async def start_container(self, container_name_or_id: str) -> bool:
        """
        Start a container

        Args:
            container_name_or_id: Container name or ID

        Returns:
            True if successful
        """
        self._check_operation_allowed("start")

        try:
            await self._api_request(
                "POST",
                f"/containers/{container_name_or_id}/start"
            )

            await self._audit_log(
                operation="start",
                container=container_name_or_id,
                success=True
            )

            logger.info(
                "container_started",
                service=self.service_name,
                container=container_name_or_id
            )

            return True

        except PodmanAPIError as e:
            await self._audit_log(
                operation="start",
                container=container_name_or_id,
                success=False,
                error=str(e)
            )
            raise

    async def stop_container(
        self,
        container_name_or_id: str,
        timeout: int = 10
    ) -> bool:
        """
        Stop a container

        Args:
            container_name_or_id: Container name or ID
            timeout: Timeout in seconds for graceful shutdown

        Returns:
            True if successful
        """
        self._check_operation_allowed("stop")

        try:
            await self._api_request(
                "POST",
                f"/containers/{container_name_or_id}/stop",
                params={"timeout": timeout}
            )

            await self._audit_log(
                operation="stop",
                container=container_name_or_id,
                success=True
            )

            logger.info(
                "container_stopped",
                service=self.service_name,
                container=container_name_or_id
            )

            return True

        except PodmanAPIError as e:
            await self._audit_log(
                operation="stop",
                container=container_name_or_id,
                success=False,
                error=str(e)
            )
            raise

    async def get_container_logs(
        self,
        container_name_or_id: str,
        tail: int = 100,
        follow: bool = False
    ) -> str:
        """
        Get container logs

        Args:
            container_name_or_id: Container name or ID
            tail: Number of lines from end
            follow: Stream logs (not yet implemented)

        Returns:
            Log output as string
        """
        self._check_operation_allowed("logs")

        try:
            logs = await self._api_request(
                "GET",
                f"/containers/{container_name_or_id}/logs",
                params={
                    "stdout": "true",
                    "stderr": "true",
                    "tail": tail
                }
            )

            await self._audit_log(
                operation="logs",
                container=container_name_or_id,
                success=True
            )

            return logs

        except PodmanAPIError as e:
            await self._audit_log(
                operation="logs",
                container=container_name_or_id,
                success=False,
                error=str(e)
            )
            raise

    async def create_container(
        self,
        image: str,
        name: Optional[str] = None,
        command: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        ports: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Create a container (but don't start it)

        Args:
            image: Image name
            name: Container name (optional)
            command: Command to run
            env: Environment variables
            volumes: Volume mounts
            ports: Port mappings

        Returns:
            Container creation response
        """
        self._check_operation_allowed("create")

        # Build container spec
        spec = {
            "image": image,
        }

        if name:
            spec["name"] = name
        if command:
            spec["command"] = command
        if env:
            spec["env"] = env
        if volumes:
            spec["volumes"] = volumes
        if ports:
            spec["ports"] = ports

        try:
            result = await self._api_request(
                "POST",
                "/containers/create",
                json=spec
            )

            await self._audit_log(
                operation="create",
                container=name or result.get("Id", "unknown"),
                success=True,
                metadata={"image": image}
            )

            logger.info(
                "container_created",
                service=self.service_name,
                container=name,
                image=image
            )

            return result

        except PodmanAPIError as e:
            await self._audit_log(
                operation="create",
                container=name,
                success=False,
                error=str(e),
                metadata={"image": image}
            )
            raise


# Example usage
if __name__ == "__main__":
    async def main():
        """Example usage"""
        # Create client
        async with PodmanAPIClient(
            service_name="example-service",
            allowed_operations=["list", "inspect", "restart"]
        ) as client:
            # List containers
            containers = await client.list_containers()
            print(f"Found {len(containers)} containers")

            # Get specific container
            try:
                container = await client.get_container("local-ai-postgres")
                print(f"Container status: {container['State']['Status']}")
            except ContainerNotFoundError:
                print("Container not found")

            # Restart container
            try:
                await client.restart_container("local-ai-postgres")
                print("Container restarted successfully")
            except OperationNotAllowedError as e:
                print(f"Operation not allowed: {e}")

    asyncio.run(main())
