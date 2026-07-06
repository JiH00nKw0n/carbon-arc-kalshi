# 사전지식 실험 — 전체 레벨 종합 (company-fit)

원본: `factor1_priorknowledge/outputs/summary_all.md`

L0=정보없음, L1=연구자가 정보 선택(oracle 상한선), L2=LLM 자율, L2b=선택강제, L2c=풀좁히기.

## card

| level | AUC | top-k |
|---|---|---|
| L0 baseline | +0.594 | +0.267 |
| L1 oracle-WebSearch | +0.572 | +0.133 |
| L1 oracle-FactSet | +0.609 | +0.467 |
| L2 agent-free | +0.584 | +0.133 |
| L2b agent-forced | +0.629 | +0.067 |
| L2c screen-topN | — | +0.533 |

## foot

| level | AUC | top-k |
|---|---|---|
| L0 baseline | +0.514 | +0.385 |
| L1 oracle-WebSearch | +0.557 | +0.462 |
| L1 oracle-FactSet | +0.477 | +0.308 |
| L2 agent-free | +0.513 | +0.385 |
| L2b agent-forced | +0.527 | +0.462 |
| L2c screen-topN | — | +0.600 |

