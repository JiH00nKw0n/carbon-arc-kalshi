"""
HTML 보고서 생성 (Task 9) — self-contained, 인라인 CSS/JS, 외부 의존 없음.

읽는 파일 (전 단계 산출물):
  gt_channel_metric.csv, gt_channel_company.csv     실제 실험결과
  llm_pred_metric.csv, llm_pred_company.csv          LLM 식별 예측
  llm_reasoning.json                                 LLM 근거
  validation_metric.csv, validation_company.csv, validation_summary.json  검증

산출물: outputs/report.html  (dataviz 팔레트 준수: categorical blue/aqua/…, status good/critical)

Usage:  python li_04_report.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from li_config import OUT, CHANNELS  # noqa: E402

# validated dataviz palette (light/dark handled via CSS vars)
PAL = {"blue": "#2a78d6", "aqua": "#1baf7a", "yellow": "#eda100", "violet": "#4a3aa7",
       "red": "#e34948", "good": "#0ca30c", "critical": "#d03b3b", "warn": "#fab219"}


def load():
    d = {}
    for f in ["gt_channel_metric", "gt_channel_metric_full", "gt_channel_company", "llm_pred_metric",
              "llm_pred_company", "validation_metric", "validation_company"]:
        p = OUT / f"{f}.csv"
        d[f] = pd.read_csv(p) if p.exists() else pd.DataFrame()
    d["reasoning"] = json.load(open(OUT / "llm_reasoning.json")) if (OUT / "llm_reasoning.json").exists() else []
    d["vsummary"] = json.load(open(OUT / "validation_summary.json")) if (OUT / "validation_summary.json").exists() else {}
    return d


def badge(passed):
    c, t = (PAL["good"], "PASS") if passed else (PAL["critical"], "fail")
    return f'<span class="badge" style="background:{c}">{t}</span>'


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def metric_fit_section(d):
    gt = d["gt_channel_metric"]; llm = d["llm_pred_metric"]; val = d["validation_metric"]
    vs = {r["channel"]: r for r in d["vsummary"].get("metric_fit", [])}
    html = ["<h2>1. Metric-fit — LLM이 예측한 'Y 적합성' vs 실제</h2>",
            "<p class='lead'>각 alt-data 채널에서 어떤 Y metric이 잘 예측될지 LLM이 <b>결과를 모르는 상태로</b> "
            "랭킹했다. 아래는 그 랭킹을 실제 |r| 랭킹과 겹쳐 본 것 — 순위 상관(Spearman)과 유의성 예측 정확도.</p>"]
    for ch in ["card", "foot", "click"]:
        s = vs.get(ch, {})
        rho = s.get("rank_spearman", "—"); acc = s.get("sig_accuracy", "—")
        html.append(f"<h3>{ch} <span class='sub'>rank Spearman={rho} · significance accuracy={acc}</span></h3>")
        sub = val[val.channel == ch].sort_values("actual_rank") if len(val) else pd.DataFrame()
        html.append("<div class='twrap'><table><tr><th>Y metric</th><th>LLM rank</th><th>실제 rank</th>"
                    "<th>LLM: 유의?</th><th>실제 r</th><th>실제 pass</th></tr>")
        for _, r in sub.iterrows():
            ok = "✓" if bool(r["will_be_significant"]) == bool(r["pass"]) else "✗"
            html.append(f"<tr><td>{esc(r['metric'])}</td><td>{int(r['rank'])}</td>"
                        f"<td>{int(r['actual_rank'])}</td>"
                        f"<td>{'예' if r['will_be_significant'] else '아니오'} {ok}</td>"
                        f"<td>{r['r']:+.3f}</td><td>{badge(bool(r['pass']))}</td></tr>")
        html.append("</table></div>")
    return "\n".join(html)


def company_fit_section(d):
    val = d["validation_company"]
    vs = {r["channel"]: r for r in d["vsummary"].get("company_fit", [])}
    html = ["<h2>2. Company-fit — LLM이 예측한 '회사 적합성' vs 실제</h2>",
            "<p class='lead'>LLM이 각 채널에서 alt-data가 revenue surprise를 잘 예측할 회사를 랭킹했다. "
            "실제 per-company 상관(r_company)과 비교 — top-k precision과 순위 상관.</p>"]
    for ch in ["card", "foot", "click"]:
        s = vs.get(ch, {})
        html.append(f"<h3>{ch} <span class='sub'>rank Spearman={s.get('rank_spearman','—')} · "
                    f"top{s.get('topk','')} precision={s.get('topk_precision','—')} · "
                    f"AUC={s.get('auc_strong','—')}</span></h3>")
        sub = val[val.channel == ch].sort_values("actual_rank") if len(val) else pd.DataFrame()
        html.append("<div class='twrap'><table><tr><th>ticker</th><th>LLM rank</th><th>실제 rank</th>"
                    "<th>LLM 강도</th><th>실제 r_company</th><th>n</th></tr>")
        for _, r in sub.head(15).iterrows():
            col = PAL["good"] if r["r_company"] > 0.3 else (PAL["warn"] if r["r_company"] > 0 else PAL["critical"])
            html.append(f"<tr><td><b>{esc(r['ticker'])}</b></td><td>{int(r['rank'])}</td>"
                        f"<td>{int(r['actual_rank'])}</td><td>{esc(r['signal_strength'])}</td>"
                        f"<td style='color:{col};font-weight:600'>{r['r_company']:+.3f}</td>"
                        f"<td>{int(r['n_company'])}</td></tr>")
        html.append("</table></div><p class='note'>상위 15개만 표시 (전체는 CSV).</p>")
    return "\n".join(html)


def gt_heatmap_section(d):
    gt = d["gt_channel_metric_full"] if len(d["gt_channel_metric_full"]) else d["gt_channel_metric"]
    html = ["<h2>3. Ground truth — 전체 그리드 (8 Y × 3 channel = 24조합)</h2>",
            "<p class='lead'>모든 채널 × 모든 Y를 실제 검정한 완전한 정답지. 색 = |r|, "
            "PASS = clustered-bootstrap &amp; surrogate 이중검정 통과. n&lt;15 = 커버리지 부족(회색).</p>",
            "<div class='twrap'><table><tr><th>channel</th><th>Y</th><th>r</th><th>rank-IC</th>"
            "<th>n</th><th>검정</th></tr>"]
    for _, r in gt.iterrows():
        has_r = pd.notna(r["r"])
        if not has_r:
            html.append(f"<tr><td>{esc(r['channel'])}</td><td>{esc(r['y'])}</td>"
                        f"<td style='color:var(--ink2)'>—</td><td>—</td>"
                        f"<td>{int(r['n'])}</td><td><span class='badge' style='background:#999'>n&lt;15</span></td></tr>")
            continue
        ar = abs(r["r"])
        bg = f"rgba(42,120,214,{min(ar*1.6,0.85):.2f})"
        ic = f"{r['mean_ic']:+.3f}" if pd.notna(r.get("mean_ic")) else "—"
        html.append(f"<tr><td>{esc(r['channel'])}</td><td>{esc(r['y'])}</td>"
                    f"<td style='background:{bg};color:#fff;font-weight:600'>{r['r']:+.3f}</td>"
                    f"<td>{ic}</td><td>{int(r['n'])}</td><td>{badge(bool(r['pass']))}</td></tr>")
    html.append("</table></div>")
    return "\n".join(html)


def methodology_section():
    return """
