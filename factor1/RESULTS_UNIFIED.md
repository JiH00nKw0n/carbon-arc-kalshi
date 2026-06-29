# Alt-data × Earnings-call × LLM → Revenue Surprise — Unified Results (web + card + foot)

*Channel-agnostic pipeline, identical setting for all three X channels. Spec: `EXPERIMENT_SPEC.md`.
gpt-5.5 (cutoff 2025-12-01); eval restricted to events **reported after** the cutoff (no memorization).
Seeds = 2026. Primary tables are **outlier-excluded** (see §1.1).*

---

## TL;DR

1. **On typical quarters (|surprise| ≤ 10%), the LLM's signal is real and competitive-to-winning** — it **beats** the best classical baseline on **web** (calibrated R² 0.47 vs 0.20), **ties** on **card** (0.10 vs 0.10), and on **foot** its `fin` arm beats the linear baseline (though a tree still leads). On the **full** distribution it only ties (web/card) or loses (foot) — because **the LLM misses the tails** (large beats/misses). So its weakness is tail events, not typical quarters.
2. **X×Z fusion adds genuine information only on web.** web `fin+x+text` is the best arm (corr 0.71); on card/foot the LLM's best arm is `fin` alone — adding the alt-data or text individually *hurts*, and only "recovers" when combined (mutual-recovery synergy, not a real gain).
3. **Signal structure differs by channel.** web & card are **linear** (a tree (GBT) does not beat linear OLS); **foot is nonlinear** — a GBT is the single best model. Foot's nonlinearity is a **threshold/tail shape** (only extreme visit moves carry signal) with **downside asymmetry**, and its predictive power is mostly **autoregression (lag) + foot-on-top**, *not* a foot×text synergy.
4. **Foot is the most screening-sensitive channel:** signal exists only for **foot-dominant (strong-O)** names; moderate-O foot carries **zero** signal (all-O dilutes to null).
5. **The honest cross-channel verdict:** no channel shows the LLM *cleanly dominating* the best calibrated classical model on the full distribution. The LLM's value is **information on typical quarters + zero-shot/no-fit generality**; its gaps are **tail events** and **nonlinear signals** (where trees win).

---

## 0. Setup

- **Y (target)** = revenue surprise `= (actual − consensus)/consensus`, %. Consensus = FactSet point-in-time mean at quarter-end (no post-print revision leak).
- **X (alt-data)** YoY: **web** = website-visitor YoY (CA0030, all-O 33 firms) · **card** = consumer card-spend YoY (CA0056, all-O 99) · **foot** = physical-visit YoY (CA0060, **strong-O 34** — foot-dominant only).
- **Z** = prior-quarter earnings-call transcript. **Leakage frame**: classical models fit pre-cutoff, predict the same post-cutoff set the LLM sees.
- **Classical baselines**: `N0` company-mean · `N1` X-OLS · `N2` sentiment-OLS (Loughran-McDonald 2011) · `N3` X+sent · `N4` +X×sent interaction · `N3b` X+sent+lag · `N4b` +interaction · `N5` **GBT** (gradient-boosted trees on X,sent,lag — captures nonlinearity).

### 1.1 How to read the metrics + outlier policy

- **corr / corr²** = direction/ranking (scale-invariant); corr² = the R² reachable after an optimal linear rescale (calibration ceiling). **RMSE / R²_OOS** = actual squared-error accuracy (punishes miscalibration). The LLM is zero-shot/uncalibrated, so its raw R² sits below its corr² ceiling — we also report a **leak-free 5-fold-by-company calibration** (§5).
- **Outlier policy (primary tables exclude test events with |surprise| > 10%).** Headlines were fragile to single extreme events at small n; we therefore unify on the **typical-quarter** view. This drops **1 point each**: web **FIGS +22.4%**, card **PLNT +12.7%**, foot one point.
  - ⚠️ **Two honest caveats.** (a) Trimming on the realized |y| is **outcome-conditional** — it selects "easy" quarters and inflates apparent skill; treat it as a robustness lens, not an unbiased OOS metric. (b) **FIGS is a *real* beat** (verified: FactSet=FMP $202M actual; stock +25%; 3 analyst upgrades), **not** a data artifact — so removing it specifically deletes a genuine tail-case the LLM (and all analysts) missed. The structural-break artifact **DLTR −39.3%** (Family Dollar spinoff) sits in *pre-cutoff training* and is excluded by a pre-declared rule.

