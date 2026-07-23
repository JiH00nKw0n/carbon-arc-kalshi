"""Channel/Y-neutral, arm-aware prompt blocks: one interleaved TIMELINE table.

Generalizes factor1's ``prompt_versions._periods / _timeline_body / _tl_row / TL_HEADER``:

* the financials columns (revenue, revenue YoY, consensus, surprise) are the always-present
  ``fin`` block — the timeline is unusable without them;
* the alt-data (``x``) columns render only when ``"x"`` is in the arm's blocks, and are labelled
  from the ChannelSpec (``x_table_label`` / ``x_unit``) — never a literal "CARD SPEND", so web and
  foot read correctly;
* earnings-call transcripts interleave (each call before the quarter it guided) only when
  ``"text"`` is in the arm's blocks.

Jihoon's main protocol keeps the timeline Y-neutral and always shows leakage-safe early
consensus/surprise. The manuscript protocol preserves that layout for the two surprise targets but
uses its dedicated revenue/YoY-only timeline for ``rev_yoy``. BASE and TOOL remain byte-identical
within a fixed target and arm.
"""
from __future__ import annotations

from datetime import date, timedelta

__all__ = ["HIST_ROWS", "periods", "timeline_body"]

HIST_ROWS = 6

_HEADER = (
    "Company {tkr}. Everything below is information available BEFORE the upcoming quarter "
    "({q}) earnings report, in time order (each earnings call is followed by the data that came "
    "after it). You do NOT know the actual result.\n\n")

_TITLE = "TIMELINE (per quarter: the earnings call, then that quarter's data row):"
_FIN_COLS = ("revenue ($M)", "revenue YoY", "consensus ($M)", "surprise %")


# ---------- periods (generic, Y-neutral display rows) ----------
def periods(target, hist_rows: int = HIST_ROWS) -> list[dict]:
    """Last ``hist_rows`` history quarters + the target quarter, oldest -> newest.

    Each row is a dict of generic display keys — ``q, report, x_m, x_yoy, rev_m, rev_yoy,
    cons_m, surprise, target`` — read straight off the panel rows. History is restricted to
    quarters with a non-null alt-data YoY (so the x column never shows gaps), matching factor1.
    """
    rows = [_history_period(r) for r in _recent_history(target.hist, hist_rows)]
    rows.append(_target_period(target.row))
    return rows


def _recent_history(hist, hist_rows: int):
    dated = [r for r in hist if _is_number(r.x_yoy)]
    return dated[-hist_rows:]


def _history_period(r) -> dict:
    return {
        "q": r.fp_end, "report": r.report_date,
        "x_m": r.x_abs / 1e6, "x_yoy": r.x_yoy * 100,
        "rev_m": r.actual, "rev_yoy": r.rev_yoy * 100 if _is_number(r.rev_yoy) else None,
        "cons_m": r.cons_early, "surprise": r.surprise_early * 100, "target": False,
    }


def _target_period(r) -> dict:
    return {
        "q": r.fp_end, "report": r.report_date,
        "x_m": r.x_abs / 1e6, "x_yoy": r.x_yoy * 100,
        "rev_m": None, "rev_yoy": None, "cons_m": r.cons_early,
        "surprise": None, "target": True,
    }


# ---------- timeline body (arm-aware assembly) ----------
def timeline_body(target, transcript_store, channel_spec, y_target,
                  arm_blocks, n_calls: int, hist_rows: int = HIST_ROWS,
                  prompt_protocol: str = "jihoon_main") -> str:
    """Neutral header + interleaved TIMELINE table (call, then that quarter's row).

    ``arm_blocks`` (a set/frozenset over {fin, x, text}) drives what renders: x columns iff
    ``"x"`` in it, interleaved transcripts iff ``"text"`` in it; ``fin`` is always present.
    Under ``jihoon_main`` the body is Y-neutral. Under ``paper``, ``rev_yoy`` uses the manuscript's
    revenue/YoY-only columns while the surprise targets retain consensus/surprise columns.
    """
    if getattr(channel_spec, "kind", "scalar") == "ladder":
        return _ladder_body(
            target, transcript_store, y_target, arm_blocks, n_calls, hist_rows, prompt_protocol
        )
    ps = periods(target, hist_rows)
    show_x = "x" in arm_blocks
    paper_yoy = _is_paper_yoy(y_target, prompt_protocol)
    calls = transcript_store.prior_calls(target.ticker, target.report, n_calls) \
        if "text" in arm_blocks else []
    guided = _assign_calls(calls, ps)

    lines = [_TITLE]
    if show_x:
        lines.append(f"[alt-data columns: {channel_spec.x_table_label}]")
    lines.extend(_table_header(channel_spec, show_x, paper_yoy))
    for i, p in enumerate(ps):
        if i in guided:
            lines.append("\n" + _call_block(guided[i], transcript_store))
        lines.append(_row(p, show_x, paper_yoy))
    return _HEADER.format(tkr=target.ticker, q=target.fp) + "\n".join(lines)


