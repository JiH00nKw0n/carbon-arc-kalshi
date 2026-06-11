#!/usr/bin/env python3
"""
smoke_test.py — verify read-only Polymarket access end to end (no auth, no SDK).

Walks: Gamma markets -> pick a liquid 2-outcome market -> CLOB book/midpoint/price
-> CLOB price history -> Data holders -> Gamma search. Prints a one-line PASS/FAIL
per stage. Run: python scripts/polymarket/smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/ on path
from polymarket import PolymarketClient  # noqa: E402


def main() -> int:
    c = PolymarketClient()
    fails = 0

    # 1. Gamma: list a liquid binary market
    mk = c.get_markets(limit=20, active=True, closed=False, order="volumeNum", ascending=False)
    m = next((x for x in mk if x.get("clobTokenIds") and len(eval_outcomes(x)) == 2), mk[0])
    import json
    token_ids = json.loads(m["clobTokenIds"])
    cond = m["conditionId"]
    print(f"[1] gamma /markets       PASS  {m['question'][:50]!r}")
    print(f"      conditionId={cond[:18]}…  tokens={len(token_ids)}  vol=${m.get('volumeNum',0):,.0f}")

    yes_token = token_ids[0]

    # 2. CLOB: order book
    try:
        book = c.get_book(yes_token)
        nb, na = len(book.get("bids", [])), len(book.get("asks", []))
        print(f"[2] clob /book           PASS  bids={nb} asks={na}")
    except Exception as e:
        fails += 1; print(f"[2] clob /book           FAIL  {e}")

    # 3. CLOB: midpoint + price
    try:
        mid = c.get_midpoint(yes_token).get("mid")
        bid = c.get_price(yes_token, "BUY").get("price")
        print(f"[3] clob /midpoint,/price PASS  mid={mid} buy={bid}")
    except Exception as e:
        fails += 1; print(f"[3] clob /midpoint,/price FAIL  {e}")

    # 4. CLOB: price history
    try:
        hist = c.get_prices_history(yes_token, interval="1w", fidelity=60).get("history", [])
        span = f"{hist[0]['t']}→{hist[-1]['t']}" if hist else "empty"
        print(f"[4] clob /prices-history PASS  points={len(hist)} ({span})")
    except Exception as e:
        fails += 1; print(f"[4] clob /prices-history FAIL  {e}")

    # 5. Data: top holders
    try:
        holders = c.get_holders(cond)
        n = sum(len(h.get("holders", [])) for h in holders) if isinstance(holders, list) else 0
        print(f"[5] data /holders        PASS  tokens={len(holders) if isinstance(holders,list) else '?'} holders≈{n}")
    except Exception as e:
        fails += 1; print(f"[5] data /holders        FAIL  {e}")

    # 6. Gamma: search
    try:
        res = c.search("bitcoin", limit_per_type=3)
        ev = len(res.get("events", []) or [])
        print(f"[6] gamma /public-search PASS  events_hit={ev}")
    except Exception as e:
        fails += 1; print(f"[6] gamma /public-search FAIL  {e}")

    print("\n" + ("ALL READ ENDPOINTS OK ✅" if fails == 0 else f"{fails} stage(s) FAILED ❌"))
    return 1 if fails else 0


def eval_outcomes(market: dict) -> list:
    import json
    try:
        return json.loads(market.get("outcomes", "[]"))
    except Exception:
        return market.get("outcomes", []) or []


if __name__ == "__main__":
    raise SystemExit(main())
