"""Channel/Y-neutral, arm-aware prompt blocks: one interleaved TIMELINE table.

Generalizes factor1's ``prompt_versions._periods / _timeline_body / _tl_row / TL_HEADER``:

* the financials columns (revenue, revenue YoY, consensus, surprise) are the always-present
  ``fin`` block — the timeline is unusable without them;
* the alt-data (``x``) columns render only when ``"x"`` is in the arm's blocks, and are labelled
  from the ChannelSpec (``x_table_label`` / ``x_unit``) — never a literal "CARD SPEND", so web and
  foot read correctly;
* earnings-call transcripts interleave (each call before the quarter it guided) only when
  ``"text"`` is in the arm's blocks.

The body is deliberately Y-neutral: it shows the leakage-free EARLY consensus/surprise for every
target, and the Y-specific ask is appended by the prompt variant. This keeps the (channel, arm)
timeline byte-identical across the three Y targets and across BASE/TOOL (which share one prompt).
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
                  arm_blocks, n_calls: int, hist_rows: int = HIST_ROWS) -> str:
    """Neutral header + interleaved TIMELINE table (call, then that quarter's row).

    ``arm_blocks`` (a set/frozenset over {fin, x, text}) drives what renders: x columns iff
    ``"x"`` in it, interleaved transcripts iff ``"text"`` in it; ``fin`` is always present.
    ``y_target`` is accepted for a uniform block-builder signature but not branched on — the body
    is Y-neutral (the variant appends the Y-specific ask).
    """
    ps = periods(target, hist_rows)
    show_x = "x" in arm_blocks
    calls = transcript_store.prior_calls(target.ticker, target.report, n_calls) \
        if "text" in arm_blocks else []
    guided = _assign_calls(calls, ps)

    lines = [_TITLE]
    if show_x:
        lines.append(f"[alt-data columns: {channel_spec.x_table_label}]")
    lines.extend(_table_header(channel_spec, show_x))
    for i, p in enumerate(ps):
        if i in guided:
            lines.append("\n" + _call_block(guided[i], transcript_store))
        lines.append(_row(p, show_x))
    return _HEADER.format(tkr=target.ticker, q=target.fp) + "\n".join(lines)


def _table_header(channel_spec, show_x: bool) -> list[str]:
    cols = ["quarter", *(_x_headers(channel_spec) if show_x else ()), *_FIN_COLS]
    return ["| " + " | ".join(cols) + " |", "|---" * len(cols) + "|"]


def _x_headers(channel_spec) -> tuple[str, str]:
    """(level, YoY) column headers derived from the channel's x_unit (e.g. 'card_spend_yoy')."""
    base = channel_spec.x_unit[:-4] if channel_spec.x_unit.endswith("_yoy") else channel_spec.x_unit
    return f"{base} (M)", channel_spec.x_unit


def _row(p: dict, show_x: bool) -> str:
    cells = [f"{p['q']}"]
    if show_x:
        cells += [f"{p['x_m']:,.1f}", f"{p['x_yoy']:+.1f}%"]
    if p["target"]:
        cells += ["???", "n/a", f"{p['cons_m']:,.0f}", "PREDICT ←"]
    else:
        cells += [f"{p['rev_m']:,.0f}", _pct(p["rev_yoy"]),
                  f"{p['cons_m']:,.0f}", f"{p['surprise']:+.2f}%"]
    return "| " + " | ".join(cells) + " |"


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