---

## 2. WEB — outlier-excluded (n=59, 29 firms)

H1 (web alone, full panel): **web_yoy → surprise r=+0.200, p_boot=0.001 ✅**.
```
model                  RMSE   R²_OOS   corr   corr²   MAE
N0 naive               2.44  +0.297  +0.583  0.339  1.71
N1 X-OLS               2.97  -0.039  +0.137  0.019  2.12
N3b X+sent+lag         2.60  +0.203  +0.482  0.233  1.83   <- best classical
N5 GBT (x,sent,lag)    3.15  -0.172  +0.313  0.098  2.08   <- tree WORSE than linear → web is LINEAR
LLM fin                2.31  +0.372  +0.611  0.374  1.68   <- best LLM (raw R² already > N3b)
LLM fin+text           2.50  +0.261  +0.583  0.340  1.80
LLM fin+x+text         2.59  +0.207  +0.714  0.510  1.94   <- best corr / ceiling
```
calibration (R²_OOS): LLM `fin+x+text` raw +0.207 → **calib +0.470** vs **N3b +0.203** → **the LLM clearly wins** (and `fin` alone +0.37 already beats N3b). synergy: corr +0.267 (p=0.006 ✅), MSE-skill +0.568 (p=0.001 ✅); surrogate p<0.001 ✅. architecture B(end-to-end) +0.714 ≫ A +0.238.

→ **On typical quarters the LLM beats classical on web, via the X×Z fusion** (best arm). *Untrimmed (incl. FIGS) this is only a tie — the LLM's single failure is the +22% tail it missed.*

## 3. CARD — outlier-excluded (n=209, 95 firms)

H1: **card_yoy → surprise r=+0.136 ✅**.
```
model                  RMSE   R²_OOS   corr   corr²   MAE
N0 naive               2.61  -0.173  +0.245  0.060  1.86
N3b X+sent+lag         2.29  +0.097  +0.364  0.132  1.72   <- best classical
N5 GBT (x,sent,lag)    2.30  +0.085  +0.316  0.100  1.71   <- ≈ N3b → card is LINEAR
LLM fin                2.32  +0.073  +0.376  0.141  1.61   <- best LLM arm (financials only)
LLM fin+x              2.50  -0.079  +0.321  0.103  1.71
LLM fin+text           2.42  -0.012  +0.261  0.068  1.75
LLM fin+x+text         2.39  +0.010  +0.283  0.080  1.69
```
calibration: LLM `fin` calib **+0.103 ≈ N3b +0.097** → **TIE** (robust; n=210). card-X and text both *hurt* the LLM — its value is `fin`. synergy: corr +0.074 (p=0.160 ✗), MSE-skill +0.181 (p=0.013 ✅, mutual-recovery); surrogate p<0.001 ✅. architecture B +0.283 > A +0.150.

→ **card is a simple LINEAR low-signal problem — the LLM matches the linear baseline (tie), neither X nor Z adds.** Unchanged by trimming (robust).

## 4. FOOT — outlier-excluded (n=76, 34 firms; strong-O)

H1 (strong-O): **foot_yoy → surprise r=+0.202, p_boot=0.006, p_surr=0.009 ✅** (web-level). DLTR 2025-01-31 break excluded.

**Tier-sensitivity (why strong-O only).** all-O dilutes to null because moderate-O foot has zero signal:
| foot universe | r | p_boot |
|---|--:|--:|
| strong-O (34) | **+0.243** | 0.000 ✅ |
| moderate-O (19) | −0.001 | 0.969 ✗ |
| all-O (54) | +0.113 | 0.069 ❌ |
Foot predicts surprise *only* where visits ≈ the whole revenue channel.

```
model                  RMSE   R²_OOS   corr   corr²   MAE
N0 naive               2.60  -0.272  +0.388  0.150  1.86
N1 X-OLS               2.52  -0.196  -0.097  0.009  1.83   <- linear foot useless
N3b X+sent+lag         2.42  -0.100  +0.212  0.045  1.74
N5 GBT (x,sent,lag)    2.05  +0.205  +0.490  0.241  1.51   <- best of ALL models (nonlinear)
LLM fin                2.16  +0.120  +0.469  0.220  1.48   <- best LLM; beats N3b
LLM fin+x              2.84  -0.516  +0.153  0.023  1.98   <- foot CRASHES the LLM
LLM fin+text           2.43  -0.112  +0.288  0.083  1.68
LLM fin+x+text         2.72  -0.397  +0.171  0.029  1.85
```
calibration: **GBT +0.205 (self-cal)** > LLM `fin` calib **+0.151** > N3b **−0.100**. synergy: corr +0.188 (p=0.064 ✗ at n=76), **MSE-skill +0.362 (p=0.019 ✅)**; surrogate p_surr=0.079 (✗ at n=76). architecture A +0.191 ≈ B +0.171.

