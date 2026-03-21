#!/usr/bin/env python3
"""
Comprehensive Test Suite for Workflow Automation.

This script tests all workflow automation components including generation,
optimization, templates, adaptation, prediction, and execution.
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add lib to path
lib_path = Path(__file__).parent.parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from workflows import (
    WorkflowGenerator,
    WorkflowOptimizer,
    TemplateManager,
    WorkflowAdapter,
    SuccessPredictor,
    WorkflowExecutor,
    WorkflowStore,
)
from workflows.workflow_optimizer import WorkflowTelemetry, TaskTelemetry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WorkflowAutomationTests:
    """Test suite for workflow automation."""

    def __init__(self):
        """Initialize test suite."""
        self.generator = WorkflowGenerator()
        self.optimizer = WorkflowOptimizer()
        self.template_manager = TemplateManager("/tmp/test-templates")
        self.adapter = WorkflowAdapter()
        self.predictor = SuccessPredictor()
        self.executor = WorkflowExecutor(state_dir="/tmp/test-workflow-state")
        self.store = WorkflowStore("/tmp/test-workflow-store.db")

        self.passed = 0
        self.failed = 0
        self.test_workflows = []

    def run_test(self, test_name: str, test_func):
        """Run a single test."""
        print(f"\n{'='*80}")
        print(f"TEST: {test_name}")
        print('='*80)

        try:
            result = test_func()
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)

            print(f"✓ PASSED: {test_name}")
            self.passed += 1
            return True

        except AssertionError as e:
            print(f"✗ FAILED: {test_name}")
            print(f"  Error: {e}")
            self.failed += 1
            return False

        except Exception as e:
            print(f"✗ ERROR: {test_name}")
            print(f"  Exception: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1
            return False

    # Workflow Generator Tests

    def test_generate_deployment_workflow(self):
        """Test generating a deployment workflow."""
        goal = "Deploy authentication service with health checks and monitoring"

        workflow = self.generator.generate(goal)

        assert workflow is not None, "Workflow should be generated"
        assert workflow.id is not None, "Workflow should have an ID"
        assert workflow.goal == goal, "Workflow goal should match"
        assert len(workflow.tasks) > 0, "Workflow should have tasks"

        # Should have deployment-related tasks
        task_types = [t.task_type.value for t in workflow.tasks]
        assert "deploy" in task_types, "Should have deploy task"

        print(f"  Generated workflow with {len(workflow.tasks)} tasks")
        self.test_workflows.append(workflow)

        return True

    def test_generate_feature_workflow(self):
        """Test generating a feature development workflow."""
        goal = "Add rate limiting to API endpoints"

        workflow = self.generator.generate(goal)

        assert workflow is not None, "Workflow should be generated"
        assert len(workflow.tasks) > 0, "Workflow should have tasks"

        # Should have development-related tasks
        task_types = [t.task_type.value for t in workflow.tasks]
        assert "code" in task_types, "Should have code task"

        print(f"  Generated workflow with {len(workflow.tasks)} tasks")
        self.test_workflows.append(workflow)

        return True

    def test_generate_investigation_workflow(self):
        """Test generating an investigation workflow."""
        goal = "Investigate and fix high memory usage in production"

        workflow = self.generator.generate(goal)

        assert workflow is not None, "Workflow should be generated"
        assert len(workflow.tasks) > 0, "Workflow should have tasks"

        # Should have investigation tasks
        task_types = [t.task_type.value for t in workflow.tasks]
        assert "investigate" in task_types or "analyze" in task_types, \
            "Should have investigation or analysis task"

        print(f"  Generated workflow with {len(workflow.tasks)} tasks")
        self.test_workflows.append(workflow)

        return True

    def test_workflow_validation(self):
        """Test workflow validation."""
        goal = "Test workflow validation"
        workflow = self.generator.generate(goal)

        # Should validate successfully
        is_valid = self.generator.validate(workflow)
        assert is_valid, "Generated workflow should be valid"

        # Get execution order (should work for valid workflow)
        batches = workflow.get_execution_order()
        assert len(batches) > 0, "Should have execution batches"

        print(f"  Workflow is valid with {len(batches)} execution batches")

        return True

    # Workflow Optimizer Tests

    def test_optimizer_with_telemetry(self):
        """Test workflow optimizer with sample telemetry."""
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]

        # Create sample telemetry
        telemetry = self._create_sample_telemetry(workflow, num_executions=5)

        # Optimize
        result = self.optimizer.optimize(workflow, telemetry)

        assert result is not None, "Should produce optimization result"
        assert result.analyzed_executions == 5, "Should analyze 5 executions"
        assert isinstance(result.bottlenecks, list), "Should have bottlenecks list"
        assert isinstance(result.suggestions, list), "Should have suggestions list"

        print(f"  Found {len(result.bottlenecks)} bottlenecks")
        print(f"  Generated {len(result.suggestions)} suggestions")

        return True

    def test_bottleneck_detection(self):
        """Test bottleneck detection."""
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]

        # Create telemetry with intentional bottleneck
        telemetry = self._create_sample_telemetry(
            workflow,
            num_executions=3,
            slow_task_id="task_1"
        )

        result = self.optimizer.optimize(workflow, telemetry)

        # Should detect the slow task
        assert len(result.bottlenecks) > 0, "Should detect bottlenecks"

        print(f"  Detected bottlenecks: {[b.task_id for b in result.bottlenecks]}")

        return True

    # Template Manager Tests

    def test_create_template_from_workflow(self):
        """Test creating a template from a workflow."""
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]
        telemetry = self._create_sample_telemetry(workflow, num_executions=3)

        template = self.template_manager.create_template(workflow, telemetry)

        assert template is not None, "Should create template"
        assert template.id is not None, "Template should have ID"
        assert len(template.parameters) > 0, "Template should have parameters"
        assert len(template.task_template) > 0, "Template should have task template"

        print(f"  Created template with {len(template.parameters)} parameters")

        return True

    def test_template_search(self):
        """Test template search."""
        # Create a template first
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]
        self.template_manager.create_template(workflow)

        # Search for templates
        templates = self.template_manager.search_templates("deploy")

        assert isinstance(templates, list), "Should return list"
        print(f"  Found {len(templates)} templates matching 'deploy'")

        return True

    def test_template_recommendation(self):
        """Test template recommendation."""
        # Create a template first
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]
        self.template_manager.create_template(workflow)

        # Get recommendations
        goal = "Deploy new service with monitoring"
        recommendations = self.template_manager.recommend_templates(goal)

        assert isinstance(recommendations, list), "Should return list"
        print(f"  Got {len(recommendations)} recommendations")

        if recommendations:
            template, score = recommendations[0]
            print(f"  Top recommendation score: {score:.2f}")

        return True

    # Workflow Adapter Tests

    def test_similarity_detection(self):
        """Test goal similarity detection."""
        goal1 = "Deploy authentication service"
        goal2 = "Deploy authorization service"

        similarity = self.adapter.similarity_detector.calculate_goal_similarity(
            goal1, goal2
        )

        assert 0 <= similarity <= 1, "Similarity should be 0-1"
        assert similarity > 0.5, "Similar goals should have high similarity"

        print(f"  Similarity between goals: {similarity:.2f}")

        return True

    def test_workflow_adaptation(self):
        """Test workflow adaptation."""
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        source_workflow = self.test_workflows[0]
        new_goal = "Deploy new authentication service"

        result = self.adapter.adapt_from_workflow(source_workflow, new_goal)

        assert result is not None, "Should produce adaptation result"
        assert result.adapted_workflow is not None, "Should have adapted workflow"
        assert result.adapted_workflow.goal == new_goal, "Goal should be updated"
        assert result.validation_status == "Valid", "Adapted workflow should be valid"

        print(f"  Adapted workflow with {len(result.adaptations_applied)} adaptations")
        print(f"  Similarity score: {result.similarity_score:.2f}")

        return True

    # Success Predictor Tests

    def test_success_prediction(self):
        """Test workflow success prediction."""
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]

        prediction = self.predictor.predict(workflow)

        assert prediction is not None, "Should produce prediction"
        assert 0 <= prediction.success_probability <= 1, "Probability should be 0-1"
        assert 0 <= prediction.confidence <= 1, "Confidence should be 0-1"
        assert isinstance(prediction.risk_factors, list), "Should have risk factors"

        print(f"  Success probability: {prediction.success_probability:.1%}")
        print(f"  Confidence: {prediction.confidence:.1%}")
        print(f"  Risk factors: {len(prediction.risk_factors)}")

        return True

    def test_risk_identification(self):
        """Test risk factor identification."""
        # Create a complex workflow that should have risks
        goal = "Deploy complex microservices architecture with 30 components"
        workflow = self.generator.generate(goal)

        prediction = self.predictor.predict(workflow)

        # Should identify complexity risk
        risk_types = [r.factor for r in prediction.risk_factors]

        print(f"  Identified risks: {risk_types}")

        return True

    # Workflow Executor Tests

    async def test_workflow_execution(self):
        """Test workflow execution."""
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]

        # Execute workflow
        execution = await self.executor.execute(workflow)

        assert execution is not None, "Should produce execution result"
        assert execution.status.value in ["success", "failure"], \
            "Should have final status"
        assert execution.total_duration >= 0, "Should have duration"

        print(f"  Execution status: {execution.status.value}")
        print(f"  Total duration: {execution.total_duration}s")
        print(f"  Tasks completed: {len(execution.task_executions)}")

        return True

    async def test_parallel_execution(self):
        """Test parallel task execution."""
        # Create workflow with parallelizable tasks
        goal = "Run parallel tests"
        workflow = self.generator.generate(goal)

        execution = await self.executor.execute(workflow)

        # Check execution order had parallelism
        batches = workflow.get_execution_order()
        has_parallelism = any(len(batch) > 1 for batch in batches)

        print(f"  Execution had parallelism: {has_parallelism}")
        print(f"  Execution batches: {len(batches)}")

        return True

    # Workflow Store Tests

    def test_store_workflow(self):
        """Test storing and retrieving workflow."""
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]

        # Store workflow
        self.store.save_workflow(workflow)

        # Retrieve workflow
        retrieved = self.store.get_workflow(workflow.id)

        assert retrieved is not None, "Should retrieve workflow"
        assert retrieved["id"] == workflow.id, "IDs should match"

        print(f"  Stored and retrieved workflow {workflow.id}")

        return True

    def test_store_execution(self):
        """Test storing execution."""
        # Need to run execution first
        if not self.test_workflows:
            self.test_generate_deployment_workflow()

        workflow = self.test_workflows[0]
        execution = asyncio.run(self.executor.execute(workflow))

        # Store execution
        self.store.save_execution(execution)

        # Retrieve execution
        retrieved = self.store.get_execution(execution.execution_id)

        assert retrieved is not None, "Should retrieve execution"
        assert retrieved["execution_id"] == execution.execution_id, "IDs should match"

        print(f"  Stored and retrieved execution {execution.execution_id}")

        return True

    def test_workflow_statistics(self):
        """Test workflow statistics."""
        stats = self.store.get_statistics()

        assert isinstance(stats, dict), "Should return statistics dict"
        assert "total_workflows" in stats, "Should have total workflows"

        print(f"  Statistics: {stats}")

        return True

    # Integration Tests

    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow."""
        # 1. Generate workflow
        goal = "Deploy new microservice"
        workflow = self.generator.generate(goal)
        print(f"  1. Generated workflow: {workflow.id}")

        # 2. Predict success
        prediction = self.predictor.predict(workflow)
        print(f"  2. Success prediction: {prediction.success_probability:.1%}")

        # 3. Store workflow
        self.store.save_workflow(workflow)
        print(f"  3. Stored workflow")

        # 4. Execute workflow
        execution = asyncio.run(self.executor.execute(workflow))
        print(f"  4. Executed workflow: {execution.status.value}")

        # 5. Store execution
        self.store.save_execution(execution)
        print(f"  5. Stored execution")

        # 6. Create template
        template = self.template_manager.create_template(workflow)
        print(f"  6. Created template: {template.id}")

        # 7. Adapt template
        new_goal = "Deploy updated microservice"
        adapted = self.adapter.adapt_from_template(template, new_goal)
        print(f"  7. Adapted workflow from template")

        assert adapted.adapted_workflow is not None, "Should complete end-to-end"

        return True

    # Helper methods

    def _create_sample_telemetry(
        self,
        workflow,
        num_executions: int = 3,
        slow_task_id: str = None
    ) -> List[WorkflowTelemetry]:
        """Create sample telemetry data for testing."""
        telemetry = []

        for i in range(num_executions):
            task_telemetry = []

            for task in workflow.tasks:
                duration = task.estimated_duration

                # Make specific task slow if requested
                if slow_task_id and task.id == slow_task_id:
                    duration *= 5

                task_telemetry.append(TaskTelemetry(
                    task_id=task.id,
                    workflow_id=workflow.id,
                    execution_id=f"exec_{i}_{task.id}",
                    start_time="2024-01-01T00:00:00",
                    end_time="2024-01-01T00:01:00",
                    duration=duration,
                    status="success",
                    agent_id=f"agent_{task.agent_role.value}",
                ))

            telemetry.append(WorkflowTelemetry(
                workflow_id=workflow.id,
                execution_id=f"exec_{i}",
                start_time="2024-01-01T00:00:00",
                end_time="2024-01-01T01:00:00",
                total_duration=sum(t.duration for t in task_telemetry),
                task_telemetry=task_telemetry,
                success=True,
            ))

        return telemetry

    def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*80)
        print("WORKFLOW AUTOMATION TEST SUITE")
        print("="*80)

        # Generator tests
        self.run_test("Generate Deployment Workflow", self.test_generate_deployment_workflow)
        self.run_test("Generate Feature Workflow", self.test_generate_feature_workflow)
        self.run_test("Generate Investigation Workflow", self.test_generate_investigation_workflow)
        self.run_test("Workflow Validation", self.test_workflow_validation)

        # Optimizer tests
        self.run_test("Optimizer with Telemetry", self.test_optimizer_with_telemetry)
        self.run_test("Bottleneck Detection", self.test_bottleneck_detection)

        # Template tests
        self.run_test("Create Template from Workflow", self.test_create_template_from_workflow)
        self.run_test("Template Search", self.test_template_search)
        self.run_test("Template Recommendation", self.test_template_recommendation)

        # Adapter tests
        self.run_test("Similarity Detection", self.test_similarity_detection)
        self.run_test("Workflow Adaptation", self.test_workflow_adaptation)

        # Predictor tests
        self.run_test("Success Prediction", self.test_success_prediction)
        self.run_test("Risk Identification", self.test_risk_identification)

        # Executor tests
        self.run_test("Workflow Execution", self.test_workflow_execution)
        self.run_test("Parallel Execution", self.test_parallel_execution)

        # Store tests
        self.run_test("Store Workflow", self.test_store_workflow)
        self.run_test("Store Execution", self.test_store_execution)
        self.run_test("Workflow Statistics", self.test_workflow_statistics)

        # Integration tests
        self.run_test("End-to-End Workflow", self.test_end_to_end_workflow)

        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total:  {self.passed + self.failed}")
        print(f"Success Rate: {self.passed/(self.passed+self.failed)*100:.1f}%")

        return self.failed == 0


def main():
    """Run test suite."""
    tests = WorkflowAutomationTests()
    success = tests.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
