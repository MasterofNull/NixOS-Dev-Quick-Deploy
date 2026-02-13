#!/usr/bin/env python3
"""
RAG Workflow Test Script

Purpose: Test RAG (Retrieval Augmented Generation) workflow
Following: docs/agent-guides/21-RAG-CONTEXT.md
"""

import os
import sys
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
import uuid
from datetime import datetime
from sentence_transformers import SentenceTransformer

# Initialize embedding model (matches AIDB architecture)
embedding_model = None

def get_embedding_model():
    """Lazy-load embedding model"""
    global embedding_model
    if embedding_model is None:
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return embedding_model

def get_embedding(text: str, model: str = None, base_url: str = None) -> list:
    """Generate embeddings using SentenceTransformer (matches AIDB implementation)."""
    model_instance = get_embedding_model()
    embedding = model_instance.encode(text, convert_to_tensor=False)
    return embedding.tolist()


class RAGWorkflowTester:
    """Test RAG workflow components"""

    def __init__(self):
        service_host = os.getenv("SERVICE_HOST", "localhost")
        qdrant_url = os.getenv("QDRANT_URL", f"http://{service_host}:6333")
        self.client = QdrantClient(url=qdrant_url)
        self.test_results = []

    def log_test(self, name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if message:
            print(f"       {message}")
        self.test_results.append({"name": name, "passed": passed, "message": message})

    def test_embedding_generation(self) -> bool:
        """Test SentenceTransformer embedding generation"""
        try:
            embedding = get_embedding("test query")

            if len(embedding) > 0:
                self.log_test(
                    "SentenceTransformer Embedding Generation",
                    True,
                    f"Generated {len(embedding)}-dimensional embedding"
                )
                return True
            else:
                self.log_test(
                    "SentenceTransformer Embedding Generation",
                    False,
                    "Embedding response was empty"
                )
                return False

        except Exception as e:
            self.log_test(
                "SentenceTransformer Embedding Generation",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_qdrant_connection(self) -> bool:
        """Test Qdrant connection"""
        try:
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]

            self.log_test(
                "Qdrant Connection",
                True,
                f"Found {len(collection_names)} collections"
            )
            return True

        except Exception as e:
            self.log_test(
                "Qdrant Connection",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_collection_exists(self, collection_name: str) -> bool:
        """Test if required collection exists"""
        try:
            info = self.client.get_collection(collection_name)
            point_count = info.points_count

            self.log_test(
                f"Collection '{collection_name}' exists",
                True,
                f"{point_count} points stored"
            )
            return True

        except Exception as e:
            self.log_test(
                f"Collection '{collection_name}' exists",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_store_and_retrieve(self, collection_name: str = "error-solutions") -> bool:
        """Test storing and retrieving a point"""
        try:
            # Step 1: Create test data
            test_query = f"Test error at {datetime.now().isoformat()}"
            test_solution = "Test solution for verification"

            # Step 2: Create embedding
            embedding = get_embedding(test_query)

            # Step 3: Store point
            point_id = str(uuid.uuid4())
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "query": test_query,
                            "solution": test_solution,
                            "test": True,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                ]
            )

            # Step 4: Retrieve point
            retrieved = self.client.retrieve(
                collection_name=collection_name,
                ids=[point_id]
            )

            if retrieved and retrieved[0].payload["solution"] == test_solution:
                self.log_test(
                    "Store and Retrieve",
                    True,
                    f"Successfully stored and retrieved test point"
                )

                # Cleanup
                self.client.delete(
                    collection_name=collection_name,
                    points_selector=[point_id]
                )

                return True
            else:
                self.log_test(
                    "Store and Retrieve",
                    False,
                    "Retrieved data doesn't match"
                )
                return False

        except Exception as e:
            self.log_test(
                "Store and Retrieve",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_semantic_search(self, collection_name: str = "error-solutions") -> bool:
        """Test semantic search functionality"""
        try:
            # Store test data with known queries
            test_data = [
                ("GNOME keyring error in NixOS", "Add libsecret and gcr packages"),
                ("Python read-only filesystem error", "Use virtual environment"),
                ("Container port already in use", "Check and kill conflicting process")
            ]

            stored_ids = []

            # Store test data
            for query, solution in test_data:
                embedding = get_embedding(query)

                point_id = str(uuid.uuid4())
                self.client.upsert(
                    collection_name=collection_name,
                    points=[
                        PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload={
                                "query": query,
                                "solution": solution,
                                "test": True
                            }
                        )
                    ]
                )
                stored_ids.append(point_id)

            # Test semantic search
            search_query = "keyring problem nixos"  # Similar to first item
            search_embedding = get_embedding(search_query)

            results = self.client.search(
                collection_name=collection_name,
                query_vector=search_embedding,
                limit=3,
                score_threshold=0.0  # Get all results for testing
            )

            # Check if we found relevant results
            found_keyring = any("keyring" in r.payload.get("query", "").lower() for r in results)

            if found_keyring and results[0].score > 0.5:
                self.log_test(
                    "Semantic Search",
                    True,
                    f"Found relevant result with score {results[0].score:.3f}"
                )
                success = True
            else:
                self.log_test(
                    "Semantic Search",
                    False,
                    f"No relevant results found (best score: {results[0].score if results else 0:.3f})"
                )
                success = False

            # Cleanup
            self.client.delete(
                collection_name=collection_name,
                points_selector=stored_ids
            )

            return success

        except Exception as e:
            self.log_test(
                "Semantic Search",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_rag_workflow_complete(self) -> bool:
        """Test complete RAG workflow: store, search, augment"""
        try:
            collection_name = "error-solutions"

            # Step 1: Store known solution
            known_error = "OSError: Read-only file system /nix/store"
            known_solution = "Use Python virtual environment: python3 -m venv venv"

            embedding = get_embedding(known_error)

            point_id = str(uuid.uuid4())
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "error": known_error,
                            "solution": known_solution,
                            "test": True
                        }
                    )
                ]
            )

            # Step 2: Query with similar error
            user_query = "Getting read-only filesystem error when installing Python packages"

            query_embedding = get_embedding(user_query)

            # Step 3: Search for relevant context
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=3,
                score_threshold=0.6
            )

            # Step 4: Check if we found the relevant solution
            if results and results[0].score > 0.6:
                context_solution = results[0].payload.get("solution", "")

                if "virtual environment" in context_solution.lower():
                    self.log_test(
                        "Complete RAG Workflow",
                        True,
                        f"Successfully retrieved relevant solution (score: {results[0].score:.3f})"
                    )
                    success = True
                else:
                    self.log_test(
                        "Complete RAG Workflow",
                        False,
                        "Retrieved result but not the expected solution"
                    )
                    success = False
            else:
                self.log_test(
                    "Complete RAG Workflow",
                    False,
                    "No relevant results found"
                )
                success = False

            # Cleanup
            self.client.delete(
                collection_name=collection_name,
                points_selector=[point_id]
            )

            return success

        except Exception as e:
            self.log_test(
                "Complete RAG Workflow",
                False,
                f"Error: {str(e)}"
            )
            return False

    def run_all_tests(self) -> bool:
        """Run all RAG workflow tests"""
        print("=== RAG Workflow Test Suite ===")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        # Required collections
        required_collections = [
            "codebase-context",
            "skills-patterns",
            "error-solutions",
            "best-practices",
            "interaction-history"
        ]

        # Run tests
        all_passed = True

        # Basic connectivity
        all_passed &= self.test_embedding_generation()
        all_passed &= self.test_qdrant_connection()

        # Collection existence
        for collection in required_collections:
            all_passed &= self.test_collection_exists(collection)

        # Functional tests
        all_passed &= self.test_store_and_retrieve()
        all_passed &= self.test_semantic_search()
        all_passed &= self.test_rag_workflow_complete()

        # Summary
        print()
        print("=== Test Summary ===")
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed

        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if failed > 0:
            print()
            print("Failed Tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['name']}: {result['message']}")

        print()

        return all_passed


def main():
    """Main entry point"""
    tester = RAGWorkflowTester()
    success = tester.run_all_tests()

    if success:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed. See above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