→ **foot's predictive signal is NONLINEAR — a GBT is the single best model**, beating the LLM and (collapsing) linear OLS. The LLM `fin` does beat the linear N3b here, but a tree beats the LLM. *(At n=76 the corr-synergy and surrogate lose significance — read foot as directional.)*

---

## 5. The calibration verdict (LLM vs best classical, outlier-excluded)

| channel | best classical (calib R²) | best LLM (calib R²) | verdict |
|---|--:|--:|---|
| **web** | N3b +0.203 | **fin+x+text +0.470** | **LLM wins** (via X×Z fusion) |
| **card** | N3b +0.097 | fin +0.103 | tie |
| **foot** | **GBT +0.205** | fin +0.151 | **classical (GBT) wins** |

The LLM has real, calibratable information everywhere (its corr² ceilings exceed its raw R²), but it only *wins* where the signal is **linear AND the X×Z fusion adds info** (web). On a linear signal with no fusion it ties (card); on a nonlinear signal a tree beats it (foot).

## 6. Synergy (company-clustered bootstrap, 5000, seed 2026)

| | corr-synergy | p | MSE-skill synergy | p |
|---|--:|--:|--:|--:|
| web | +0.267 | 0.006 ✅ | +0.568 | 0.001 ✅ |
| card | +0.074 | 0.160 ✗ | +0.181 | 0.013 ✅ |
| foot | +0.188 | 0.064 ✗ | +0.362 | 0.019 ✅ |

- **MSE-skill synergy is positive everywhere**, but read it correctly: **web = genuine gain** (fin+x+text is the best arm); **card & foot = mutual-recovery** (X-alone and Z-alone each *hurt* the LLM, combining only recovers — the best arm is `fin` alone, fusion does not beat it).
- corr-synergy is significant only on web.

## 7. Architecture + Z-depth

- **End-to-end ≫ distilled** on web/card (B ≫ A,C): you cannot replace the LLM by "extract scores → regress." On foot A ≈ B (both weak). Classical interactions on a sentiment scalar (N4/N4b) and GBT do **not** reproduce the LLM's fusion either — *any* scalar compression of Z loses signal. (But the preserved signal only ties/loses on accuracy.)
- **Z-depth (1 vs 2 prior calls):** no consistent effect (web 1-call slightly better, card 2-call, foot ≈). Inconclusive.

---

## 8. FOOT deep-dive — what the nonlinear signal actually is

**GBT feature ablation (strong-O, n=75):**
```
features                 GBT_R²  GBT_corr   (OLS_R²)
lag_surprise              +0.093  +0.409     +0.033   <- the workhorse (autoregression)
x_yoy (foot alone)        -4.5    +0.058     -0.060   <- OOS-useless alone (overfits)
sent (alone)              -0.56   -0.038     -0.023   <- useless
x_yoy + lag               +0.241  +0.497     -0.002   <- foot adds +0.09 corr ON TOP of lag
sent + lag                +0.089  +0.407     -0.058   <- sentiment adds ~0
x_yoy + sent + lag (full) +0.240  +0.497     -0.002   <- sentiment contributes nothing
```
→ **GBT's edge is `lag (autoregression) + foot`, NOT a foot×Z synergy.** Sentiment/Z adds nothing; foot alone is OOS-useless; the predictive content is the track-record autoregression plus foot's contribution on top.

