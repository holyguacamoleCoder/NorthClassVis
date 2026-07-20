"""Pull recent Langfuse generations and summarize prompt / cache usage if present."""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]  # .../backend
ENV = BACKEND / ".env"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        # Prefer .env over empty/stale process env for this probe.
        os.environ[k.strip()] = v.strip().strip('"').strip("'")


def api_get(base: str, path: str, pub: str, sec: str, params: dict) -> dict:
    q = urllib.parse.urlencode(params)
    url = f"{base.rstrip('/')}{path}?{q}"
    req = urllib.request.Request(url, method="GET")
    token = base64.b64encode(f"{pub}:{sec}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def dig_usage(obj: dict) -> dict:
    out = {}
    for key in (
        "usage",
        "usageDetails",
        "usage_details",
        "calculatedUsage",
        "calculatedTotalCost",
    ):
        if key in obj and obj[key] is not None:
            out[key] = obj[key]
    meta = obj.get("metadata") or {}
    if isinstance(meta, dict):
        for key in ("usage", "cached_tokens", "cache_read_input_tokens", "prompt_cache_hit"):
            if key in meta:
                out[f"meta.{key}"] = meta[key]
    # flatten common usage shapes
    usage = obj.get("usage") or obj.get("usageDetails") or {}
    if isinstance(usage, dict):
        for k, v in usage.items():
            if any(x in str(k).lower() for x in ("cache", "prompt", "input", "output", "total")):
                out[f"usage.{k}"] = v
    return out


def main() -> int:
    load_env(ENV)
    if os.environ.get("LANGFUSE_ENABLED", "true").lower() in ("0", "false", "no"):
        print("LANGFUSE_ENABLED is false")
        return 1
    pub = (os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    sec = (os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()
    base = (
        os.environ.get("LANGFUSE_BASE_URL")
        or os.environ.get("LANGFUSE_HOST")
        or "https://cloud.langfuse.com"
    ).strip()
    if not pub or not sec:
        print("missing Langfuse keys")
        return 1

    print(f"host={base}")
    try:
        data = api_get(
            base,
            "/api/public/observations",
            pub,
            sec,
            {"type": "GENERATION", "limit": 30},
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body[:500]}")
        return 1

    rows = data.get("data") or data.get("observations") or []
    print(f"fetched_generations={len(rows)}")
    if not rows:
        print("no generations found — run a few agent turns first, then re-run this script")
        return 0

    cache_hits = 0
    with_usage = 0
    input_sum = 0
    output_sum = 0
    cache_sum = 0
    samples = []

    for obs in rows:
        name = obs.get("name") or ""
        model = obs.get("model") or ""
        usage_info = dig_usage(obs)
        ud = obs.get("usageDetails") or obs.get("usage") or {}
        inp = obs.get("promptTokens")
        out_t = obs.get("completionTokens")
        cached = None
        if isinstance(ud, dict):
            if inp in (None, 0):
                inp = ud.get("input") or ud.get("promptTokens") or ud.get("prompt_tokens")
            if out_t in (None, 0):
                out_t = ud.get("output") or ud.get("completionTokens")
            cached = (
                ud.get("input_cached_tokens")
                or ud.get("cache_read_input_tokens")
                or ud.get("cachedTokens")
                or ud.get("cache_read_tokens")
                or ud.get("prompt_cache_hit_tokens")
                or ud.get("input_cache_read")
            )
        if inp not in (None, 0) or out_t not in (None, 0):
            with_usage += 1
        try:
            if inp is not None:
                input_sum += int(inp)
        except Exception:
            pass
        try:
            if out_t is not None:
                output_sum += int(out_t)
        except Exception:
            pass
        if cached is not None:
            try:
                c = int(cached)
                cache_sum += c
                if c > 0:
                    cache_hits += 1
            except Exception:
                pass
        samples.append(
            {
                "name": name,
                "model": model,
                "promptTokens": obs.get("promptTokens"),
                "completionTokens": obs.get("completionTokens"),
                "totalTokens": obs.get("totalTokens"),
                "latency_ms": obs.get("latency"),
                "cached": cached,
                "usage": ud,
            }
        )

    print(f"with_nonzero_tokens={with_usage}/{len(rows)}")
    print(f"generations_with_cached>0={cache_hits}/{len(rows)}")
    print(f"sum_promptTokens={input_sum}")
    print(f"sum_completionTokens={output_sum}")
    print(f"sum_cached_tokens={cache_sum}")
    if input_sum:
        print(f"cached_ratio_over_inputs={cache_sum/input_sum:.3f}")
    print("--- sample (newest first) ---")
    for s in samples[:15]:
        print(json.dumps(s, ensure_ascii=False))

    # raw peek first observation usage-related keys for schema discovery
    first = rows[0]
    print("--- first observation token fields ---")
    print(
        json.dumps(
            {
                "promptTokens": first.get("promptTokens"),
                "completionTokens": first.get("completionTokens"),
                "totalTokens": first.get("totalTokens"),
                "usage": first.get("usage"),
                "usageDetails": first.get("usageDetails"),
                "latency": first.get("latency"),
                "tools_count": (first.get("metadata") or {}).get("tools_count"),
            },
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
