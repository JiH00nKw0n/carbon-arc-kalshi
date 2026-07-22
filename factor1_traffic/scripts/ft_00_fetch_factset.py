"""
Foot Traffic — FactSet Point-in-Time Revenue Surprise 수집.

10개 티커(CMG, COST, DG, DLTR, DRI, EAT, MCD, ROST, SBUX, ULTA)에 대해
FactSet Estimates v2 /surprise API (OAuth)로 PIT consensus+actual 수집.

OUT: traffic/data/factset_foot10_pit.json   {"rows": [...]}
     traffic/data/revenue_surprise_foot10.csv

Usage:
    python ft_00_fetch_factset.py
"""
import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[4] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ft_config import DATA, OUT

TICKERS = ["CMG", "COST", "DG", "DLTR", "DRI", "EAT", "MCD", "ROST", "SBUX", "ULTA"]
FACTSET_TICKERS = [f"{t}-US" for t in TICKERS]

CLIENT_ID  = os.getenv("FACTSET_OAUTH_CLIENT_ID")
KEY_ID     = os.getenv("FACTSET_OAUTH_KEY_ID")
JWK_RAW    = os.getenv("FACTSET_OAUTH_PRIVATE_KEY")
START_DATE = "2022-01-01"
END_DATE   = "2026-06-27"


