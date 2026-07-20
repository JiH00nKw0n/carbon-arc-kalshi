"""
Foot Traffic — evaluation (wrapper over f1_22_eval via ft_lib). $0, no LLM.
Run:  python ft_22_eval.py
Writes: factor1_traffic/outputs/results_foot.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ft_lib  # noqa: E402  — patches paths + cfg before f1_22_eval imports f1_lib

_F1_SCRIPTS = Path(__file__).resolve().parents[2] / "factor1" / "scripts"
sys.path.insert(0, str(_F1_SCRIPTS))

# run f1_22_eval.main() directly — it reads active()/OUT from patched f1_lib
import f1_22_eval  # noqa: E402

if __name__ == "__main__":
    f1_22_eval.main()
