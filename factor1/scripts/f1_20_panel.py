"""Factor 1 — channel-agnostic panel builder. Run:  F1_CHANNEL=card python3 f1_20_panel.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_lib import build_panel, OUT, active  # noqa: E402

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    p = build_panel()
    out = OUT / f"panel_{active()}.csv"
    p.to_csv(out, index=False)
    post = p[p.REPORT_DATE.astype(str) > "2025-12-01"]
    print(f"[{active()}] panel rows={len(p)} · tickers={p.ticker.nunique()} · "
          f"x_yoy non-null={p.x_yoy.notna().sum()} · post-cutoff rows={len(post)}")
    print(f"  strength O tiers: {p.dropna(subset=['strength']).groupby('strength').ticker.nunique().to_dict()}")
    print(f"  [written] {out}")
