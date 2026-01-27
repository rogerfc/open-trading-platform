"""Compiles YAML DSL to executable Strategy objects."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import yaml

from agentplatform.strategies import Action, MarketContext, Strategy
from agentplatform.strategies.dsl.schema import (
    Condition,
    Rule,
    StrategyDSL,
    TradeAction,
)


class DSLCompilationError(Exception):
    """Error during DSL compilation with helpful message."""

    def __init__(self, message: str, line: int | None = None):
        self.line = line
        super().__init__(f"{message}" + (f" (near line {line})" if line else ""))


class CompiledRule:
    """A rule compiled for efficient evaluation."""

    def __init__(self, rule: Rule, settings: dict):
        self.rule = rule
        self.settings = settings
        self.cooldowns: dict[str, datetime] = {}  # ticker -> last_triggered

    def is_on_cooldown(self, ticker: str) -> bool:
        """Check if rule is on cooldown for ticker."""
        if ticker not in self.cooldowns:
            return False
        elapsed = (datetime.now() - self.cooldowns[ticker]).total_seconds()
        return elapsed < self.rule.cooldown_seconds

    def mark_triggered(self, ticker: str) -> None:
        """Mark rule as triggered for cooldown."""
        self.cooldowns[ticker] = datetime.now()

    def evaluate_condition(
        self,
        condition: Condition,
        context: MarketContext,
        ticker: str,
    ) -> bool:
        """Evaluate a single condition."""
        # Get the metric value
        value = self._get_metric_value(condition.metric, context, ticker)
        if value is None:
            return False

        # Compare
        compare_to = condition.value
        ops = {
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        return ops[condition.operator](value, compare_to)

    def _get_metric_value(
        self,
        metric: str,
        context: MarketContext,
        ticker: str,
    ) -> float | None:
        """Get the current value of a metric."""
        if metric == "price":
            price = context.get_last_price(ticker)
            return float(price) if price else None

        elif metric == "bid_price":
            bid = context.get_best_bid(ticker)
            return float(bid) if bid else None

        elif metric == "ask_price":
            ask = context.get_best_ask(ticker)
            return float(ask) if ask else None

        elif metric == "spread_pct":
            bid = context.get_best_bid(ticker)
            ask = context.get_best_ask(ticker)
            if bid and ask and bid > 0:
                return float((ask - bid) / bid * 100)
            return None

        elif metric == "my_cash":
            return float(context.account.cash_balance)

        elif metric == "my_holdings":
            return float(context.get_holding(ticker))

        elif metric == "my_position_value":
            holdings = context.get_holding(ticker)
            price = context.get_last_price(ticker)
            if price:
                return float(holdings * price)
            return 0.0

        elif metric == "my_open_orders":
            return len([o for o in context.open_orders if o.ticker == ticker])

        elif metric == "price_change_pct":
            # Calculate from recent trades
            trades = context.recent_trades.get(ticker, [])
            if len(trades) < 2:
                return 0.0
            current = trades[0].price
            # Use average of last N trades as reference
            n = min(10, len(trades))
            avg = sum(t.price for t in trades[:n]) / n
            if avg > 0:
                return float((current - avg) / avg * 100)
            return 0.0

        return None

    def generate_actions(
        self,
        trade_actions: list[TradeAction],
        context: MarketContext,
        ticker: str,
    ) -> list[Action]:
        """Generate Action objects from TradeAction definitions."""
        actions = []

        for ta in trade_actions:
            target_ticker = ta.ticker or ticker

            if ta.action == "cancel_orders":
                # Cancel all open orders for ticker
                for order in context.open_orders:
                    if order.ticker == target_ticker:
                        actions.append(Action.cancel(order.id))
                continue

            # Calculate quantity
            quantity = self._calculate_quantity(ta, context, target_ticker)
            if quantity <= 0:
                continue

            # Calculate price
            price = self._calculate_price(ta, context, target_ticker)

            # Create action
            if ta.action == "buy":
                actions.append(
                    Action.buy(
                        ticker=target_ticker,
                        quantity=quantity,
                        price=price,
                        order_type=ta.order_type.upper(),
                    )
                )
            elif ta.action == "sell":
                actions.append(
                    Action.sell(
                        ticker=target_ticker,
                        quantity=quantity,
                        price=price,
                        order_type=ta.order_type.upper(),
                    )
                )

        return actions

    def _calculate_quantity(
        self,
        ta: TradeAction,
        context: MarketContext,
        ticker: str,
    ) -> int:
        """Calculate order quantity based on specification."""
        if ta.quantity is not None:
            return ta.quantity

        if ta.action == "sell":
            holdings = context.get_holding(ticker)
            if ta.quantity_all:
                return holdings
            if ta.quantity_pct is not None:
                return int(holdings * ta.quantity_pct)
            return 0

        # Buy
        price = context.get_best_ask(ticker) or context.get_last_price(ticker)
        if not price or price <= 0:
            return 0

        # Respect settings
        available = float(context.account.cash_balance)
        available -= self.settings.get("min_cash_reserve", 0)
        max_order = self.settings.get("max_order_value", float("inf"))
        available = min(available, max_order)

        if available <= 0:
            return 0

        if ta.quantity_all:
            return int(available / float(price))
        if ta.quantity_pct is not None:
            return int((available * ta.quantity_pct) / float(price))

        return 0

    def _calculate_price(
        self,
        ta: TradeAction,
        context: MarketContext,
        ticker: str,
    ) -> Decimal | None:
        """Calculate order price based on specification."""
        if ta.order_type == "market":
            return None

        if ta.price is not None:
            return ta.price

        # Get reference price
        if ta.action == "buy":
            ref = context.get_best_ask(ticker) or context.get_last_price(ticker)
        else:
            ref = context.get_best_bid(ticker) or context.get_last_price(ticker)

        if not ref:
            return None

        if ta.price_offset_pct is not None:
            ref = ref * Decimal(str(1 + ta.price_offset_pct))

        return ref.quantize(Decimal("0.01"))


class RuleBasedStrategy:
    """Strategy compiled from YAML DSL rules."""

    def __init__(self, dsl: StrategyDSL):
        self.dsl = dsl
        self.compiled_rules = [
            CompiledRule(rule, dsl.settings)
            for rule in sorted(dsl.rules, key=lambda r: -r.priority)
        ]

    def decide(self, context: MarketContext) -> list[Action]:
        """Evaluate rules and generate actions."""
        all_actions: list[Action] = []

        # Get list of tickers to evaluate
        tickers = [c.ticker for c in context.companies]

        for compiled in self.compiled_rules:
            rule = compiled.rule

            # Determine which tickers to check
            rule_tickers = tickers if rule.ticker == "all" else [rule.ticker]

            for ticker in rule_tickers:
                # Skip if on cooldown
                if compiled.is_on_cooldown(ticker):
                    continue

                # Evaluate all conditions (AND logic)
                all_conditions_met = all(
                    compiled.evaluate_condition(cond, context, ticker)
                    for cond in rule.when
                )

                if all_conditions_met:
                    # Generate actions
                    actions = compiled.generate_actions(rule.then, context, ticker)
                    if actions:
                        all_actions.extend(actions)
                        compiled.mark_triggered(ticker)

        return all_actions


def compile_yaml(yaml_source: str) -> RuleBasedStrategy:
    """Compile YAML source to a RuleBasedStrategy.

    Args:
        yaml_source: YAML string defining the strategy

    Returns:
        Compiled strategy ready for execution

    Raises:
        DSLCompilationError: If YAML is invalid or violates schema
    """
    try:
        data = yaml.safe_load(yaml_source)
    except yaml.YAMLError as e:
        raise DSLCompilationError(f"Invalid YAML: {e}")

    if not isinstance(data, dict):
        raise DSLCompilationError("Strategy must be a YAML mapping/dictionary")

    # Parse into DSL objects
    dsl = _parse_strategy(data)

    # Validate
    _validate_strategy(dsl)

    # Compile
    return RuleBasedStrategy(dsl)


def _parse_strategy(data: dict) -> StrategyDSL:
    """Parse raw YAML dict into StrategyDSL object."""
    rules = []
    for rule_data in data.get("rules", []):
        rules.append(_parse_rule(rule_data))

    return StrategyDSL(
        name=data.get("name", "Unnamed Strategy"),
        description=data.get("description", ""),
        settings=data.get("settings", {}),
        rules=rules,
    )


def _parse_rule(data: dict) -> Rule:
    """Parse a rule from YAML dict."""
    conditions = []
    for cond_data in data.get("when", []):
        conditions.append(
            Condition(
                metric=cond_data["metric"],
                operator=cond_data["operator"],
                value=cond_data["value"],
                ticker=cond_data.get("ticker"),
            )
        )

    actions = []
    for action_data in data.get("then", []):
        actions.append(
            TradeAction(
                action=action_data["action"],
                ticker=action_data.get("ticker"),
                quantity=action_data.get("quantity"),
                quantity_pct=action_data.get("quantity_pct"),
                quantity_all=action_data.get("quantity_all", False),
                price=Decimal(str(action_data["price"]))
                if action_data.get("price")
                else None,
                price_offset_pct=action_data.get("price_offset_pct"),
                order_type=action_data.get("order_type", "limit"),
            )
        )

    return Rule(
        name=data.get("name", "Unnamed Rule"),
        description=data.get("description", ""),
        ticker=data.get("ticker", "all"),
        when=conditions,
        then=actions,
        cooldown_seconds=data.get("cooldown_seconds", 60),
        priority=data.get("priority", 0),
    )


def _validate_strategy(dsl: StrategyDSL) -> None:
    """Validate a parsed strategy for safety and correctness."""
    if not dsl.rules:
        raise DSLCompilationError("Strategy must have at least one rule")

    for rule in dsl.rules:
        if not rule.when:
            raise DSLCompilationError(
                f"Rule '{rule.name}' must have at least one condition"
            )
        if not rule.then:
            raise DSLCompilationError(
                f"Rule '{rule.name}' must have at least one action"
            )

        # Validate condition metrics
        valid_metrics = {
            "price",
            "price_change_pct",
            "bid_price",
            "ask_price",
            "spread_pct",
            "my_cash",
            "my_holdings",
            "my_position_value",
            "my_open_orders",
        }
        for cond in rule.when:
            if cond.metric not in valid_metrics:
                raise DSLCompilationError(
                    f"Rule '{rule.name}': unknown metric '{cond.metric}'. "
                    f"Valid metrics: {', '.join(sorted(valid_metrics))}"
                )

        # Validate actions
        valid_actions = {"buy", "sell", "cancel_orders"}
        for action in rule.then:
            if action.action not in valid_actions:
                raise DSLCompilationError(
                    f"Rule '{rule.name}': unknown action '{action.action}'. "
                    f"Valid actions: {', '.join(sorted(valid_actions))}"
                )
