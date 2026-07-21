"""
사전지식(prior-knowledge) 주입 실험 config.

가설: LLM company-fit이 낮았던 이유 = 회사별 사전지식 부족(티커+채널설명만 줬음).
WebSearch로 회사별 사업모델·디지털비중·결제믹스를 가져와 LLM 프롬프트에 주입하면
company-fit(어느 회사에서 신호 강할지)이 개선되는가?

비교: baseline(사전지식 X) vs enriched(사전지식 O). 실제 per-company r과 대조.
"""
from pathlib import Path

ROOT  = Path(__file__).resolve().parents[1]
DATA  = ROOT / "data"
OUT   = ROOT / "outputs"
CACHE = ROOT / "cache"
for d in (DATA, OUT, CACHE):
    d.mkdir(parents=True, exist_ok=True)

REPO = ROOT.parent                                    # carbon-arc-kalshi/
YS_LI = REPO / "factor1_yswitch" / "llm_identify"     # reuse li_llm, gt_channel_company
LI_SCRIPTS = YS_LI / "scripts"
GT_COMPANY = YS_LI / "outputs" / "gt_channel_company.csv"   # 실제 per-company r (정답지)

OPENAI_MODEL = "gpt-5.5"
