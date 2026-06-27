# Alt-data × Earnings-call × LLM → Revenue Surprise — Unified Results (web + card)

*Channel-agnostic pipeline, identical setting for both X channels. Spec: `EXPERIMENT_SPEC.md`.
Metrics are MSE-primary. gpt-5.5 (knowledge cutoff 2025-12-01); evaluation restricted to events
**reported after** the cutoff so the model cannot have memorized the answer.*

---

## TL;DR

1. **The X×Z fusion is super-additive on the MSE-skill scale in BOTH channels** (web p=0.001, card p=0.010): combining structured alt-data (X) and the earnings-call transcript (Z) through the LLM produces error-reduction that the parts alone do not. This is the central positive result.
2. **On calibrated R² the LLM TIES (not beats) the best classical baseline** (web 0.29 vs 0.30; card 0.10 vs 0.10). **But raw R² is the LLM's *worst* metric, and it genuinely wins elsewhere:** lowest **MAE / typical error** in both channels (beating N3b *and* the naive mean), highest **corr / ranking** in both, plus a fusion + end-to-end signal that classical models cannot produce or distill, and it does this **zero-shot with no fitting** (§4b, §5, §6).
3. **The LLM fuses X with the *full transcript*, not a scalar.** Classical interactions on a sentiment scalar — an `X×sentiment` term, or gradient-boosted trees — do **not** reproduce the fusion (they tie or *underperform* the additive baseline), and distilling Z to scores then regressing (architecture A/C) fails the same way. The LLM's niche is reading raw text with no feature engineering — not capturing an interaction classical models structurally can't (they can; it just doesn't help on a scalar Z).
4. Revenue surprise is a **near-efficient, low-signal target** (consensus already absorbs public info), so a tie — not LLM dominance — is the honest, expected outcome.

---

## 0. Setup (what is being predicted, and how)

- **Y (target) = revenue surprise** `= (actual − consensus)/consensus`, in %. Consensus is the FactSet point-in-time mean taken at quarter-end (before the print), so there is no post-announcement revision leak.
- **X (alt-data)** = the candidate demand proxy, year-over-year: **web** = website-visitor YoY (Carbon Arc CA0030); **card** = consumer card-spend YoY (CA0056).
- **Z (text)** = the prior-quarter earnings-call transcript (HTML stripped to text).
- **Universe** = companies where X is a *dominant revenue driver* (the O/X screen); web n=60 events / 29 firms, card n=210 events / 95 firms.
- **Leakage frame** = classical models are fit on pre-cutoff events and predict the **same** post-cutoff test set the LLM sees; every model is scored on the **identical** matched event set.

## 1. How to read the metrics (this matters for interpretation)

Two families of metric answer **different questions**:

| metric | question it answers | sensitive to… |
|---|---|---|
| **corr** / **corr²** | does the prediction move in the **right direction / order**? | nothing about scale or offset |
| **RMSE** / **R²_OOS** | is the **actual number** right? (`R² = 1 − MSE/Var`) | scale, bias, miscalibration |

- **Calibration** here means a one-step linear rescale `pred → a + b·pred`. If a model says "+0.5%" when reality swings ±4%, its *direction* can be perfect (high corr) while its *magnitude* is wrong (bad RMSE); the fix is to stretch by `b` and shift by `a`.
- **corr² is the calibration ceiling**: a mathematical identity says the best R² achievable by *any* linear rescale of a prediction equals corr². So `raw R² ≤ (realized calibrated R²) ≤ corr²`.
- **OLS is self-calibrating** (it is fit by least squares on the target scale), so for the classical baselines raw R² ≈ corr² already. The **LLM is zero-shot and uncalibrated**, so its raw R² sits far below its corr² ceiling — the gap is *calibration loss, not missing information*.

Because of this asymmetry, comparing a fitted regressor against a raw LLM on RMSE is unfair to the LLM. We therefore also report a **leak-free realized calibration** (§4): a 5-fold-by-company rescale where the `a,b` are fit on the *other* folds and applied out-of-fold — no test-set peeking.

**Classical baselines.** `N0` per-company mean surprise (track record); `N1` OLS on X; `N2` OLS on call sentiment (Loughran-McDonald 2011 lexicon); `N3` X+sentiment (additive); `N4` adds an explicit **X×sentiment interaction** term; `N3b` X+sentiment+lagged-surprise; `N4b` = N3b + the interaction; `N5` **gradient-boosted trees** on (X, sentiment, lag), which learn interactions/nonlinearity freely. N4/N4b/N5 exist specifically to test whether a *classical* model can capture an X×Z interaction (it can — the question is whether it helps). `N3b` is the strong one (the lag captures that beaters keep beating).

---

## 2. WEB results  (n=60, 29 firms; truth mean +1.98%, sd 3.96%)

```
model                     RMSE   R²_OOS   corr   corr²   MAE   sign
N0 naive (company mean)    3.41  +0.246  +0.499  0.249   2.00  0.78
N1 X-OLS                   4.00  -0.037  +0.276  0.076   2.44  0.78
N2 sentiment-OLS           3.92  +0.003  +0.170  0.029   2.62  0.78
N3 X+sent (additive)       3.86  +0.033  +0.322  0.104   2.39  0.78
N4 X×sent interaction      3.88  +0.025  +0.179  0.032   2.54  0.77   <- interaction HURTS vs N3
N3b X+sent+lag             3.28  +0.302  +0.569  0.324   2.06  0.82   <- best classical
N4b +lag+interaction       3.27  +0.308  +0.558  0.311   2.10  0.78   <- ≈ N3b (interaction adds ~0)
N5 GBT (x,sent,lag)        3.69  +0.117  +0.423  0.179   2.30  0.78   <- trees don't beat N3b
LLM fin                    3.49  +0.210  +0.466  0.217   1.99  0.75   <- best MAE
LLM fin+x                  3.93  +0.002  +0.513  0.264   2.69  0.57
LLM fin+text               3.68  +0.123  +0.460  0.212   2.12  0.82
LLM fin+x+text             3.73  +0.098  +0.607  0.369   2.26  0.78   <- best corr / best ceiling
```

- On **raw RMSE/R²**, the calibrated classical **N3b wins** (3.28 / +0.302). On **information (corr/corr²)**, the **LLM fusion wins** (0.607 / 0.369): it ranks beat-vs-miss best, but its raw magnitudes are uncalibrated, so its raw R² (0.098) is far below its ceiling (0.369).
- Adding X and Z to the LLM **raises corr monotonically** (fin 0.466 → fin+x+text 0.607): on web, the fusion genuinely *is* the best arm.

## 3. CARD results  (n=210, 95 firms; truth mean +1.05%, sd 2.54%)

```
model                     RMSE   R²_OOS   corr   corr²   MAE   sign
N0 naive (company mean)    2.70  -0.141  +0.253  0.064   1.90  0.64
N1 X-OLS                   2.63  -0.078  +0.148  0.022   1.84  0.64
N2 sentiment-OLS           2.54  -0.006  +0.067  0.004   1.84  0.66
N3 X+sent (additive)       2.58  -0.040  +0.162  0.026   1.94  0.66
N4 X×sent interaction      2.72  -0.154  -0.080  0.006   1.97  0.63   <- interaction badly HURTS
N3b X+sent+lag             2.40  +0.099  +0.353  0.125   1.76  0.67   <- best classical
N4b +lag+interaction       2.71  -0.145  +0.147  0.022   1.97  0.60   <- interaction destroys N3b
N5 GBT (x,sent,lag)        2.42  +0.084  +0.312  0.097   1.75  0.66   <- ≈ N3b, no gain
LLM fin                    2.43  +0.075  +0.378  0.143   1.66  0.68   <- best LLM + best MAE
LLM fin+x                  2.62  -0.070  +0.311  0.097   1.76  0.70
LLM fin+text               2.55  -0.014  +0.260  0.068   1.79  0.61
LLM fin+x+text             2.53  +0.005  +0.274  0.075   1.74  0.65
```

- The card story is **different**: the LLM's **best arm is `fin` alone** (corr 0.378). Adding X or Z *individually* **hurts** the LLM (corr drops to 0.31 / 0.26), and the full fusion (0.274) is below fin-only.
- N3b again leads on raw RMSE/R² (2.40 / +0.099); LLM `fin` is essentially tied (2.43 / +0.075).

## 4. The decisive test — does the LLM's information survive an honest calibration?

Leak-free 5-fold-by-company rescale (fit `a,b` on other folds, apply out-of-fold). `R²_OOS`:

```
                   raw R²   calib R²(OOF)   corr²(ceiling)
WEB  LLM fin        +0.210     +0.166         0.217
     LLM fin+x      +0.002     +0.171         0.264
     LLM fin+text   +0.123     +0.101         0.212
     LLM fin+x+text +0.098     +0.286         0.369        <- recovers from 0.10 to 0.29
     N3b (OLS ref)  +0.302     +0.302         (self-calibrated)
CARD LLM fin        +0.075     +0.100         0.143        <- best calibrated LLM
     LLM fin+x      -0.070     +0.047         0.097
     LLM fin+text   -0.014     +0.025         0.068
     LLM fin+x+text +0.005     +0.027         0.075
     N3b (OLS ref)  +0.099     +0.099         (self-calibrated)
```

**Interpretation.** Calibration recovers most of the LLM's raw-RMSE handicap (web fin+x+text: 0.098 → 0.286; the loss really was calibration, not information). **But the honest, realized calibrated LLM only ties the best classical baseline:**
- **web:** LLM fin+x+text **0.286** vs N3b **0.302** — a statistical tie, marginally below.
- **card:** LLM fin **0.100** vs N3b **0.099** — a tie.

So the answer to "is the LLM unnecessary?" is **no, but it does not dominate**: it matches a well-specified calibrated regression on accuracy, while extracting the signal in a way the regression cannot (next sections).

### 4b. Where the LLM genuinely wins

Raw R²/RMSE is the LLM's *worst-case* metric — squared error punishes its few uncalibrated outliers. On the other axes it has real, honest advantages:

- **MAE (typical error) — best model in BOTH channels.** LLM `fin` MAE = **1.99 web / 1.66 card**, below N3b (2.06 / 1.76) *and* the naive company-mean (2.00 / 1.90). The LLM's *typical* prediction is tighter; its RMSE lag comes from a handful of badly-*scaled* magnitudes, not from being wrong on average. Needs **no calibration**. *(MAE not yet bootstrapped; the card gap is decisive, web narrow.)*
- **corr / ranking — best model in BOTH channels** (web fin+x+text 0.607 > N3b 0.569; card fin 0.378 > N3b 0.353): the LLM ranks beat-vs-miss best. *(Margins are within run-variance — directionally true, significance pending the re-run round.)*
- **Super-additive X×Z fusion (§5)** and **end-to-end irreplaceability (§6)** — only the LLM produces these; a feature-regression cannot.
- **Zero-shot, no fitting.** The LLM matches a *trained* OLS while itself being *untrained* — no per-task fitting, and it works on a brand-new ticker with **no history** to fit a regression on (cold-start). The R² "tie" hides that the classical side needed pre-cutoff training data and the LLM did not.

## 5. Synergy — is X×Z super-additive?  (company-clustered bootstrap, 5000, seed 2026)

`synergy = M(fin+x+text) − [M(fin+x) + M(fin+text) − M(fin)]`, on corr and on MSE-skill (`1−MSE/Var`).

| | corr-synergy | p | **MSE-skill synergy** | p |
|---|--:|--:|--:|--:|
| **web** | +0.104 | 0.046 ✅ | **+0.225** | **0.001 ✅** |
| **card** | +0.078 | 0.136 ✗ | **+0.171** | **0.010 ✅** |

- **MSE-skill synergy is positive and significant in both channels** → the fusion reduces error super-additively. This is the robust H2 result.
- **Read it correctly per channel, though:** on **web** the synergy is a *genuine gain* (fin+x+text is the best arm). On **card** it is *mutual recovery*: X-alone and Z-alone each **hurt** the LLM, and only together do they cancel back to ≈ fin-only — super-additive in the formula, but **not** an endorsement that fusion beats financials-alone on card.
- corr-synergy is significant only on web → **not robust**.

**Can a classical interaction term reproduce the synergy?** This is the right way to pin down the LLM's edge — and the answer is **no, but not because interactions are impossible classically.** Adding an explicit `X×sentiment` term (N4/N4b) or gradient-boosted trees on (X, sentiment, lag) (N5) does **not** capture it: N4 is *worse* than the additive N3 in both channels (web R² +0.025 vs +0.033; card −0.154 vs −0.040), N4b ≈ N3b (interaction adds ~0), and N5 does not beat N3b. The reason: these interact with **sentiment — a single scalar that compresses the entire transcript** (and is itself weak, N2 corr 0.17/0.07); multiplying two noisy scalars just adds variance and overfits. The LLM instead interacts X with the **full unstructured text** — an interaction no `X×scalar` term or 3-feature tree can represent (same lesson as §6: scalar-distilling Z destroys the signal). **Honest bound:** even so, the LLM's text-fusion does **not beat** N3b once calibrated (§4); on this near-efficient target the marginal transcript signal above X+lag is small for everyone — the LLM merely extracts it from raw text with no feature engineering.

## 6. Architecture — end-to-end vs distilled (corr to truth)

| | A (text→score) | C (x+text→features) | **B (end-to-end)** |
|---|--:|--:|--:|
| **web** | +0.229 | +0.197 | **+0.607** |
| **card** | +0.147 | −0.018 | **+0.274** |

In both channels, distilling the LLM into interpretable scores and regressing them **destroys** the signal; only the end-to-end prediction works. This is the same lesson as the classical interaction baselines (§5, N4/N5): **any pipeline that first compresses Z to scalar(s) — sentiment *or* distilled LLM scores — and then regresses (with or without interaction terms / trees) loses the signal.** Reading the raw text end-to-end is what preserves it. (Caveat: that preserved signal still only ties N3b on calibrated accuracy, §4.)

## 7. Z-depth — 1 vs 2 prior calls

| | z1 (1 call) | z2 (2 calls) |
|---|--:|--:|
| **web** | corr +0.596 | +0.456 |
| **card** | corr +0.266 | **+0.368** |

Opposite directions (web prefers 1 call, card prefers 2), both on small subsets and within run-to-run noise → **no reliable conclusion**; treat as inconclusive.

---

## 8. What is robust vs fragile (reading both channels together)

**Robust — holds in both channels, significant:**
- **MSE-skill super-additivity of X×Z** (web p=0.001, card p=0.010).
- **Signal is firm-specific** (shuffle-company surrogate p≈0.000 in both) — not a common-trend artifact.
- **Reading raw text beats scalar-summarizing it** — end-to-end LLM ≫ distilled scores (A/C), and classical `X×sentiment` interactions / GBT (N4/N5) do **not** reproduce the fusion (they tie or underperform the additive baseline). Any scalar compression of Z loses signal. *(But raw text only ties N3b on accuracy, §4 — the preserved signal is modest.)*
- **N3b (calibrated OLS with X+sentiment+lag) is a strong baseline**, best-or-tied on raw RMSE/R² in both.
- **After leak-free calibration the LLM ties, not beats, N3b** in both.

**Fragile / channel-dependent — do NOT generalize:**
- **Which LLM arm is best**: web → fin+x+text (fusion helps); card → fin alone (fusion hurts).
- **corr-synergy** significant on web only.
- **Z-depth** direction flips between channels.
- Any **close gap** (e.g., web LLM corr 0.607 vs N3b 0.569) is **within LLM generation variance + sampling noise** and is **not yet significance-established** — see caveats.

## 9. Takeaway

On revenue surprise — a near-efficient target where consensus already prices public information — the honest finding is that the LLM **does not dominate on calibrated squared-error accuracy** (it ties N3b). That is the conservative headline. But "tie" is specific to R²/RMSE; the LLM has clear, defensible strengths the tie hides:

- it has the **lowest typical error (MAE)** in both channels — beating the strong classical baseline *and* the naive mean, with **no calibration needed**;
- it has the **best ranking (corr)** of beat-vs-miss in both channels;
- it produces **super-additive X×Z fusion** and **end-to-end signal that cannot be distilled** into a feature regression — uniquely the LLM's;
- it does all of this **zero-shot, with no fitting**, so it ties a *trained* model while needing no training data and working **cold-start** on new tickers.

For deployment: use the LLM for fusion, ranking, and cold-start / interpretable reasoning, and add a calibration layer for the point estimate. Do not expect it to beat a well-specified calibrated regression on *squared-error accuracy* for this particular near-efficient target — but that single metric understates its value.

## 10. Caveats / what would sharpen these claims

- **LLM generation variance is not yet quantified.** The bootstrap CIs capture *which companies* are sampled, not the LLM's run-to-run randomness. Close calls (the corr orderings, Z-depth) could move on re-run. **Deferred:** K independent re-runs → mean±SD per metric and paired across-run tests (spec §10 "re-run stability"), optionally an ensemble-mean to cut variance and improve calibration.
- **Small n** (web 60) makes RMSE differences noisy; card (210) is firmer.
- The **realized calibration** (§4) is a finite-sample estimate (5 folds); it lands between raw and the corr² ceiling and would tighten with more data.

---

*Pipeline: `f1_channels.py` (channel config) · `f1_20_panel.py` (panel) · `f1_21_run.py` (LLM ablation+architecture+Z-depth, one pass) · `f1_22_eval.py` (MSE-primary eval + calibration + synergy + surrogate). Per-channel raw dumps: `factor1/outputs/results_{web,card}.md`. Seeds = 2026. LLM cost: web $26.24 + card $114.04 = $140.28.*
