#!/usr/bin/env python3
"""
Scenario management CLI for the stock exchange simulation.

Usage:
    python -m scenario.cli load scenario/scenarios/basic_market.yaml
    python -m scenario.cli load scenario/scenarios/basic_market.yaml --no-clear
    python -m scenario.cli load scenario/scenarios/basic_market.yaml --no-start
    python -m scenario.cli validate scenario/scenarios/basic_market.yaml
    python -m scenario.cli list
    python -m scenario.cli status
    python -m scenario.cli stop
    python -m scenario.cli start
"""

import json
from datetime import datetime
from pathlib import Path

import click
import httpx
import yaml

from scenario.schema import ScenarioConfig

STATE_FILE = Path(".scenario_state.json")


def load_yaml(path: Path) -> ScenarioConfig:
    """Load and validate a scenario YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    config = ScenarioConfig(**data)
    config.resolve_strategy_sources(path.parent)
    return config


def save_state(
    scenario_path: str,
    api_keys: dict[str, str],
    agent_ids: dict[str, str],
) -> None:
    """Save scenario state to JSON file."""
    state = {
        "scenario": scenario_path,
        "loaded_at": datetime.utcnow().isoformat() + "Z",
        "api_keys": api_keys,
        "agent_ids": agent_ids,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_state() -> dict | None:
    """Load scenario state from JSON file."""
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


@click.group()
def cli():
    """Scenario management for stock exchange simulation."""
    pass


@cli.command("list")
def list_scenarios():
    """List available scenarios."""
    # Look for scenarios in scenario/scenarios/ directory relative to this file
    scenarios_dir = Path(__file__).parent / "scenarios"
    if not scenarios_dir.exists():
        click.echo("No scenarios directory found.")
        return

    yaml_files = list(scenarios_dir.glob("*.yaml")) + list(scenarios_dir.glob("*.yml"))
    if not yaml_files:
        click.echo("No scenario files found in scenario/scenarios/")
        return

    click.echo("\nAvailable scenarios:")
    click.echo("-" * 60)

    for path in sorted(yaml_files):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            name = data.get("name", "Unnamed")
            desc = data.get("description", "")[:40]
            click.echo(f"  {path.name:<25} {name:<20} {desc}")
        except Exception as e:
            click.echo(f"  {path.name:<25} (error: {e})")

    click.echo()


@cli.command("validate")
@click.argument("scenario_file", type=click.Path(exists=True))
def validate_scenario(scenario_file: str):
    """Validate a scenario file without loading it."""
    path = Path(scenario_file)

    try:
        config = load_yaml(path)
        click.echo(f"Scenario '{config.name}' is valid.")
        click.echo(f"  Companies: {len(config.companies)}")
        click.echo(f"  Accounts:  {len(config.accounts)}")
        click.echo(f"  Agents:    {len(config.agents)}")
    except Exception as e:
        click.echo(f"Validation error: {e}", err=True)
        raise SystemExit(1)


@cli.command("load")
@click.argument("scenario_file", type=click.Path(exists=True))
@click.option("--no-clear", is_flag=True, help="Skip database reset")
@click.option("--no-start", is_flag=True, help="Don't auto-start agents")
def load_scenario(scenario_file: str, no_clear: bool, no_start: bool):
    """Load a scenario, creating companies, accounts, and agents."""
    path = Path(scenario_file)

    # Parse and validate
    try:
        config = load_yaml(path)
    except Exception as e:
        click.echo(f"Error parsing scenario: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"\nLoading scenario: {config.name}")
    if config.description:
        click.echo(f"  {config.description}")
    click.echo()

    exchange_url = config.exchange.url
    agent_platform_url = config.agent_platform.url

    # Check connectivity
    try:
        with httpx.Client(base_url=exchange_url, timeout=5) as client:
            client.get("/health")
    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to exchange at {exchange_url}", err=True)
        raise SystemExit(1)

    try:
        with httpx.Client(base_url=agent_platform_url, timeout=5) as client:
            client.get("/health")
    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to agent platform at {agent_platform_url}", err=True)
        raise SystemExit(1)

    # Reset databases if requested
    if not no_clear:
        click.echo("Resetting databases...")

        # Reset exchange
        with httpx.Client(base_url=exchange_url, timeout=30) as client:
            response = client.post("/admin/reset")
            if response.status_code != 200:
                click.echo(f"Warning: Exchange reset failed: {response.text}", err=True)
            else:
                click.echo("  Exchange reset complete")

        # Reset agent platform
        with httpx.Client(base_url=agent_platform_url, timeout=30) as client:
            response = client.post("/admin/reset")
            if response.status_code != 200:
                click.echo(f"Warning: Agent platform reset failed: {response.text}", err=True)
            else:
                click.echo("  Agent platform reset complete")

    # Create companies
    if config.companies:
        click.echo(f"\nCreating {len(config.companies)} companies...")
        with httpx.Client(base_url=exchange_url, timeout=30) as client:
            for company in config.companies:
                data = {
                    "ticker": company.ticker,
                    "name": company.name,
                    "total_shares": company.total_shares,
                    "float_shares": company.float_shares,
                    "ipo_price": company.ipo_price,
                }
                response = client.post("/admin/companies", json=data)
                if response.status_code == 201:
                    click.echo(f"  Created {company.ticker}: {company.name}")
                elif response.status_code == 409:
                    click.echo(f"  Skipped {company.ticker} (already exists)")
                else:
                    click.echo(
                        f"  Error creating {company.ticker}: {response.text}", err=True
                    )

    # Create accounts and collect API keys
    api_keys: dict[str, str] = {}
    if config.accounts:
        click.echo(f"\nCreating {len(config.accounts)} accounts...")
        with httpx.Client(base_url=exchange_url, timeout=30) as client:
            for account in config.accounts:
                data = {
                    "account_id": account.id,
                    "initial_cash": account.initial_cash,
                }
                response = client.post("/admin/accounts", json=data)
                if response.status_code == 201:
                    result = response.json()
                    api_keys[account.id] = result.get("api_key", "")
                    click.echo(f"  Created {account.id} (${account.initial_cash:,.2f})")
                elif response.status_code == 409:
                    click.echo(f"  Skipped {account.id} (already exists)")
                    # Try to get existing account info (API key won't be available)
                    api_keys[account.id] = "(existing - key unknown)"
                else:
                    click.echo(
                        f"  Error creating {account.id}: {response.text}", err=True
                    )

    # Create agents
    agent_ids: dict[str, str] = {}
    if config.agents:
        click.echo(f"\nCreating {len(config.agents)} agents...")
        with httpx.Client(base_url=agent_platform_url, timeout=30) as client:
            for agent in config.agents:
                # Get API key for this agent's account
                account_api_key = api_keys.get(agent.account, "")
                if not account_api_key or account_api_key.startswith("("):
                    click.echo(
                        f"  Warning: No API key for account '{agent.account}', "
                        f"skipping agent '{agent.name}'",
                        err=True,
                    )
                    continue

                data = {
                    "name": agent.name,
                    "exchange_url": exchange_url,
                    "api_key": account_api_key,
                    "strategy_type": agent.strategy_type,
                    "strategy_params": agent.strategy_params,
                    "strategy_source": agent.strategy_source,
                    "interval_seconds": agent.interval_seconds,
                }
                response = client.post("/agents", json=data)
                if response.status_code == 201:
                    result = response.json()
                    agent_id = result["id"]
                    agent_ids[agent.name] = agent_id
                    click.echo(f"  Created agent '{agent.name}' (id: {agent_id[:8]}...)")

                    # Auto-start if requested
                    if agent.auto_start and not no_start:
                        start_response = client.post(f"/agents/{agent_id}/start")
                        if start_response.status_code == 200:
                            click.echo(f"    Started")
                        else:
                            click.echo(f"    Failed to start: {start_response.text}")
                else:
                    click.echo(
                        f"  Error creating agent '{agent.name}': {response.text}",
                        err=True,
                    )

    # Save state
    save_state(scenario_file, api_keys, agent_ids)

    click.echo("\n" + "=" * 60)
    click.echo("Scenario loaded successfully!")
    click.echo(f"State saved to: {STATE_FILE}")
    click.echo("=" * 60)

    # Show API keys
    if api_keys:
        click.echo("\nAPI Keys (save these!):")
        for account_id, key in api_keys.items():
            click.echo(f"  {account_id}: {key}")


@cli.command("status")
def show_status():
    """Show current scenario state."""
    state = load_state()
    if not state:
        click.echo("No scenario loaded. Use 'scenario.py load <file>' first.")
        return

    click.echo(f"\nCurrent scenario: {state['scenario']}")
    click.echo(f"Loaded at: {state['loaded_at']}")

    click.echo(f"\nAccounts ({len(state['api_keys'])}):")
    for account_id in state["api_keys"]:
        click.echo(f"  - {account_id}")

    click.echo(f"\nAgents ({len(state['agent_ids'])}):")

    # Try to get live status
    agent_platform_url = "http://localhost:8001"
    try:
        with httpx.Client(base_url=agent_platform_url, timeout=5) as client:
            for name, agent_id in state["agent_ids"].items():
                try:
                    response = client.get(f"/agents/{agent_id}")
                    if response.status_code == 200:
                        agent = response.json()
                        status = agent["status"]
                        cycles = agent["total_cycles"]
                        trades = agent["total_trades"]
                        click.echo(
                            f"  - {name}: {status} (cycles: {cycles}, trades: {trades})"
                        )
                    else:
                        click.echo(f"  - {name}: (not found)")
                except Exception:
                    click.echo(f"  - {name}: (error fetching status)")
    except httpx.ConnectError:
        for name in state["agent_ids"]:
            click.echo(f"  - {name}: (agent platform unavailable)")


@cli.command("stop")
def stop_agents():
    """Stop all agents from current scenario."""
    state = load_state()
    if not state:
        click.echo("No scenario loaded. Use 'scenario.py load <file>' first.")
        return

    agent_platform_url = "http://localhost:8001"
    try:
        with httpx.Client(base_url=agent_platform_url, timeout=30) as client:
            for name, agent_id in state["agent_ids"].items():
                response = client.post(f"/agents/{agent_id}/stop")
                if response.status_code == 200:
                    click.echo(f"Stopped: {name}")
                elif response.status_code == 400:
                    click.echo(f"Already stopped: {name}")
                else:
                    click.echo(f"Error stopping {name}: {response.text}")
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to agent platform", err=True)
        raise SystemExit(1)


@cli.command("start")
def start_agents():
    """Start all agents from current scenario."""
    state = load_state()
    if not state:
        click.echo("No scenario loaded. Use 'scenario.py load <file>' first.")
        return

    agent_platform_url = "http://localhost:8001"
    try:
        with httpx.Client(base_url=agent_platform_url, timeout=30) as client:
            for name, agent_id in state["agent_ids"].items():
                response = client.post(f"/agents/{agent_id}/start")
                if response.status_code == 200:
                    click.echo(f"Started: {name}")
                elif response.status_code == 400:
                    click.echo(f"Already running: {name}")
                else:
                    click.echo(f"Error starting {name}: {response.text}")
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to agent platform", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
