"""Agent service - business logic for agent management."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentplatform.models.agent import Agent, AgentStatus
from agentplatform.schemas.agent import AgentCreate, AgentUpdate


async def create_agent(session: AsyncSession, data: AgentCreate) -> Agent:
    """Create a new agent."""
    agent = Agent(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        exchange_url=data.exchange_url,
        api_key=data.api_key,
        strategy_type=data.strategy_type,
        strategy_params=data.strategy_params,
        strategy_source=data.strategy_source,
        interval_seconds=data.interval_seconds,
        status=AgentStatus.CREATED,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


async def get_agent(session: AsyncSession, agent_id: str) -> Agent | None:
    """Get an agent by ID."""
    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    return result.scalar_one_or_none()


async def list_agents(
    session: AsyncSession,
    status: str | None = None,
) -> list[Agent]:
    """List agents with optional filters."""
    query = select(Agent).order_by(Agent.created_at.desc())

    if status:
        query = query.where(Agent.status == AgentStatus[status])

    result = await session.execute(query)
    return list(result.scalars().all())


async def update_agent(
    session: AsyncSession,
    agent: Agent,
    data: AgentUpdate,
) -> Agent:
    """Update agent configuration."""
    if data.name is not None:
        agent.name = data.name
    if data.description is not None:
        agent.description = data.description
    if data.strategy_params is not None:
        agent.strategy_params = data.strategy_params
    if data.strategy_source is not None:
        agent.strategy_source = data.strategy_source
    if data.interval_seconds is not None:
        agent.interval_seconds = data.interval_seconds

    await session.commit()
    await session.refresh(agent)
    return agent


async def delete_agent(session: AsyncSession, agent: Agent) -> None:
    """Delete an agent."""
    await session.delete(agent)
    await session.commit()


async def start_agent(session: AsyncSession, agent: Agent) -> Agent:
    """Mark agent as running."""
    agent.status = AgentStatus.RUNNING
    agent.started_at = datetime.utcnow()
    agent.last_error = None
    await session.commit()
    await session.refresh(agent)
    return agent


async def stop_agent(session: AsyncSession, agent: Agent) -> Agent:
    """Mark agent as stopped."""
    agent.status = AgentStatus.STOPPED
    agent.stopped_at = datetime.utcnow()
    await session.commit()
    await session.refresh(agent)
    return agent


async def pause_agent(session: AsyncSession, agent: Agent) -> Agent:
    """Mark agent as paused."""
    agent.status = AgentStatus.PAUSED
    await session.commit()
    await session.refresh(agent)
    return agent


async def record_error(
    session: AsyncSession,
    agent: Agent,
    error: str,
) -> Agent:
    """Record an agent error."""
    agent.last_error = error
    agent.error_count += 1
    if agent.error_count >= 10:  # Too many errors, auto-stop
        agent.status = AgentStatus.ERROR
        agent.stopped_at = datetime.utcnow()
    await session.commit()
    await session.refresh(agent)
    return agent


async def record_cycle(session: AsyncSession, agent: Agent, trades: int) -> Agent:
    """Record a completed trading cycle."""
    agent.total_cycles += 1
    agent.total_trades += trades
    await session.commit()
    return agent
