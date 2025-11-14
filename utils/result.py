"""Result type for operations that may succeed or fail."""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass
class Result(Generic[T, E]):
    """Result type for operations that may succeed or fail."""

    value: T | None = None
    error: E | None = None

    @property
    def is_success(self) -> bool:
        """Check if the result is successful."""
        return self.error is None

    @property
    def is_error(self) -> bool:
        """Check if the result is an error."""
        return self.error is not None

    @classmethod
    def success(cls, value: T) -> "Result[T, E]":
        """Create a successful result."""
        return cls(value=value, error=None)

    @classmethod
    def failure(cls, error: E) -> "Result[T, E]":
        """Create a failed result."""
        return cls(value=None, error=error)

    def unwrap(self) -> T:
        """Unwrap the value, raising if error."""
        if self.is_error:
            raise ValueError(f"Cannot unwrap error result: {self.error}")
        return self.value  # type: ignore

    def unwrap_or(self, default: T) -> T:
        """Unwrap the value or return default if error."""
        return self.value if self.is_success else default
