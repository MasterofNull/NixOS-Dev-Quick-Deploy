#!/usr/bin/env python3
"""
SOP (Standard Operating Procedure) Engine

Parses and executes markdown-based SOPs with RFC 2119 constraint detection.
Inspired by strands-agents/agent-sop pattern.

RFC 2119 Keywords:
- MUST, REQUIRED, SHALL: Absolute requirement
- MUST NOT, SHALL NOT: Absolute prohibition
- SHOULD, RECOMMENDED: Strong recommendation (can deviate with justification)
- SHOULD NOT, NOT RECOMMENDED: Strong discouragement
- MAY, OPTIONAL: Truly optional
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ConstraintLevel(Enum):
    """RFC 2119 constraint levels."""
    MUST = "must"              # Absolute requirement
    MUST_NOT = "must_not"      # Absolute prohibition  
    SHOULD = "should"          # Strong recommendation
    SHOULD_NOT = "should_not"  # Strong discouragement
    MAY = "may"                # Optional
    NONE = "none"              # No explicit constraint


@dataclass
class SOPStep:
    """A single step in an SOP."""
    number: int
    title: str
    description: str
    constraint: ConstraintLevel
    substeps: List['SOPStep'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_required(self) -> bool:
        """Check if this step is required (MUST/SHALL)."""
        return self.constraint == ConstraintLevel.MUST
    
    def is_prohibited(self) -> bool:
        """Check if this step is prohibited (MUST NOT/SHALL NOT)."""
        return self.constraint == ConstraintLevel.MUST_NOT
    
    def is_optional(self) -> bool:
        """Check if this step is optional (MAY/OPTIONAL)."""
        return self.constraint == ConstraintLevel.MAY


@dataclass
class SOPSection:
    """A section within an SOP."""
    title: str
    level: int  # Heading level (1-6)
    content: str
    steps: List[SOPStep] = field(default_factory=list)


@dataclass
class SOPDefinition:
    """Complete SOP definition."""
    name: str
    description: str
    version: str = "1.0.0"
    parameters: Dict[str, Any] = field(default_factory=dict)
    sections: List[SOPSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_required_steps(self) -> List[SOPStep]:
        """Get all required (MUST) steps."""
        required = []
        for section in self.sections:
            required.extend([s for s in section.steps if s.is_required()])
        return required
    
    def get_optional_steps(self) -> List[SOPStep]:
        """Get all optional (MAY) steps."""
        optional = []
        for section in self.sections:
            optional.extend([s for s in section.steps if s.is_optional()])
        return optional


class SOPParser:
    """
    Parser for markdown-based SOPs.
    
    Extracts structure, steps, and RFC 2119 constraints from SOP documents.
    """
    
    # RFC 2119 keyword patterns
    RFC2119_PATTERNS = {
        ConstraintLevel.MUST: r'\b(MUST|REQUIRED|SHALL)\b',
        ConstraintLevel.MUST_NOT: r'\b(MUST NOT|SHALL NOT)\b',
        ConstraintLevel.SHOULD: r'\b(SHOULD|RECOMMENDED)\b',
        ConstraintLevel.SHOULD_NOT: r'\b(SHOULD NOT|NOT RECOMMENDED)\b',
        ConstraintLevel.MAY: r'\b(MAY|OPTIONAL)\b',
    }
    
    def __init__(self):
        self._compiled_patterns = {
            level: re.compile(pattern)
            for level, pattern in self.RFC2119_PATTERNS.items()
        }
    
    def detect_constraint(self, text: str) -> ConstraintLevel:
        """
        Detect RFC 2119 constraint level in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Highest constraint level found (MUST > SHOULD > MAY)
        """
        # Check in order of precedence
        for level in [
            ConstraintLevel.MUST_NOT,
            ConstraintLevel.MUST,
            ConstraintLevel.SHOULD_NOT,
            ConstraintLevel.SHOULD,
            ConstraintLevel.MAY,
        ]:
            if self._compiled_patterns[level].search(text):
                return level
        
        return ConstraintLevel.NONE
    
    def parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """
        Extract YAML frontmatter if present.
        
        Returns:
            (frontmatter_dict, remaining_content)
        """
        frontmatter = {}
        
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                # Parse YAML frontmatter (simple key: value parsing)
                fm_text = parts[1]
                for line in fm_text.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        frontmatter[key.strip()] = value.strip()
                
                content = parts[2]
        
        return frontmatter, content
    
    def parse_sections(self, content: str) -> List[SOPSection]:
        """
        Parse markdown sections (headings).
        
        Returns:
            List of SOPSection objects
        """
        sections = []
        current_section = None
        current_content = []
        
        for line in content.split('\n'):
            # Check for heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                # Save previous section
                if current_section:
                    current_section.content = '\n'.join(current_content)
                    sections.append(current_section)
                
                # Start new section
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                current_section = SOPSection(
                    title=title,
                    level=level,
                    content="",
                )
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # Save last section
        if current_section:
            current_section.content = '\n'.join(current_content)
            sections.append(current_section)
        
        return sections
    
    def parse_steps(self, section: SOPSection) -> List[SOPStep]:
        """
        Parse steps from section content.
        
        Looks for numbered lists and extracts steps with constraints.
        """
        steps = []
        lines = section.content.split('\n')
        
        step_pattern = re.compile(r'^(\d+)\.\s+(.+)$')
        current_step = None
        current_desc = []
        
        for line in lines:
            step_match = step_pattern.match(line.strip())
            
            if step_match:
                # Save previous step
                if current_step:
                    current_step.description = '\n'.join(current_desc)
                    steps.append(current_step)
                
                # Start new step
                number = int(step_match.group(1))
                title = step_match.group(2).strip()
                
                # Detect constraint in title
                constraint = self.detect_constraint(title)
                
                current_step = SOPStep(
                    number=number,
                    title=title,
                    description="",
                    constraint=constraint,
                )
                current_desc = []
            elif current_step and line.strip():
                current_desc.append(line)
        
        # Save last step
        if current_step:
            current_step.description = '\n'.join(current_desc)
            steps.append(current_step)
        
        return steps
    
    def parse(self, filepath: Path) -> SOPDefinition:
        """
        Parse an SOP file.
        
        Args:
            filepath: Path to SOP markdown file
            
        Returns:
            SOPDefinition object
        """
        content = filepath.read_text(encoding='utf-8')
        
        # Extract frontmatter
        frontmatter, content = self.parse_frontmatter(content)
        
        # Parse sections
        sections = self.parse_sections(content)
        
        # Parse steps within sections
        for section in sections:
            section.steps = self.parse_steps(section)
        
        # Build SOP definition
        sop = SOPDefinition(
            name=frontmatter.get('name', filepath.stem),
            description=frontmatter.get('description', sections[0].content if sections else ""),
            version=frontmatter.get('version', '1.0.0'),
            parameters=frontmatter.get('parameters', {}),
            sections=sections,
            metadata=frontmatter,
        )
        
        return sop


class SOPExecutor:
    """
    Executor for running SOPs with validation and logging.
    """
    
    def __init__(self):
        self.execution_log: List[Dict[str, Any]] = []
    
    def validate_step(self, step: SOPStep, result: Any) -> bool:
        """
        Validate step execution result against constraints.
        
        Args:
            step: The step that was executed
            result: Execution result
            
        Returns:
            True if validation passed
        """
        # MUST steps require successful result
        if step.is_required() and not result:
            return False
        
        # MUST NOT steps require no result or false result
        if step.is_prohibited() and result:
            return False
        
        # SHOULD/MAY steps always pass validation
        return True
    
    def execute_step(
        self,
        step: SOPStep,
        context: Dict[str, Any],
        executor_func: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single SOP step.
        
        Args:
            step: Step to execute
            context: Execution context (variables, state)
            executor_func: Optional custom executor function
            
        Returns:
            Execution result dict
        """
        result = {
            "step": step.number,
            "title": step.title,
            "constraint": step.constraint.value,
            "status": "pending",
            "output": None,
            "valid": True,
        }
        
        try:
            # Execute step (custom or default)
            if executor_func:
                output = executor_func(step, context)
            else:
                # Default: just mark as executed
                output = {"executed": True}
            
            result["output"] = output
            result["status"] = "completed"
            
            # Validate result
            result["valid"] = self.validate_step(step, output)
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["valid"] = False
        
        self.execution_log.append(result)
        return result
    
    def execute_sop(
        self,
        sop: SOPDefinition,
        context: Optional[Dict[str, Any]] = None,
        executor_func: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Execute complete SOP.
        
        Args:
            sop: SOP definition to execute
            context: Initial execution context
            executor_func: Optional custom step executor
            
        Returns:
            Execution summary
        """
        context = context or {}
        self.execution_log = []
        
        total_steps = 0
        completed_steps = 0
        failed_steps = 0
        
        for section in sop.sections:
            for step in section.steps:
                total_steps += 1
                result = self.execute_step(step, context, executor_func)
                
                if result["status"] == "completed":
                    completed_steps += 1
                elif result["status"] == "error":
                    failed_steps += 1
                    
                    # Stop on required step failure
                    if step.is_required() and not result["valid"]:
                        return {
                            "status": "failed",
                            "reason": f"Required step {step.number} failed",
                            "total_steps": total_steps,
                            "completed_steps": completed_steps,
                            "failed_steps": failed_steps,
                            "execution_log": self.execution_log,
                        }
        
        return {
            "status": "completed",
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "execution_log": self.execution_log,
        }


# Convenience functions

def parse_sop(filepath: Path) -> SOPDefinition:
    """Parse an SOP file."""
    parser = SOPParser()
    return parser.parse(filepath)


def execute_sop(
    sop: SOPDefinition,
    context: Optional[Dict[str, Any]] = None,
    executor_func: Optional[callable] = None,
) -> Dict[str, Any]:
    """Execute an SOP."""
    executor = SOPExecutor()
    return executor.execute_sop(sop, context, executor_func)
