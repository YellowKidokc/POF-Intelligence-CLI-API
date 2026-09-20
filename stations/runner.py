"""Crash-safe station execution built on the existing CLI, ledger, and FileRouter."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from actions.file_router import FileRouter
from ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"name", "provider_profile", "input_globs", "output_format", "output_name"}


def _load(station_dir):
    station = Path(station_dir).resolve()
    config = json.loads((station / "station.json").read_text(encoding="utf-8"))
    missing = REQUIRED - config.keys()
    if missing: raise ValueError("station.json missing: " + ", ".join(sorted(missing)))
    if config.get("mode", "per_item") not in ("per_item", "aggregate"): raise ValueError("mode must be per_item or aggregate")
    if int(config.get("max_input_chars", 0)) < 1: raise ValueError("max_input_chars must be positive")
    return station, config


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def _read(path): return path.read_text(encoding="utf-8", errors="replace")


def _category(text, key):
    if not key: return ""
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try: value = json.loads(match.group()).get(key, "")
        except json.JSONDecodeError: value = ""
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")
    return ""


class _BalancedHTML(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    def __init__(self): super().__init__(); self.stack = []
    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID: self.stack.append(tag)
    def handle_startendtag(self, tag, attrs): pass
    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag: raise ValueError(f"unbalanced closing tag: {tag}")


def _validate_html(text):
    if not text.lstrip().lower().startswith("<!doctype html"): raise ValueError("HTML must start with <!doctype html")
    if re.search(r"(?:https?:)?//", text, re.I): raise ValueError("HTML contains an external URL")
    parser = _BalancedHTML(); parser.feed(text)
    if parser.stack: raise ValueError("unbalanced HTML tags: " + ", ".join(parser.stack[-5:]))


def _attachments(station, patterns):
    paths = []
    for pattern in patterns or []: paths.extend(Path(p) for p in glob.glob(str(station / pattern), recursive=True))
    return [p for p in sorted(set(paths)) if p.is_file()]


def _sources(station, entries):
    found = []
    for entry in entries:
        candidate = Path(entry)
        pattern = str(candidate if candidate.is_absolute() else station / candidate)
        matches = [Path(p) for p in glob.glob(pattern, recursive=True)]
        if not matches and Path(pattern).exists(): matches = [Path(pattern)]
        for path in matches:
            if path.is_dir(): found.extend(p for p in path.rglob("*") if p.is_file())
            elif path.is_file(): found.append(path)
    return sorted(set(p.resolve() for p in found))


def _source_text(path):
    return _read(path)  # Aggregate sources stay complete, including bundle metadata.


def _call(station, config, text, output_path, ledger, item, profile_override, execute):
    from cli import api_call
    profile_name = profile_override or config["provider_profile"]
    from cli import ROOT as CLI_ROOT, profile
    settings = profile(CLI_ROOT / "config.ini", profile_name)
    model = config.get("model") or settings.get("model", "")
    if profile_name == "openrouter" and config.get("auto_model"):
        from stations.model_router import current_model
        model = current_model(priority=config.get("model_priority", "quality"), max_age_minutes=60,
                              max_probe_seconds=config.get("max_probe_seconds", 45),
                              min_context_tokens=config.get("min_context_tokens", 0),
                              demote_minutes=config.get("demote_minutes", 120))
    args = argparse.Namespace(config=str(ROOT / "config.ini"), profile=profile_name,
        system=str(station / "system.md") if (station / "system.md").exists() else "", dry_run=not execute,
        stream=False, settings_override={"model": model or "", "max_tokens": str(config.get("max_tokens", 4096)),
        "temperature": str(config.get("temperature", .2))})
    if profile_name == "openrouter":
        from stations.model_router import note_request, remaining_allowance
        if remaining_allowance() <= 0: raise RuntimeError("OpenRouter free daily request allowance exhausted")
    started = time.monotonic()
    result = api_call(args, text, ledger, output_path=output_path,
                      ledger_extra={"station": config["name"], "item": str(item)})
    elapsed = time.monotonic() - started
    if profile_name == "openrouter": note_request()
    if elapsed > float(config.get("max_latency_seconds", 120)):
        raise TimeoutError(f"model call took {elapsed:.2f}s (limit {config.get('max_latency_seconds', 120)}s)")
    return result


def _receipt(station, name, data):
    path = station / "receipts" / f"{name}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _recover(station, router):
    cutoff = time.time() - 900
    for path in (station / "waiting").glob("*"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            router.move(path, station / "inbox" / path.name, dry_run=False)


def _base_summary(config, execute):
    return {"station": config["name"], "status": "success", "dry_run": not execute, "claimed": 0,
            "successes": 0, "failures": 0, "skipped": 0, "categories": {}, "input_tokens": 0,
            "output_tokens": 0, "total_cost_usd": 0.0, "receipts_written": []}


def run_station(station_dir, *, execute=False, limit=None, profile_override=None):
    station, config = _load(station_dir)
    summary = _base_summary(config, execute)
    # Resolve credentials from the single shared config, but never expose them.
    from cli import profile
    settings = profile(ROOT / "config.ini", profile_override or config["provider_profile"])
    model = config.get("model") or settings.get("model", "")
    summary["resolved_provider"] = settings["provider"]; summary["resolved_model"] = model
    if config.get("mode", "per_item") == "aggregate":
        return _run_aggregate(station, config, summary, execute, profile_override)
    inbox = station / "inbox"
    # Recovery precedes discovery so recovered work is eligible in this run.
    if execute:
        recovery_ledger = Ledger(ROOT / "ledger.sqlite")
        _recover(station, FileRouter(ROOT, recovery_ledger))
    matches = []
    for pattern in config["input_globs"]: matches.extend(inbox.glob(pattern))
    items = sorted(set(p for p in matches if p.is_file()))[:limit]
    summary["planned"] = len(items)
    if not execute:
        max_chars = int(config["max_input_chars"])
        summary["estimated_input_tokens"] = sum(len(_read(p)) // 4 for p in items)
        try:
            from providers.openai_provider import PRICING
            rates = PRICING.get(model, (0.0, 0.0))
            summary["estimated_cost_usd"] = (summary["estimated_input_tokens"] * rates[0] + len(items) * int(config.get("max_tokens", 4096)) * rates[1]) / 1_000_000
        except ImportError: summary["estimated_cost_usd"] = 0.0
        for path in items: print(f"DRY RUN: would claim, process, receipt, and archive {path}")
        return summary
    ledger = Ledger(ROOT / "ledger.sqlite"); router = FileRouter(ROOT, ledger)
    prompt = _read(station / "prompt.md") if (station / "prompt.md").exists() else ""
    attachments = _attachments(station, config.get("attachments", []))
    attachment_text = "".join(f"\n\n--- attachment: {p.name} ---\n{_read(p)}" for p in attachments)
    max_chars = int(config["max_input_chars"]); ceiling = float(config.get("cost_ceiling_usd", float("inf")))
    for source in items:
        if summary["total_cost_usd"] > ceiling:
            summary["status"] = "cost_ceiling_reached"; summary["skipped"] += 1; break
        waiting = station / "waiting" / source.name
        produced_output = None
        try:
            router.move(source, waiting, dry_run=False); summary["claimed"] += 1
            raw = _read(waiting); truncated = False; body = raw
            text = f"{prompt}\n\n--- item: {source.name} ---\n{body}{attachment_text}"
            ext = config["output_format"]; provisional = station / "outbox" / config["output_name"].format(stem=source.stem, ext=ext, date=time.strftime("%Y-%m-%d"))
            result = _call(station, config, text, provisional, ledger, source.name, profile_override, True)
            produced_output = provisional
            if ext.lower() == "html": _validate_html(result["text"])
            category = _category(result["text"], config.get("categorize_by"))
            final = station / "outbox" / category / provisional.name if category else provisional
            if final != provisional: final.parent.mkdir(parents=True, exist_ok=True); router.move(provisional, final, dry_run=False); produced_output = final
            receipt = {"station": config["name"], "item": source.name, "status": "success", "model": result["model"],
                       "category": category, "truncated": truncated, "original_chars": len(raw), "used_chars": len(body),
                       "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"], "cost_usd": result["cost_usd"],
                       "output": str(final)}
            receipt_path = _receipt(station, source.stem, receipt); summary["receipts_written"].append(str(receipt_path))
            consumed = station / config.get("move_input_to", "outbox/_consumed") / waiting.name
            router.move(waiting, consumed, dry_run=False)
            handoff = config.get("on_success", "outbox")
            if handoff != "outbox": router.copy(final, (station / handoff).resolve() / final.name, dry_run=False)
            if config.get("vectorize"):
                from stations.vectorize import VectorStore
                VectorStore(station, profile_name=profile_override or config["provider_profile"], model=config.get("embedding_model", "text-embedding-3-small")).add([final])
            summary["successes"] += 1; summary["categories"][category or "uncategorized"] = summary["categories"].get(category or "uncategorized", 0) + 1
            summary["input_tokens"] += result["input_tokens"]; summary["output_tokens"] += result["output_tokens"]; summary["total_cost_usd"] += result["cost_usd"]
        except Exception as error:
            summary["failures"] += 1; summary["status"] = "partial_failure"
            candidate = waiting if waiting.exists() else source
            failed = station / config.get("on_failure", "failed") / candidate.name
            if candidate.exists(): router.move(candidate, failed, dry_run=False)
            if produced_output and produced_output.exists():
                router.move(produced_output, failed.parent / produced_output.name, dry_run=False)
            failed.parent.mkdir(parents=True, exist_ok=True); (failed.parent / f"{failed.name}.error.txt").write_text(str(error), encoding="utf-8")
            receipt_path = _receipt(station, source.stem, {"station": config["name"], "item": source.name, "status": "failed", "error": str(error)})
            summary["receipts_written"].append(str(receipt_path))
    return summary


def _run_aggregate(station, config, summary, execute, profile_override):
    sources = _sources(station, config.get("sources", [])); summary["planned"] = len(sources)
    metadata = [{"path": str(p), "size": p.stat().st_size, "sha256": _hash(p)} for p in sources]
    prompt_path = station / "prompt.md"; prompt = _read(prompt_path) if prompt_path.exists() else ""
    if not prompt.strip():
        for source in sources:
            handoff = source.parent / "HANDOFF_PROMPT.md"
            if handoff.exists(): prompt = _read(handoff); break
    chunks = [f"--- {p.name} ---\n{_source_text(p)}" for p in sources]
    combined = "\n\n".join(chunks); two_pass = False  # Complete sources; no excerpt masquerading as a second pass.
    text = f"{prompt}\n\n{combined}"
    name = config["output_name"].format(stem=config["name"], ext=config["output_format"], date=time.strftime("%Y-%m-%d"))
    output = station / "outbox" / name
    if not execute:
        input_estimate = len(text) // 4
        try:
            from providers.openai_provider import PRICING
            rates = PRICING.get(summary["resolved_model"], (0.0, 0.0))
            cost_estimate = (input_estimate * rates[0] + int(config.get("max_tokens", 4096)) * rates[1]) / 1_000_000
        except ImportError: cost_estimate = 0.0
        summary.update({"estimated_input_tokens": input_estimate, "estimated_cost_usd": cost_estimate, "two_pass": two_pass, "sources": metadata})
        print(f"DRY RUN: would aggregate {len(sources)} sources into {output}"); return summary
    ledger = Ledger(ROOT / "ledger.sqlite")
    try:
        result = _call(station, config, text, output, ledger, "aggregate", profile_override, True)
        if config["output_format"].lower() == "html": _validate_html(result["text"])
        receipt = _receipt(station, "aggregate", {"station": config["name"], "status": "success", "model": result["model"],
            "sources": metadata, "two_pass": two_pass, "output": str(output), "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"], "cost_usd": result["cost_usd"]})
        summary.update(successes=1, claimed=len(sources), input_tokens=result["input_tokens"], output_tokens=result["output_tokens"], total_cost_usd=result["cost_usd"])
        summary["receipts_written"].append(str(receipt))
    except Exception as error:
        summary.update(status="partial_failure", failures=1)
        failed = station / "failed" / name
        if output.exists(): FileRouter(ROOT, ledger).move(output, failed, dry_run=False)
        failed.parent.mkdir(parents=True, exist_ok=True); (failed.parent / f"{name}.error.txt").write_text(str(error), encoding="utf-8")
        summary["receipts_written"].append(str(_receipt(station, "aggregate", {"status": "failed", "sources": metadata, "error": str(error), "two_pass": two_pass})))
    return summary
