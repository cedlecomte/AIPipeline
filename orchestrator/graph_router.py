"""Graph-based pipeline routing for visual pipeline definitions."""

from typing import Any

import structlog

from shared.models.definitions import PipelineDefinition, PipelineEdge, PipelineNode

logger = structlog.get_logger()


class GraphRouter:
    """Routes messages through a pipeline graph based on edges and condition nodes."""

    def __init__(self, pipeline: PipelineDefinition):
        self.pipeline = pipeline
        self.adjacency: dict[str, list[PipelineEdge]] = {}
        self._nodes: dict[str, PipelineNode] = {}
        self._build()

    def _build(self) -> None:
        for node in self.pipeline.nodes:
            self._nodes[node.node_id] = node
        for edge in self.pipeline.edges:
            self.adjacency.setdefault(edge.source_node_id, []).append(edge)

    def get_entry_node(self) -> PipelineNode:
        for node in self.pipeline.nodes:
            if node.node_type == "trigger":
                return node
        node = self._nodes.get(self.pipeline.entry_node_id)
        if not node:
            raise ValueError(f"No trigger node and entry_node_id {self.pipeline.entry_node_id} not found")
        return node

    def get_first_agent_after_trigger(self) -> list[PipelineNode]:
        trigger = self.get_entry_node()
        if trigger.node_type == "trigger":
            return self.get_next_nodes(trigger.node_id, {})
        return [trigger]

    def get_node(self, node_id: str) -> PipelineNode:
        node = self._nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        return node

    def get_next_nodes(self, current_node_id: str, result: dict[str, Any]) -> list[PipelineNode]:
        """Determine next nodes based on edges, conditions, and condition nodes."""
        edges = self.adjacency.get(current_node_id, [])
        next_nodes = []

        for edge in edges:
            target = self._nodes.get(edge.target_node_id)
            if not target:
                continue

            if edge.condition is None:
                next_nodes.append(target)
            elif self._evaluate_edge_condition(edge.condition, result):
                next_nodes.append(target)

        return next_nodes

    def evaluate_condition_node(self, node: PipelineNode, payload: dict[str, Any]) -> list[PipelineNode]:
        """Evaluate an If/condition node and return the next nodes based on the result.

        A condition node has two output handles: "true" and "false".
        Edges from a condition node have their condition field set to "true" or "false"
        to indicate which handle they come from.
        """
        config = node.config
        field = config.get("field", "")
        operator = config.get("operator", "==")
        value = config.get("value", "")

        result = self._evaluate_condition(field, operator, value, payload)

        logger.info(
            "graph_router.condition_evaluated",
            node_id=node.node_id,
            field=field,
            operator=operator,
            value=value,
            result=result,
        )

        handle = "true" if result else "false"
        edges = self.adjacency.get(node.node_id, [])
        next_nodes = []

        for edge in edges:
            if edge.condition == handle:
                target = self._nodes.get(edge.target_node_id)
                if target:
                    next_nodes.append(target)

        return next_nodes

    def _evaluate_condition(self, field: str, operator: str, value: str, payload: dict[str, Any]) -> bool:
        """Evaluate a condition expression against the payload."""
        actual = payload.get(field)
        if actual is None:
            # Try nested access with dot notation
            parts = field.split(".")
            actual = payload
            for part in parts:
                if isinstance(actual, dict):
                    actual = actual.get(part)
                else:
                    actual = None
                    break

        if operator == "exists":
            return actual is not None and actual != "" and actual is not False

        if actual is None:
            return False

        actual_str = str(actual)

        if operator == "==":
            return actual_str == value or actual == _try_parse(value)
        elif operator == "!=":
            return actual_str != value and actual != _try_parse(value)
        elif operator == "contains":
            return value in actual_str
        elif operator == ">":
            try:
                return float(actual) > float(value)
            except (ValueError, TypeError):
                return False
        elif operator == "<":
            try:
                return float(actual) < float(value)
            except (ValueError, TypeError):
                return False

        return False

    def _evaluate_edge_condition(self, condition: str, result: dict[str, Any]) -> bool:
        if condition in ("true", "false"):
            return True
        if condition in result and result[condition]:
            return True
        if result.get("status") == condition:
            return True
        return False


def _try_parse(value: str) -> Any:
    """Try to parse a string value as bool/int/float."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
