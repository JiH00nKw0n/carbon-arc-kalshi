"""
L2b (선택강제) + L2c (풀좁히기) 에이전트.

L2 (pk_04)의 문제: LLM이 도구를 가려서 안 부르고 모든 회사에 다 부름(50:50) → 채널별
정보 매칭이라는 메타인지가 안 나타남.

L2b — 선택 강제: 프롬프트에 "도구 호출당 비용이 크다. 이 alt-data 채널에 정말 필요한 정보만
  최소로 요청하라"를 넣어, LLM이 채널별로 옳은 도구를 고르는지(card→fundamentals, foot→profile)
  테스트. 도구 호출 패턴이 핵심 결과.

L2c — 풀좁히기 (Notion 코멘트 "X,Y 많으면 filtering"): 전체 유니버스를 주고 먼저 "이 신호가
  잘 될 회사 top-N만 골라라(스크리닝)"→ 좁힌 풀 안에서만 정보수집+랭킹. 실전 스크리닝 방식.
  company-fit을 '좁힌 풀 내'에서 측정 + 스크리닝 자체의 정밀도(고른 N개가 실제 강신호인가).

기존 pk_04_agent 재사용 (TOOLS, run_tool, RANK_SCHEMA, evaluate).

OUT: outputs/pk_l2b_*.csv, pk_l2c_*.csv, agent_variants_toolcalls.csv, l2_variants_compare.md

Usage:  python pk_05_agent_variants.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pk_config import DATA, OUT, GT_COMPANY, LI_SCRIPTS, CACHE  # noqa: E402

sys.path.insert(0, str(LI_SCRIPTS))
from li_config import CHANNELS  # noqa: E402
from li_llm import _key  # noqa: E402
import pk_01_llm_compare as V1  # evaluate, CH_KEY  # noqa: E402
import pk_04_agent as A  # TOOLS, run_tool, RANK_SCHEMA, MODEL  # noqa: E402

# ---------- L2b: 선택 강제 ----------
SYSTEM_L2B = (
    "You are a quantitative alt-data researcher. Rank companies by how well a given alt-data signal "
    "predicts revenue surprise. You have tools to fetch company info, but EACH TOOL CALL IS COSTLY. "
    "Fetch ONLY the information that genuinely matters for THIS signal's mechanism — do not fetch "
    "everything. First reason about WHICH single kind of information is most decisive for this "
    "particular alt-data channel, then fetch only that, for only the tickers where it changes your "
    "judgment. Minimize tool calls."
)

# ---------- L2c: 풀좁히기 ----------
SCREEN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["shortlist", "reasoning"],
    "properties": {"shortlist": {"type": "array", "items": {"type": "string"}},
                   "reasoning": {"type": "string"}},
}


def agent_rank_generic(ch, tickers, system, toolog, tag):
    """tool-loop with a given system prompt (L2b uses cost-framed system)."""
    from openai import OpenAI
    client = OpenAI(api_key=_key())
    meta = CHANNELS[V1.CH_KEY[ch]]
    user = (f"ALT-DATA: {ch} ({meta['dataset']})\nSignal: {meta['signal']}\n"
            f"Description: {meta['description']}\n\n"
            f"COMPANY SET ({len(tickers)}): {', '.join(tickers)}\n\n"
            "Rank ALL tickers (rank 1 = strongest predictor of revenue surprise). "
            "Fetch only the information you truly need first.")
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for _ in range(40):
        resp = client.chat.completions.create(model=A.MODEL, messages=msgs, tools=A.TOOLS,
                                              max_completion_tokens=9000)
        m = resp.choices[0].message
        if m.tool_calls:
            msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in m.tool_calls]})
            for tc in m.tool_calls:
                res = A.run_tool(tc.function.name, json.loads(tc.function.arguments), toolog, ch)
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(res)})
            continue
        break
    msgs.append({"role": "user", "content": "Now output the final ranking as JSON."})
    resp = client.chat.completions.create(
        model=A.MODEL, messages=msgs,
        response_format={"type": "json_schema", "json_schema": {"name": "rank", "strict": True,
                                                                "schema": A.RANK_SCHEMA}},
        max_completion_tokens=6000)
    df = pd.DataFrame(json.loads(resp.choices[0].message.content)["ranking"]); df["channel"] = ch
    return df


def screen_shortlist(ch, tickers, n):
    """L2c step 1: LLM screens full universe → top-N shortlist (no tools, just prior reasoning)."""
    from openai import OpenAI
    client = OpenAI(api_key=_key())
    meta = CHANNELS[V1.CH_KEY[ch]]
    user = (f"ALT-DATA: {ch} ({meta['dataset']})\nSignal: {meta['signal']}\n"
            f"Description: {meta['description']}\n\n"
            f"FULL UNIVERSE ({len(tickers)}): {', '.join(tickers)}\n\n"
            f"Screen this universe down to the {n} companies where THIS alt-data signal is most likely "
            f"to predict revenue surprise well. Return exactly {n} tickers as a shortlist.")
    resp = client.chat.completions.create(
        model=A.MODEL, messages=[{"role": "system", "content": A.SYSTEM},
                                 {"role": "user", "content": user}],
        response_format={"type": "json_schema", "json_schema": {"name": "screen", "strict": True,
                                                                "schema": SCREEN_SCHEMA}},
        max_completion_tokens=4000)
    out = json.loads(resp.choices[0].message.content)
    return out["shortlist"][:n]


def main():
    gt = pd.read_csv(GT_COMPANY)
    uni = json.load(open(DATA / "universe.json"))
    toolog, rows = [], []

    for ch in ["card", "foot", "web"]:
        tickers = sorted([t for t, chans in uni.items() if ch in chans])

        # ---- L2b: 선택 강제 ----
        cf = CACHE / f"l2b_{ch}.json"
        if cf.exists():
            c = json.load(open(cf)); pred = pd.DataFrame(c["ranking"]); pred["channel"] = ch; toolog += c["toolcalls"]
        else:
            log = []; pred = agent_rank_generic(ch, tickers, SYSTEM_L2B, log, "l2b")
            json.dump({"ranking": pred.drop(columns=["channel"]).to_dict("records"), "toolcalls": log},
                      open(cf, "w"), indent=2); toolog += log
        ev = V1.evaluate(pred, gt, ch)
        if ev:
            rows.append({"channel": ch, "cond": "L2b_forced", **ev})
            print(f"  {ch} L2b(선택강제): Spearman={ev['rank_spearman']} topk={ev['topk_precision']} AUC={ev['auc']}")

        # ---- L2c: 풀좁히기 (top-N=15) ----
        N = 15
        sf = CACHE / f"l2c_shortlist_{ch}.json"
        if sf.exists():
            shortlist = json.load(open(sf))
        else:
            shortlist = screen_shortlist(ch, tickers, N)
            json.dump(shortlist, open(sf, "w"), indent=2)
        # 스크리닝 정밀도: 고른 N개 중 실제 강신호(r_company > 채널중앙값) 비율
        g = gt[gt.channel == ch].set_index("ticker")["r_company"]
        med = g.median()
        picked = [t for t in shortlist if t in g.index]
        if picked:
            screen_prec = np.mean([g[t] > med for t in picked])
            rows.append({"channel": ch, "cond": "L2c_screen", "n": len(picked),
                         "rank_spearman": None, "topk_precision": round(float(screen_prec), 3),
                         "auc": None})
            print(f"  {ch} L2c(풀좁히기 top{N}): 스크리닝 정밀도={screen_prec:.0%} "
                  f"(고른 {len(picked)}개 중 실제 강신호 비율, 랜덤기대 50%)")

    tl = pd.DataFrame(toolog)
    tl.to_csv(OUT / "agent_variants_toolcalls.csv", index=False)
    print("\n=== L2b 자율 도구 호출 패턴 (선택 강제 후) ===")
    if not tl.empty:
        print(tl.groupby(["channel", "tool"]).size().unstack(fill_value=0).to_string())
    pd.DataFrame(rows).to_csv(OUT / "l2_variants_compare.csv", index=False)
    print(f"\nsaved: agent_variants_toolcalls.csv, l2_variants_compare.csv")


if __name__ == "__main__":
    main()
