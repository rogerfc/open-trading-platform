"""YAML DSL schema definitions for trading strategies."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


@dataclass
class Condition:
    """A single condition in a rule.

    Example YAML:
        - metric: price_change_pct
          operator: "<"
          value: -5
    """

    # What to check
    metric: Literal[
        "price",  # Current/last price
        "price_change_pct",  # % change from average of recent trades
        "bid_price",  # Best bid
        "ask_price",  # Best ask
        "spread_pct",  # Bid-ask spread as %
        "my_cash",  # Available cash
        "my_holdings",  # Shares held for ticker
        "my_position_value",  # Holdings * price
        "my_open_orders",  # Number of open orders
    ]

    # Comparison operator
    operator: Literal["<", "<=", ">", ">=", "==", "!="]

    # Value to compare against
    value: float | int

    # Optional ticker (defaults to rule's ticker)
    ticker: str | None = None


@dataclass
class TradeAction:
    """An action to execute when conditions are met.

    Example YAML:
        - action: buy
          quantity_pct: 0.25
          order_type: limit
    """

    action: Literal["buy", "sell", "cancel_orders"]

    # For buy/sell - target ticker (optional, defaults to rule's ticker)
    ticker: str | None = None

    # Quantity specification (pick one)
    quantity: int | None = None  # Exact quantity
    quantity_pct: float | None = None  # % of holdings (sell) or affordable (buy)
    quantity_all: bool = False  # All holdings (sell) or max affordable (buy)

    # Price specification
    price: Decimal | None = None  # Exact price
    price_offset_pct: float | None = None  # Offset from market price
    order_type: Literal["limit", "market"] = "limit"


@dataclass
class Rule:
    """A complete trading rule: IF conditions THEN actions.

    Example YAML:
        - name: "Buy the Dip"
          description: "Buy when price drops 5%"
          ticker: all
          when:
            - metric: price_change_pct
              operator: "<"
              value: -5
          then:
            - action: buy
              quantity_pct: 0.25
          cooldown_seconds: 300
    """

    name: str
    description: str = ""

    # Target ticker(s) - "all" means apply to all companies
    ticker: str | Literal["all"] = "all"

    # Conditions (all must be true = AND logic)
    when: list[Condition] = field(default_factory=list)

    # Actions to take
    then: list[TradeAction] = field(default_factory=list)

    # Cooldown to prevent rapid repeated triggers
    cooldown_seconds: int = 60

    # Priority (higher = checked first)
    priority: int = 0


@dataclass
class StrategyDSL:
    """Complete DSL strategy definition.

    Example YAML:
        name: "My Strategy"
        description: "A simple trading strategy"
        settings:
          max_order_value: 500
          min_cash_reserve: 100
        rules:
          - name: "Buy Low"
            ...
    """

    name: str
    description: str = ""

    # Global settings for safety
    settings: dict = field(
        default_factory=lambda: {
            "max_position_pct": 0.5,  # Max % of portfolio in one stock
            "max_order_value": 10000,  # Max value per order
            "min_cash_reserve": 100,  # Always keep this much cash
        }
    )

    # Trading rules
    rules: list[Rule] = field(default_factory=list)
