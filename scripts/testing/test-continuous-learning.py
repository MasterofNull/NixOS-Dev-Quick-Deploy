#!/usr/bin/env python3
"""
Continuous Learning Workflow Test

Purpose: Test continuous learning system components
Following: docs/agent-guides/22-CONTINUOUS-LEARNING.md
"""

import os
import sys
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid
from datetime import datetime
from sentence_transformers import SentenceTransformer

SERVICE_HOST = os.getenv("SERVICE_HOST", "localhost")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost")

# Initialize embedding model (matches AIDB architecture)
embedding_model = None

def get_embedding_model():
    """Lazy-load embedding model"""
    global embedding_model
    if embedding_model is None:
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return embedding_model

def calculate_value_score(interaction: dict) -> float:
    """
    Calculate value score (0-1) using 5-factor algorithm
    Following: docs/agent-guides/41-VALUE-SCORING.md
    """

    # Factor 1: Complexity (0.2 weight)
    complexity = min(1.0, interaction.get("lines_of_code", 0) / 100)

    # Factor 2: Reusability (0.3 weight)
    reusability_map = {
        "single_case": 0.2,
        "similar_cases": 0.5,
        "category": 0.8,
        "universal": 1.0
    }
    reusability = reusability_map.get(
        interaction.get("applicability_scope", "single_case"),
        0.3
    )

    # Factor 3: Novelty (0.2 weight)
    novelty = 1.0 if interaction.get("is_novel", True) else 0.3

    # Factor 4: Confirmation (0.15 weight)
    confirmation_map = {
        "explicit_success": 1.0,
        "implicit_success": 0.8,
        "partial_success": 0.5,
        "unconfirmed": 0.3
    }
    confirmation = confirmation_map.get(
        interaction.get("confirmation", "unconfirmed"),
        0.3
    )

    # Factor 5: Impact (0.15 weight)
    impact_map = {
        "critical": 1.0,
        "high": 0.8,
        "medium": 0.5,
        "low": 0.3
    }
    impact = impact_map.get(interaction.get("severity", "medium"), 0.5)

    # Weighted average
    value_score = (
        complexity * 0.2 +
        reusability * 0.3 +
        novelty * 0.2 +
        confirmation * 0.15 +
        impact * 0.15
    )

    return round(value_score, 2)


def get_embedding(text: str, model: str = None, base_url: str = None) -> list:
    """Generate embeddings using SentenceTransformer (matches AIDB implementation)."""
    model_instance = get_embedding_model()
    embedding = model_instance.encode(text, convert_to_tensor=False)
    return embedding.tolist()


def store_interaction(query: str, response: str, metadata: dict) -> str:
    """Store interaction with value scoring"""

    client = QdrantClient(url=QDRANT_URL)

    # Calculate value score
    value_score = calculate_value_score(metadata)

    # Create embedding
    embedding_vector = get_embedding(query)

    # Prepare payload
    payload = {
        "query": query,
        "response": response,
        "value_score": value_score,
        "timestamp": datetime.utcnow().isoformat(),
        **metadata
    }

    # Store in interaction-history
    point_id = str(uuid.uuid4())
    client.upsert(
        collection_name="interaction-history",
        points=[
            PointStruct(
                id=point_id,
                vector=embedding_vector,
                payload=payload
            )
        ]
    )

    # If high value, also store in skills-patterns
    if value_score >= 0.7:
        client.upsert(
            collection_name="skills-patterns",
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding_vector,
                    payload=payload
                )
            ]
        )

    return point_id


def store_error_solution(error: str, solution: str, root_cause: str = None, severity: str = "medium") -> str:
    """Store error and solution"""

    client = QdrantClient(url=QDRANT_URL)

    # Create embedding
    embedding = get_embedding(error)

    # Prepare payload
    payload = {
        "error": error,
        "solution": solution,
        "root_cause": root_cause or "Unknown",
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat(),
        "resolved": True
    }

    # Store in error-solutions
    point_id = str(uuid.uuid4())
    client.upsert(
        collection_name="error-solutions",
        points=[
            PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )
        ]
    )

    return point_id


