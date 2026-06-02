"""Configuration management using Pydantic settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Vertex AI (as per Anthropic SDK documentation)
    # https://docs.anthropic.com/en/api/claude-on-vertex-ai
    anthropic_vertex_project_id: str = Field(..., description="GCP project ID for VertexAI")
    cloud_ml_region: str = Field(
        default="us-east5",
        description="VertexAI region (us-east5, us-central1, europe-west1, etc.)"
    )
    # Authentication uses Google Cloud Application Default Credentials:
    # - gcloud auth application-default login (development)
    # - GOOGLE_APPLICATION_CREDENTIALS env var (production)
    # - Automatic when running on GCP (Compute Engine, Cloud Run, etc.)

    # Anthropic API (fallback if not using VertexAI)
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")

    # Redis
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: str | None = Field(default=None, description="Redis password")

    # Jira
    jira_base_url: str = Field(..., description="Jira base URL (e.g. https://yoursite.atlassian.net)")
    jira_email: str = Field(..., description="Jira account email for API auth")
    jira_cloud_id: str = Field(..., description="Jira cloud ID")
    jira_api_token: str = Field(..., description="Jira API token")
    jira_project_key: str = Field(default="ANSIBLE", description="Jira project key")

    # Git Platform
    github_token: str | None = Field(default=None, description="GitHub personal access token")
    gitlab_token: str | None = Field(default=None, description="GitLab access token")
    git_platform: str = Field(default="github", description="github or gitlab")
    git_repo_owner: str = Field(
        default="ansible-collections", description="Repository owner/organization"
    )
    git_repo_name: str = Field(default="amazon.aws", description="Repository name")

    # Agent Configuration
    agent_model: str = Field(default="claude-sonnet-4-5@20250929", description="Claude model to use")
    agent_max_tokens: int = Field(default=16000, description="Max tokens per request")
    agent_effort: str = Field(default="enabled", description="Thinking mode: enabled|disabled")
    yolo_mode: bool = Field(default=True, description="Autonomous operation mode")

    # Dashboard
    dashboard_host: str = Field(default="0.0.0.0", description="Dashboard host")
    dashboard_port: int = Field(default=8080, description="Dashboard port")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Logging format: json or console")

    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