def get_token() -> str:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateNumbers, RSAPublicNumbers

    TOKEN_URL = "https://auth.factset.com/as/token.oauth2"

    def b64d(s): return int.from_bytes(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)), "big")
    def b64e(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    jwk  = json.loads(JWK_RAW)
    pub  = RSAPublicNumbers(e=b64d(jwk["e"]), n=b64d(jwk["n"]))
    priv = RSAPrivateNumbers(p=b64d(jwk["p"]), q=b64d(jwk["q"]), d=b64d(jwk["d"]),
                             dmp1=b64d(jwk["dp"]), dmq1=b64d(jwk["dq"]), iqmp=b64d(jwk["qi"]),
                             public_numbers=pub).private_key(default_backend())
    now = int(time.time())
    hdr = b64e(json.dumps({"alg": "RS256", "typ": "JWT", "kid": KEY_ID}, separators=(",", ":")).encode())
    pld = b64e(json.dumps({"iss": CLIENT_ID, "sub": CLIENT_ID, "aud": TOKEN_URL,
                            "jti": str(uuid.uuid4()), "iat": now, "exp": now + 300},
                           separators=(",", ":")).encode())
    sig = b64e(priv.sign(f"{hdr}.{pld}".encode(), padding.PKCS1v15(), hashes.SHA256()))
    jwt = f"{hdr}.{pld}.{sig}"

    r = requests.post(TOKEN_URL,
                      data={"grant_type": "client_credentials",
                            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                            "client_assertion": jwt},
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def fetch_surprise(token: str) -> list[dict]:
    """/surprise로 actual + surpriseBefore(=CONS_PRINT) 수집."""
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/json",
            "Content-Type": "application/json"}
    r = requests.post(
        "https://api.factset.com/content/factset-estimates/v2/surprise",
        json={"ids": FACTSET_TICKERS, "metrics": ["SALES"], "periodicity": "QTR",
              "startDate": START_DATE, "endDate": END_DATE, "statistic": "MEAN"},
        headers=hdrs, timeout=30)
    if not r.ok:
        print(f"API error {r.status_code}: {r.text[:500]}")
        r.raise_for_status()
    return r.json().get("data", [])


def fetch_cons_early(token: str, fq_end: str) -> dict[str, float]:
    """rolling-consensus로 FQ_end+7d 이전 최신 consensus(CONS_EARLY) 수집.

    EXPERIMENT_SPEC §3: CONS_EARLY = CONS_END_DATE ≤ fiscal_quarter_end + 7d 의 최신값.
    Returns: {fsymId: mean_consensus}
    """
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/json",
            "Content-Type": "application/json"}
    cutoff = (pd.Timestamp(fq_end) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    # window: FQ_end - 90d ~ FQ_end + 7d (분기말 직전 90일 consensus 히스토리)
    window_start = (pd.Timestamp(fq_end) - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    r = requests.post(
        "https://api.factset.com/content/factset-estimates/v2/rolling-consensus",
        json={"ids": FACTSET_TICKERS, "metrics": ["SALES"], "periodicity": "QTR",
              "startDate": window_start, "endDate": cutoff, "statistic": "MEAN"},
        headers=hdrs, timeout=30)
    if not r.ok:
        return {}
    data = r.json().get("data", [])
    # 각 fsymId별로 estimateDate가 FQ_end와 가장 가까운(cutoff 이내) row 선택
    best: dict[str, dict] = {}
    for row in data:
        if row.get("fiscalEndDate") != fq_end:
            continue
        fsym = row["fsymId"]
        if fsym not in best or row["estimateDate"] > best[fsym]["estimateDate"]:
            best[fsym] = row
    return {fsym: v["mean"] for fsym, v in best.items() if v.get("mean") is not None}


def main():
    print(f"FactSet PIT Revenue Surprise — {', '.join(TICKERS)}")
    token = get_token()
    print("OAuth OK")

    raw = fetch_surprise(token)
    print(f"surprise rows: {len(raw)}")

    # surprise → base rows (actual + CONS_PRINT)
    base: dict[tuple, dict] = {}
    for item in raw:
        ticker  = item["requestId"].replace("-US", "")
        actual  = item.get("surpriseAfter")
        cons_p  = item.get("surpriseBefore")
        date    = item.get("fiscalEndDate")
        fsym    = item.get("fsymId")
        report  = item.get("surpriseDate")
        if actual is None or cons_p is None or cons_p == 0 or date is None:
            continue
        key = (fsym, date)
        if key not in base or item.get("surpriseDate", "") > base[key].get("REPORT_DATE", ""):
            base[key] = {"FSYM_ID": fsym, "ticker": ticker, "FE_FP_END": date,
                         "REPORT_DATE": report, "ACTUAL": actual, "CONS_PRINT": cons_p}

    # 고유 FQ end 날짜 목록
    fq_ends = sorted({v["FE_FP_END"] for v in base.values()})
    print(f"unique FQ ends: {len(fq_ends)} — fetching CONS_EARLY per quarter...")

    # 분기별 CONS_EARLY 수집 (rolling-consensus, FQ_end+7d 스냅샷)
    cons_early_map: dict[tuple, float] = {}  # (fsymId, fq_end) → mean
    for fq_end in fq_ends:
        ce = fetch_cons_early(token, fq_end)
        for fsym, val in ce.items():
            cons_early_map[(fsym, fq_end)] = val
        print(f"  {fq_end}: {len(ce)} tickers")

    # 최종 rows 조합
    rows = []
    for (fsym, fq_end), v in base.items():
        cons_early = cons_early_map.get((fsym, fq_end), v["CONS_PRINT"])  # fallback to CONS_PRINT
        rows.append({**v, "CONS_EARLY": cons_early})

    df = pd.DataFrame(rows)
    df["FE_FP_END"] = pd.to_datetime(df["FE_FP_END"])
    df = df.drop_duplicates(subset=["ticker", "FE_FP_END"], keep="last")
    df = df.sort_values(["ticker", "FE_FP_END"]).reset_index(drop=True)

    # CONS_EARLY vs CONS_PRINT 차이 확인
    df["ce_vs_cp"] = (df["CONS_EARLY"] - df["CONS_PRINT"]) / df["CONS_PRINT"].abs()
    print(f"\nCONS_EARLY vs CONS_PRINT diff (mean abs): {df['ce_vs_cp'].abs().mean():.4f}")
    print(f"CONS_EARLY == CONS_PRINT rows: {(df['ce_vs_cp'].abs() < 0.001).sum()} / {len(df)}")

    fsym_map = df.drop_duplicates("ticker").set_index("FSYM_ID")["ticker"].to_dict()
    print(f"\nFSYM2TKR = {fsym_map}")

    DATA.mkdir(parents=True, exist_ok=True)
    out_json = DATA / "factset_foot10_pit.json"
    out_csv  = DATA / "revenue_surprise_foot10.csv"

    df_json = df.drop(columns=["ce_vs_cp"]).copy()
    df_json["FE_FP_END"] = df_json["FE_FP_END"].dt.strftime("%Y-%m-%d")
    with open(out_json, "w") as f:
        json.dump({"rows": df_json.to_dict(orient="records")}, f, indent=2)

    df.to_csv(out_csv, index=False)
    print(f"\n저장: {out_json}")
    print(f"저장: {out_csv}")
    print(f"\n티커별 분기 수:")
    print(df.groupby("ticker")["FE_FP_END"].agg(["min", "max", "count"]).to_string())


if __name__ == "__main__":
    main()