def _table_header(channel_spec, show_x: bool, paper_yoy: bool = False) -> list[str]:
    fin_cols = ("revenue ($M)", "revenue YoY") if paper_yoy else _FIN_COLS
    cols = ["quarter", *(_x_headers(channel_spec) if show_x else ()), *fin_cols]
    return ["| " + " | ".join(cols) + " |", "|---" * len(cols) + "|"]


def _x_headers(channel_spec) -> tuple[str, str]:
    """(level, YoY) column headers derived from the channel's x_unit (e.g. 'card_spend_yoy')."""
    base = channel_spec.x_unit[:-4] if channel_spec.x_unit.endswith("_yoy") else channel_spec.x_unit
    return f"{base} (M)", channel_spec.x_unit


def _row(p: dict, show_x: bool, paper_yoy: bool = False) -> str:
    cells = [f"{p['q']}"]
    if show_x:
        cells += [f"{p['x_m']:,.1f}", f"{p['x_yoy']:+.1f}%"]
    if paper_yoy:
        cells += ["???", "PREDICT <-"] if p["target"] else [
            f"{p['rev_m']:,.0f}", _pct(p["rev_yoy"])
        ]
        return "| " + " | ".join(cells) + " |"
    if p["target"]:
        cells += ["???", "n/a", f"{p['cons_m']:,.0f}", "PREDICT ←"]
    else:
        cells += [f"{p['rev_m']:,.0f}", _pct(p["rev_yoy"]),
                  f"{p['cons_m']:,.0f}", f"{p['surprise']:+.2f}%"]
    return "| " + " | ".join(cells) + " |"


# ---------- ladder channel (Kalshi): fin timeline + a distribution block, not scalar x columns ----------
def _ladder_body(target, transcript_store, y_target, arm_blocks, n_calls: int, hist_rows: int,
                 prompt_protocol: str) -> str:
    """Chronological financial timeline with each quarter's raw ladder beside that quarter.

    The scalar path couples the history to a non-null x_yoy; a ladder channel's x_yoy is usually
    undefined, so history here is every recent quarter. X is a full market distribution rather than
    a (level, YoY) pair and is rendered only for quarters that actually carry a frozen payload.
    """
    ps = _ladder_periods(target, hist_rows)
    calls = transcript_store.prior_calls(target.ticker, target.report, n_calls) \
        if "text" in arm_blocks else []
    guided = _assign_calls(calls, ps)
    paper_yoy = _is_paper_yoy(y_target, prompt_protocol)
    fin_cols = ("revenue ($M)", "revenue YoY") if paper_yoy else _FIN_COLS
    lines = [_TITLE]
    lines.append("| " + " | ".join(("quarter", *fin_cols)) + " |")
    lines.append("|---" * (len(fin_cols) + 1) + "|")
    for i, p in enumerate(ps):
        if i in guided:
            lines.append("\n" + _call_block(guided[i], transcript_store))
        lines.append(_ladder_fin_row(p, paper_yoy))
        if "x" in arm_blocks and p["x_payload"]:
            lines.append(_ladder_block(p["x_payload"], f"quarter {p['q']}"))
    return _HEADER.format(tkr=target.ticker, q=target.fp) + "\n".join(lines)


def _ladder_periods(target, hist_rows: int) -> list[dict]:
    """Recent history quarters (NOT filtered on x_yoy) + the target quarter, fin fields only."""
    rows = [{
        "q": r.fp_end, "report": r.report_date, "rev_m": r.actual,
        "rev_yoy": r.rev_yoy * 100 if _is_number(r.rev_yoy) else None,
        "cons_m": r.cons_early, "surprise": r.surprise_early * 100, "target": False,
        "x_payload": getattr(r, "x_payload", None),
    } for r in list(target.hist)[-hist_rows:]]
    r = target.row
    rows.append({"q": r.fp_end, "report": r.report_date, "rev_m": None, "rev_yoy": None,
                 "cons_m": r.cons_early, "surprise": None, "target": True,
                 "x_payload": target.x_payload})
    return rows


