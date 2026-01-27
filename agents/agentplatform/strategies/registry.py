"""Strategy registry - manages available strategies and their parameter schemas."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable

from agentplatform.strategies import Strategy


@dataclass
class ParameterSchema:
    """Schema for a single strategy parameter."""

    name: str
    param_type: str  # "int", "float", "decimal", "string", "bool", "choice"
    description: str
    default: Any
    required: bool = False
    min_value: float | int | None = None
    max_value: float | int | None = None
    choices: list[str] | None = None  # For "choice" type

    def validate(self, value: Any) -> tuple[bool, str | None]:
        """Validate a value against this schema.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            if self.required:
                return False, f"Parameter '{self.name}' is required"
            return True, None

        # Type validation
        if self.param_type == "int":
            if not isinstance(value, int):
                return False, f"Parameter '{self.name}' must be an integer"
        elif self.param_type == "float":
            if not isinstance(value, (int, float)):
                return False, f"Parameter '{self.name}' must be a number"
        elif self.param_type == "decimal":
            try:
                Decimal(str(value))
            except Exception:
                return False, f"Parameter '{self.name}' must be a decimal number"
        elif self.param_type == "bool":
            if not isinstance(value, bool):
                return False, f"Parameter '{self.name}' must be true or false"
        elif self.param_type == "choice":
            if value not in (self.choices or []):
                return False, f"Parameter '{self.name}' must be one of: {self.choices}"

        # Range validation
        if self.min_value is not None and value < self.min_value:
            return False, f"Parameter '{self.name}' must be at least {self.min_value}"
        if self.max_value is not None and value > self.max_value:
            return False, f"Parameter '{self.name}' must be at most {self.max_value}"

        return True, None


@dataclass
class StrategyDefinition:
    """Complete definition of a registered strategy."""

    id: str
    name: str
    description: str
    difficulty: str  # "beginner", "intermediate", "advanced"
    category: str  # "trend", "mean_reversion", "arbitrage", "custom"
    parameters: list[ParameterSchema] = field(default_factory=list)
    factory: Callable[..., Strategy] | None = None  # Creates strategy instance
    is_dsl: bool = False  # True for rule-based DSL strategies

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate all parameters, return list of error messages."""
        errors = []
        for schema in self.parameters:
            value = params.get(schema.name, schema.default)
            is_valid, error = schema.validate(value)
            if not is_valid and error:
                errors.append(error)
        return errors

    def create_strategy(self, params: dict[str, Any]) -> Strategy:
        """Create a strategy instance with the given parameters."""
        if self.factory is None:
            raise ValueError(f"Strategy '{self.id}' has no factory")

        # Apply defaults
        final_params = {}
        for schema in self.parameters:
            final_params[schema.name] = params.get(schema.name, schema.default)

        return self.factory(**final_params)


class StrategyRegistry:
    """Registry of available trading strategies."""

    def __init__(self):
        self._strategies: dict[str, StrategyDefinition] = {}

    def register(self, definition: StrategyDefinition) -> None:
        """Register a strategy definition."""
        self._strategies[definition.id] = definition

    def get(self, strategy_id: str) -> StrategyDefinition | None:
        """Get a strategy definition by ID."""
        return self._strategies.get(strategy_id)

    def list_all(self) -> list[StrategyDefinition]:
        """List all registered strategies."""
        return list(self._strategies.values())

    def list_by_difficulty(self, difficulty: str) -> list[StrategyDefinition]:
        """List strategies by difficulty level."""
        return [s for s in self._strategies.values() if s.difficulty == difficulty]

    def list_by_category(self, category: str) -> list[StrategyDefinition]:
        """List strategies by category."""
        return [s for s in self._strategies.values() if s.category == category]


# Global registry instance
registry = StrategyRegistry()
