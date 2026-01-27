"""Pydantic schemas for agent management endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StrategyParameterSchema(BaseModel):
    """Schema for a strategy parameter."""

    name: str
    param_type: str
    description: str
    default: Any
    required: bool = False
    min_value: float | None = None
    max_value: float | None = None
    choices: list[str] | None = None


class StrategyInfo(BaseModel):
    """Information about an available strategy."""

    id: str
    name: str
    description: str
    difficulty: str
    category: str
    parameters: list[StrategyParameterSchema]
    is_dsl: bool = False


class AgentCreate(BaseModel):
    """Request to create a new agent."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    exchange_url: str = Field(
        default="http://localhost:8000", description="Exchange API URL"
    )
    api_key: str = Field(..., min_length=1, description="Exchange API key")
    strategy_type: str = Field(..., description="Strategy ID from registry")
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    strategy_source: str | None = Field(
        default=None, description="YAML source for rule-based strategies"
    )
    interval_seconds: float = Field(default=5.0, ge=1.0, le=300.0)


class AgentUpdate(BaseModel):
    """Request to update an agent."""

    name: str | None = None
    description: str | None = None
    strategy_params: dict[str, Any] | None = None
    strategy_source: str | None = None
    interval_seconds: float | None = Field(default=None, ge=1.0, le=300.0)


class AgentResponse(BaseModel):
    """Response with agent details."""

    id: str
    name: str
    description: str
    exchange_url: str
    strategy_type: str
    strategy_params: dict[str, Any]
    strategy_source: str | None
    interval_seconds: float
    status: str
    created_at: datetime
    started_at: datetime | None
    stopped_at: datetime | None
    last_error: str | None
    error_count: int
    total_trades: int
    total_cycles: int

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """Response for listing agents."""

    agents: list[AgentResponse]


class StrategyValidationRequest(BaseModel):
    """Request to validate a strategy."""

    strategy_type: str
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    strategy_source: str | None = None


class StrategyValidationResponse(BaseModel):
    """Response from strategy validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
