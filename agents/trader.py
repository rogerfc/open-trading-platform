"""Trading agent - main loop that executes a strategy."""

import argparse
import asyncio
import logging
import sys

from agents.client import ExchangeClient
from agents.config import AgentConfig
from agents.strategies import Action, MarketContext, Strategy
from agents.strategies.random_strategy import RandomStrategy

logger = logging.getLogger(__name__)


async def gather_context(client: ExchangeClient) -> MarketContext:
    """Gather complete market context from the exchange.

    This fetches all relevant data in parallel where possible.
    """
    # Fetch account data and companies first
    account, holdings, companies, open_orders = await asyncio.gather(
        client.get_account(),
        client.get_holdings(),
        client.get_companies(),
        client.get_orders(status="OPEN"),
    )

    # Fetch order books and recent trades for all companies
    tickers = [c.ticker for c in companies]

    orderbook_tasks = [client.get_orderbook(t) for t in tickers]
    trades_tasks = [client.get_trades(t, limit=20) for t in tickers]

    orderbooks_list = await asyncio.gather(*orderbook_tasks, return_exceptions=True)
    trades_list = await asyncio.gather(*trades_tasks, return_exceptions=True)

    # Build dictionaries, skipping any that failed
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


async def execute_action(client: ExchangeClient, action: Action, agent_name: str) -> None:
    """Execute a single action."""
    try:
        if action.action_type == "CANCEL":
            if action.order_id:
                order = await client.cancel_order(action.order_id)
                logger.info(f"[{agent_name}] Cancelled order {order.id}")
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
                    f"[{agent_name}] Placed BUY {action.order_type} order: "
                    f"{order.quantity} {order.ticker} @ {order.price} -> {order.status}"
                )
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
                    f"[{agent_name}] Placed SELL {action.order_type} order: "
                    f"{order.quantity} {order.ticker} @ {order.price} -> {order.status}"
                )
    except Exception as e:
        logger.warning(f"[{agent_name}] Action failed: {action} - {e}")


async def run_agent(
    config: AgentConfig,
    strategy: Strategy,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run a trading agent.

    Args:
        config: Agent configuration
        strategy: Trading strategy to use
        stop_event: Optional event to signal shutdown
    """
    agent_name = config.name or config.api_key[:8]
    logger.info(f"[{agent_name}] Starting agent (interval: {config.interval}s)")

    async with ExchangeClient(config.base_url, config.api_key) as client:
        # Verify connection
        try:
            account = await client.get_account()
            logger.info(
                f"[{agent_name}] Connected as {account.account_id} "
                f"(cash: ${account.cash_balance})"
            )
        except Exception as e:
            logger.error(f"[{agent_name}] Failed to connect: {e}")
            return

        cycle = 0
        while True:
            # Check for shutdown
            if stop_event and stop_event.is_set():
                logger.info(f"[{agent_name}] Shutting down")
                break

            cycle += 1
            logger.debug(f"[{agent_name}] Cycle {cycle}")

            try:
                # Gather market context
                context = await gather_context(client)

                # Let strategy decide
                actions = strategy.decide(context)

                # Execute actions
                for action in actions:
                    await execute_action(client, action, agent_name)

                # Log status periodically
                if cycle % 10 == 0:
                    logger.info(
                        f"[{agent_name}] Status: cash=${context.account.cash_balance}, "
                        f"holdings={len(context.holdings)}, "
                        f"open_orders={len(context.open_orders)}"
                    )

            except Exception as e:
                logger.error(f"[{agent_name}] Cycle error: {e}")

            # Wait for next cycle
            try:
                await asyncio.wait_for(
                    stop_event.wait() if stop_event else asyncio.sleep(config.interval),
                    timeout=config.interval,
                )
                if stop_event and stop_event.is_set():
                    break
            except asyncio.TimeoutError:
                pass  # Normal timeout, continue


def main() -> None:
    """CLI entry point for running a single agent."""
    parser = argparse.ArgumentParser(description="Run a trading agent")
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    parser.add_argument(
        "--base-url", default="http://localhost:8000", help="Exchange API base URL"
    )
    parser.add_argument(
        "--interval", type=float, default=5.0, help="Seconds between trading cycles"
    )
    parser.add_argument("--name", default="", help="Agent name for logging")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    config = AgentConfig(
        api_key=args.api_key,
        base_url=args.base_url,
        interval=args.interval,
        name=args.name,
    )

    strategy = RandomStrategy()

    try:
        asyncio.run(run_agent(config, strategy))
    except KeyboardInterrupt:
        print("\nShutdown requested")
        sys.exit(0)


if __name__ == "__main__":
    main()
