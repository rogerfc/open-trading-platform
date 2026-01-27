"""Multi-agent runner - run multiple trading agents in parallel."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from agents.config import AgentConfig
from agents.strategies import Strategy
from agents.strategies.random_strategy import RandomStrategy
from agents.trader import run_agent

logger = logging.getLogger(__name__)


async def run_multiple_agents(
    configs: list[AgentConfig],
    strategy_factory: type[Strategy] = RandomStrategy,
) -> None:
    """Run multiple agents concurrently.

    Args:
        configs: List of agent configurations
        strategy_factory: Strategy class to instantiate for each agent
    """
    stop_event = asyncio.Event()

    # Create tasks for each agent
    tasks = []
    for config in configs:
        strategy = strategy_factory()
        task = asyncio.create_task(run_agent(config, strategy, stop_event))
        tasks.append(task)

    logger.info(f"Started {len(tasks)} agents")

    # Wait for all agents (or until interrupted)
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Agents cancelled")
        stop_event.set()
        # Give agents time to clean up
        await asyncio.sleep(0.5)


def load_config_file(path: str) -> list[AgentConfig]:
    """Load agent configurations from a JSON file.

    Expected format:
    {
        "base_url": "http://localhost:8000",
        "interval": 5.0,
        "agents": [
            {"api_key": "sk_...", "name": "alice"},
            {"api_key": "sk_...", "name": "bob"}
        ]
    }
    """
    with open(path) as f:
        data = json.load(f)

    base_url = data.get("base_url", "http://localhost:8000")
    interval = data.get("interval", 5.0)

    configs = []
    for agent_data in data.get("agents", []):
        config = AgentConfig(
            api_key=agent_data["api_key"],
            base_url=agent_data.get("base_url", base_url),
            interval=agent_data.get("interval", interval),
            name=agent_data.get("name", ""),
        )
        configs.append(config)

    return configs


def main() -> None:
    """CLI entry point for running multiple agents."""
    parser = argparse.ArgumentParser(description="Run multiple trading agents")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to JSON config file with agent configurations",
    )
    parser.add_argument(
        "--api-keys",
        type=str,
        help="Comma-separated list of API keys (alternative to --config)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Exchange API base URL",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between trading cycles",
    )
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

    # Build configurations
    configs: list[AgentConfig] = []

    if args.config:
        if not Path(args.config).exists():
            logger.error(f"Config file not found: {args.config}")
            sys.exit(1)
        configs = load_config_file(args.config)
        logger.info(f"Loaded {len(configs)} agents from {args.config}")

    elif args.api_keys:
        api_keys = [k.strip() for k in args.api_keys.split(",") if k.strip()]
        for i, key in enumerate(api_keys):
            configs.append(
                AgentConfig(
                    api_key=key,
                    base_url=args.base_url,
                    interval=args.interval,
                    name=f"agent_{i+1}",
                )
            )
        logger.info(f"Created {len(configs)} agents from API keys")

    else:
        logger.error("Must provide either --config or --api-keys")
        parser.print_help()
        sys.exit(1)

    if not configs:
        logger.error("No agent configurations found")
        sys.exit(1)

    # Run agents
    try:
        asyncio.run(run_multiple_agents(configs))
    except KeyboardInterrupt:
        print("\nShutdown requested")
        sys.exit(0)


if __name__ == "__main__":
    main()