class ContinuousLearningTester:
    """Test continuous learning workflow"""

    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL)
        self.test_results = []
        self.test_point_ids = []

    def log_test(self, name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if message:
            print(f"       {message}")
        self.test_results.append({"name": name, "passed": passed, "message": message})

    def test_value_scoring(self) -> bool:
        """Test value scoring algorithm"""
        try:
            # High-value interaction
            high_value = {
                "lines_of_code": 75,
                "applicability_scope": "category",
                "is_novel": True,
                "confirmation": "explicit_success",
                "severity": "high"
            }

            score = calculate_value_score(high_value)

            if 0.7 <= score <= 1.0:
                self.log_test(
                    "Value Scoring (High)",
                    True,
                    f"Score: {score} (expected > 0.7)"
                )
                high_pass = True
            else:
                self.log_test(
                    "Value Scoring (High)",
                    False,
                    f"Score: {score} (expected > 0.7)"
                )
                high_pass = False

            # Low-value interaction
            low_value = {
                "lines_of_code": 5,
                "applicability_scope": "single_case",
                "is_novel": False,
                "confirmation": "unconfirmed",
                "severity": "low"
            }

            score = calculate_value_score(low_value)

            if score < 0.5:
                self.log_test(
                    "Value Scoring (Low)",
                    True,
                    f"Score: {score} (expected < 0.5)"
                )
                low_pass = True
            else:
                self.log_test(
                    "Value Scoring (Low)",
                    False,
                    f"Score: {score} (expected < 0.5)"
                )
                low_pass = False

            return high_pass and low_pass

        except Exception as e:
            self.log_test(
                "Value Scoring",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_store_interaction(self) -> bool:
        """Test storing interaction with value score"""
        try:
            query = f"Test interaction at {datetime.now().isoformat()}"
            response = "Test response for continuous learning"

            metadata = {
                "lines_of_code": 50,
                "applicability_scope": "category",
                "is_novel": True,
                "confirmation": "explicit_success",
                "severity": "medium",
                "test": True
            }

            point_id = store_interaction(query, response, metadata)
            self.test_point_ids.append(("interaction-history", point_id))

            # Verify it was stored
            retrieved = self.client.retrieve(
                collection_name="interaction-history",
                ids=[point_id]
            )

            if retrieved and retrieved[0].payload.get("value_score") is not None:
                value_score = retrieved[0].payload["value_score"]
                self.log_test(
                    "Store Interaction",
                    True,
                    f"Stored with value score: {value_score}"
                )
                return True
            else:
                self.log_test(
                    "Store Interaction",
                    False,
                    "Interaction not stored correctly"
                )
                return False

        except Exception as e:
            self.log_test(
                "Store Interaction",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_store_error_solution(self) -> bool:
        """Test storing error and solution"""
        try:
            error = f"Test error at {datetime.now().isoformat()}"
            solution = "Test solution for error logging"
            root_cause = "Test root cause"

            point_id = store_error_solution(error, solution, root_cause, "high")
            self.test_point_ids.append(("error-solutions", point_id))

            # Verify it was stored
            retrieved = self.client.retrieve(
                collection_name="error-solutions",
                ids=[point_id]
            )

            if retrieved and retrieved[0].payload.get("resolved") == True:
                self.log_test(
                    "Store Error Solution",
                    True,
                    "Error solution stored correctly"
                )
                return True
            else:
                self.log_test(
                    "Store Error Solution",
                    False,
                    "Error solution not stored correctly"
                )
                return False

        except Exception as e:
            self.log_test(
                "Store Error Solution",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_high_value_pattern_storage(self) -> bool:
        """Test that high-value interactions are stored in skills-patterns"""
        try:
            query = f"High-value test at {datetime.now().isoformat()}"
            response = "High-value response"

            # Create high-value metadata
            metadata = {
                "lines_of_code": 100,
                "applicability_scope": "universal",
                "is_novel": True,
                "confirmation": "explicit_success",
                "severity": "critical",
                "test": True
            }

            point_id = store_interaction(query, response, metadata)
            self.test_point_ids.append(("interaction-history", point_id))

            # Search skills-patterns for this high-value interaction
            embedding = get_embedding(query)

            results = self.client.search(
                collection_name="skills-patterns",
                query_vector=embedding,
                limit=5,
                score_threshold=0.9  # Should be exact match
            )

            # Check if our high-value interaction is there
            found = any(r.payload.get("query") == query for r in results)

            if found:
                self.log_test(
                    "High-Value Pattern Storage",
                    True,
                    "High-value interaction stored in skills-patterns"
                )
                return True
            else:
                self.log_test(
                    "High-Value Pattern Storage",
                    False,
                    "High-value interaction not found in skills-patterns"
                )
                return False

        except Exception as e:
            self.log_test(
                "High-Value Pattern Storage",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_error_retrieval(self) -> bool:
        """Test retrieving stored error solutions"""
        try:
            # Store a known error
            known_error = "NixOS read-only filesystem error"
            known_solution = "Use Python virtual environment"

            point_id = store_error_solution(
                known_error,
                known_solution,
                "NixOS /nix/store is immutable",
                "high"
            )
            self.test_point_ids.append(("error-solutions", point_id))

            # Search for similar error
            search_query = "filesystem is read only when installing packages"

            embedding = get_embedding(search_query)

            results = self.client.search(
                collection_name="error-solutions",
                query_vector=embedding,
                limit=3,
                score_threshold=0.5
            )

            # Check if we found the solution
            found = any("virtual environment" in r.payload.get("solution", "").lower() for r in results)

            if found and results[0].score > 0.5:
                self.log_test(
                    "Error Retrieval",
                    True,
                    f"Found solution with score: {results[0].score:.3f}"
                )
                return True
            else:
                self.log_test(
                    "Error Retrieval",
                    False,
                    "Could not retrieve error solution"
                )
                return False

        except Exception as e:
            self.log_test(
                "Error Retrieval",
                False,
                f"Error: {str(e)}"
            )
            return False

    def cleanup(self):
        """Clean up test data"""
        print()
        print("Cleaning up test data...")

        for collection, point_id in self.test_point_ids:
            try:
                self.client.delete(
                    collection_name=collection,
                    points_selector=[point_id]
                )
            except Exception as e:
                print(f"Warning: Could not delete {point_id} from {collection}: {e}")

    def run_all_tests(self) -> bool:
        """Run all continuous learning tests"""
        print("=== Continuous Learning Test Suite ===")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        all_passed = True

        # Run tests
        all_passed &= self.test_value_scoring()
        all_passed &= self.test_store_interaction()
        all_passed &= self.test_store_error_solution()
        all_passed &= self.test_high_value_pattern_storage()
        all_passed &= self.test_error_retrieval()

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

        # Cleanup
        self.cleanup()

        print()

        return all_passed


def main():
    """Main entry point"""
    tester = ContinuousLearningTester()

    try:
        success = tester.run_all_tests()

        if success:
            print("✓ All tests passed!")
            return 0
        else:
            print("✗ Some tests failed. See above for details.")
            return 1
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Cleaning up...")
        tester.cleanup()
        return 130


if __name__ == "__main__":
    sys.exit(main())
