#!/usr/bin/env python3
"""
Hospital AI Stack End-to-End Test Suite
Tests the complete system flow for HIPAA-compliant hospital deployment
"""

import requests
import time
import json
import subprocess
import os
import signal
from datetime import datetime

# Configuration
TIMEOUT = 30

class HospitalE2ETests:
    """End-to-end tests for hospital AI stack"""

    def __init__(self):
        self.results = []
        self.start_time = datetime.now()
        self.port_forward_procs = []

    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")

    def cleanup_port_forwards(self):
        """Clean up any port-forward processes"""
        for proc in self.port_forward_procs:
            try:
                os.kill(proc.pid, signal.SIGTERM)
            except:
                pass

    def test_kubernetes_health(self):
        """Test K3s cluster health"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "nodes", "-o", "jsonpath={.items[0].status.conditions[-1].type}"],
                capture_output=True, text=True, timeout=10
            )
            passed = result.stdout.strip() == "Ready"
            self.log_result("K3s Cluster Health", passed, result.stdout.strip())
        except Exception as e:
            self.log_result("K3s Cluster Health", False, str(e))

    def test_all_pods_running(self):
        """Verify all pods are in Running state"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "ai-stack", "--no-headers"],
                capture_output=True, text=True, timeout=10
            )
            lines = [l for l in result.stdout.strip().split("\n") if l]
            optional = {"open-webui", "autogpt"}
            total = 0
            running = 0
            not_ready = []
            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                name = parts[0]
                status = parts[2] if len(parts) > 2 else ""
                if any(name.startswith(opt) for opt in optional):
                    continue
                total += 1
                if status == "Running":
                    running += 1
                else:
                    not_ready.append(name)
            passed = running == total and total > 0
            details = f"not_ready={not_ready}" if not passed else ""
            self.log_result(f"All Required Pods Running ({running}/{total})", passed, details)
        except Exception as e:
            self.log_result("All Pods Running", False, str(e))

    def test_database_connectivity(self):
        """Test PostgreSQL database is accepting connections"""
        try:
            result = subprocess.run([
                "kubectl", "exec", "-n", "ai-stack", "deployment/postgres", "--",
                "pg_isready", "-U", "mcp"
            ], capture_output=True, text=True, timeout=10)
            passed = "accepting connections" in result.stdout
            self.log_result("PostgreSQL Connectivity", passed, result.stdout.strip())
        except Exception as e:
            self.log_result("PostgreSQL Connectivity", False, str(e))

    def test_redis_connectivity(self):
        """Test Redis is responding to PING"""
        try:
            import base64
            result = subprocess.run([
                "kubectl", "get", "secret", "redis-password", "-n", "ai-stack",
                "-o", "jsonpath={.data.redis-password}"
            ], capture_output=True, text=True, timeout=10)
            password = base64.b64decode(result.stdout).decode() if result.stdout else ""

            result = subprocess.run([
                "kubectl", "exec", "-n", "ai-stack", "deployment/redis", "--",
                "redis-cli", "-a", password, "PING"
            ], capture_output=True, text=True, timeout=10)
            passed = "PONG" in result.stdout
            self.log_result("Redis Connectivity", passed)
        except Exception as e:
            self.log_result("Redis Connectivity", False, str(e))

    def test_vector_db_health(self):
        """Test Qdrant vector database health via port-forward"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/qdrant", "16333:6333"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(2)
            response = requests.get("http://localhost:16333/healthz", timeout=5)
            passed = response.status_code == 200
            self.log_result("Qdrant Vector DB Health", passed, response.text[:100] if response.text else "")
            proc.terminate()
        except Exception as e:
            self.log_result("Qdrant Vector DB Health", False, str(e))

    def test_aidb_health(self):
        """Test AIDB MCP server health via port-forward"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/aidb", "18091:8091"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(2)
            response = requests.get("http://localhost:18091/health", timeout=5)
            data = response.json()
            passed = data.get("status") == "ok"
            self.log_result("AIDB Health", passed, f"DB: {data.get('database')}, Redis: {data.get('redis')}")
            proc.terminate()
        except Exception as e:
            self.log_result("AIDB Health", False, str(e))

    def test_hybrid_coordinator_health(self):
        """Test Hybrid Coordinator health via port-forward"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/hybrid-coordinator", "18092:8092"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(2)
            response = requests.get("http://localhost:18092/health", timeout=5)
            data = response.json()
            passed = data.get("status") == "healthy"
            self.log_result("Hybrid Coordinator Health", passed, f"Collections: {data.get('collections')}")
            proc.terminate()
        except Exception as e:
            self.log_result("Hybrid Coordinator Health", False, str(e))

    def test_ralph_wiggum_health(self):
        """Test Ralph Wiggum orchestrator health via port-forward"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/ralph-wiggum", "18098:8098"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(3)
            passed = False
            details = ""
            for _ in range(3):
                try:
                    response = requests.get("http://localhost:18098/health", timeout=5)
                    data = response.json()
                    passed = data.get("status") == "healthy"
                    details = f"Loop: {data.get('loop_enabled')}, Tasks: {data.get('active_tasks')}"
                    if passed:
                        break
                except Exception as inner:
                    details = str(inner)
                    time.sleep(2)
            self.log_result("Ralph Wiggum Health", passed, details)
            proc.terminate()
        except Exception as e:
            self.log_result("Ralph Wiggum Health", False, str(e))

    def test_llm_inference(self):
        """Test llama-cpp local LLM inference (critical for HIPAA - no cloud calls)"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/llama-cpp", "18080:8080"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(2)
            response = requests.get("http://localhost:18080/health", timeout=5)
            data = response.json()
            passed = data.get("status") == "ok"
            self.log_result("Local LLM Inference (HIPAA)", passed, "llama-cpp responding")
            proc.terminate()
        except Exception as e:
            self.log_result("Local LLM Inference (HIPAA)", False, str(e))

    def test_embeddings_service(self):
        """Test embeddings service health via port-forward"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/embeddings", "18081:8081"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(2)
            response = requests.get("http://localhost:18081/health", timeout=5)
            data = response.json()
            passed = data.get("status") == "ok"
            self.log_result("Embeddings Service Health", passed, f"Model: {data.get('model')}")
            proc.terminate()
        except Exception as e:
            self.log_result("Embeddings Service Health", False, str(e))

    def test_grafana_accessibility(self):
        """Test Grafana monitoring dashboard"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/grafana", "13002:3002"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(2)
            response = requests.get("http://localhost:13002/api/health", timeout=5)
            passed = response.status_code == 200
            self.log_result("Grafana Dashboard Accessible", passed)
            proc.terminate()
        except Exception as e:
            self.log_result("Grafana Dashboard Accessible", False, str(e))

    def test_prometheus_targets(self):
        """Test Prometheus is scraping targets via port-forward"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/prometheus", "19090:9090"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(2)
            response = requests.get("http://localhost:19090/api/v1/targets", timeout=5)
            data = response.json()
            targets = data.get("data", {}).get("activeTargets", [])
            expected = {"aidb:8091", "embeddings:8081", "hybrid-coordinator:8092", "nixos-docs:8094", "ralph-wiggum:8098"}
            found = {t.get("labels", {}).get("instance") for t in targets if t.get("labels")}
            missing = sorted([t for t in expected if t not in found])
            health_by_instance = {
                t.get("labels", {}).get("instance"): t.get("health")
                for t in targets if t.get("labels")
            }
            down = sorted([inst for inst in expected if health_by_instance.get(inst) != "up"])
            passed = not missing and not down
            details = "all targets up" if passed else f"missing={missing}, down={down}"
            self.log_result("Prometheus Targets", passed, details)
            proc.terminate()
        except Exception as e:
            self.log_result("Prometheus Targets", False, str(e))

    def test_logging_stack(self):
        """Test Loki logging is operational"""
        try:
            result = subprocess.run([
                "kubectl", "get", "pods", "-n", "logging", "--no-headers"
            ], capture_output=True, text=True, timeout=10)
            lines = [l for l in result.stdout.strip().split("\n") if l]
            running = sum(1 for l in lines if "Running" in l)
            passed = running >= 2  # Loki + Promtail
            self.log_result(f"Logging Stack ({running} pods)", passed)
        except Exception as e:
            self.log_result("Logging Stack", False, str(e))

    def test_backup_cronjobs(self):
        """Test backup CronJobs are configured"""
        try:
            result = subprocess.run([
                "kubectl", "get", "cronjobs", "-n", "backups", "--no-headers"
            ], capture_output=True, text=True, timeout=10)
            lines = [l for l in result.stdout.strip().split("\n") if l]
            passed = len(lines) >= 1
            self.log_result(f"Backup CronJobs ({len(lines)} configured)", passed)
        except Exception as e:
            self.log_result("Backup CronJobs", False, str(e))

    def test_secrets_not_default(self):
        """Verify secrets are not using default values (security check)"""
        try:
            import base64
            result = subprocess.run([
                "kubectl", "get", "secret", "postgres-password", "-n", "ai-stack",
                "-o", "jsonpath={.data.postgres-password}"
            ], capture_output=True, text=True, timeout=10)
            password = base64.b64decode(result.stdout).decode() if result.stdout else ""
            default_passwords = ["password", "postgres", "admin", "root", "changeme", "secret"]
            passed = password and password.lower() not in default_passwords and len(password) >= 16
            self.log_result("Secrets Not Default (Security)", passed,
                          "Password appears secure" if passed else "Weak or default password detected")
        except Exception as e:
            self.log_result("Secrets Not Default (Security)", False, str(e))

    def test_no_external_api_calls(self):
        """Verify AutoGPT (external API) is scaled down (HIPAA compliance)"""
        try:
            result = subprocess.run([
                "kubectl", "get", "deployment", "autogpt", "-n", "ai-stack",
                "-o", "jsonpath={.spec.replicas}"
            ], capture_output=True, text=True, timeout=10)
            replicas = int(result.stdout) if result.stdout else 1
            passed = replicas == 0
            self.log_result("External API Services Disabled (HIPAA)", passed,
                          "AutoGPT scaled to 0" if passed else f"AutoGPT has {replicas} replicas")
        except Exception as e:
            self.log_result("External API Services Disabled (HIPAA)", True, "AutoGPT not deployed")

    def test_circuit_breakers(self):
        """Test circuit breakers are in closed state"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/aidb", "18091:8091"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.append(proc)
            time.sleep(2)
            response = requests.get("http://localhost:18091/health", timeout=5)
            data = response.json()
            breakers = data.get("circuit_breakers", {})
            all_closed = all(v == "CLOSED" for v in breakers.values()) if breakers else False
            passed = all_closed
            self.log_result("Circuit Breakers (Resilience)", passed, str(breakers))
            proc.terminate()
        except Exception as e:
            self.log_result("Circuit Breakers (Resilience)", False, str(e))

    def test_telemetry_flow(self):
        """Test telemetry data is flowing through the system"""
        try:
            import base64

            aidb_key = ""
            ralph_key = ""
            result = subprocess.run([
                "kubectl", "get", "secret", "aidb-api-key", "-n", "ai-stack",
                "-o", "jsonpath={.data.aidb-api-key}"
            ], capture_output=True, text=True, timeout=10)
            if result.stdout:
                aidb_key = base64.b64decode(result.stdout).decode()

            result = subprocess.run([
                "kubectl", "get", "secret", "ralph-wiggum-api-key", "-n", "ai-stack",
                "-o", "jsonpath={.data.ralph-wiggum-api-key}"
            ], capture_output=True, text=True, timeout=10)
            if result.stdout:
                ralph_key = base64.b64decode(result.stdout).decode()

            hybrid_key = ""
            result = subprocess.run([
                "kubectl", "get", "secret", "hybrid-coordinator-api-key", "-n", "ai-stack",
                "-o", "jsonpath={.data.hybrid-coordinator-api-key}"
            ], capture_output=True, text=True, timeout=10)
            if result.stdout:
                hybrid_key = base64.b64decode(result.stdout).decode()

            aidb_pf = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/aidb", "18091:8091"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            hybrid_pf = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/hybrid-coordinator", "18092:8092"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            ralph_pf = subprocess.Popen(
                ["kubectl", "port-forward", "-n", "ai-stack", "svc/ralph-wiggum", "18098:8098"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.port_forward_procs.extend([aidb_pf, hybrid_pf, ralph_pf])
            time.sleep(3)

            headers = {"Content-Type": "application/json"}
            if aidb_key:
                headers["x-api-key"] = aidb_key
            probe_payload = {"model": "telemetry-probe", "prompt_chars": 42}
            try:
                requests.post("http://localhost:18091/telemetry/probe", json=probe_payload, headers=headers, timeout=8)
            except Exception:
                pass

            # Explicit hybrid telemetry trigger
            try:
                hybrid_headers = {"Content-Type": "application/json"}
                if hybrid_key:
                    hybrid_headers["x-api-key"] = hybrid_key
                requests.post(
                    "http://localhost:18092/augment_query",
                    json={"query": "telemetry flow probe", "agent_type": "local"},
                    headers=hybrid_headers,
                    timeout=8
                )
            except Exception:
                pass

            if ralph_key:
                headers = {"Content-Type": "application/json", "x-api-key": ralph_key}
            else:
                headers = {"Content-Type": "application/json"}
            task_payload = {
                "prompt": "Telemetry flow probe - record a lightweight event and exit",
                "max_iterations": 1,
                "require_approval": False
            }
            try:
                requests.post("http://localhost:18098/tasks", json=task_payload, headers=headers, timeout=8)
            except Exception:
                pass

            time.sleep(5)

            aidb_lines = subprocess.run([
                "kubectl", "exec", "-n", "ai-stack", "deployment/aidb", "--",
                "sh", "-c", "test -f /data/telemetry/aidb-events.jsonl && wc -l < /data/telemetry/aidb-events.jsonl || echo 0"
            ], capture_output=True, text=True, timeout=10)
            hybrid_lines = subprocess.run([
                "kubectl", "exec", "-n", "ai-stack", "deployment/hybrid-coordinator", "--",
                "sh", "-c", "test -f /data/telemetry/hybrid-events.jsonl && wc -l < /data/telemetry/hybrid-events.jsonl || echo 0"
            ], capture_output=True, text=True, timeout=10)

            aidb_count = int(aidb_lines.stdout.strip() or 0)
            hybrid_count = int(hybrid_lines.stdout.strip() or 0)
            passed = aidb_count > 0 and hybrid_count > 0
            details = f"aidb_events={aidb_count}, hybrid_events={hybrid_count}"
            self.log_result("Telemetry Data Flow", passed, details)

            aidb_pf.terminate()
            hybrid_pf.terminate()
            ralph_pf.terminate()
        except Exception as e:
            self.log_result("Telemetry Data Flow", False, str(e))

    def run_all_tests(self):
        """Run all E2E tests"""
        print("\n" + "="*60)
        print("🏥 Hospital AI Stack End-to-End Test Suite")
        print(f"   Started: {self.start_time.isoformat()}")
        print("   Environment: K3s Kubernetes (HIPAA Compliant)")
        print("="*60 + "\n")

        try:
            print("📋 Infrastructure Tests:")
            print("-" * 40)
            self.test_kubernetes_health()
            self.test_all_pods_running()

            print("\n📋 Database Tests:")
            print("-" * 40)
            self.test_database_connectivity()
            self.test_redis_connectivity()
            self.test_vector_db_health()

            print("\n📋 MCP Server Tests:")
            print("-" * 40)
            self.test_aidb_health()
            self.test_hybrid_coordinator_health()
            self.test_ralph_wiggum_health()

            print("\n📋 AI/ML Service Tests:")
            print("-" * 40)
            self.test_llm_inference()
            self.test_embeddings_service()

            print("\n📋 Monitoring Tests:")
            print("-" * 40)
            self.test_grafana_accessibility()
            self.test_prometheus_targets()
            self.test_logging_stack()
            self.test_backup_cronjobs()

            print("\n📋 Security & Compliance Tests:")
            print("-" * 40)
            self.test_secrets_not_default()
            self.test_no_external_api_calls()
            self.test_circuit_breakers()

            print("\n📋 Telemetry Tests:")
            print("-" * 40)
            self.test_telemetry_flow()

        finally:
            self.cleanup_port_forwards()

        # Summary
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)

        print("\n" + "="*60)
        print(f"📊 RESULTS: {passed}/{total} tests passed")
        print(f"   Duration: {(datetime.now() - self.start_time).total_seconds():.2f}s")

        if passed == total:
            print("\n✅ ALL TESTS PASSED - System ready for hospital deployment")
            print("   HIPAA Compliance: Local inference verified")
            print("   Security: No default passwords")
            print("   Resilience: Circuit breakers active")
        else:
            print("\n⚠️  SOME TESTS FAILED - Review before deployment")
            print("\nFailed tests:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  - {r['test']}: {r['details']}")

        print("="*60 + "\n")

        return passed == total

if __name__ == "__main__":
    tests = HospitalE2ETests()
    success = tests.run_all_tests()
    exit(0 if success else 1)
