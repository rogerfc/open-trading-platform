"""Agent runner - executes trading agents."""

import asyncio
import logging

from agentplatform.client import ExchangeClient
from agentplatform.database import AsyncSessionLocal
from agentplatform.models.agent import Agent, AgentStatus
from agentplatform.services import agent as agent_service
from agentplatform.strategies import Action, MarketContext, Strategy
from agentplatform.strategies.registry import registry
from agentplatform.strategies.dsl.compiler import compile_yaml
from agentplatform import telemetry

logger = logging.getLogger(__name__)


async def gather_context(client: ExchangeClient) -> MarketContext:
    """Gather complete market context from the exchange."""
    account, holdings, companies, open_orders = await asyncio.gather(
        client.get_account(),
        client.get_holdings(),
        client.get_companies(),
        client.get_orders(status="OPEN"),
    )

    tickers = [c.ticker for c in companies]

    orderbook_tasks = [client.get_orderbook(t) for t in tickers]
    trades_tasks = [client.get_trades(t, limit=20) for t in tickers]

    orderbooks_list = await asyncio.gather(*orderbook_tasks, return_exceptions=True)
    trades_list = await asyncio.gather(*trades_tasks, return_exceptions=True)

    orderbooks = {}
    for ticker, ob in zip(tickers, orderbooks_list):
        if not isinstance(ob, Exception):
            orderbooks[ticker] = ob

    recent_trades = {}
    for ticker, trades in zip(tickers, trades_list):
        if not isinstance(trades, Exception):
            recent_trades[ticker] = trades

    return MarketContext(
        account=account,
        holdings=holdings,
        companies=companies,
        orderbooks=orderbooks,
        open_orders=open_orders,
        recent_trades=recent_trades,
    )


async def execute_action(
    client: ExchangeClient, action: Action, agent_name: str, strategy_type: str
) -> bool:
    """Execute a single action. Returns True if a trade was executed."""
    try:
        if action.action_type == "CANCEL":
            if action.order_id:
                order = await client.cancel_order(action.order_id)
                logger.info(f"[{agent_name}] Cancelled order {order.id}")
                telemetry.record_action(agent_name, "CANCEL")
                return False
        elif action.action_type == "BUY":
            if action.ticker and action.quantity:
                order = await client.place_order(
                    ticker=action.ticker,
                    side="BUY",
                    order_type=action.order_type,
                    quantity=action.quantity,
                    price=action.price,
                )
                logger.info(
                    f"[{agent_name}] BUY {order.quantity} {order.ticker} "
                    f"@ {order.price} -> {order.status}"
                )
                telemetry.record_action(agent_name, "BUY")
                if order.status == "FILLED":
                    telemetry.record_trade(agent_name, strategy_type)
                    return True
        elif action.action_type == "SELL":
            if action.ticker and action.quantity:
                order = await client.place_order(
                    ticker=action.ticker,
                    side="SELL",
                    order_type=action.order_type,
                    quantity=action.quantity,
                    price=action.price,
                )
                logger.info(
                    f"[{agent_name}] SELL {order.quantity} {order.ticker} "
                    f"@ {order.price} -> {order.status}"
                )
                telemetry.record_action(agent_name, "SELL")
                if order.status == "FILLED":
                    telemetry.record_trade(agent_name, strategy_type)
                    return True
    except Exception as e:
        logger.warning(f"[{agent_name}] Action failed: {action} - {e}")
    return False


def build_strategy(agent: Agent) -> Strategy:
    """Build a strategy instance from agent configuration."""
    definition = registry.get(agent.strategy_type)
    if not definition:
        raise ValueError(f"Unknown strategy: {agent.strategy_type}")

    if definition.is_dsl:
        if not agent.strategy_source:
            raise ValueError("Rule-based strategy requires YAML source")
        return compile_yaml(agent.strategy_source)

    return definition.create_strategy(agent.strategy_params)


class AgentRunner:
    """Runs trading agents."""

    def __init__(self):
        self._running_agents: dict[str, asyncio.Task] = {}
        self._stop_events: dict[str, asyncio.Event] = {}

    async def start_agent(self, agent: Agent) -> bool:
        """Start running an agent."""
        if agent.id in self._running_agents:
            logger.warning(f"Agent {agent.id} is already running")
            return False

        stop_event = asyncio.Event()
        self._stop_events[agent.id] = stop_event

        task = asyncio.create_task(self._run_agent_loop(agent, stop_event))
        self._running_agents[agent.id] = task

        return True

    async def stop_agent(self, agent_id: str) -> bool:
        """Stop a running agent."""
        if agent_id not in self._running_agents:
            return False

        self._stop_events[agent_id].set()

        try:
            await asyncio.wait_for(self._running_agents[agent_id], timeout=10.0)
        except asyncio.TimeoutError:
            self._running_agents[agent_id].cancel()

        del self._running_agents[agent_id]
        del self._stop_events[agent_id]

        return True

    async def _run_agent_loop(self, agent: Agent, stop_event: asyncio.Event) -> None:
        """Main agent execution loop."""
        agent_id = agent.id
        agent_name = agent.name
        strategy_type = agent.strategy_type
        exchange_url = agent.exchange_url
        api_key = agent.api_key
        interval = agent.interval_seconds

        # Build strategy
        try:
            strategy = build_strategy(agent)
        except Exception as e:
            logger.error(f"[{agent_name}] Failed to build strategy: {e}")
            telemetry.record_error(agent_name, "strategy_build")
            async with AsyncSessionLocal() as session:
                db_agent = await agent_service.get_agent(session, agent_id)
                if db_agent:
                    await agent_service.record_error(session, db_agent, str(e))
            return

        # Run the trading loop
        async with ExchangeClient(exchange_url, api_key) as client:
            logger.info(f"[{agent_name}] Starting agent")

            while not stop_event.is_set():
                try:
                    # Check if still supposed to be running
                    async with AsyncSessionLocal() as session:
                        db_agent = await agent_service.get_agent(session, agent_id)
                        if not db_agent or db_agent.status != AgentStatus.RUNNING:
                            logger.info(f"[{agent_name}] Agent no longer running")
                            break

                    # Execute trading cycle
                    context = await gather_context(client)
                    actions = strategy.decide(context)

                    trades_executed = 0
                    for action in actions:
                        if await execute_action(client, action, agent_name, strategy_type):
                            trades_executed += 1

                    # Record metrics
                    telemetry.record_cycle(agent_name, strategy_type)
                    async with AsyncSessionLocal() as session:
                        db_agent = await agent_service.get_agent(session, agent_id)
                        if db_agent:
                            await agent_service.record_cycle(
                                session, db_agent, trades_executed
                            )

                except Exception as e:
                    logger.error(f"[{agent_name}] Cycle error: {e}")
                    telemetry.record_error(agent_name, "cycle")
                    async with AsyncSessionLocal() as session:
                        db_agent = await agent_service.get_agent(session, agent_id)
                        if db_agent:
                            await agent_service.record_error(session, db_agent, str(e))
                            if db_agent.status == AgentStatus.ERROR:
                                break

                # Wait for next cycle
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    pass  # Normal, continue to next cycle

            logger.info(f"[{agent_name}] Agent stopped")


# Global runner instance
runner = AgentRunner()
