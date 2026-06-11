"""Polymarket access layer for the carbon_arc project.

`client.PolymarketClient` is a thin, dependency-light (requests-only) wrapper over
the three PUBLIC Polymarket REST APIs — Gamma, Data, and CLOB read endpoints — none
of which need authentication. Trading (order placement/cancel) is exposed separately
via `client.PolymarketClient.trading_client()`, which lazily builds an authenticated
py_clob_client_v2 client from environment credentials.
"""
from .client import PolymarketClient, GAMMA, DATA, CLOB

__all__ = ["PolymarketClient", "GAMMA", "DATA", "CLOB"]
