"""
Foot Traffic — panel builder (wrapper over f1_20_panel via ft_lib).
Run:  python ft_20_panel.py
Writes: factor1_traffic/outputs/panel_foot.csv
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ft_lib  # noqa: E402  — patches paths + cfg before f1_lib runs

from ft_lib import OUT, build_panel, active  # noqa: E402

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    p = build_panel()
    out = OUT / f"panel_{active()}.csv"
    p.to_csv(out, index=False)
    post = p[p.REPORT_DATE.astype(str) > "2025-12-01"]
    print(f"[{active()}] panel rows={len(p)} · tickers={p.ticker.nunique()} · "
          f"x_yoy non-null={p.x_yoy.notna().sum()} · post-cutoff rows={len(post)}")
    print(f"  [written] {out}")
