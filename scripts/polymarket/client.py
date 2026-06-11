#!/usr/bin/env python3
"""
client.py — read-only Polymarket access + optional authenticated trading client.

Three public hosts (NO auth, NO key needed for any read here):
  GAMMA  https://gamma-api.polymarket.com   markets / events / tags / search (metadata)
  DATA   https://data-api.polymarket.com    positions / trades / holders / OI / leaderboard
  CLOB   https://clob.polymarket.com        order book / prices / midpoint / price history

Design mirrors scripts/auto/s_k0_fetch_kalshi.py: one requests.Session, a small get()
with backoff on 429/5xx, deterministic and agent-free. Every method returns parsed JSON.

Trading (placing/cancelling orders) is the ONLY thing that needs credentials. It is kept
out of the read path: call PolymarketClient.trading_client() to lazily construct an
authenticated py_clob_client_v2.ClobClient from env vars (see .env / docs/polymarket_sdk.md).
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests

GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

_UA = {"accept": "application/json", "user-agent": "carbonarc-research/1.0"}
_RETRY_STATUS = (429, 500, 502, 503, 504)


class PolymarketClient:
    """Read-only client over Gamma + Data + CLOB public endpoints."""

    def __init__(self, timeout: int = 30, max_retries: int = 4):
        self.timeout = timeout
        self.max_retries = max_retries
        self.sess = requests.Session()
        self.sess.headers.update(_UA)

    # ---- low-level -------------------------------------------------------
    def get(self, base: str, path: str, params: dict | None = None) -> Any:
        url = f"{base}{path}"
        last = None
        for attempt in range(self.max_retries):
            try:
                r = self.sess.get(url, params=params, timeout=self.timeout)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in _RETRY_STATUS:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                r.raise_for_status()
            except requests.RequestException as e:
                last = e
                time.sleep(0.5 * (attempt + 1))
        if last:
            raise last
        raise RuntimeError(f"GET {url} failed after {self.max_retries} retries")

    def post(self, base: str, path: str, json_body: Any) -> Any:
        url = f"{base}{path}"
        for attempt in range(self.max_retries):
            r = self.sess.post(url, json=json_body, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code in _RETRY_STATUS:
                time.sleep(0.5 * (attempt + 1))
                continue
            r.raise_for_status()
        raise RuntimeError(f"POST {url} failed after {self.max_retries} retries")

    # ================= GAMMA (markets / events / search) =================
    def get_markets(self, **params) -> list[dict]:
        """List markets. Common params: limit, offset, active, closed, archived,
        order (e.g. 'volumeNum'), ascending, tag_id, clob_token_ids, condition_ids."""
        return self.get(GAMMA, "/markets", params)

    def get_market(self, market_id: str | int) -> dict:
        return self.get(GAMMA, f"/markets/{market_id}")

    def get_market_by_slug(self, slug: str) -> dict:
        return self.get(GAMMA, f"/markets/slug/{slug}")

    def get_events(self, **params) -> list[dict]:
        """List events (an event groups related markets). Same paging params as markets."""
        return self.get(GAMMA, "/events", params)

    def get_event(self, event_id: str | int) -> dict:
        return self.get(GAMMA, f"/events/{event_id}")

    def get_event_by_slug(self, slug: str) -> dict:
        return self.get(GAMMA, f"/events/slug/{slug}")

    def get_tags(self, **params) -> list[dict]:
        return self.get(GAMMA, "/tags", params)

    def search(self, q: str, **params) -> dict:
        """Full-text search across markets, events, and profiles."""
        params["q"] = q
        return self.get(GAMMA, "/public-search", params)

    def iter_markets(self, page_size: int = 500, max_pages: int = 200, **params):
        """Yield every market matching `params` via offset pagination."""
        offset = 0
        for _ in range(max_pages):
            batch = self.get_markets(limit=page_size, offset=offset, **params)
            if not batch:
                return
            yield from batch
            if len(batch) < page_size:
                return
            offset += page_size

    # ================= DATA (positions / trades / holders) ===============
    def get_positions(self, user: str, **params) -> list[dict]:
        """Current positions for a wallet (proxy address). params: market, limit, ..."""
        params["user"] = user
        return self.get(DATA, "/positions", params)

    def get_closed_positions(self, user: str, **params) -> list[dict]:
        params["user"] = user
        return self.get(DATA, "/closed-positions", params)

    def get_trades(self, **params) -> list[dict]:
        """Trades for a `user` (wallet) and/or `market` (condition id). params: limit, offset, side."""
        return self.get(DATA, "/trades", params)

    def get_activity(self, user: str, **params) -> list[dict]:
        params["user"] = user
        return self.get(DATA, "/activity", params)

    def get_holders(self, market: str, **params) -> list[dict]:
        """Top holders for a market (condition id)."""
        params["market"] = market
        return self.get(DATA, "/holders", params)

    def get_value(self, user: str, **params) -> dict:
        """Total USD value of a user's open positions."""
        params["user"] = user
        return self.get(DATA, "/value", params)

    def get_open_interest(self, **params) -> dict:
        return self.get(DATA, "/oi", params)

    def get_leaderboard(self, **params) -> list[dict]:
        return self.get(DATA, "/v1/leaderboard", params)

    # ================= CLOB (book / price / history) =====================
    def get_book(self, token_id: str) -> dict:
        """Full order book for one CLOB token (a clobTokenId from the market)."""
        return self.get(CLOB, "/book", {"token_id": token_id})

    def get_books(self, token_ids: list[str]) -> list[dict]:
        return self.post(CLOB, "/books", [{"token_id": t} for t in token_ids])

    def get_price(self, token_id: str, side: str = "BUY") -> dict:
        """Best price for a token. side = 'BUY' or 'SELL'."""
        return self.get(CLOB, "/price", {"token_id": token_id, "side": side})

    def get_midpoint(self, token_id: str) -> dict:
        return self.get(CLOB, "/midpoint", {"token_id": token_id})

    def get_spread(self, token_id: str) -> dict:
        return self.get(CLOB, "/spread", {"token_id": token_id})

    def get_last_trade_price(self, token_id: str) -> dict:
        return self.get(CLOB, "/last-trade-price", {"token_id": token_id})

    def get_tick_size(self, token_id: str) -> dict:
        return self.get(CLOB, f"/tick-size/{token_id}")

    def get_prices_history(
        self,
        token_id: str,
        interval: str | None = "max",
        fidelity: int | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> dict:
        """Historical price series for a CLOB token.

        `token_id` is a clobTokenId (NOT the condition id). Use EITHER `interval`
        (1m/1h/6h/1d/1w/max) OR an explicit start_ts/end_ts (unix seconds).
        `fidelity` = bar width in minutes (e.g. 60 = hourly, 720 = 12h).
        Returns {"history": [{"t": <unix>, "p": <price 0..1>}, ...]}.
        """
        params: dict[str, Any] = {"market": token_id}
        if start_ts is not None or end_ts is not None:
            if start_ts is not None:
                params["startTs"] = start_ts
            if end_ts is not None:
                params["endTs"] = end_ts
        elif interval:
            params["interval"] = interval
        if fidelity is not None:
            params["fidelity"] = fidelity
        return self.get(CLOB, "/prices-history", params)

    def get_clob_market(self, condition_id: str) -> dict:
        return self.get(CLOB, f"/clob-markets/{condition_id}")

    def get_sampling_markets(self, **params) -> dict:
        """Markets currently offering liquidity rewards (active, with a real book)."""
        return self.get(CLOB, "/sampling-markets", params)

    # ================= TRADING (authenticated, lazy) =====================
    def trading_client(self):
        """Build an authenticated py_clob_client_v2 ClobClient for placing/cancelling
        orders. Requires POLYMARKET_PRIVATE_KEY in env (plus optional L2 creds /
        POLYMARKET_FUNDER for a proxy/email wallet). Import is lazy so the read path
        never needs the SDK installed.
        """
        try:
            from py_clob_client_v2 import ApiCreds, ClobClient  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "py-clob-client-v2 is not installed. Run:\n"
                "    pip install py-clob-client-v2\n"
                "(only needed for trading; all read methods work without it)."
            ) from e

        key = os.getenv("POLYMARKET_PRIVATE_KEY")
        if not key:
            raise RuntimeError("POLYMARKET_PRIVATE_KEY not set in environment (.env)")
        host = os.getenv("POLYMARKET_HOST", CLOB)
        chain_id = int(os.getenv("POLYMARKET_CHAIN_ID", "137"))  # Polygon mainnet
        funder = os.getenv("POLYMARKET_FUNDER")  # proxy wallet, if using email/magic login

        kwargs: dict[str, Any] = {"host": host, "chain_id": chain_id, "key": key}
        if funder:
            kwargs["funder"] = funder

        # L2 creds: reuse if all three provided, else derive from the L1 key.
        api_key = os.getenv("POLYMARKET_API_KEY")
        api_secret = os.getenv("POLYMARKET_API_SECRET")
        api_pass = os.getenv("POLYMARKET_API_PASSPHRASE")
        if api_key and api_secret and api_pass:
            kwargs["creds"] = ApiCreds(
                api_key=api_key, api_secret=api_secret, api_passphrase=api_pass
            )
            return ClobClient(**kwargs)

        client = ClobClient(**kwargs)
        client.set_api_creds(client.create_or_derive_api_key())  # L1 -> L2 on the fly
        return client


if __name__ == "__main__":
    # tiny self-check
    c = PolymarketClient()
    mk = c.get_markets(limit=1, active=True, closed=False, order="volumeNum", ascending=False)
    m = mk[0]
    print("OK gamma:", m["question"][:60], "| conditionId:", m["conditionId"][:14], "...")
