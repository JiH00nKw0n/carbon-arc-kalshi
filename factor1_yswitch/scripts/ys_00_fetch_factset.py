"""
Y-switching — FactSet PIT revenue surprise for the UNION of all channel tickers.

Same OAuth + /surprise + /rolling-consensus logic as 지훈's ft_00_fetch_factset.py, but
parameterized to the 121-ticker union across card/foot/click channels.

OUT: factor1_yswitch/data/factset_yswitch_pit.json  {"rows":[{FSYM_ID,ticker,FE_FP_END,
     REPORT_DATE,ACTUAL,CONS_EARLY,CONS_PRINT}, ...]}

FactSet uses the firm's own subscription (OAuth), NOT Carbon Arc credits — this call is
free w.r.t. the CA balance.

Usage:  python ys_00_fetch_factset.py
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

# FactSet OAuth creds live in the LinqAlpha repo root .env (parents[4]); CA token in
# carbonarc_poc/.env (parents[3]). Load both so either set of vars resolves.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[4] / ".env")   # /Users/.../LinqAlpha/.env
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env")   # carbonarc_poc/.env

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ys_config import DATA, CARD_CSV, FOOT_CSVS, CLICK_CSV, CLICK_NAME2TKR  # noqa: E402

CLIENT_ID = os.getenv("FACTSET_OAUTH_CLIENT_ID")
KEY_ID    = os.getenv("FACTSET_OAUTH_KEY_ID")
JWK_RAW   = os.getenv("FACTSET_OAUTH_PRIVATE_KEY")
START_DATE = "2022-01-01"
END_DATE   = "2026-07-01"


def ticker_union() -> list[str]:
    card = set(pd.read_csv(CARD_CSV)["entity_name"].unique())
    foot = set()
    for f in FOOT_CSVS:
        foot |= set(pd.read_csv(f)["entity_name"].unique())
    click = {CLICK_NAME2TKR.get(n) for n in pd.read_csv(CLICK_CSV)["entity_name"].unique()}
    click.discard(None)
    return sorted(card | foot | click)


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


def fetch_surprise(token: str, fs_ids: list[str]) -> list[dict]:
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/json",
            "Content-Type": "application/json"}
    out = []
    # batch in chunks of 25 (FactSet id-count limit safety)
    for i in range(0, len(fs_ids), 25):
        chunk = fs_ids[i:i + 25]
        r = requests.post(
            "https://api.factset.com/content/factset-estimates/v2/surprise",
            json={"ids": chunk, "metrics": ["SALES"], "periodicity": "QTR",
                  "startDate": START_DATE, "endDate": END_DATE, "statistic": "MEAN"},
            headers=hdrs, timeout=45)
        if not r.ok:
            print(f"  surprise chunk {i//25} error {r.status_code}: {r.text[:200]}")
            continue
        out += r.json().get("data", [])
        time.sleep(0.3)
    return out


def fetch_cons_early(token: str, fs_ids: list[str], fq_end: str) -> dict[str, float]:
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/json",
            "Content-Type": "application/json"}
    cutoff = (pd.Timestamp(fq_end) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    window_start = (pd.Timestamp(fq_end) - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    best: dict[str, dict] = {}
    for i in range(0, len(fs_ids), 25):
        chunk = fs_ids[i:i + 25]
        r = requests.post(
            "https://api.factset.com/content/factset-estimates/v2/rolling-consensus",
            json={"ids": chunk, "metrics": ["SALES"], "periodicity": "QTR",
                  "startDate": window_start, "endDate": cutoff, "statistic": "MEAN"},
            headers=hdrs, timeout=45)
        if not r.ok:
            continue
        for row in r.json().get("data", []):
            if row.get("fiscalEndDate") != fq_end:
                continue
            fsym = row["fsymId"]
            if fsym not in best or row["estimateDate"] > best[fsym]["estimateDate"]:
                best[fsym] = row
        time.sleep(0.2)
    return {fsym: v["mean"] for fsym, v in best.items() if v.get("mean") is not None}


def main():
    tickers = ticker_union()
    fs_ids = [f"{t}-US" for t in tickers]
    print(f"Y-switch FactSet fetch — {len(tickers)} tickers")
    token = get_token()
    print("OAuth OK")

    raw = fetch_surprise(token, fs_ids)
    print(f"surprise rows: {len(raw)}")

    base: dict[tuple, dict] = {}
    for item in raw:
        ticker = item["requestId"].replace("-US", "")
        actual = item.get("surpriseAfter")
        cons_p = item.get("surpriseBefore")
        date   = item.get("fiscalEndDate")
        fsym   = item.get("fsymId")
        report = item.get("surpriseDate")
        if actual is None or cons_p is None or cons_p == 0 or date is None:
            continue
        key = (fsym, date)
        if key not in base or (report or "") > base[key].get("REPORT_DATE", ""):
            base[key] = {"FSYM_ID": fsym, "ticker": ticker, "FE_FP_END": date,
                         "REPORT_DATE": report, "ACTUAL": actual, "CONS_PRINT": cons_p}

    fq_ends = sorted({v["FE_FP_END"] for v in base.values()})
    print(f"unique FQ ends: {len(fq_ends)} — fetching CONS_EARLY per quarter...")
    cons_early_map: dict[tuple, float] = {}
    for fq_end in fq_ends:
        ce = fetch_cons_early(token, fs_ids, fq_end)
        for fsym, val in ce.items():
            cons_early_map[(fsym, fq_end)] = val
        print(f"  {fq_end}: {len(ce)} tickers")

    rows = []
    for (fsym, fq_end), v in base.items():
        cons_early = cons_early_map.get((fsym, fq_end), v["CONS_PRINT"])
        rows.append({**v, "CONS_EARLY": cons_early})

    df = pd.DataFrame(rows)
    df["FE_FP_END"] = pd.to_datetime(df["FE_FP_END"])
    df = df.drop_duplicates(subset=["ticker", "FE_FP_END"], keep="last")
    df = df.sort_values(["ticker", "FE_FP_END"]).reset_index(drop=True)

    DATA.mkdir(parents=True, exist_ok=True)
    dfj = df.copy()
    dfj["FE_FP_END"] = dfj["FE_FP_END"].dt.strftime("%Y-%m-%d")
    with open(DATA / "factset_yswitch_pit.json", "w") as f:
        json.dump({"rows": dfj.to_dict(orient="records")}, f, indent=2)

    print(f"\nsaved: {DATA / 'factset_yswitch_pit.json'}")
    print(f"coverage: {df.ticker.nunique()} tickers, {len(df)} qtr-rows, "
          f"{df.FE_FP_END.min().date()}..{df.FE_FP_END.max().date()}")
    missing = sorted(set(tickers) - set(df.ticker.unique()))
    print(f"missing (no FactSet SALES surprise): {len(missing)} — {missing}")


if __name__ == "__main__":
    main()
