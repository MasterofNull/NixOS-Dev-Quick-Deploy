#!/usr/bin/env python3
"""
Tree of Thoughts (ToT) Pattern

Implements Tree of Thoughts for complex multi-step reasoning:
- Generate multiple thought candidates at each step
- Evaluate each thought's promise
- Search through thought space (BFS/DFS)
- Backtrack when needed
- Find optimal solution path

Part of Phase 4 Batch 4.1: Agentic Pattern Library

Reference: "Tree of Thoughts: Deliberate Problem Solving with Large Language Models"
https://arxiv.org/abs/2305.10601
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SearchStrategy(Enum):
    """Search strategy for thought tree"""
    BFS = "breadth_first"  # Breadth-first search
    DFS = "depth_first"  # Depth-first search
    BEAM = "beam_search"  # Beam search (keep top-k at each level)


@dataclass
class ThoughtNode:
    """Node in the thought tree"""
    thought: str
    depth: int
    parent: Optional['ThoughtNode'] = None
    children: List['ThoughtNode'] = field(default_factory=list)
    value: float = 0.0  # Evaluation score
    visited: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ToTResult:
    """Result of Tree of Thoughts execution"""
    task: str
    success: bool
    solution_path: List[str]
    total_nodes_explored: int
    max_depth_reached: int
    best_value: float
    search_strategy: SearchStrategy
    error_message: Optional[str] = None


class TreeOfThoughtsAgent:
    """Tree of Thoughts reasoning agent"""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        search_strategy: SearchStrategy = SearchStrategy.BFS,
        max_depth: int = 5,
        thoughts_per_step: int = 3,
        beam_width: int = 3,
    ):
        self.llm_client = llm_client
        self.search_strategy = search_strategy
        self.max_depth = max_depth
        self.thoughts_per_step = thoughts_per_step
        self.beam_width = beam_width

        logger.info(
            f"Tree of Thoughts agent initialized "
            f"(strategy={search_strategy.value}, "
            f"max_depth={max_depth}, "
            f"thoughts_per_step={thoughts_per_step})"
        )

    async def solve(self, task: str, goal_checker: Optional[Callable] = None) -> ToTResult:
        """Solve task using Tree of Thoughts"""
        logger.info(f"ToT: Solving task: {task}")

        # Create root node
        root = ThoughtNode(
            thought=f"Task: {task}",
            depth=0,
        )

        # Track explored nodes
        nodes_explored = 0
        max_depth = 0

        try:
            # Search through thought space
            if self.search_strategy == SearchStrategy.BFS:
                solution_node = await self._breadth_first_search(
                    root, task, goal_checker
                )
            elif self.search_strategy == SearchStrategy.DFS:
                solution_node = await self._depth_first_search(
                    root, task, goal_checker
                )
            else:  # BEAM
                solution_node = await self._beam_search(
                    root, task, goal_checker
                )

            # Count explored nodes
            nodes_explored = self._count_nodes(root)
            max_depth = self._get_max_depth(root)

            if solution_node:
                # Extract solution path
                solution_path = self._extract_path(solution_node)

                return ToTResult(
                    task=task,
                    success=True,
                    solution_path=solution_path,
                    total_nodes_explored=nodes_explored,
                    max_depth_reached=max_depth,
                    best_value=solution_node.value,
                    search_strategy=self.search_strategy,
                )
            else:
                return ToTResult(
                    task=task,
                    success=False,
                    solution_path=[],
                    total_nodes_explored=nodes_explored,
                    max_depth_reached=max_depth,
                    best_value=0.0,
                    search_strategy=self.search_strategy,
                    error_message="No solution found",
                )

        except Exception as e:
            logger.exception(f"ToT error: {e}")
            return ToTResult(
                task=task,
                success=False,
                solution_path=[],
                total_nodes_explored=nodes_explored,
                max_depth_reached=max_depth,
                best_value=0.0,
                search_strategy=self.search_strategy,
                error_message=str(e),
            )

    async def _breadth_first_search(
        self,
        root: ThoughtNode,
        task: str,
        goal_checker: Optional[Callable],
    ) -> Optional[ThoughtNode]:
        """Breadth-first search through thought tree"""
        queue = deque([root])

        while queue:
            node = queue.popleft()
            node.visited = True

            logger.info(f"  Exploring (depth={node.depth}): {node.thought[:60]}...")

            # Check if goal reached
            if goal_checker and goal_checker(node.thought):
                logger.info(f"  Goal reached!")
                return node

            # Stop at max depth
            if node.depth >= self.max_depth:
                continue

            # Generate child thoughts
            children = await self._generate_thoughts(node, task)

            # Evaluate each child
            for child in children:
                child.value = await self._evaluate_thought(child, task)
                node.children.append(child)
                queue.append(child)

        # No solution found
        return None

    async def _depth_first_search(
        self,
        root: ThoughtNode,
        task: str,
        goal_checker: Optional[Callable],
    ) -> Optional[ThoughtNode]:
        """Depth-first search through thought tree"""
        stack = [root]

        while stack:
            node = stack.pop()
            node.visited = True

            logger.info(f"  Exploring (depth={node.depth}): {node.thought[:60]}...")

            # Check if goal reached
            if goal_checker and goal_checker(node.thought):
                logger.info(f"  Goal reached!")
                return node

            # Stop at max depth
            if node.depth >= self.max_depth:
                continue

            # Generate child thoughts
            children = await self._generate_thoughts(node, task)

            # Evaluate and add children (in reverse for DFS)
            for child in reversed(children):
                child.value = await self._evaluate_thought(child, task)
                node.children.append(child)
                stack.append(child)

        return None

    async def _beam_search(
        self,
        root: ThoughtNode,
        task: str,
        goal_checker: Optional[Callable],
    ) -> Optional[ThoughtNode]:
        """Beam search - keep top-k candidates at each level"""
        current_level = [root]

        for depth in range(self.max_depth):
            next_level = []

            for node in current_level:
                node.visited = True

                logger.info(f"  Exploring (depth={node.depth}): {node.thought[:60]}...")

                # Check if goal reached
                if goal_checker and goal_checker(node.thought):
                    logger.info(f"  Goal reached!")
                    return node

                # Generate child thoughts
                children = await self._generate_thoughts(node, task)

                # Evaluate children
                for child in children:
                    child.value = await self._evaluate_thought(child, task)
                    node.children.append(child)
                    next_level.append(child)

            if not next_level:
                break

            # Keep only top-k (beam width)
            next_level.sort(key=lambda n: n.value, reverse=True)
            current_level = next_level[:self.beam_width]

            logger.info(f"  Beam search: kept top {len(current_level)} thoughts")

        # Return best node found
        if current_level:
            return max(current_level, key=lambda n: n.value)

        return None

    async def _generate_thoughts(
        self,
        parent: ThoughtNode,
        task: str,
    ) -> List[ThoughtNode]:
        """Generate possible next thoughts"""
        thoughts = []

        # Generate multiple thought candidates
        for i in range(self.thoughts_per_step):
            thought_text = await self._generate_single_thought(parent, task, i)

            thought = ThoughtNode(
                thought=thought_text,
                depth=parent.depth + 1,
                parent=parent,
            )

            thoughts.append(thought)

        return thoughts

    async def _generate_single_thought(
        self,
        parent: ThoughtNode,
        task: str,
        variant: int,
    ) -> str:
        """Generate a single thought candidate"""
        if self.llm_client:
            # Would query LLM for next thought
            return await self._query_llm_for_thought(parent, task, variant)
        else:
            # Fallback: simple thought generation
            return f"Thought variant {variant + 1} from: {parent.thought[:30]}..."

    async def _query_llm_for_thought(
        self,
        parent: ThoughtNode,
        task: str,
        variant: int,
    ) -> str:
        """Query LLM for thought (placeholder)"""
        # In production, would call actual LLM
        return f"Next step {variant + 1} for solving: {task}"

    async def _evaluate_thought(
        self,
        thought: ThoughtNode,
        task: str,
    ) -> float:
        """Evaluate how promising a thought is"""
        if self.llm_client:
            # Would use LLM to evaluate thought quality
            return await self._query_llm_for_evaluation(thought, task)
        else:
            # Fallback: simple heuristic evaluation
            # Longer, more detailed thoughts score higher
            return min(1.0, len(thought.thought) / 100.0)

    async def _query_llm_for_evaluation(
        self,
        thought: ThoughtNode,
        task: str,
    ) -> float:
        """Query LLM for thought evaluation (placeholder)"""
        # In production, would call actual LLM
        return 0.7  # Default score

    def _extract_path(self, node: ThoughtNode) -> List[str]:
        """Extract path from root to node"""
        path = []
        current = node

        while current:
            path.append(current.thought)
            current = current.parent

        return list(reversed(path))

    def _count_nodes(self, root: ThoughtNode) -> int:
        """Count total nodes in tree"""
        count = 1

        for child in root.children:
            count += self._count_nodes(child)

        return count

    def _get_max_depth(self, root: ThoughtNode) -> int:
        """Get maximum depth reached"""
        if not root.children:
            return root.depth

        return max(self._get_max_depth(child) for child in root.children)


async def main():
    """Test Tree of Thoughts"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Tree of Thoughts Pattern Test")
    logger.info("=" * 60)

    # Create agent
    agent = TreeOfThoughtsAgent(
        search_strategy=SearchStrategy.BFS,
        max_depth=3,
        thoughts_per_step=2,
    )

    # Simple goal checker
    def goal_checker(thought: str) -> bool:
        return "solution" in thought.lower()

    # Test task
    task = "Find the optimal solution"

    result = await agent.solve(task, goal_checker=goal_checker)

    logger.info(f"\nResult:")
    logger.info(f"  Success: {result.success}")
    logger.info(f"  Nodes Explored: {result.total_nodes_explored}")
    logger.info(f"  Max Depth: {result.max_depth_reached}")
    logger.info(f"  Best Value: {result.best_value:.2f}")

    if result.success:
        logger.info(f"\nSolution Path:")
        for i, thought in enumerate(result.solution_path):
            logger.info(f"  {i + 1}. {thought}")


if __name__ == "__main__":
    asyncio.run(main())