def _ladder_fin_row(p: dict, paper_yoy: bool = False) -> str:
    if paper_yoy:
        cells = (
            [f"{p['q']}", "???", "PREDICT <-"]
            if p["target"]
            else [f"{p['q']}", f"{p['rev_m']:,.0f}", _pct(p["rev_yoy"])]
        )
        return "| " + " | ".join(cells) + " |"
    if p["target"]:
        cells = [f"{p['q']}", "???", "n/a", f"{p['cons_m']:,.0f}", "PREDICT ←"]
    else:
        cells = [f"{p['q']}", f"{p['rev_m']:,.0f}", _pct(p["rev_yoy"]),
                 f"{p['cons_m']:,.0f}", f"{p['surprise']:+.2f}%"]
    return "| " + " | ".join(cells) + " |"


def _ladder_block(payload: str, when: str) -> str:
    """Render every retained raw field for one quarter's pre-publication KPI ladder."""
    import json

    lines = [
        "KALSHI PRE-PUBLICATION KPI MARKET LADDER "
        "(raw, uncalibrated; frozen before the report):",
    ]
    for ladder in json.loads(payload):
        rungs = ladder.get("rungs") or []
        if len(rungs) < 2:
            continue
        lines += [
            f"event: {ladder.get('event_ticker')}  KPI: {ladder.get('metric_label') or 'unknown'}  ({when})",
            f"coverage: {ladder.get('n_priced_rungs', len(rungs))}/"
            f"{ladder.get('n_ladder_markets', len(rungs))} rungs; raw monotonicity violations: "
            f"{ladder.get('monotonicity_violations', 'n/a')}",
            "market | YES condition | probability | source | bid | ask | last | previous | spread | "
            "candle_utc | daily_volume | open_interest",
        ]
        for rung in sorted(rungs, key=lambda item: item.get("strike", 0)):
            lines.append(
                f"{rung.get('market_ticker', 'unknown')} | KPI "
                f"{rung.get('threshold_operator', '>')} {_number(rung.get('strike'))} | "
                f"{_number(rung.get('probability'), 3)} | {rung.get('price_source', 'unknown')} | "
                f"{_number(rung.get('yes_bid'), 3)} | {_number(rung.get('yes_ask'), 3)} | "
                f"{_number(rung.get('last'), 3)} | {_number(rung.get('previous'), 3)} | "
                f"{_number(rung.get('spread'), 3)} | {rung.get('candle_at') or 'n/a'} | "
                f"{_number(rung.get('daily_volume'))} | {_number(rung.get('open_interest'))}"
            )
    return "\n".join(lines)


# ---------- call interleaving ----------
def _assign_calls(calls, ps: list[dict]) -> dict[int, object]:
    """Map each call (oldest -> newest) to the first later, unclaimed quarter it guided."""
    guided: dict[int, object] = {}
    for ref in calls:
        for i, p in enumerate(ps):
            if i not in guided and _guides(p["report"], ref.call_date):
                guided[i] = ref
                break
    return guided


def _guides(report: date, call_date: date) -> bool:
    return report > call_date + timedelta(days=1)


def _call_block(ref, transcript_store) -> str:
    text = transcript_store.read_text(ref.path)
    return f"[EARNINGS CALL {ref.call_date}]\n{text}" if text else ""


# ---------- formatting helpers ----------
def _pct(v) -> str:
    return "n/a" if v is None else f"{v:+.1f}%"


def _is_number(v) -> bool:
    return v is not None and v == v  # rejects None and NaN


def _number(value, decimals: int = 2) -> str:
    if not _is_number(value):
        return "n/a"
    number = float(value)
    if abs(number) >= 1_000:
        return f"{number:,.6g}"
    return f"{number:.{decimals}f}"


def _is_paper_yoy(y_target, prompt_protocol: str) -> bool:
    return prompt_protocol == "paper" and getattr(y_target, "name", None) == "rev_yoy"
