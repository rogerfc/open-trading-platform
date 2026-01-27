"""Random trading strategy - demonstrates agent capabilities."""

import random
from decimal import Decimal

from agents.strategies import Action, MarketContext, Strategy


class RandomStrategy(Strategy):
    """A simple random trading strategy.

    This strategy:
    - Randomly picks a ticker each cycle
    - Decides to buy or sell based on current holdings
    - Uses limit orders at slight discount/premium to market
    - Occasionally cancels old orders

    This is meant to demonstrate the agent can access all exchange data
    and execute trades. The "logic" is intentionally simple/random.
    """

    def __init__(
        self,
        max_order_value: Decimal = Decimal("1000"),
        price_offset_pct: Decimal = Decimal("0.02"),
        cancel_probability: float = 0.1,
    ):
        """Initialize the strategy.

        Args:
            max_order_value: Maximum value per order in cash
            price_offset_pct: Percentage offset from market price for limit orders
            cancel_probability: Probability of cancelling an old order each cycle
        """
        self.max_order_value = max_order_value
        self.price_offset_pct = price_offset_pct
        self.cancel_probability = cancel_probability

    def decide(self, context: MarketContext) -> list[Action]:
        """Make random trading decisions."""
        actions: list[Action] = []

        # Maybe cancel an old order
        if context.open_orders and random.random() < self.cancel_probability:
            order_to_cancel = random.choice(context.open_orders)
            actions.append(Action.cancel(order_to_cancel.id))

        # Skip if no companies available
        if not context.companies:
            return actions

        # Pick a random ticker
        company = random.choice(context.companies)
        ticker = company.ticker

        # Get market data for this ticker
        best_bid = context.get_best_bid(ticker)
        best_ask = context.get_best_ask(ticker)
        last_price = context.get_last_price(ticker)
        current_holding = context.get_holding(ticker)

        # Determine reference price
        ref_price = last_price or best_ask or best_bid
        if ref_price is None:
            # No price data available, skip
            return actions

        # Decide to buy or sell
        # More likely to sell if we have holdings, more likely to buy if we don't
        if current_holding > 0:
            # 60% chance to sell, 40% to buy
            should_sell = random.random() < 0.6
        else:
            # Can only buy if no holdings
            should_sell = False

        if should_sell and current_holding > 0:
            # Sell some or all holdings
            quantity = random.randint(1, current_holding)

            # Set price slightly above last price (premium)
            price = ref_price * (1 + self.price_offset_pct)
            price = price.quantize(Decimal("0.01"))

            actions.append(Action.sell(ticker, quantity, price, "LIMIT"))

        else:
            # Buy - check if we have enough cash
            if context.account.cash_balance < ref_price:
                return actions

            # Calculate max quantity we can afford
            max_qty_by_cash = int(self.max_order_value / ref_price)
            max_qty_by_balance = int(context.account.cash_balance / ref_price)
            max_qty = min(max_qty_by_cash, max_qty_by_balance)

            if max_qty < 1:
                return actions

            quantity = random.randint(1, max_qty)

            # Set price slightly below last price (discount)
            price = ref_price * (1 - self.price_offset_pct)
            price = price.quantize(Decimal("0.01"))

            actions.append(Action.buy(ticker, quantity, price, "LIMIT"))

        return actions
