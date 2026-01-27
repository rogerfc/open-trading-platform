"""Configuration for trading agents."""

from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Configuration for a single trading agent."""

    api_key: str
    base_url: str = "http://localhost:8000"
    interval: float = 5.0  # seconds between trading cycles
    name: str = ""  # optional display name for logging


@dataclass
class RunnerConfig:
    """Configuration for multi-agent runner."""

    agents: list[AgentConfig] = field(default_factory=list)
    base_url: str = "http://localhost:8000"
    interval: float = 5.0
