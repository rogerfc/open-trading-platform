"""Random trading strategy - for testing purposes."""

import random
from decimal import Decimal

from agentplatform.strategies import Action, MarketContext, Strategy


class RandomStrategy:
    """Makes random buy/sell decisions. Good for testing."""

    def __init__(
        self,
        max_order_value: Decimal = Decimal("1000"),
        price_offset_pct: Decimal = Decimal("0.02"),
        cancel_probability: float = 0.1,
    ):
        self.max_order_value = max_order_value
        self.price_offset_pct = price_offset_pct
        self.cancel_probability = cancel_probability

    def decide(self, context: MarketContext) -> list[Action]:
        """Generate random trading actions."""
        actions: list[Action] = []

        # Maybe cancel an existing order
        if context.open_orders and random.random() < self.cancel_probability:
            order = random.choice(context.open_orders)
            actions.append(Action.cancel(order.id))
            return actions

        # Pick a random company
        if not context.companies:
            return actions

        company = random.choice(context.companies)
        ticker = company.ticker

        # Get market price
        last_price = context.get_last_price(ticker)
        if not last_price or last_price <= 0:
            return actions

        # Decide buy or sell
        if random.random() < 0.5:
            # Buy
            available = float(context.account.cash_balance)
            max_spend = min(available * 0.1, float(self.max_order_value))
            if max_spend > float(last_price):
                quantity = random.randint(1, int(max_spend / float(last_price)))
                price = last_price * (1 - self.price_offset_pct)
                actions.append(
                    Action.buy(
                        ticker=ticker,
                        quantity=quantity,
                        price=price.quantize(Decimal("0.01")),
                        order_type="LIMIT",
                    )
                )
        else:
            # Sell
            holding = context.get_holding(ticker)
            if holding > 0:
                quantity = random.randint(1, holding)
                price = last_price * (1 + self.price_offset_pct)
                actions.append(
                    Action.sell(
                        ticker=ticker,
                        quantity=quantity,
                        price=price.quantize(Decimal("0.01")),
                        order_type="LIMIT",
                    )
                )

        return actions
