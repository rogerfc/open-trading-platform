"""Agent management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agentplatform.database import get_session, engine, Base
from agentplatform.models.agent import Agent, AgentStatus
from agentplatform.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    StrategyInfo,
    StrategyParameterSchema,
    StrategyValidationRequest,
    StrategyValidationResponse,
)
from agentplatform.services import agent as agent_service
from agentplatform.services.runner import runner
from agentplatform.strategies.registry import registry
from agentplatform.strategies.dsl.compiler import compile_yaml, DSLCompilationError

router = APIRouter()


# ============================================================================
# Admin Endpoints
# ============================================================================


@router.post(
    "/admin/reset",
    summary="Reset platform",
    response_model=dict,
)
async def reset_platform(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Stop all running agents and clear the database."""
    # Stop all running agents
    agents = await agent_service.list_agents(session)
    stopped_count = 0
    for agent in agents:
        if agent.status == AgentStatus.RUNNING:
            await runner.stop_agent(agent.id)
            stopped_count += 1

    # Clear database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    return {"status": "reset", "agents_stopped": stopped_count}


# ============================================================================
# Strategy Registry Endpoints
# ============================================================================


@router.get(
    "/strategies",
    response_model=list[StrategyInfo],
    summary="List available strategies",
)
async def list_strategies(
    difficulty: str | None = None,
    category: str | None = None,
) -> list[StrategyInfo]:
    """Get all available strategies with their parameter schemas."""
    strategies = registry.list_all()

    if difficulty:
        strategies = [s for s in strategies if s.difficulty == difficulty]
    if category:
        strategies = [s for s in strategies if s.category == category]

    return [
        StrategyInfo(
            id=s.id,
            name=s.name,
            description=s.description,
            difficulty=s.difficulty,
            category=s.category,
            parameters=[
                StrategyParameterSchema(
                    name=p.name,
                    param_type=p.param_type,
                    description=p.description,
                    default=p.default,
                    required=p.required,
                    min_value=p.min_value,
                    max_value=p.max_value,
                    choices=p.choices,
                )
                for p in s.parameters
            ],
            is_dsl=s.is_dsl,
        )
        for s in strategies
    ]


@router.get(
    "/strategies/{strategy_id}",
    response_model=StrategyInfo,
    summary="Get strategy details",
)
async def get_strategy(strategy_id: str) -> StrategyInfo:
    """Get detailed information about a specific strategy."""
    definition = registry.get(strategy_id)
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy '{strategy_id}' not found",
        )

    return StrategyInfo(
        id=definition.id,
        name=definition.name,
        description=definition.description,
        difficulty=definition.difficulty,
        category=definition.category,
        parameters=[
            StrategyParameterSchema(
                name=p.name,
                param_type=p.param_type,
                description=p.description,
                default=p.default,
                required=p.required,
                min_value=p.min_value,
                max_value=p.max_value,
                choices=p.choices,
            )
            for p in definition.parameters
        ],
        is_dsl=definition.is_dsl,
    )


@router.post(
    "/strategies/validate",
    response_model=StrategyValidationResponse,
    summary="Validate strategy configuration",
)
async def validate_strategy(
    request: StrategyValidationRequest,
) -> StrategyValidationResponse:
    """Validate a strategy configuration without creating an agent."""
    errors = []
    warnings = []

    definition = registry.get(request.strategy_type)
    if not definition:
        return StrategyValidationResponse(
            valid=False,
            errors=[f"Unknown strategy type: {request.strategy_type}"],
        )

    if definition.is_dsl:
        if not request.strategy_source:
            return StrategyValidationResponse(
                valid=False,
                errors=["Rule-based strategy requires YAML source"],
            )

        try:
            compile_yaml(request.strategy_source)
        except DSLCompilationError as e:
            return StrategyValidationResponse(
                valid=False,
                errors=[str(e)],
            )
    else:
        param_errors = definition.validate_params(request.strategy_params)
        if param_errors:
            return StrategyValidationResponse(
                valid=False,
                errors=param_errors,
            )

    return StrategyValidationResponse(valid=True, errors=[], warnings=warnings)