<h2>0. 검증 메트릭 — 정의와 근거</h2>
<p class='lead'>LLM의 예측(랭킹)을 실제 실험결과와 대조하려면, "랭킹이 맞았나"와 "강신호를 골랐나"를
정량화하는 지표가 필요하다. 아래 4개를 도입했다. 각 메트릭의 정의(코드와 1:1)와, <b>왜 이 검증에
적합한지</b>를 함께 밝힌다.</p>

<h3>① Rank Spearman — 순위 상관</h3>
<p class='lead'><b>정의</b>: LLM이 매긴 순위(rank 1 = 가장 유망)와, 실제 |r|로 매긴 순위 사이의
Spearman 상관계수 (<code>spearmanr(llm_rank, actual_rank)</code>). +1 = 순위 완벽 일치, 0 = 무관, −1 = 정반대.<br>
<b>왜 적합한가</b>: LLM의 출력은 <b>절대 점수가 아니라 순위</b>다("card엔 rev_yoy가 surprise보다
유망"). 실제 r의 절대값을 LLM이 맞힐 필요는 없고 <b>순서만</b> 맞으면 식별에 성공한 것이므로,
스케일에 둔감한 순위 상관이 정확히 이 질문에 답한다. Pearson이 아니라 Spearman인 이유: r 분포에
꼬리가 있어 한두 조합이 상관을 좌우하는 것을 막기 위해.</p>

<h3>② Significance accuracy / precision / recall — 유의성 예측 정확도</h3>
<p class='lead'><b>정의</b>: LLM의 <code>will_be_significant</code>(각 Y가 유의할 거란 예/아니오)를
실제 <code>pass</code>(이중검정 통과)와 대조한 혼동행렬. accuracy = (TP+TN)/전체,
precision = TP/(TP+FP), recall = TP/(TP+FN).<br>
<b>왜 적합한가</b>: 순위와 별개로 <b>"이 Y가 실전에서 쓸 수 있는가(유의한가)"는 이진 판단</b>이다.
LLM이 유망하다고 지목한 Y가 실제로 통과하는지(precision), 실제 통과 Y를 놓치지 않는지(recall)를
분리해 본다. 특히 <b>precision이 낮으면 = LLM이 과대평가</b>(foot에서 surprise류를 유의하다 예측했으나
실패) → 이 실패 모드를 잡아내는 게 핵심.</p>

<h3>③ Top-k precision — 상위 회사픽 적중률</h3>
<p class='lead'><b>정의</b>: k = max(3, 회사수/4). LLM 상위 k개 회사와 실제 r_company 상위 k개의
교집합 크기 / k (<code>|LLM_topk ∩ actual_topk| / k</code>).<br>
<b>왜 적합한가</b>: 실전에서 alt-data를 쓸 때 <b>"어느 회사에 이 신호를 적용할까"는 상위 몇 개만
고르는 문제</b>다. 전체 순위가 다 맞을 필요 없이 <b>상위권이 실제 상위권과 겹치는지</b>가 실용적으로
중요하므로, 상위 k에 초점을 둔 precision이 랭킹 전체 상관보다 이 목적에 더 맞다. 무작위 기대값 =
k/n (예: 63종목 중 top-15면 24%) — 이보다 높아야 의미 있음.</p>

<h3>④ AUC — 강신호 분류 성능</h3>
<p class='lead'><b>정의</b>: 실제 r_company가 채널 중앙값 초과면 "강신호(1)"로 라벨. LLM 순위(−rank를
점수로)가 이 라벨을 얼마나 분리하는지의 ROC-AUC. 0.5 = 무작위, 1.0 = 완벽 분리.<br>
<b>왜 적합한가</b>: top-k precision은 임계값(k) 하나에만 의존하지만, <b>AUC는 모든 임계값에 걸쳐
LLM 순위가 강/약 회사를 분리하는 능력을 요약</b>한다. threshold-free라 "LLM 회사랭킹이 애초에
신호강도와 상관있나"를 편향 없이 판정. <b>AUC ≈ 0.5는 곧 "회사 수준에선 사실상 랜덤"</b>이라는
이 실험의 핵심 결론을 뒷받침한다.</p>

<div class='takeaway'><b>왜 metric-fit과 company-fit을 분리했나</b>: 전자는 "채널×메트릭"이라는
<b>구조적 지식</b>(경제 논리로 추론 가능)을, 후자는 "이 개별 회사가 이번에 셀지"라는
<b>사례별 지식</b>(데이터 없이는 어려움)을 측정한다. 두 축을 나눠야 LLM 사전지식의 <b>한계선이
정확히 어디인지</b>가 드러난다 — 그리고 실제로 그 경계에서 갈렸다.</div>
"""


def reasoning_section(d):
    html = ["<h2>4. LLM 근거 (발췌)</h2>"]
    for r in d["reasoning"]:
        html.append(f"<h3>{esc(r['channel'])}</h3>")
        html.append(f"<div class='quote'><b>metric:</b> {esc(r['metric_reasoning'])}</div>")
        html.append(f"<div class='quote'><b>company:</b> {esc(r['company_reasoning'])}</div>")
    return "\n".join(html)


def kpi_section(d):
    mf = {r["channel"]: r for r in d["vsummary"].get("metric_fit", [])}
    cf = {r["channel"]: r for r in d["vsummary"].get("company_fit", [])}
    # aggregate headline numbers
    m_acc = [mf[c]["sig_accuracy"] for c in mf]
    c_prec = [cf[c]["topk_precision"] for c in cf]
    m_rho = [mf[c]["rank_spearman"] for c in mf]
    c_rho = [cf[c]["rank_spearman"] for c in cf]

    def avg(x):
        return sum(x) / len(x) if x else float("nan")

    cards = [
        ("Metric-fit 정확도", f"{avg(m_acc)*100:.0f}%", "LLM이 어떤 Y가 유의할지 맞힌 비율 (채널평균)",
         PAL["good"] if avg(m_acc) >= 0.6 else PAL["warn"]),
        ("Metric 순위상관", f"{avg(m_rho):+.2f}", "LLM metric 랭킹 vs 실제 |r| 랭킹 (Spearman 평균)",
         PAL["good"] if avg(m_rho) >= 0.4 else PAL["warn"]),
        ("Company top-k precision", f"{avg(c_prec)*100:.0f}%", "LLM 상위 회사픽이 실제 상위와 겹친 비율",
         PAL["warn"] if avg(c_prec) >= 0.3 else PAL["critical"]),
        ("Company 순위상관", f"{avg(c_rho):+.2f}", "LLM 회사 랭킹 vs 실제 per-company r (평균)",
         PAL["critical"] if avg(c_rho) < 0.2 else PAL["warn"]),
    ]
    html = ["<section class='kpi-grid'>"]
    for label, val, sub, col in cards:
        html.append(f"<div class='kpi'><div class='kpi-v' style='color:{col}'>{val}</div>"
                    f"<div class='kpi-l'>{label}</div><div class='kpi-s'>{sub}</div></div>")
    html.append("</section>")
    html.append(
        "<div class='takeaway'><b>핵심:</b> LLM은 <b>어떤 Y metric이 각 alt-data에 맞는지</b>는 "
        "경제 논리로 잘 식별했지만(metric-fit 정확도 높음), <b>어떤 개별 회사에서 신호가 강할지</b>는 "
        "거의 못 맞혔다(company 순위상관 ≈ 0). 즉 <b>메트릭 적합성 ≫ 회사 적합성</b> — "
        "LLM의 사전지식은 '채널×메트릭' 수준의 구조는 알지만 '이 회사가 이번에 신호가 셀지'는 데이터가 필요하다.</div>")
    return "\n".join(html)


def build():
    d = load()
    body = "\n".join([
        "<header><div class='eyebrow'>Carbon Arc × FactSet · Stage-1 Identification</div>"
        "<h1>Alt-data가 예측하는 Y를 LLM이 미리 맞힐 수 있는가</h1>",
        "<p class='sub'>gpt-5.5가 <b>실험 결과를 모르는 상태로</b> (a) 채널별 유용한 Y metric과 "
        "(b) 신호가 강한 회사를 예측했다. 아래는 그 예측을 실제 실험결과와 대조한 것이다. "
        "X = card / foot / click (Carbon Arc), Y = 매출·서프라이즈·SSS·운영지표.</p></header>",
        kpi_section(d),
        methodology_section(),
        metric_fit_section(d), company_fit_section(d), gt_heatmap_section(d), reasoning_section(d),
        "<footer>재현: <code>li_00→li_04</code> 순차 실행. LLM 응답·FactSet metric 전부 캐시(cache/) — "
        "같은 입력 → 같은 출력. Carbon Arc 추가 다운로드 없음(기구매 framework 무료 재사용). "
        "검정 gate = clustered-bootstrap &amp; shuffle-surrogate 이중검정. no-lookahead: X 관측 &lt; 실적발표일.</footer>",
    ])
    css = """
    :root{--surface:#fbfbf9;--card:#fff;--ink:#111110;--ink2:#54534e;--line:#e6e5e0;
      --accent:#2a78d6;--accent-soft:rgba(42,120,214,.08)}
    @media(prefers-color-scheme:dark){:root{--surface:#181816;--card:#232320;--ink:#f5f4ef;
      --ink2:#b6b5ab;--line:#32322d;--accent:#5598e7;--accent-soft:rgba(85,152,231,.12)}}
    *{box-sizing:border-box}
    body{margin:0;background:var(--surface);color:var(--ink);
      font:15px/1.65 ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      -webkit-font-smoothing:antialiased}
    .wrap{max-width:940px;margin:0 auto;padding:40px 24px 72px}
    .num{font-variant-numeric:tabular-nums}
    header{border-bottom:2px solid var(--accent);padding-bottom:20px;margin-bottom:24px}
    .eyebrow{text-transform:uppercase;letter-spacing:.09em;font-size:11px;font-weight:700;
      color:var(--accent);margin-bottom:10px}
    h1{font-size:29px;line-height:1.2;margin:0 0 10px;letter-spacing:-.015em;text-wrap:balance;max-width:24ch}
    h2{font-size:20px;margin:44px 0 6px;letter-spacing:-.01em}
    h2::before{content:'';display:inline-block;width:3px;height:.85em;background:var(--accent);
      margin-right:9px;vertical-align:-1px;border-radius:2px}
    h3{font-size:15px;margin:22px 0 6px;font-weight:700}
    .sub{color:var(--ink2);font-weight:400;font-size:13.5px;max-width:68ch}
    .lead{color:var(--ink2);margin:2px 0 14px;max-width:68ch}
    .note{color:var(--ink2);font-size:12px;margin:4px 0 0}
    .kpi-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:8px 0 4px}
    @media(min-width:640px){.kpi-grid{grid-template-columns:repeat(4,1fr)}}
    .kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 14px}
    .kpi-v{font-size:28px;font-weight:750;letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1}
    .kpi-l{font-size:12.5px;font-weight:650;margin-top:7px}
    .kpi-s{font-size:11px;color:var(--ink2);margin-top:3px;line-height:1.4}
    .takeaway{background:var(--accent-soft);border:1px solid var(--line);border-radius:10px;
      padding:14px 16px;margin:16px 0 4px;font-size:14px;line-height:1.6}
    .twrap{overflow-x:auto;margin:8px 0}
    table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
    th,td{border-bottom:1px solid var(--line);padding:7px 11px;text-align:left;white-space:nowrap}
    thead th,tr:first-child th{background:var(--accent-soft);font-weight:650;
      border-bottom:1.5px solid var(--line)}
    tbody tr:hover,tr:hover{background:var(--accent-soft)}
    .badge{color:#fff;padding:1px 9px;border-radius:10px;font-size:11px;font-weight:650;letter-spacing:.02em}
    .quote{background:var(--card);border-left:3px solid var(--accent);padding:9px 13px;margin:7px 0;
      border-radius:0 7px 7px 0;font-size:12.5px;color:var(--ink2);line-height:1.55}
    code{background:var(--accent-soft);padding:1px 5px;border-radius:4px;font-size:.9em}
    footer{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);color:var(--ink2);
      font-size:11.5px;line-height:1.7}
    """
    html = (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>LLM Identification 검증 보고서</title><style>{css}</style></head>"
            f"<body><div class='wrap'>{body}</div></body></html>")
    (OUT / "report.html").write_text(html, encoding="utf-8")
    print(f"saved: {OUT/'report.html'}")


if __name__ == "__main__":
    build()
