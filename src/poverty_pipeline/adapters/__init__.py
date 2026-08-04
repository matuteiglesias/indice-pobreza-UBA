"""Synthetic, contract-first table adapters."""

from .census import adapt_census
from .income import adapt_income, to_linear_ars

__all__ = ["adapt_census", "adapt_income", "to_linear_ars"]
