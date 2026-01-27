"""Agent model - represents an autonomous trading agent."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from agentplatform.database import Base


class AgentStatus(enum.Enum):
    """Agent lifecycle status."""

    CREATED = "CREATED"  # Agent created but never started
    RUNNING = "RUNNING"  # Currently executing trades
    PAUSED = "PAUSED"  # Temporarily stopped, can resume
    STOPPED = "STOPPED"  # Permanently stopped
    ERROR = "ERROR"  # Stopped due to error


class Agent(Base):
    """An autonomous trading agent configuration."""

    __tablename__ = "agents"

    # Primary key
    id: Mapped[str] = mapped_column(String, primary_key=True)

    # Human-readable name
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Description (optional, for users to document their strategy)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Exchange connection
    exchange_url: Mapped[str] = mapped_column(
        String(500), nullable=False, default="http://localhost:8000"
    )
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)

    # Strategy configuration
    strategy_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "rule_based", "random", "momentum"

    # Strategy parameters as JSON
    strategy_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # For DSL strategies, store the YAML source
    strategy_source: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Execution settings
    interval_seconds: Mapped[float] = mapped_column(Float, default=5.0)

    # Lifecycle
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus), default=AgentStatus.CREATED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Error tracking
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    # Performance tracking
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_cycles: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"Agent(id={self.id!r}, name={self.name!r}, status={self.status.value})"