**Shape of foot's nonlinearity (in-panel, n=265) — threshold/tail + downside asymmetry:**
| foot_yoy quintile | median | mean surprise |
|---|--:|--:|
| Q1 (visits ↓) | −3.6% | **−0.13%** |
| Q2–Q4 (normal) | +0.4…+5.5% | **~+0.78% (flat plateau)** |
| Q5 (visits surge) | +12.4% | **+1.47%** |
- Foot is informative **only in the extremes**: the middle 60% is a flat plateau (ordinary visit swings = noise, already in consensus). Only a **collapse or a surge** breaks the consensus-priced range.
- **Downside asymmetry**: foot<0 corr +0.245 > foot>0 corr +0.181 — falling visits predict a miss more reliably than rising visits predict a beat.
- A linear `foot×lag` product adds 0 (the interaction is foot's own threshold curvature, not a clean product); `foot²` adds a little.
- **This is why trees win and linear/LLM lose:** a GBT learns the threshold split ("only big moves matter"); linear OLS averages it to ~0; the LLM doesn't apply the "extremes-only" rule.

**Why text adds nothing on foot (and card) but does on web.** Text helped *only* on web, fused with web-traffic. For online names, X (web visits) and the call point at the **same online-demand signal**, so the call contextualizes X → genuine fusion. For physical retail/restaurants (card/foot), surprise is driven by **AOV/price/comp/mix** that the call describes only qualitatively (not as magnitude), and physical seasonality is largely already in consensus → text carries little incremental surprise-signal. *(Caveat: "text adds nothing" = as captured by sentiment-scalar / this LLM at this n — not proof Z has no info; calls do contain comp/guidance numbers the LLM may under-extract.)*

---

## 9. Cross-channel synthesis — two independent axes

| | signal type (GBT vs linear) | X×Z fusion adds info? | LLM outcome (typical-quarter) |
|---|---|---|---|
| **web** | linear | **yes** (aligned online demand) | **LLM wins** (fusion best arm) |
| **card** | linear | no | tie (fin best arm) |
| **foot** | **nonlinear** (threshold/tail) | no | **GBT wins** (LLM misses nonlinearity) |

1. **Linear vs nonlinear** decides whether a tree can beat the LLM: web/card are linear (GBT ≤ linear, LLM can match), foot is nonlinear (GBT >> linear & LLM).
2. **X×Z alignment** decides whether text helps: only web's X and Z point at the same demand → fusion works.
3. **Tails**: the LLM is good on typical quarters but **whiffs on tail surprises** — which is exactly what the outlier-trim removes, and why the untrimmed verdict (tie/loss) is harsher than the trimmed one (win/tie/competitive). The tails are where the real beats/misses live, so this is a genuine LLM limitation, not just noise.

## 10. Robust vs fragile

- **Robust (hold across channels & trimming):** every channel's alt-data has a real H1 signal (r≈0.14–0.20); MSE-skill synergy is positive everywhere; end-to-end ≫ distilled; the LLM never *cleanly* beats the best calibrated classical on the **full** distribution.
- **Fragile / changed by trimming:** **web flips tie→LLM-win** when its one real tail point (FIGS) is removed (n=60 too small). **foot's** surrogate & corr-synergy lose significance at n=76. card is stable.
- **Channel-specific:** best LLM arm (web fusion / card,foot fin); foot nonlinear & tier-sensitive; Z-depth direction.

## 11. Caveats / next

- **Outlier-trim is outcome-conditional** (selects easy quarters) and web's removed point is a *real* tail-miss — so "LLM wins on web" means "on typical quarters." Report both views; weight card (robust) for the headline.
- **Small n** (web 59, foot 76) → tail/CI fragility; card (209) firm.
- **LLM generation variance not yet quantified** (bootstrap captures company-sampling only) → re-run-stability deferred (spec §10).
- **Why the LLM under-performs (next $0–$ diagnostics):** (a) give the LLM an explicit prior-quarter-surprise/lag feature — the GBT workhorse it may under-use; (b) feed the LLM only the GBT numeric features (foot#, sent#, lag#) and compare — can it do the nonlinear/threshold combination?; (c) LLM-distilled scores → GBT (nonlinear combiner) instead of OLS; (d) per-subsector error decomposition; (e) tail-focused error analysis. (a)/(b) are the priority.

---

*Pipeline: `f1_channels.py` (web/card/foot) · `f1_20_panel.py` · `f1_21_run.py` (LLM ablation+architecture+Z-depth) · `f1_22_eval.py` (MSE eval + leak-free calibration + synergy + surrogate; `F1_DROP_OUTLIER_PCT` for the trimmed view). Raw dumps `factor1/outputs/results_{web,card,foot}.md` (gitignored). Seeds=2026. LLM cost: web $26.24 + card $114.04 + foot $43.98 = $184.26. Foot data CA0060: strong-O $664.40 + moderate-O $390.78.*
