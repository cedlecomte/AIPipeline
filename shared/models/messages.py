"""Shared message models for inter-agent communication."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of agents in the pipeline."""

    JIRA_INTEGRATION = "jira_integration"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    TESTER = "tester"
    CODE_REVIEWER = "code_reviewer"
    RELEASE = "release"
    CERTIFICATION = "certification"
    ORCHESTRATOR = "orchestrator"


class MessageType(str, Enum):
    """Types of messages passed between agents."""

    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_ERROR = "task_error"
    STATUS_UPDATE = "status_update"
    ARTIFACT_READY = "artifact_ready"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"


class TaskStatus(str, Enum):
    """Status of a task in the pipeline."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentMessage(BaseModel):
    """Base message structure for inter-agent communication."""

    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_type: MessageType
    from_agent: AgentType
    to_agent: AgentType
    task_id: str
    correlation_id: str  # Traces the entire pipeline run
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class DynamicAgentMessage(BaseModel):
    """Message for dynamic agents using string slugs instead of AgentType enum."""

    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_type: MessageType
    from_agent: str
    to_agent: str
    task_id: str
    correlation_id: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class JiraRequirements(BaseModel):
    """Extracted requirements from a Jira card."""

    issue_key: str
    summary: str
    description: str
    acceptance_criteria: list[str]
    labels: list[str]
    components: list[str]
    priority: str
    raw_data: dict[str, Any]


class ArchitecturePlan(BaseModel):
    """Architecture plan created by the Architect agent."""

    modules: list[dict[str, Any]]
    roles: list[dict[str, Any]]
    plugins: list[dict[str, Any]]
    dependencies: list[str]
    file_structure: dict[str, Any]
    implementation_notes: str
    estimated_complexity: str


class CodeArtifact(BaseModel):
    """Code artifact produced by the Developer agent."""

    file_path: str
    content: str
    artifact_type: str  # module, role, plugin, test, doc
    dependencies: list[str] = Field(default_factory=list)


class TestResults(BaseModel):
    """Test results from the Tester agent."""

    test_type: str  # unit, integration, sanity
    passed: int
    failed: int
    skipped: int
    total: int
    failures: list[dict[str, Any]] = Field(default_factory=list)
    coverage_percent: float | None = None
    log_output: str


class ReviewFeedback(BaseModel):
    """Code review feedback from the Code Reviewer agent."""

    overall_score: float  # 0-10
    security_issues: list[dict[str, Any]]
    quality_issues: list[dict[str, Any]]
    best_practices: list[dict[str, Any]]
    recommendations: list[str]
    approved: bool


class ReleaseInfo(BaseModel):
    """Release information from the Release agent."""

    version: str
    changelog: str
    release_notes: str
    git_tag: str
    published_url: str | None = None


class CertificationReport(BaseModel):
    """Certification report from the Certification agent."""

    compliant: bool
    ansible_version_tested: str
    galaxy_score: float | None = None
    issues: list[dict[str, Any]]
    recommendations: list[str]
