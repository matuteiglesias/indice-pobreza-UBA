"""Synthetic, contract-first table adapters."""

from .baskets import adapt_canastas_poverty_slice
from .census import adapt_census
from .income import adapt_income, to_linear_ars

__all__ = ["adapt_canastas_poverty_slice", "adapt_census", "adapt_income", "to_linear_ars"]
