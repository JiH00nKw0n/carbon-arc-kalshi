"""
L2 — Tool-use 에이전트: LLM이 사전지식을 '스스로' 선택.

L1(pk_01/pk_03)은 연구자가 사전지식을 고정 주입 → 순환논법 위험(연구자가 답을 심음).
L2는 LLM에게 도구만 주고 "필요하면 직접 정보를 가져오라"고 함. **어느 채널에서 어떤 도구를
몇 번 호출하는지**가 논문의 핵심 결과 — LLM이 card엔 변동성(fundamentals), foot엔 채널믹스
(business_profile)를 자발적으로 요청한다면, 이는 각 alt-data의 신호 메커니즘과 일치.

도구는 이미 수집한 캐시에서 서빙(FactSet OAuth fundamentals + WebSearch profile) — LLM이
'요청할 때만' 노출. 연구자는 심지 않음.

OpenAI function-calling loop. 로그: outputs/agent_toolcalls.csv (channel, ticker, tool).

OUT: outputs/pk_agent_pred_<ch>.csv, agent_toolcalls.csv, pk_agent_compare.md

Usage:  python pk_04_agent.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pk_config import DATA, OUT, GT_COMPANY, LI_SCRIPTS, CACHE  # noqa: E402

sys.path.insert(0, str(LI_SCRIPTS))
from li_config import CHANNELS  # noqa: E402
from li_llm import _key  # reuse OpenAI key loader  # noqa: E402
import pk_01_llm_compare as V1  # evaluate, CH_KEY  # noqa: E402

MODEL = "gpt-5.5"

# ---- tool backends (serve from already-collected caches) ----
PK = json.load(open(DATA / "priorknowledge_all.json"))
FUND = json.load(open(DATA / "factset_fundamentals.json"))

TOOLS = [
    {"type": "function", "function": {
        "name": "get_fundamentals",
        "description": "FactSet financial fundamentals for a ticker: quarterly sales size, operating "
                       "margin, margin_volatility (std of op margin), sales_growth_volatility (std of "
                       "YoY sales growth). Higher volatility = harder-to-forecast earnings = more room "
                       "for alt-data to predict revenue surprise.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}},
                       "required": ["ticker"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_business_profile",
        "description": "Business profile for a ticker: business model, digital/online revenue %, "
                       "in-store %, whether card spend / foot traffic is a meaningful revenue driver.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}},
                       "required": ["ticker"], "additionalProperties": False}}},
]


def run_tool(name, args, log, ch):
    t = args.get("ticker", "").upper()
    log.append({"channel": ch, "ticker": t, "tool": name})
    if name == "get_fundamentals":
        return FUND.get(t, {"error": "no data"})
    if name == "get_business_profile":
        d = PK.get(t, {})
        return {k: d.get(k) for k in ("business_model", "digital_pct", "instore_pct",
                                      "card_dominant", "traffic_relevant")} or {"error": "no data"}
    return {"error": "unknown tool"}


RANK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["ranking"],
    "properties": {"ranking": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["ticker", "rank", "signal_strength"],
        "properties": {"ticker": {"type": "string"}, "rank": {"type": "integer"},
                       "signal_strength": {"type": "string", "enum": ["strong", "moderate", "weak"]}}}}},
}

SYSTEM = (
    "You are a quantitative alt-data researcher. Rank companies by how well a given alt-data signal "
    "predicts their quarterly revenue surprise. You have TOOLS to fetch company information. "
    "Call whatever tools you judge NECESSARY for THIS alt-data channel — do not fetch blindly; fetch "
    "the information that actually matters for this signal's mechanism. Then output the final ranking. "
    "Be economical with tool calls but get what you need."
)


def agent_rank(ch, tickers, toolog):
    from openai import OpenAI
    client = OpenAI(api_key=_key())
    meta = CHANNELS[V1.CH_KEY[ch]]
    user = (f"ALT-DATA: {ch} ({meta['dataset']})\nSignal: {meta['signal']}\n"
            f"Description: {meta['description']}\n\n"
            f"COMPANY SET ({len(tickers)}): {', '.join(tickers)}\n\n"
            "Decide what company information you need to rank these by how well THIS signal predicts "
            "revenue surprise, fetch it via tools, then rank ALL tickers (rank 1 = strongest). "
            "You may fetch for as many or as few tickers as you judge useful.")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

    for _ in range(40):  # tool loop cap
        resp = client.chat.completions.create(
            model=MODEL, messages=msgs, tools=TOOLS,
            max_completion_tokens=9000)
        m = resp.choices[0].message
        if m.tool_calls:
            msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in m.tool_calls]})
            for tc in m.tool_calls:
                args = json.loads(tc.function.arguments)
                res = run_tool(tc.function.name, args, toolog, ch)
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(res)})
            continue
        break

    # final structured ranking call (force JSON)
    msgs.append({"role": "user", "content": "Now output the final ranking as JSON."})
    resp = client.chat.completions.create(
        model=MODEL, messages=msgs,
        response_format={"type": "json_schema",
                         "json_schema": {"name": "rank", "strict": True, "schema": RANK_SCHEMA}},
        max_completion_tokens=6000)
    out = json.loads(resp.choices[0].message.content)
    df = pd.DataFrame(out["ranking"]); df["channel"] = ch
    return df


def main():
    gt = pd.read_csv(GT_COMPANY)
    uni = json.load(open(DATA / "universe.json"))
    toolog, rows = [], []

    for ch in ["card", "foot", "web"]:
        tickers = sorted([t for t, chans in uni.items() if ch in chans])
        cache_f = CACHE / f"agent_{ch}.json"
        if cache_f.exists():
            cached = json.load(open(cache_f))
            pred = pd.DataFrame(cached["ranking"]); pred["channel"] = ch
            toolog += cached["toolcalls"]
        else:
            local_log = []
            pred = agent_rank(ch, tickers, local_log)
            json.dump({"ranking": pred.drop(columns=["channel"]).to_dict("records"),
                       "toolcalls": local_log}, open(cache_f, "w"), indent=2)
            toolog += local_log
        pred.to_csv(OUT / f"pk_agent_pred_{ch}.csv", index=False)
        ev = V1.evaluate(pred, gt, ch)
        if ev:
            rows.append({"channel": ch, "cond": "agent_L2", **ev})
            print(f"  {ch} agent: Spearman={ev['rank_spearman']} topk={ev['topk_precision']} AUC={ev['auc']}")

    tl = pd.DataFrame(toolog)
    tl.to_csv(OUT / "agent_toolcalls.csv", index=False)
    print("\n=== 자율 도구 호출 패턴 (채널별) ===")
    if not tl.empty:
        pivot = tl.groupby(["channel", "tool"]).size().unstack(fill_value=0)
        print(pivot.to_string())
    pd.DataFrame(rows).to_csv(OUT / "pk_agent_compare.csv", index=False)
    print(f"\nsaved: agent_toolcalls.csv, pk_agent_compare.csv")


if __name__ == "__main__":
    main()