# ============================================================================
# Agent CRUD Endpoints
# ============================================================================


@router.post(
    "/agents",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new agent",
)
async def create_agent(
    data: AgentCreate,
    session: AsyncSession = Depends(get_session),
) -> AgentResponse:
    """Create a new autonomous trading agent."""
    definition = registry.get(data.strategy_type)
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown strategy type: {data.strategy_type}",
        )

    if definition.is_dsl:
        if not data.strategy_source:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rule-based strategy requires strategy_source (YAML)",
            )
        try:
            compile_yaml(data.strategy_source)
        except DSLCompilationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid strategy YAML: {e}",
            )
    else:
        errors = definition.validate_params(data.strategy_params)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid parameters: {'; '.join(errors)}",
            )

    agent = await agent_service.create_agent(session, data)
    return _agent_to_response(agent)


@router.get(
    "/agents",
    response_model=AgentListResponse,
    summary="List all agents",
)
async def list_agents(
    status_filter: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> AgentListResponse:
    """Get all agents, optionally filtered by status."""
    agents = await agent_service.list_agents(session, status=status_filter)
    return AgentListResponse(agents=[_agent_to_response(a) for a in agents])


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent details",
)
async def get_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentResponse:
    """Get detailed information about an agent."""
    agent = await agent_service.get_agent(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )
    return _agent_to_response(agent)


@router.patch(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="Update an agent",
)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    session: AsyncSession = Depends(get_session),
) -> AgentResponse:
    """Update agent configuration. Only stopped or paused agents can be updated."""
    agent = await agent_service.get_agent(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.status == AgentStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a running agent. Stop it first.",
        )

    agent = await agent_service.update_agent(session, agent, data)
    return _agent_to_response(agent)


@router.delete(
    "/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an agent",
)
async def delete_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an agent. Running agents must be stopped first."""
    agent = await agent_service.get_agent(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.status == AgentStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running agent. Stop it first.",
        )

    await agent_service.delete_agent(session, agent)


# ============================================================================
# Agent Lifecycle Endpoints
# ============================================================================


@router.post(
    "/agents/{agent_id}/start",
    response_model=AgentResponse,
    summary="Start an agent",
)
async def start_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentResponse:
    """Start an agent's trading loop."""
    agent = await agent_service.get_agent(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.status == AgentStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is already running",
        )

    # Update status first (before starting runner to avoid race condition)
    agent = await agent_service.start_agent(session, agent)

    # Start the agent in the runner
    await runner.start_agent(agent)

    return _agent_to_response(agent)


@router.post(
    "/agents/{agent_id}/stop",
    response_model=AgentResponse,
    summary="Stop an agent",
)
async def stop_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentResponse:
    """Stop an agent's trading loop."""
    agent = await agent_service.get_agent(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.status not in (AgentStatus.RUNNING, AgentStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot stop agent in {agent.status.value} status",
        )

    # Stop the agent in the runner
    await runner.stop_agent(agent.id)

    # Update status
    agent = await agent_service.stop_agent(session, agent)
    return _agent_to_response(agent)


@router.post(
    "/agents/{agent_id}/pause",
    response_model=AgentResponse,
    summary="Pause an agent",
)
async def pause_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentResponse:
    """Temporarily pause an agent."""
    agent = await agent_service.get_agent(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.status != AgentStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only running agents can be paused",
        )

    # Pause in runner
    await runner.stop_agent(agent.id)

    # Update status
    agent = await agent_service.pause_agent(session, agent)
    return _agent_to_response(agent)


def _agent_to_response(agent) -> AgentResponse:
    """Convert agent model to response schema."""
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        exchange_url=agent.exchange_url,
        strategy_type=agent.strategy_type,
        strategy_params=agent.strategy_params,
        strategy_source=agent.strategy_source,
        interval_seconds=agent.interval_seconds,
        status=agent.status.value,
        created_at=agent.created_at,
        started_at=agent.started_at,
        stopped_at=agent.stopped_at,
        last_error=agent.last_error,
        error_count=agent.error_count,
        total_trades=agent.total_trades,
        total_cycles=agent.total_cycles,
    )
