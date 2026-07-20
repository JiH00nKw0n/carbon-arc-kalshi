# LLM Identification — Stage-1 재현가능 파이프라인

Notion 연구설계(wecoverai 2026-06-29)의 **1단계 Identification**을 재현가능한 코드로 구현.
LLM이 실험 결과를 모르는 상태로 (a) 채널별 유용한 Y metric, (b) 신호 강한 회사를 예측하게 하고,
실제 실험결과와 대조해 **식별 정확도**를 측정한다.

## 파이프라인 (li_00 → li_04 순차 실행)

```bash
cd scripts
python li_00_build_inputs.py     # 입력: 채널 entity list + FactSet 692 metric 카탈로그
python li_01_ground_truth.py     # 정답지: channel×Y (11) + channel×company (150) 실제 신호
python li_02_llm_identify.py     # Stage-1: gpt-5.5가 metric/company 랭킹 예측 (캐시됨)
python li_03_validate.py         # 검증: LLM 예측 vs 실제 (Spearman, accuracy, top-k, AUC)
python li_04_report.py           # HTML 보고서 → outputs/report.html
```

**재현성**: 모든 LLM 응답은 `cache/`에 (model, prompt, schema) 해시로 캐시 — 같은 입력이면 API 재호출
없이 같은 출력. FactSet metric 카탈로그도 캐시. Carbon Arc 추가 다운로드 없음(기구매 framework 재사용).

## 파일

| 파일 | 역할 |
|------|------|
| `li_config.py` | 채널 설명(card/foot/click), Y metric 후보 설명, 경로, gpt-5.5 |
| `li_llm.py` | OpenAI 클라이언트 + JSON schema 강제 + 디스크 캐싱 |
| `li_00_build_inputs.py` | 입력 카탈로그 (결정적) |
| `li_01_ground_truth.py` | 실제 실험결과 통합 (factor1_yswitch 패널 재사용) |
| `li_02_llm_identify.py` | Stage-1 LLM 예측 (metric + company) |
| `li_03_validate.py` | 예측 vs 실제 정량 비교 |
| `li_04_report.py` | self-contained HTML 보고서 (dataviz 팔레트) |

## 핵심 결과 (2026-07-03, gpt-5.5)

**Metric-fit (LLM이 어떤 Y가 각 채널에 맞는지):**
- card: rank Spearman **+1.0**, significance accuracy **100%** — 완벽 식별
- foot: Spearman +1.0이나 accuracy 50% — surprise에 붙을 거라 예측했으나 실제론 실패(과대평가)
- click: Spearman −0.5, accuracy 67%

**Company-fit (LLM이 어느 회사에서 신호 강할지):**
- card/foot/click 모두 rank Spearman ≈ **0** (0.01~0.13), top-k precision 20~38%, AUC ≈ 0.5

**결론**: LLM 사전지식은 **채널×메트릭 구조는 잘 알지만(metric-fit 우수) 개별 회사 신호강도는 거의
못 맞힘(company-fit ≈ random)**. 회사 수준 식별엔 결국 데이터가 필요. Notion의 "LLM이 alt-data 영향
큰 회사를 잘 고른다"는 기대는 **metric 수준에선 참, company 수준에선 과장**.

## 관련
- 정답지 패널: `../outputs/panel_{card,foot,click}.csv` (factor1_yswitch)
- Y-스위칭 상세: `../RESULTS.md`, `../TIMING.md`, `../outputs/foot_ytargets.md`, `nonrev_ytargets.md`
