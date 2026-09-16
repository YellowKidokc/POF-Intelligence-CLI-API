#!/usr/bin/env python3
"""POF Intelligence CLI: providers, audited file routing, scans, and dispatch."""
import argparse, configparser, hashlib, json, os, sys, time
from pathlib import Path
from urllib.request import urlopen

from actions.file_router import FileRouter
from ledger import Ledger

ROOT = Path(__file__).resolve().parent


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", default="default"); p.add_argument("--config", default=str(ROOT / "config.ini"))
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--execute", action="store_true", help="confirm filesystem mutations")
    p.add_argument("--clipboard", action="store_true"); p.add_argument("--url"); p.add_argument("--batch")
    p.add_argument("--stream", action="store_true"); p.add_argument("--conversation", action="store_true"); p.add_argument("--system", default=str(ROOT / "system.txt"))
    p.add_argument("--move", nargs=2, metavar=("SOURCE", "DEST")); p.add_argument("--copy", nargs=2, metavar=("SOURCE", "DEST"))
    p.add_argument("--rename", nargs=2, metavar=("PATH", "NEW_NAME")); p.add_argument("--archive"); p.add_argument("--undo", nargs="?", const=1, type=int)
    p.add_argument("--scan"); p.add_argument("--fis-actions"); p.add_argument("--convert"); p.add_argument("--nlp", nargs="+", metavar="ARG")
    p.add_argument("--route"); p.add_argument("--stats", action="store_true"); p.add_argument("--health", action="store_true")
    p.add_argument("--station"); p.add_argument("--chain"); p.add_argument("--station-new")
    p.add_argument("--from", dest="station_from"); p.add_argument("--description", default="")
    p.add_argument("--station-status", action="store_true"); p.add_argument("--vectorize")
    p.add_argument("--vector-search"); p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--openrouter-watch", action="store_true"); p.add_argument("--once", action="store_true")
    return p


def profile(path, name):
    config = configparser.ConfigParser(); config.read(path)
    if name not in config: raise ValueError(f"Profile [{name}] not found in {path}")
    defaults = config["default"] if "default" in config else {}
    return {key.lower(): config[name].get(key, defaults.get(key, fallback) if hasattr(defaults, "get") else fallback) for key, fallback in {"provider": name, "model": "", "api_key": "", "base_url": "", "max_tokens": "4096", "temperature": "0.7"}.items()}


def prompt_text(args):
    parts = []
    if args.clipboard:
        import pyperclip
        parts.append(pyperclip.paste())
    if args.url:
        with urlopen(args.url, timeout=30) as response: parts.append(response.read().decode("utf-8", errors="replace"))
    if not parts and not sys.stdin.isatty(): parts.append(sys.stdin.read())
    if not parts:
        prompt = ROOT / "prompt.txt"
        if prompt.exists(): parts.append(prompt.read_text(encoding="utf-8"))
    input_dir = ROOT / "input"
    for path in sorted(input_dir.glob("*")) if input_dir.exists() else []:
        if path.is_file(): parts.append(f"\n--- {path.name} ---\n{path.read_text(encoding='utf-8', errors='replace')}")
    return "\n".join(parts).strip()


