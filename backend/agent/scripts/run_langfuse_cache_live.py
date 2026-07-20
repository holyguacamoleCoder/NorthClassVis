"""Live check: stream LLM twice, print usage/cache, flush Langfuse, probe API."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
AGENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT))

# Load backend .env before anything else
env_path = BACKEND / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

import runtime_bootstrap  # noqa: E402, F401
from common.langfuse_tracing import _usage_details, flush  # noqa: E402
from common.llm_client import LLMClient  # noqa: E402
from common.paths import bootstrap_agent_paths  # noqa: E402


SYS = (
    "你是简洁的数据分析助手。只用一两句话回答。"
    "这是一段用于测量 prompt cache 的固定 system 前缀，"
    "需要足够长以超过 DeepSeek 自动缓存门槛。"
    + ("缓存前缀填充。" * 200)
)


def _one_call(client: LLMClient, n: int) -> dict:
    deltas: list[str] = []

    def on_delta(d: str) -> None:
        deltas.append(d)

    resp = client.create_completion(
        system_prompt=SYS,
        messages=[{"role": "user", "content": f"第{n}次：用一个词回答：1+1等于几？"}],
        tools=None,
        max_tokens=32,
        on_content_delta=on_delta,
        langfuse_name="cache_probe_stream",
        langfuse_metadata={"probe": "langfuse_cache", "call_index": n},
    )
    usage = getattr(resp, "usage", None)
    details = _usage_details(resp) or {}
    raw = {}
    if usage is not None:
        raw = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "prompt_cache_hit_tokens": getattr(usage, "prompt_cache_hit_tokens", None),
            "prompt_tokens_details": str(getattr(usage, "prompt_tokens_details", None)),
        }
        # dump all usage attrs for discovery
        try:
            raw["usage_dict"] = usage.model_dump() if hasattr(usage, "model_dump") else None
        except Exception:
            raw["usage_dict"] = None
        if raw["usage_dict"] is None and hasattr(usage, "to_dict"):
            try:
                raw["usage_dict"] = usage.to_dict()
            except Exception:
                pass
        if raw["usage_dict"] is None:
            raw["usage_dir"] = [
                a
                for a in dir(usage)
                if not a.startswith("_")
                and ("token" in a.lower() or "cache" in a.lower())
            ]
    return {
        "call": n,
        "text": "".join(deltas)[:80],
        "details": details,
        "raw_usage": raw,
    }


def main() -> int:
    bootstrap_agent_paths()
    client = LLMClient()
    if not client.config.is_available():
        print("OPENAI_API_KEY missing")
        return 1
    print(f"model={client.config.model}")
    print(f"base_url={client.config.base_url}")
    print(f"LANGFUSE_ENABLED={os.environ.get('LANGFUSE_ENABLED')}")
    print(f"system_chars={len(SYS)}")

    from common.langfuse_tracing import user_turn_trace

    results = []
    with user_turn_trace(
        session_id="cache-probe-session",
        job_id="cache-probe-job",
        user_message="langfuse cache live probe",
        permission_mode="analyze",
        extra_metadata={"probe": "langfuse_cache"},
    ):
        for i in (1, 2, 3):
            print(f"\n--- call {i} ---")
            info = _one_call(client, i)
            results.append(info)
            print(json.dumps(info, ensure_ascii=False, default=str, indent=2))
            time.sleep(0.8)

    print("\nflushing langfuse…")
    flush()
    time.sleep(8.0)

    probe_path = Path(__file__).resolve().parent / "langfuse_cache_probe.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("langfuse_cache_probe", probe_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("\n=== Langfuse probe (filter cache_probe_stream) ===")
    # Monkeypatch limit filter by printing filtered client-side after fetch
    # Reuse API helper
    import base64
    import urllib.parse
    import urllib.request

    pub = os.environ["LANGFUSE_PUBLIC_KEY"]
    sec = os.environ["LANGFUSE_SECRET_KEY"]
    base = os.environ.get("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
    q = urllib.parse.urlencode({"type": "GENERATION", "limit": 50, "name": "cache_probe_stream"})
    url = f"{base.rstrip('/')}/api/public/observations?{q}"
    req = urllib.request.Request(url)
    token = base64.b64encode(f"{pub}:{sec}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    rows = data.get("data") or []
    # Also accept any name containing probe
    if not rows:
        q2 = urllib.parse.urlencode({"type": "GENERATION", "limit": 50})
        url2 = f"{base.rstrip('/')}/api/public/observations?{q2}"
        req2 = urllib.request.Request(url2)
        req2.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req2, timeout=60) as resp2:
            data2 = json.loads(resp2.read().decode("utf-8"))
        rows = [
            r
            for r in (data2.get("data") or [])
            if "cache_probe" in str(r.get("name") or "")
            or "probe" in str((r.get("metadata") or {}))
        ]
    print(f"matched_generations={len(rows)}")
    for r in rows[:10]:
        print(
            json.dumps(
                {
                    "name": r.get("name"),
                    "promptTokens": r.get("promptTokens"),
                    "completionTokens": r.get("completionTokens"),
                    "usage": r.get("usage"),
                    "usageDetails": r.get("usageDetails"),
                    "latency": r.get("latency"),
                    "createdAt": r.get("createdAt"),
                },
                ensure_ascii=False,
                default=str,
            )
        )

    print("\n=== Local DeepSeek usage summary ===")
    for info in results:
        d = info["details"]
        print(
            f"call {info['call']}: input={d.get('input')} cached={d.get('input_cached_tokens')} output={d.get('output')}"
        )
    hits = [info["details"].get("input_cached_tokens") or 0 for info in results]
    print(f"cache_hit_tokens_by_call={hits}")
    if len(hits) >= 2 and hits[0] == 0 and any(h > 0 for h in hits[1:]):
        print("RESULT: DeepSeek cache engaged on later calls (local usage).")
    elif all(h == 0 for h in hits):
        print("RESULT: DeepSeek reported 0 cache hits (provider/threshold/policy).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
