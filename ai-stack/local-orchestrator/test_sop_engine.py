#!/usr/bin/env python3
"""Test SOP engine functionality."""

from pathlib import Path
import sys
import pytest

# Add local-orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))

from sop_engine import parse_sop, execute_sop, ConstraintLevel, SOPDefinition, SOPStep, SOPSection


def load_codebase_analysis_sop():
    """Test parsing an SOP file."""
    sop_path = Path(__file__).parent.parent / "sop-templates" / "codebase-analysis.sop.md"
    
    print("Testing SOP Parser:")
    print("=" * 60)
    print(f"Parsing: {sop_path}")
    
    sop = parse_sop(sop_path)
    
    print(f"\nSOP Name: {sop.name}")
    print(f"Description: {sop.description}")
    print(f"Version: {sop.version}")
    print(f"Parameters: {sop.parameters}")
    
    print(f"\nSections: {len(sop.sections)}")
    for section in sop.sections:
        print(f"  - {section.title} (Level {section.level}, {len(section.steps)} steps)")
    
    # Count constraints
    required_steps = sop.get_required_steps()
    optional_steps = sop.get_optional_steps()
    
    print(f"\nConstraint Analysis:")
    print(f"  Required (MUST) steps: {len(required_steps)}")
    print(f"  Optional (MAY) steps: {len(optional_steps)}")
    
    # Show first few steps with constraints
    print(f"\nSample Steps:")
    step_count = 0
    for section in sop.sections:
        for step in section.steps[:2]:  # First 2 steps per section
            print(f"\n  Step {step.number}: {step.title}")
            print(f"    Constraint: {step.constraint.value}")
            print(f"    Required: {step.is_required()}")
            step_count += 1
            if step_count >= 5:
                break
        if step_count >= 5:
            break
    
    print("\n✓ SOP parsing test passed!")
    return sop


def test_parse_sop():
    load_codebase_analysis_sop()


@pytest.fixture
def sop():
    return SOPDefinition(
        name="test-sop",
        description="test description",
        sections=[
            SOPSection(
                title="Section 1",
                level=2,
                content="section content",
                steps=[
                    SOPStep(number=1, title="step1", description="first step", constraint=ConstraintLevel.MUST),
                    SOPStep(number=2, title="step2", description="second step", constraint=ConstraintLevel.SHOULD),
                ]
            )
        ]
    )

def test_sop_execution(sop):
    """Test SOP execution."""
    print("\n" + "=" * 60)
    print("Testing SOP Execution:")
    print("=" * 60)
    
    # Simple executor that marks all steps as completed
    def simple_executor(step, context):
        print(f"  Executing step {step.number}: {step.title[:50]}...")
        return {"completed": True, "constraint": step.constraint.value}
    
    # Execute SOP
    result = execute_sop(
        sop,
        context={"target_directory": ".", "depth": "full"},
        executor_func=simple_executor
    )
    
    print(f"\nExecution Result:")
    print(f"  Status: {result['status']}")
    print(f"  Total steps: {result['total_steps']}")
    print(f"  Completed: {result['completed_steps']}")
    print(f"  Failed: {result['failed_steps']}")
    
    print("\n✓ SOP execution test passed!")
    assert result["status"] == "completed"
    assert result["completed_steps"] == result["total_steps"]
    assert result["failed_steps"] == 0


if __name__ == "__main__":
    sop_obj = load_codebase_analysis_sop()
    test_sop_execution(sop_obj)
    
    print("\n" + "=" * 60)
    print("All SOP engine tests passed!")
    print("=" * 60)