def api_call(args, text, ledger, *, output_path=None, ledger_extra=None, provider_instance=None):
    settings = profile(args.config, args.profile); settings.update(getattr(args, "settings_override", {}) or {})
    system = Path(args.system).read_text(encoding="utf-8") if args.system and Path(args.system).exists() else ""
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": text}]
    if args.dry_run:
        estimate = {"input_tokens": max(1, len(text) // 4), "output_tokens": int(settings["max_tokens"]), "cost_usd": 0.0}
        print(json.dumps({"profile": args.profile, "provider": settings["provider"], "model": settings["model"], "messages": messages, "estimate": estimate}, indent=2)); return {"text": "", **estimate, "model": settings["model"]}
    from providers import create_provider
    provider = provider_instance or create_provider(settings["provider"], settings["api_key"], settings["base_url"] or None); provider.model = settings["model"]
    started = time.monotonic()
    if args.stream:
        chunks = []
        for chunk in provider.stream(messages, settings["model"], float(settings["temperature"]), int(settings["max_tokens"])):
            print(chunk, end="", flush=True); chunks.append(chunk)
        print(); output = "".join(chunks); inputs = outputs = 0
    else:
        response = provider.call(messages, settings["model"], float(settings["temperature"]), int(settings["max_tokens"])); output, inputs, outputs = response.text, response.input_tokens, response.output_tokens; print(output)
    estimate = provider.estimate_cost(inputs, outputs); output_path = Path(output_path) if output_path else ROOT / "output" / time.strftime("response_%Y%m%d_%H%M%S.md")
    output_path.parent.mkdir(parents=True, exist_ok=True); output_path.write_text(output, encoding="utf-8")
    values = dict(provider=settings["provider"], model=settings["model"], profile=args.profile, input_hash=hashlib.sha256(text.encode()).hexdigest(), output_hash=hashlib.sha256(output.encode()).hexdigest(), input_tokens=inputs, output_tokens=outputs, cost_usd=estimate["cost_usd"], dest_path=str(output_path), status="success", duration_seconds=time.monotonic() - started)
    values.update(ledger_extra or {}); ledger.record("api_call", **values)
    print(f'\nSaved: {output_path} | Estimated cost: ${estimate["cost_usd"]:.6f}', file=sys.stderr)
    return {"text": output, **estimate, "model": settings["model"], "output_path": str(output_path)}


def health(args):
    settings = profile(args.config, args.profile); registry = ROOT / "registries/watch_folders.json"
    folders = [{"path": item["path"], "exists": Path(item["path"]).exists()} for item in json.loads(registry.read_text())]
    return {"python": sys.version.split()[0], "profile": args.profile, "provider": settings["provider"], "api_key_configured": bool(settings["api_key"]), "watched_folders": folders}


def station_status(root=ROOT / "stations"):
    from stations.model_router import remaining_allowance
    results = []
    for config_path in sorted(Path(root).glob("*/station.json")):
        station = config_path.parent; config = json.loads(config_path.read_text(encoding="utf-8"))
        row = {"station": config.get("name", station.name)}
        for name in ("inbox", "waiting", "outbox", "failed"):
            row[name] = sum(1 for path in (station / name).rglob("*") if path.is_file())
        try:
            settings = profile(ROOT / "config.ini", config.get("provider_profile", "default"))
            row.update(provider=settings["provider"], model=config.get("model") or settings["model"], api_key_configured=bool(settings["api_key"]), cost_ceiling_usd=config.get("cost_ceiling_usd"))
        except ValueError as error: row["configuration_error"] = str(error)
        if config.get("provider_profile") == "openrouter": row["free_requests_remaining"] = remaining_allowance()
        results.append(row)
    return results


def main(argv=None):
    args = parser().parse_args(argv); ledger = Ledger(ROOT / "ledger.sqlite"); router = FileRouter(ROOT, ledger)
    if args.station_new:
        from stations.duplicate import duplicate_station
        if not args.station_from: raise ValueError("--station-new requires --from")
        print(duplicate_station(args.station_from, args.station_new, description=args.description)); return 0
    if args.station_status: print(json.dumps(station_status(), indent=2)); return 0
    if args.chain:
        from stations.chain import run_chain
        print(json.dumps(run_chain(args.chain, execute=args.execute), indent=2)); return 0
    if args.vectorize:
        from stations.vectorize import vectorize_folder
        station = Path(args.station).resolve() if args.station else Path(args.vectorize).resolve().parent
        config = json.loads((station / "station.json").read_text())
        print(json.dumps(vectorize_folder(args.vectorize, station, execute=args.execute, profile_name=config["provider_profile"], model=config.get("embedding_model", "text-embedding-3-small")), indent=2)); return 0
    if args.vector_search:
        from stations.vectorize import VectorStore
        if not args.station: raise ValueError("--vector-search requires --station")
        config = json.loads((Path(args.station) / "station.json").read_text())
        store = VectorStore(args.station, profile_name=config["provider_profile"], model=config.get("embedding_model", "text-embedding-3-small"))
        print(json.dumps(store.search(args.vector_search, args.top_k), indent=2)); return 0
    if args.openrouter_watch:
        from stations.model_router import watch
        watch(once=args.once); return 0
    if args.station:
        from stations.runner import run_station
        print(json.dumps(run_station(args.station, execute=args.execute, profile_override=None if args.profile == "default" else args.profile), indent=2)); return 0
    if args.stats: print(json.dumps(ledger.stats(), indent=2)); return 0
    if args.health: print(json.dumps(health(args), indent=2)); return 0
    if args.scan:
        from actions.folder_scan import scan_folder
        print(json.dumps(scan_folder(args.scan), indent=2)); return 0
    if args.fis_actions:
        from actions.fis_parser import execute_actions, parse_actions
        print(json.dumps(execute_actions(args.fis_actions, router, True) if args.execute else parse_actions(args.fis_actions), indent=2)); return 0
    dry = not args.execute
    for value, method in ((args.move, router.move), (args.copy, router.copy), (args.rename, router.rename)):
        if value: print(json.dumps(method(*value, dry_run=dry), indent=2)); return 0
    if args.archive: print(json.dumps(router.archive(args.archive, dry_run=dry), indent=2)); return 0
    if args.undo is not None: print(json.dumps(router.undo(args.undo, dry_run=dry), indent=2)); return 0
    if args.convert:
        from watchers.conversion_dispatch import dispatch
        print(json.dumps(dispatch(args.convert, router, dry), indent=2)); return 0
    if args.nlp:
        from watchers.nlp_router import route
        print(json.dumps(route(args.nlp[0], args.nlp[1:]), indent=2)); return 0
    text = prompt_text(args)
    if args.route:
        destination = ROOT / args.route; destination.mkdir(parents=True, exist_ok=True); target = destination / f"prompt_{int(time.time())}.txt"
        if not dry: target.write_text(text, encoding="utf-8")
        print(json.dumps({"destination": str(target), "status": "dry_run" if dry else "success"}, indent=2)); return 0
    if args.batch:
        for path in sorted(Path(args.batch).glob("*")):
            if path.is_file(): api_call(args, path.read_text(encoding="utf-8"), ledger)
        return 0
    if args.conversation:
        if not sys.stdin.isatty(): raise ValueError("--conversation requires an interactive terminal")
        while True:
            try: text = input("You> ")
            except (EOFError, KeyboardInterrupt): break
            if text.strip(): api_call(args, text, ledger)
        return 0
    if not text: raise ValueError("No prompt supplied")
    api_call(args, text, ledger); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        print(f"error: {error}", file=sys.stderr); raise SystemExit(1)
