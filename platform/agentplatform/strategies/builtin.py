"""Built-in strategy definitions for the registry."""

from decimal import Decimal

from agentplatform.strategies.registry import (
    registry,
    StrategyDefinition,
    ParameterSchema,
)
from agentplatform.strategies.random import RandomStrategy
from agentplatform.strategies.dsl.compiler import compile_yaml


def register_builtin_strategies() -> None:
    """Register all built-in strategies with the registry."""

    # Random Strategy - for testing
    registry.register(
        StrategyDefinition(
            id="random",
            name="Random Strategy",
            description="Makes random buy/sell decisions. Good for testing the system.",
            difficulty="beginner",
            category="custom",
            parameters=[
                ParameterSchema(
                    name="max_order_value",
                    param_type="decimal",
                    description="Maximum value per order in dollars",
                    default=Decimal("1000"),
                    min_value=10,
                    max_value=100000,
                ),
                ParameterSchema(
                    name="price_offset_pct",
                    param_type="decimal",
                    description="How far from market price to place limit orders (0.02 = 2%)",
                    default=Decimal("0.02"),
                    min_value=0.001,
                    max_value=0.5,
                ),
                ParameterSchema(
                    name="cancel_probability",
                    param_type="float",
                    description="Chance to cancel an old order each cycle (0.0-1.0)",
                    default=0.1,
                    min_value=0.0,
                    max_value=1.0,
                ),
            ],
            factory=lambda **kwargs: RandomStrategy(
                max_order_value=Decimal(str(kwargs.get("max_order_value", 1000))),
                price_offset_pct=Decimal(str(kwargs.get("price_offset_pct", 0.02))),
                cancel_probability=kwargs.get("cancel_probability", 0.1),
            ),
        )
    )

    # Rule-Based Strategy (DSL)
    registry.register(
        StrategyDefinition(
            id="rule_based",
            name="Rule-Based Strategy",
            description="Define your strategy using simple IF-THEN rules in YAML format. "
            "Perfect for beginners who want to create custom strategies without programming.",
            difficulty="beginner",
            category="custom",
            parameters=[],  # Parameters come from YAML
            is_dsl=True,
            factory=lambda strategy_source, **kwargs: compile_yaml(strategy_source),
        )
    )
