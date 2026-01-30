"""Pydantic models for scenario YAML validation."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ScenarioCompany(BaseModel):
    """Company definition in a scenario."""

    ticker: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1, max_length=255)
    total_shares: int = Field(..., gt=0)
    float_shares: int = Field(..., gt=0)
    ipo_price: float = Field(default=100.0, gt=0)

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        return v.upper()


class ScenarioAccount(BaseModel):
    """Account definition in a scenario."""

    id: str = Field(..., min_length=1, max_length=50)
    initial_cash: float = Field(default=0.0, ge=0)


class ScenarioAgent(BaseModel):
    """Agent definition in a scenario."""

    name: str = Field(..., min_length=1, max_length=255)
    account: str = Field(..., description="Account ID to use for trading")
    strategy_type: str = Field(..., description="Strategy ID (e.g., 'random', 'rule_based')")
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    strategy_source: str | None = Field(default=None, description="Inline YAML for rule_based")
    strategy_source_file: str | None = Field(
        default=None, description="Path to YAML file for rule_based"
    )
    interval_seconds: float = Field(default=5.0, ge=1.0, le=300.0)
    auto_start: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_strategy_source(self) -> "ScenarioAgent":
        if self.strategy_type == "rule_based":
            if not self.strategy_source and not self.strategy_source_file:
                raise ValueError(
                    "rule_based strategy requires either strategy_source or strategy_source_file"
                )
        return self


class ScenarioExchange(BaseModel):
    """Exchange connection settings."""

    url: str = Field(default="http://localhost:8000")


class ScenarioAgentPlatform(BaseModel):
    """Agent platform connection settings."""

    url: str = Field(default="http://localhost:8001")


class ScenarioConfig(BaseModel):
    """Complete scenario configuration."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    exchange: ScenarioExchange = Field(default_factory=ScenarioExchange)
    companies: list[ScenarioCompany] = Field(default_factory=list)
    accounts: list[ScenarioAccount] = Field(default_factory=list)
    agent_platform: ScenarioAgentPlatform = Field(default_factory=ScenarioAgentPlatform)
    agents: list[ScenarioAgent] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_agent_accounts(self) -> "ScenarioConfig":
        account_ids = {a.id for a in self.accounts}
        for agent in self.agents:
            if agent.account not in account_ids:
                raise ValueError(
                    f"Agent '{agent.name}' references unknown account '{agent.account}'"
                )
        return self

    def resolve_strategy_sources(self, base_path: Path) -> None:
        """Resolve strategy_source_file paths to inline strategy_source."""
        for agent in self.agents:
            if agent.strategy_source_file and not agent.strategy_source:
                source_path = base_path / agent.strategy_source_file
                if not source_path.exists():
                    raise FileNotFoundError(
                        f"Strategy file not found: {source_path} (for agent '{agent.name}')"
                    )
                agent.strategy_source = source_path.read_text()
