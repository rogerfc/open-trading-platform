"""Trading strategies for the agent platform."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

from agentplatform.client import AccountInfo, Company, Holding, Order, OrderBook, Trade


@dataclass
class MarketContext:
    """Complete market context for strategy decision-making."""

    account: AccountInfo
    holdings: list[Holding]
    companies: list[Company]
    orderbooks: dict[str, OrderBook]  # ticker -> orderbook
    open_orders: list[Order]
    recent_trades: dict[str, list[Trade]]  # ticker -> trades

    def get_holding(self, ticker: str) -> int:
        """Get quantity held for a ticker."""
        for h in self.holdings:
            if h.ticker == ticker:
                return h.quantity
        return 0

    def get_best_bid(self, ticker: str) -> Decimal | None:
        """Get best bid price for a ticker."""
        ob = self.orderbooks.get(ticker)
        if ob and ob.bids:
            return ob.bids[0].price
        return None

    def get_best_ask(self, ticker: str) -> Decimal | None:
        """Get best ask price for a ticker."""
        ob = self.orderbooks.get(ticker)
        if ob and ob.asks:
            return ob.asks[0].price
        return None

    def get_last_price(self, ticker: str) -> Decimal | None:
        """Get last trade price for a ticker."""
        ob = self.orderbooks.get(ticker)
        return ob.last_price if ob else None


@dataclass
class Action:
    """An action for the agent to take."""

    action_type: Literal["BUY", "SELL", "CANCEL"]
    ticker: str | None = None
    quantity: int | None = None
    price: Decimal | None = None
    order_type: Literal["LIMIT", "MARKET"] = "LIMIT"
    order_id: str | None = None  # for CANCEL actions

    @classmethod
    def buy(
        cls,
        ticker: str,
        quantity: int,
        price: Decimal | None = None,
        order_type: Literal["LIMIT", "MARKET"] = "LIMIT",
    ) -> "Action":
        """Create a buy action."""
        return cls(
            action_type="BUY",
            ticker=ticker,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

    @classmethod
    def sell(
        cls,
        ticker: str,
        quantity: int,
        price: Decimal | None = None,
        order_type: Literal["LIMIT", "MARKET"] = "LIMIT",
    ) -> "Action":
        """Create a sell action."""
        return cls(
            action_type="SELL",
            ticker=ticker,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

    @classmethod
    def cancel(cls, order_id: str) -> "Action":
        """Create a cancel action."""
        return cls(action_type="CANCEL", order_id=order_id)


class Strategy(Protocol):
    """Protocol for trading strategies.

    Implement this protocol to create custom trading strategies.
    """

    def decide(self, context: MarketContext) -> list[Action]:
        """Decide what actions to take given the current market context.

        Args:
            context: Current market state including account, holdings,
                    order books, and open orders.

        Returns:
            List of actions to execute. May be empty.
        """
        ...
