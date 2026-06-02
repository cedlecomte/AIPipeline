"""Data models for dynamically-defined skills, agents, and pipelines."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    """A markdown skill document that can be attached to agents."""

    skill_id: str
    name: str
    slug: str
    description: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PluginConfig(BaseModel):
    """Plugin configuration with environment variables for an agent."""

    plugin_name: str
    env_vars: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class AgentDefinition(BaseModel):
    """A dynamically-defined agent with prompt, skills, and plugins."""

    agent_id: str
    name: str
    slug: str
    description: str = ""
    system_prompt: str = ""
    skill_ids: list[str] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    plugins: list[PluginConfig] = Field(default_factory=list)
    model: str = "claude-sonnet-4-5@20250929"
    max_tokens: int = 16000
    effort: str = "enabled"
    is_builtin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineNode(BaseModel):
    """A node in a visual pipeline graph.

    node_type: "trigger" | "agent" | "output"
    - trigger: entry point (webhook). agent_id is empty. config has trigger settings.
    - agent: an LLM agent. agent_id references AgentDefinition.
    - output: exit point (webhook/slack). agent_id is empty. config has output settings.
    """

    node_id: str
    node_type: str = "agent"
    agent_id: str = ""
    position_x: float = 0.0
    position_y: float = 0.0
    label: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineEdge(BaseModel):
    """An edge connecting two nodes in a pipeline graph."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    condition: str | None = None


class PipelineDefinition(BaseModel):
    """A visual pipeline graph definition."""

    pipeline_id: str
    name: str
    description: str = ""
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)
    entry_node_id: str = ""
    is_active: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
