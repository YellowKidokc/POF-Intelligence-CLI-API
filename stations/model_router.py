"""Resilient OpenRouter free-model ranking, probing, and hourly watch."""
from __future__ import annotations

import json
import os
import re
import statistics
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "registries" / "openrouter_state.json"
HISTORY_PATH = ROOT / "registries" / "openrouter-model-history.json"
OPENROUTER_RPM = int(os.environ.get("OPENROUTER_RPM", "20"))
PROBES = [
    {"prompt": 'Return only JSON: {"answer": 4}', "expected": {"answer": 4}, "weight": .35},
    {"prompt": 'Return only JSON: {"items":["alpha","beta"],"count":2}', "expected": {"items": ["alpha", "beta"], "count": 2}, "weight": .35},
    {"prompt": 'Return only JSON: {"verdict":"keep","reason":"identical"}', "expected": {"verdict": "keep", "reason": "identical"}, "weight": .30},
]
minimum_score = .90
_last_request = 0.0


def _read(path, default):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return default


def _atomic(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream: json.dump(data, stream, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def extract_object(text):
    """Tolerantly extract the first balanced JSON object from model prose."""
    start = text.find("{")
    while start >= 0:
        depth = 0; quoted = False; escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if quoted:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == '"': quoted = False
            elif char == '"': quoted = True
            elif char == "{": depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try: return json.loads(text[start:index + 1])
                    except json.JSONDecodeError: break
        start = text.find("{", start + 1)
    raise ValueError("response did not contain a JSON object")


def _parameters(model):
    text = " ".join(str(model.get(k, "")) for k in ("id", "name", "description"))
    match = re.search(r"(?:^|\D)(\d+(?:\.\d+)?)\s*[Bb](?:\D|$)", text)
    return float(match.group(1)) if match else 0


def model_score(model, priority="quality"):
    context = int(model.get("context_length") or 0); score = min(context / 1000, 256)
    supported = model.get("supported_parameters") or []
    if "response_format" in supported: score += 35
    if "structured_outputs" in supported: score += 35
    identity = model.get("id", "").lower()
    if any(name in identity for name in ("nemotron", "deepseek", "qwen", "glm")): score += 55
    score += min(_parameters(model) * 1.5, 120)
    expires = model.get("expiration_date") or model.get("expires_at")
    if expires:
        try:
            expiry = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            if expiry <= datetime.now(timezone.utc) + timedelta(days=7): score -= 500
        except ValueError: pass
    if priority == "speed": score -= _parameters(model) * 1.5; score -= context / 8000
    elif priority == "long": score += context / 500
    return score


def _pace():
    global _last_request
    wait = 60 / max(1, OPENROUTER_RPM) - (time.monotonic() - _last_request)
    if wait > 0: time.sleep(wait)
    _last_request = time.monotonic()


def run_probe(model, api_key, probe=None, retries=2, max_probe_seconds=45):
    from providers.openrouter_provider import OpenRouterProvider
    provider = OpenRouterProvider(api_key); selected = [probe] if probe else PROBES
    total = 0.0; latencies = []
    for spec in selected:
        passed = False
        for attempt in range(retries + 1):
            _pace(); started = time.monotonic()
            try:
                result = provider.call([{"role": "user", "content": spec["prompt"]}], model, 0, 120)
                latency = time.monotonic() - started; latencies.append(latency)
                if latency <= max_probe_seconds and extract_object(result.text) == spec["expected"]: passed = True; break
            except Exception:
                if attempt == retries: break
        if passed: total += spec["weight"]
    denominator = sum(p["weight"] for p in selected)
    return {"passed": total / denominator >= minimum_score, "score": total / denominator, "latency_seconds": statistics.median(latencies) if latencies else None}


def _credentials():
    from cli import profile
    settings = profile(ROOT / "config.ini", "openrouter")
    return settings["api_key"]


def remaining_allowance():
    allowance = int(os.environ.get("OPENROUTER_FREE_DAILY_REQUESTS", "50")); today = datetime.now(timezone.utc).date().isoformat()
    state = _read(STATE_PATH, {}); used = state.get("daily_requests", {}).get(today, 0)
    return max(0, allowance - used)


def note_request():
    state = _read(STATE_PATH, {}); today = datetime.now(timezone.utc).date().isoformat()
    daily = state.setdefault("daily_requests", {}); daily[today] = daily.get(today, 0) + 1; _atomic(STATE_PATH, state)


def current_model(priority="quality", max_age_minutes=60, *, max_probe_seconds=45, min_context_tokens=0, demote_minutes=120):
    from providers.openrouter_provider import free_text_models
    key = _credentials(); state = _read(STATE_PATH, {}); now = datetime.now(timezone.utc)
    try:
        catalogue = free_text_models(key); ids = {row["id"] for row in catalogue}
        candidates = [row for row in catalogue if int(row.get("context_length") or 0) >= int(min_context_tokens)]
        candidates.sort(key=lambda row: model_score(row, priority), reverse=True)
        demoted = state.get("demoted", {})
        candidates.sort(key=lambda row: datetime.fromisoformat(demoted.get(row["id"], "1970-01-01T00:00:00+00:00")) > now)
        selected = state.get("selected_id"); verified = datetime.fromisoformat(state.get("last_verified", "1970-01-01T00:00:00+00:00"))
        if selected in ids and now - verified <= timedelta(minutes=max_age_minutes): return selected
        ordered = ([selected] if selected in ids else []) + [row["id"] for row in candidates if row["id"] != selected]
        for model_id in ordered:
            result = run_probe(model_id, key, probe=PROBES[0], max_probe_seconds=max_probe_seconds)
            if result["passed"]:
                history = _read(HISTORY_PATH, {}); history[model_id] = {"passed": True, "tested": now.isoformat(), **result}; _atomic(HISTORY_PATH, history)
                previous = state.get("latencies", []); previous.append(result["latency_seconds"]); previous = previous[-20:]
                state.update(selected_id=model_id, runners_up=[x for x in ordered if x != model_id], last_verified=now.isoformat(),
                             consecutive_failures=0, latencies=previous, rolling_median_latency=statistics.median(previous), last_error=None)
                _atomic(STATE_PATH, state); return model_id
            state.setdefault("demoted", {})[model_id] = (now + timedelta(minutes=demote_minutes)).isoformat()
        raise RuntimeError("no free OpenRouter model passed the availability probe")
    except Exception as error:
        state["last_error"] = str(error); state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1; _atomic(STATE_PATH, state)
        if state.get("selected_id"): return state["selected_id"]
        raise


def watch(interval_minutes=60, once=False):
    while True:
        try: current_model(max_age_minutes=0)
        except Exception: pass
        if once: return
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--once", action="store_true"); parser.add_argument("--interval-minutes", type=float, default=60)
    options = parser.parse_args(); watch(options.interval_minutes, options.once)
