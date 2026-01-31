#!/usr/bin/env python3
"""
Unified CLI for stock exchange simulation management.

Usage:
    python -m market.cli <resource> <verb> [args] [options]

Examples:
    python -m market.cli company list
    python -m market.cli account create alice --cash 10000
    python -m market.cli agent list --status RUNNING
    python -m market.cli scenario load scenario/scenarios/basic_market.yaml
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import click
import httpx
import yaml

from market.client import ExchangeClient, AgentPlatformClient, APIError
from market import output as out
from market import config as cfg


# =============================================================================
# CLI Context
# =============================================================================


class Context:
    """CLI context holding configuration and clients."""

    def __init__(self):
        self.exchange_url: str = "http://localhost:8000"
        self.agents_url: str = "http://localhost:8001"
        self.output_format: str = "table"
        self._exchange_client: ExchangeClient | None = None
        self._agents_client: AgentPlatformClient | None = None

    @property
    def exchange(self) -> ExchangeClient:
        if self._exchange_client is None:
            self._exchange_client = ExchangeClient(self.exchange_url)
        return self._exchange_client

    @property
    def agents(self) -> AgentPlatformClient:
        if self._agents_client is None:
            self._agents_client = AgentPlatformClient(self.agents_url)
        return self._agents_client


pass_context = click.make_pass_decorator(Context, ensure=True)


def require_config(ctx: Context) -> None:
    """Ensure config exists and services are reachable.

    Loads configuration from file and tests connectivity to both services.
    Exits with code 1 if config is missing or services are unreachable.
    """
    config_path = cfg.find_config()
    if config_path is None:
        out.error("No configuration found.")
        out.info("Run 'python -m market.cli config' to create one.")
        raise SystemExit(1)

    config = cfg.load_config()
    ctx.exchange_url = config.get("exchange_url", ctx.exchange_url)
    ctx.agents_url = config.get("agents_url", ctx.agents_url)
    # Reset clients to use new URLs
    ctx._exchange_client = None
    ctx._agents_client = None

    # Test connectivity
    try:
        ctx.exchange.health()
    except httpx.ConnectError:
        out.error(f"Exchange unavailable at {ctx.exchange_url}")
        raise SystemExit(1)

    try:
        ctx.agents.health()
    except httpx.ConnectError:
        out.error(f"Agent platform unavailable at {ctx.agents_url}")
        raise SystemExit(1)


# =============================================================================
# Main CLI Group
# =============================================================================


@click.group()
@click.option(
    "--exchange-url", "-e",
    envvar="EXCHANGE_URL",
    default=None,
    help="Exchange API URL (overrides config)",
)
@click.option(
    "--agents-url", "-a",
    envvar="AGENTS_URL",
    default=None,
    help="Agent Platform API URL (overrides config)",
)
@click.option(
    "--output", "-o",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Output format",
)
@pass_context
def cli(ctx: Context, exchange_url: str | None, agents_url: str | None, output: str):
    """Unified CLI for stock exchange simulation management."""
    # Load config if available
    config = cfg.load_config()
    ctx.exchange_url = exchange_url or config.get("exchange_url", "http://localhost:8000")
    ctx.agents_url = agents_url or config.get("agents_url", "http://localhost:8001")
    ctx.output_format = output


# =============================================================================
# Config Commands
# =============================================================================


@cli.command("config")
@click.argument("action", required=False, type=click.Choice(["show", "set"]))
@click.argument("args", nargs=-1)
def config_cmd(action: str | None, args: tuple):
    """Manage CLI configuration.

    Without arguments: interactive setup.

    \b
    Examples:
        market config              # Interactive setup
        market config show         # Show current config
        market config set exchange_url http://localhost:8000
    """
    if action is None:
        # Interactive setup
        config_path = cfg.find_config()
        if config_path:
            out.info(f"Config file found: {config_path}")
            current = cfg.load_config()
        else:
            out.info("No config file found. Creating new config.")
            current = cfg.get_default_config()

        # Prompt for values
        exchange_url = click.prompt(
            "Exchange URL",
            default=current.get("exchange_url", "http://localhost:8000"),
        )
        agents_url = click.prompt(
            "Agent Platform URL",
            default=current.get("agents_url", "http://localhost:8001"),
        )
        grafana_url = click.prompt(
            "Grafana URL",
            default=current.get("grafana_url", "http://localhost:3000"),
        )

        new_config = {
            "exchange_url": exchange_url,
            "agents_url": agents_url,
            "grafana_url": grafana_url,
        }

        save_path = cfg.save_config(new_config)
        out.success(f"Configuration saved to {save_path}")

    elif action == "show":
        config_path = cfg.find_config()
        if config_path is None:
            out.info("No configuration file found.")
            out.info("Run 'python -m market.cli config' to create one.")
            return

        config = cfg.load_config()
        out.info(f"Config file: {config_path}")
        out.info("")
        for key, value in config.items():
            out.info(f"  {key}: {value}")

    elif action == "set":
        if len(args) != 2:
            out.error("Usage: market config set <key> <value>")
            raise SystemExit(1)

        key, value = args
        valid_keys = {"exchange_url", "agents_url", "grafana_url"}
        if key not in valid_keys:
            out.error(f"Unknown config key: {key}")
            out.info(f"Valid keys: {', '.join(sorted(valid_keys))}")
            raise SystemExit(1)

        config = cfg.load_config()
        config[key] = value
        save_path = cfg.save_config(config)
        out.success(f"Set {key} = {value}")
        out.info(f"Saved to {save_path}")


# =============================================================================
# Top-level Run/Stop Commands
# =============================================================================


@cli.command("run")
@pass_context
def run_agents(ctx: Context):
    """Start all agents from loaded scenario."""
    require_config(ctx)

    state = load_scenario_state()
    if not state:
        out.error("No scenario loaded. Use 'market scenario load' first.")
        raise SystemExit(1)

    if not state.get("agent_ids"):
        out.info("No agents in loaded scenario.")
        return

    for name, agent_id in state["agent_ids"].items():
        try:
            ctx.agents.start_agent(agent_id)
            out.success(f"Started: {name}")
        except APIError as e:
            if "already running" in e.detail.lower():
                out.info(f"Already running: {name}")
            else:
                out.error(f"Failed: {name} - {e.detail}")


@cli.command("stop")
@pass_context
def stop_agents(ctx: Context):
    """Stop all agents from loaded scenario."""
    require_config(ctx)

    state = load_scenario_state()
    if not state:
        out.error("No scenario loaded. Use 'market scenario load' first.")
        raise SystemExit(1)

    if not state.get("agent_ids"):
        out.info("No agents in loaded scenario.")
        return

    for name, agent_id in state["agent_ids"].items():
        try:
            ctx.agents.stop_agent(agent_id)
            out.success(f"Stopped: {name}")
        except APIError as e:
            if "cannot stop" in e.detail.lower() or "not running" in e.detail.lower():
                out.info(f"Already stopped: {name}")
            else:
                out.error(f"Failed: {name} - {e.detail}")


# =============================================================================
# Company Commands
# =============================================================================


@cli.group()
def company():
    """Manage companies."""
    pass


@company.command("list")
@pass_context
def company_list(ctx: Context):
    """List all companies."""
    try:
        companies = ctx.exchange.list_companies()
        columns = [
            ("ticker", "Ticker", 8),
            ("name", "Name", 30),
            ("total_shares", "Total Shares", 15),
            ("float_shares", "Float", 15),
        ]
        out.output(companies, ctx.output_format, columns)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


@company.command("show")
@click.argument("ticker")
@pass_context
def company_show(ctx: Context, ticker: str):
    """Show company details with market data."""
    try:
        data = ctx.exchange.get_company(ticker)
        out.output(data, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


@company.command("create")
@click.argument("ticker")
@click.argument("name")
@click.option("--total-shares", type=int, required=True, help="Total shares outstanding")
@click.option("--float-shares", type=int, required=True, help="Shares available for trading")
@click.option("--ipo-price", type=float, default=100.0, help="IPO price")
@pass_context
def company_create(
    ctx: Context,
    ticker: str,
    name: str,
    total_shares: int,
    float_shares: int,
    ipo_price: float,
):
    """Create a new company."""
    try:
        result = ctx.exchange.create_company(
            ticker=ticker,
            name=name,
            total_shares=total_shares,
            float_shares=float_shares,
            ipo_price=ipo_price,
        )
        out.success(f"Created company {ticker}")
        out.output(result, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


# =============================================================================
# Account Commands
# =============================================================================


@cli.group()
def account():
    """Manage accounts."""
    pass


@account.command("list")
@pass_context
def account_list(ctx: Context):
    """List all accounts."""
    try:
        accounts = ctx.exchange.list_accounts()
        columns = [
            ("account_id", "Account ID", 20),
            ("cash_balance", "Cash Balance", 15),
            ("created_at", "Created At", 25),
        ]
        out.output(accounts, ctx.output_format, columns)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


@account.command("show")
@click.argument("account_id")
@click.option("--api-key", required=True, help="API key for authentication")
@pass_context
def account_show(ctx: Context, account_id: str, api_key: str):
    """Show account details (balance, holdings)."""
    try:
        account_data = ctx.exchange.get_account(api_key)
        holdings = ctx.exchange.get_holdings(api_key)

        if ctx.output_format == "table":
            out.info(f"\nAccount: {account_id}")
            out.info(f"Cash Balance: ${float(account_data.get('cash_balance', 0)):,.2f}")
            out.info(f"\nHoldings:")
            if holdings:
                columns = [
                    ("ticker", "Ticker", 10),
                    ("quantity", "Quantity", 12),
                ]
                out.output(holdings, "table", columns)
            else:
                out.info("  (no holdings)")
        else:
            data = {"account": account_data, "holdings": holdings}
            out.output(data, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


@account.command("create")
@click.argument("account_id")
@click.option("--cash", type=float, default=0.0, help="Initial cash balance")
@pass_context
def account_create(ctx: Context, account_id: str, cash: float):
    """Create a new account."""
    try:
        result = ctx.exchange.create_account(account_id, cash)
        out.success(f"Created account {account_id}")
        if ctx.output_format == "table":
            out.info(f"\nAPI Key (save this!): {result.get('api_key', 'N/A')}")
            out.info(f"Cash Balance: ${float(result.get('cash_balance', 0)):,.2f}")
        else:
            out.output(result, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


# =============================================================================
# Order Commands
# =============================================================================


@cli.group()
def order():
    """Manage orders."""
    pass


@order.command("list")
@click.option("--api-key", required=True, help="API key for authentication")
@click.option("--status", type=click.Choice(["OPEN", "FILLED", "CANCELLED", "PARTIAL"]), help="Filter by status")
@pass_context
def order_list(ctx: Context, api_key: str, status: str | None):
    """List orders for an account."""
    try:
        orders = ctx.exchange.list_orders(api_key, status)
        columns = [
            ("id", "Order ID", 36),
            ("ticker", "Ticker", 8),
            ("side", "Side", 6),
            ("order_type", "Type", 8),
            ("quantity", "Qty", 8),
            ("price", "Price", 10),
            ("status", "Status", 10),
        ]
        out.output(orders, ctx.output_format, columns)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


@order.command("show")
@click.argument("order_id")
@click.option("--api-key", required=True, help="API key for authentication")
@pass_context
def order_show(ctx: Context, order_id: str, api_key: str):
    """Show order details."""
    try:
        data = ctx.exchange.get_order(order_id, api_key)
        out.output(data, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


@order.command("create")
@click.option("--api-key", required=True, help="API key for authentication")
@click.option("--ticker", required=True, help="Stock ticker")
@click.option("--side", required=True, type=click.Choice(["BUY", "SELL"]), help="Order side")
@click.option("--type", "order_type", required=True, type=click.Choice(["MARKET", "LIMIT"]), help="Order type")
@click.option("--quantity", required=True, type=int, help="Number of shares")
@click.option("--price", type=float, help="Price (required for LIMIT orders)")
@pass_context
def order_create(
    ctx: Context,
    api_key: str,
    ticker: str,
    side: str,
    order_type: str,
    quantity: int,
    price: float | None,
):
    """Place a new order."""
    if order_type == "LIMIT" and price is None:
        out.error("Price is required for LIMIT orders")
        raise SystemExit(1)

    try:
        result = ctx.exchange.create_order(
            api_key=api_key,
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
        out.success(f"Order placed: {result.get('id', 'N/A')}")
        out.output(result, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


@order.command("cancel")
@click.argument("order_id")
@click.option("--api-key", required=True, help="API key for authentication")
@pass_context
def order_cancel(ctx: Context, order_id: str, api_key: str):
    """Cancel an open order."""
    try:
        result = ctx.exchange.cancel_order(order_id, api_key)
        out.success(f"Order cancelled: {order_id}")
        out.output(result, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


# =============================================================================
# Orderbook Commands
# =============================================================================


@cli.group()
def orderbook():
    """View order books."""
    pass


@orderbook.command("show")
@click.argument("ticker")
@click.option("--depth", type=int, default=10, help="Number of levels")
@pass_context
def orderbook_show(ctx: Context, ticker: str, depth: int):
    """Show order book for a ticker."""
    try:
        data = ctx.exchange.get_orderbook(ticker, depth)
        if ctx.output_format == "table":
            out.info(f"\nOrder Book: {ticker.upper()}")
            out.info(f"Spread: {data.get('spread', 'N/A')}")
            out.info("\nBids:")
            bids = data.get("bids", [])
            if bids:
                columns = [("price", "Price", 12), ("quantity", "Quantity", 12)]
                out.output(bids, "table", columns)
            else:
                out.info("  (no bids)")
            out.info("\nAsks:")
            asks = data.get("asks", [])
            if asks:
                columns = [("price", "Price", 12), ("quantity", "Quantity", 12)]
                out.output(asks, "table", columns)
            else:
                out.info("  (no asks)")
        else:
            out.output(data, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


# =============================================================================
# Trade Commands
# =============================================================================


@cli.group()
def trade():
    """View trades."""
    pass


@trade.command("list")
@click.argument("ticker")
@click.option("--limit", type=int, default=20, help="Number of trades")
@pass_context
def trade_list(ctx: Context, ticker: str, limit: int):
    """List recent trades for a ticker."""
    try:
        trades = ctx.exchange.list_trades(ticker, limit)
        columns = [
            ("id", "Trade ID", 36),
            ("price", "Price", 10),
            ("quantity", "Quantity", 10),
            ("executed_at", "Executed At", 25),
        ]
        out.output(trades, ctx.output_format, columns)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


# =============================================================================
# Agent Commands
# =============================================================================


@cli.group()
def agent():
    """Manage trading agents."""
    pass


@agent.command("list")
@click.option("--status", help="Filter by status: RUNNING, STOPPED, CREATED, etc.")
@pass_context
def agent_list(ctx: Context, status: str | None):
    """List all agents."""
    try:
        agents = ctx.agents.list_agents(status)
        columns = [
            ("id", "Agent ID", 36),
            ("name", "Name", 25),
            ("strategy_type", "Strategy", 12),
            ("status", "Status", 10),
            ("total_cycles", "Cycles", 8),
            ("total_trades", "Trades", 8),
        ]
        out.output(agents, ctx.output_format, columns)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


@agent.command("show")
@click.argument("agent_id")
@pass_context
def agent_show(ctx: Context, agent_id: str):
    """Show agent details."""
    try:
        data = ctx.agents.get_agent(agent_id)
        out.output(data, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


@agent.command("create")
@click.argument("name")
@click.option("--api-key", required=True, help="API key for the trading account")
@click.option("--strategy", required=True, help="Strategy type: random, rule_based")
@click.option("--strategy-file", type=click.Path(exists=True), help="YAML file for rule_based strategy")
@click.option("--interval", type=float, default=5.0, help="Seconds between cycles")
@click.option("--params", type=str, help="Strategy parameters as JSON")
@pass_context
def agent_create(
    ctx: Context,
    name: str,
    api_key: str,
    strategy: str,
    strategy_file: str | None,
    interval: float,
    params: str | None,
):
    """Create a new agent."""
    strategy_source = None
    if strategy_file:
        strategy_source = Path(strategy_file).read_text()

    strategy_params = {}
    if params:
        try:
            strategy_params = json.loads(params)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON for --params: {e}")
            raise SystemExit(1)

    try:
        result = ctx.agents.create_agent(
            name=name,
            api_key=api_key,
            strategy_type=strategy,
            exchange_url=ctx.exchange_url,
            strategy_params=strategy_params,
            strategy_source=strategy_source,
            interval_seconds=interval,
        )
        out.success(f"Created agent: {result.get('id', 'N/A')}")
        out.output(result, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


@agent.command("start")
@click.argument("agent_id")
@pass_context
def agent_start(ctx: Context, agent_id: str):
    """Start an agent."""
    try:
        result = ctx.agents.start_agent(agent_id)
        out.success(f"Started agent: {agent_id}")
        out.output(result, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


@agent.command("stop")
@click.argument("agent_id")
@pass_context
def agent_stop(ctx: Context, agent_id: str):
    """Stop an agent."""
    try:
        result = ctx.agents.stop_agent(agent_id)
        out.success(f"Stopped agent: {agent_id}")
        out.output(result, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


@agent.command("delete")
@click.argument("agent_id")
@click.confirmation_option(prompt="Are you sure you want to delete this agent?")
@pass_context
def agent_delete(ctx: Context, agent_id: str):
    """Delete an agent."""
    try:
        ctx.agents.delete_agent(agent_id)
        out.success(f"Deleted agent: {agent_id}")
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


# =============================================================================
# Strategy Commands
# =============================================================================


@cli.group()
def strategy():
    """Manage trading strategies."""
    pass


@strategy.command("list")
@pass_context
def strategy_list(ctx: Context):
    """List available strategies."""
    try:
        strategies = ctx.agents.list_strategies()
        columns = [
            ("id", "ID", 15),
            ("name", "Name", 25),
            ("difficulty", "Difficulty", 12),
            ("category", "Category", 15),
        ]
        out.output(strategies, ctx.output_format, columns)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


@strategy.command("show")
@click.argument("strategy_id")
@pass_context
def strategy_show(ctx: Context, strategy_id: str):
    """Show strategy details and parameters."""
    try:
        data = ctx.agents.get_strategy(strategy_id)
        out.output(data, ctx.output_format)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


@strategy.command("validate")
@click.argument("file", type=click.Path(exists=True))
@pass_context
def strategy_validate(ctx: Context, file: str):
    """Validate a strategy YAML file."""
    try:
        source = Path(file).read_text()
        result = ctx.agents.validate_strategy(
            strategy_type="rule_based",
            strategy_source=source,
        )
        if result.get("valid"):
            out.success("Strategy is valid")
        else:
            out.error("Strategy is invalid")
            for err in result.get("errors", []):
                out.info(f"  - {err}")
            raise SystemExit(1)
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


# =============================================================================
# Scenario Commands
# =============================================================================


SCENARIO_STATE_FILE = Path(".scenario_state.json")


def load_scenario_state() -> dict | None:
    """Load scenario state from file."""
    if not SCENARIO_STATE_FILE.exists():
        return None
    return json.loads(SCENARIO_STATE_FILE.read_text())


def save_scenario_state(scenario_path: str, api_keys: dict, agent_ids: dict) -> None:
    """Save scenario state to file."""
    state = {
        "scenario": scenario_path,
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "api_keys": api_keys,
        "agent_ids": agent_ids,
    }
    SCENARIO_STATE_FILE.write_text(json.dumps(state, indent=2))


@cli.group()
def scenario():
    """Manage trading scenarios."""
    pass


@scenario.command("list")
def scenario_list():
    """List available scenario files."""
    scenarios_dir = Path(__file__).parent.parent / "scenario" / "scenarios"
    if not scenarios_dir.exists():
        out.error("No scenarios directory found")
        return

    yaml_files = list(scenarios_dir.glob("*.yaml")) + list(scenarios_dir.glob("*.yml"))
    if not yaml_files:
        out.info("No scenario files found")
        return

    out.info("\nAvailable scenarios:")
    out.info("-" * 60)
    for path in sorted(yaml_files):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            name = data.get("name", "Unnamed")
            desc = data.get("description", "")[:35]
            out.info(f"  {path.name:<25} {name:<20} {desc}")
        except Exception as e:
            out.info(f"  {path.name:<25} (error: {e})")


@scenario.command("show")
@click.argument("file", type=click.Path(exists=True))
def scenario_show(file: str):
    """Show scenario summary."""
    try:
        with open(file) as f:
            data = yaml.safe_load(f)

        out.info(f"\nScenario: {data.get('name', 'Unnamed')}")
        if data.get("description"):
            out.info(f"Description: {data['description']}")
        out.info(f"\nCompanies: {len(data.get('companies', []))}")
        for c in data.get("companies", []):
            out.info(f"  - {c['ticker']}: {c['name']}")
        out.info(f"\nAccounts: {len(data.get('accounts', []))}")
        for a in data.get("accounts", []):
            out.info(f"  - {a['id']}: ${a.get('initial_cash', 0):,.2f}")
        out.info(f"\nAgents: {len(data.get('agents', []))}")
        for ag in data.get("agents", []):
            out.info(f"  - {ag['name']} ({ag['strategy_type']})")
    except Exception as e:
        out.error(f"Failed to read scenario: {e}")
        raise SystemExit(1)


@scenario.command("validate")
@click.argument("file", type=click.Path(exists=True))
def scenario_validate(file: str):
    """Validate a scenario file."""
    try:
        from scenario.schema import ScenarioConfig

        with open(file) as f:
            data = yaml.safe_load(f)

        config = ScenarioConfig(**data)
        config.resolve_strategy_sources(Path(file).parent)

        out.success(f"Scenario '{config.name}' is valid")
        out.info(f"  Companies: {len(config.companies)}")
        out.info(f"  Accounts:  {len(config.accounts)}")
        out.info(f"  Agents:    {len(config.agents)}")
    except Exception as e:
        out.error(f"Validation failed: {e}")
        raise SystemExit(1)


@scenario.command("load")
@click.argument("file", type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt for DB reset")
@click.option("--no-clear", is_flag=True, help="Don't reset databases first")
@pass_context
def scenario_load(ctx: Context, file: str, yes: bool, no_clear: bool):
    """Load a scenario (reset + create all resources).

    Resets databases, creates companies, accounts, and agents.
    Agents are created but NOT started. Use 'market run' to start trading.
    """
    try:
        from scenario.schema import ScenarioConfig

        with open(file) as f:
            data = yaml.safe_load(f)

        config = ScenarioConfig(**data)
        config.resolve_strategy_sources(Path(file).parent)
    except Exception as e:
        out.error(f"Failed to parse scenario: {e}")
        raise SystemExit(1)

    out.info(f"\nLoading scenario: {config.name}")
    if config.description:
        out.info(f"  {config.description}")

    # Check connectivity
    try:
        ctx.exchange.health()
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)

    try:
        ctx.agents.health()
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)

    # Reset if needed
    if not no_clear:
        if not yes:
            if not click.confirm("\nThis will reset both databases. Continue?"):
                out.info("Aborted.")
                return
        out.info("\nResetting databases...")
        try:
            ctx.exchange.reset()
            out.info("  Exchange reset")
        except APIError as e:
            out.warning(f"Exchange reset failed: {e.detail}")
        try:
            ctx.agents.reset()
            out.info("  Agent platform reset")
        except APIError as e:
            out.warning(f"Agent platform reset failed: {e.detail}")

    # Create companies
    if config.companies:
        out.info(f"\nCreating {len(config.companies)} companies...")
        for company in config.companies:
            try:
                ctx.exchange.create_company(
                    ticker=company.ticker,
                    name=company.name,
                    total_shares=company.total_shares,
                    float_shares=company.float_shares,
                    ipo_price=company.ipo_price,
                )
                out.info(f"  Created {company.ticker}: {company.name}")
            except APIError as e:
                if e.status_code == 409:
                    out.info(f"  Skipped {company.ticker} (exists)")
                else:
                    out.error(f"  Failed {company.ticker}: {e.detail}")

    # Create accounts
    api_keys: dict[str, str] = {}
    if config.accounts:
        out.info(f"\nCreating {len(config.accounts)} accounts...")
        for account in config.accounts:
            try:
                result = ctx.exchange.create_account(account.id, account.initial_cash)
                api_keys[account.id] = result.get("api_key", "")
                out.info(f"  Created {account.id} (${account.initial_cash:,.2f})")
            except APIError as e:
                if e.status_code == 409:
                    out.info(f"  Skipped {account.id} (exists)")
                    api_keys[account.id] = "(existing)"
                else:
                    out.error(f"  Failed {account.id}: {e.detail}")

    # Create agents (but don't start them)
    agent_ids: dict[str, str] = {}
    if config.agents:
        out.info(f"\nCreating {len(config.agents)} agents...")
        for agent in config.agents:
            account_api_key = api_keys.get(agent.account, "")
            if not account_api_key or account_api_key == "(existing)":
                out.warning(f"  Skipping {agent.name}: no API key for {agent.account}")
                continue

            try:
                # Use exchange URL from scenario (for Docker) or fallback to CLI config
                agent_exchange_url = config.exchange.url
                result = ctx.agents.create_agent(
                    name=agent.name,
                    api_key=account_api_key,
                    strategy_type=agent.strategy_type,
                    exchange_url=agent_exchange_url,
                    strategy_params=agent.strategy_params,
                    strategy_source=agent.strategy_source,
                    interval_seconds=agent.interval_seconds,
                )
                agent_id = result["id"]
                agent_ids[agent.name] = agent_id
                out.info(f"  Created {agent.name} ({agent_id[:8]}...)")
            except APIError as e:
                out.error(f"  Failed {agent.name}: {e.detail}")

    # Save state (API keys stored but not displayed)
    save_scenario_state(file, api_keys, agent_ids)

    out.info("\n" + "=" * 50)
    out.success("Scenario loaded!")
    out.info(f"State saved to: {SCENARIO_STATE_FILE}")
    out.info(f"\nAccounts: {len(api_keys)}, Agents: {len(agent_ids)}")
    out.info("Use 'market run' to start trading.")


@scenario.command("status")
@pass_context
def scenario_status(ctx: Context):
    """Show current loaded scenario state."""
    state = load_scenario_state()
    if not state:
        out.info("No scenario loaded. Use 'market scenario load <file>' first.")
        return

    out.info(f"\nScenario: {state['scenario']}")
    out.info(f"Loaded at: {state['loaded_at']}")

    out.info(f"\nAccounts ({len(state['api_keys'])}):")
    for account_id in state["api_keys"]:
        out.info(f"  - {account_id}")

    out.info(f"\nAgents ({len(state['agent_ids'])}):")
    for name, agent_id in state["agent_ids"].items():
        try:
            agent = ctx.agents.get_agent(agent_id)
            status = agent["status"]
            cycles = agent["total_cycles"]
            trades = agent["total_trades"]
            out.info(f"  - {name}: {status} (cycles: {cycles}, trades: {trades})")
        except APIError:
            out.info(f"  - {name}: (not found)")
        except httpx.ConnectError:
            out.info(f"  - {name}: (agent platform unavailable)")


@scenario.command("start")
@pass_context
def scenario_start(ctx: Context):
    """Start all agents from loaded scenario."""
    state = load_scenario_state()
    if not state:
        out.info("No scenario loaded. Use 'market scenario load <file>' first.")
        return

    for name, agent_id in state["agent_ids"].items():
        try:
            ctx.agents.start_agent(agent_id)
            out.success(f"Started: {name}")
        except APIError as e:
            if "already running" in e.detail.lower():
                out.info(f"Already running: {name}")
            else:
                out.error(f"Failed to start {name}: {e.detail}")
        except httpx.ConnectError:
            out.error("Cannot connect to agent platform")
            raise SystemExit(1)


@scenario.command("stop")
@pass_context
def scenario_stop(ctx: Context):
    """Stop all agents from loaded scenario."""
    state = load_scenario_state()
    if not state:
        out.info("No scenario loaded. Use 'market scenario load <file>' first.")
        return

    for name, agent_id in state["agent_ids"].items():
        try:
            ctx.agents.stop_agent(agent_id)
            out.success(f"Stopped: {name}")
        except APIError as e:
            if "cannot stop" in e.detail.lower():
                out.info(f"Already stopped: {name}")
            else:
                out.error(f"Failed to stop {name}: {e.detail}")
        except httpx.ConnectError:
            out.error("Cannot connect to agent platform")
            raise SystemExit(1)


# =============================================================================
# Reset Commands
# =============================================================================


@cli.group()
def reset():
    """Reset databases."""
    pass


@reset.command("exchange")
@click.confirmation_option(prompt="Reset exchange database?")
@pass_context
def reset_exchange(ctx: Context):
    """Reset exchange database."""
    try:
        ctx.exchange.reset()
        out.success("Exchange database reset")
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")
        raise SystemExit(1)


@reset.command("agents")
@click.confirmation_option(prompt="Reset agent platform database?")
@pass_context
def reset_agents(ctx: Context):
    """Reset agent platform database."""
    try:
        ctx.agents.reset()
        out.success("Agent platform database reset")
    except APIError as e:
        out.error(e.detail)
        raise SystemExit(1)
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")
        raise SystemExit(1)


@reset.command("all")
@click.confirmation_option(prompt="Reset ALL databases?")
@pass_context
def reset_all(ctx: Context):
    """Reset both exchange and agent platform databases."""
    try:
        ctx.exchange.reset()
        out.success("Exchange database reset")
    except APIError as e:
        out.error(f"Exchange reset failed: {e.detail}")
    except httpx.ConnectError:
        out.error(f"Cannot connect to exchange at {ctx.exchange_url}")

    try:
        ctx.agents.reset()
        out.success("Agent platform database reset")
    except APIError as e:
        out.error(f"Agent platform reset failed: {e.detail}")
    except httpx.ConnectError:
        out.error(f"Cannot connect to agent platform at {ctx.agents_url}")


# =============================================================================
# Grafana Commands
# =============================================================================


DASHBOARD_DIR = Path("observability/grafana/provisioning/dashboards")


@cli.group()
def grafana():
    """Manage Grafana dashboards."""
    pass


@grafana.command("deploy")
@click.option("--dashboard", "-d", help="Deploy specific dashboard (without .json extension)")
@pass_context
def grafana_deploy(ctx: Context, dashboard: str | None):
    """Deploy dashboards to Grafana via API.

    Pushes dashboard JSON files to Grafana using the HTTP API.
    This allows live updates without restarting Grafana.

    \b
    Examples:
        market grafana deploy              # Deploy all dashboards
        market grafana deploy -d exchange  # Deploy specific dashboard
    """
    config = cfg.load_config()
    grafana_url = config.get("grafana_url", "http://localhost:3000")

    # Find dashboard files
    if dashboard:
        files = [DASHBOARD_DIR / f"{dashboard}.json"]
    else:
        files = list(DASHBOARD_DIR.glob("*.json"))

    if not files:
        out.info("No dashboard files found.")
        return

    deployed = 0
    for file in files:
        if not file.exists():
            out.error(f"Dashboard not found: {file}")
            continue

        try:
            with open(file) as f:
                dashboard_json = json.load(f)
        except json.JSONDecodeError as e:
            out.error(f"Invalid JSON in {file.name}: {e}")
            continue

        # Prepare payload for Grafana API
        # Set id to null to create as new dashboard (not update provisioned)
        dashboard_json["id"] = None
        payload = {
            "dashboard": dashboard_json,
            "folderId": 0,  # General folder
            "overwrite": True,
            "message": "Deployed via market CLI",
        }

        try:
            resp = httpx.post(
                f"{grafana_url}/api/dashboards/db",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code == 200:
                result = resp.json()
                url = result.get("url", "")
                out.success(f"Deployed: {file.stem}")
                if url:
                    out.info(f"  URL: {grafana_url}{url}")
                deployed += 1
            else:
                error_msg = resp.json().get("message", resp.text)
                out.error(f"Failed: {file.stem} - {error_msg}")
        except httpx.ConnectError:
            out.error(f"Cannot connect to Grafana at {grafana_url}")
            raise SystemExit(1)
        except httpx.TimeoutException:
            out.error(f"Timeout connecting to Grafana at {grafana_url}")
            raise SystemExit(1)

    if deployed:
        out.info(f"\nDeployed {deployed} dashboard(s) to {grafana_url}")


# =============================================================================
# Status Command
# =============================================================================


@cli.command("status")
@pass_context
def status(ctx: Context):
    """Show health/status of exchange and agent platform."""
    # Configuration
    config_path = cfg.find_config()
    out.info("\nConfiguration")
    out.info("-" * 40)
    if config_path:
        out.info(f"Config file: {config_path}")
    else:
        out.info("Config file: " + click.style("Not found", fg="yellow"))
        out.info("  Run 'python -m market.cli config' to create one.")

    out.info("\nService Status")
    out.info("-" * 40)

    # Exchange
    try:
        ctx.exchange.health()
        out.info(f"Exchange ({ctx.exchange_url}): " + click.style("OK", fg="green"))
    except httpx.ConnectError:
        out.info(f"Exchange ({ctx.exchange_url}): " + click.style("UNREACHABLE", fg="red"))
    except APIError as e:
        out.info(f"Exchange ({ctx.exchange_url}): " + click.style(f"ERROR ({e.status_code})", fg="red"))

    # Agent Platform
    try:
        ctx.agents.health()
        out.info(f"Agent Platform ({ctx.agents_url}): " + click.style("OK", fg="green"))
    except httpx.ConnectError:
        out.info(f"Agent Platform ({ctx.agents_url}): " + click.style("UNREACHABLE", fg="red"))
    except APIError as e:
        out.info(f"Agent Platform ({ctx.agents_url}): " + click.style(f"ERROR ({e.status_code})", fg="red"))

    # Grafana
    config = cfg.load_config()
    grafana_url = config.get("grafana_url", "http://localhost:3000")
    try:
        resp = httpx.get(f"{grafana_url}/api/health", timeout=5.0)
        if resp.status_code == 200:
            out.info(f"Grafana ({grafana_url}): " + click.style("OK", fg="green"))
        else:
            out.info(f"Grafana ({grafana_url}): " + click.style(f"ERROR ({resp.status_code})", fg="red"))
    except httpx.ConnectError:
        out.info(f"Grafana ({grafana_url}): " + click.style("UNREACHABLE", fg="yellow"))
    except httpx.TimeoutException:
        out.info(f"Grafana ({grafana_url}): " + click.style("TIMEOUT", fg="yellow"))

    # Scenario state
    state = load_scenario_state()
    if state:
        out.info(f"\nLoaded Scenario: {state['scenario']}")
        out.info(f"  Accounts: {len(state['api_keys'])}")
        out.info(f"  Agents: {len(state['agent_ids'])}")


if __name__ == "__main__":
    cli()
