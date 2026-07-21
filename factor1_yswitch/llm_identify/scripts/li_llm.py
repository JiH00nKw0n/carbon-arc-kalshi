"""
OpenAI 클라이언트 + 캐싱 래퍼 — 재현가능성 핵심.

- 모든 호출은 (model, prompt, schema) 해시로 캐시(cache/*.json). 같은 입력 → 같은 출력, API 재호출 없음.
- Structured output: JSON schema 강제 (response_format json_schema). 파싱 실패 없음.
- gpt-5.5 는 reasoning 모델 계열이라 max_completion_tokens 넉넉히, temperature 미지정(기본).
"""
import hashlib
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from li_config import CACHE, LINQ_ENV, OPENAI_MODEL  # noqa: E402


def _key():
    k = None
    for line in open(LINQ_ENV):
        line = line.strip()
        if line.startswith("OPENAI_API_KEY="):
            k = line.split("=", 1)[1].strip().strip('"').strip("'")
    return k


def _client():
    from openai import OpenAI
    return OpenAI(api_key=_key())


def call_json(system: str, user: str, schema: dict, tag: str, model: str = OPENAI_MODEL) -> dict:
    """Structured JSON call with on-disk cache. `tag` labels the cache file for readability."""
    h = hashlib.sha256(json.dumps([model, system, user, schema], sort_keys=True).encode()).hexdigest()[:16]
    cache_file = CACHE / f"{tag}_{h}.json"
    if cache_file.exists():
        return json.load(open(cache_file))["response"]

    client = _client()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "identification", "strict": True, "schema": schema}},
        max_completion_tokens=8000,
    )
    content = resp.choices[0].message.content
    out = json.loads(content)
    json.dump({"model": model, "tag": tag, "system": system, "user": user,
               "schema": schema, "response": out}, open(cache_file, "w"), indent=2)
    return out
