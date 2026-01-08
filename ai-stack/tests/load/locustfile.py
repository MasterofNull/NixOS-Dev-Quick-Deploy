import os

from locust import HttpUser, between, task


AIDB_BASE_URL = os.getenv("AIDB_BASE_URL", "http://localhost:8091")
EMBEDDINGS_BASE_URL = os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8081")
HYBRID_BASE_URL = os.getenv("HYBRID_BASE_URL", "http://localhost:8092")
API_KEY = os.getenv("AI_STACK_API_KEY", "")


def _headers():
    return {"X-API-Key": API_KEY} if API_KEY else {}


class AIDBUser(HttpUser):
    wait_time = between(1, 3)
    host = AIDB_BASE_URL

    @task(3)
    def health(self):
        self.client.get("/health", timeout=5)

    @task(2)
    def vector_embed(self):
        payload = {"texts": ["locust test"]}
        self.client.post("/vector/embed", json=payload, timeout=10)

    @task(1)
    def vector_search(self):
        payload = {"query": "locust test", "limit": 3}
        self.client.post("/vector/search", json=payload, timeout=10)


class EmbeddingsUser(HttpUser):
    wait_time = between(1, 3)
    host = EMBEDDINGS_BASE_URL

    @task(3)
    def health(self):
        self.client.get("/health", timeout=5)

    @task(2)
    def embed(self):
        payload = {"inputs": ["locust embeddings"]}
        self.client.post(
            "/embed",
            json=payload,
            headers=_headers(),
            timeout=10,
        )


class HybridUser(HttpUser):
    wait_time = between(1, 3)
    host = HYBRID_BASE_URL

    @task(2)
    def health(self):
        self.client.get("/health", timeout=5)

    @task(1)
    def augment(self):
        payload = {"query": "locust hybrid", "agent_type": "remote"}
        self.client.post(
            "/augment_query",
            json=payload,
            headers=_headers(),
            timeout=10,
        )
