# POF Intelligence CLI

A lightweight Python 3.10+ command-line system for multi-provider chat, audited and reversible file operations, folder manifests, FIS action extraction, conversion dispatch, and local NLP routing.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -r requirements.txt
```

Put credentials in `config.ini` (which should remain private in production), then run `python cli.py --dry-run` to inspect a request without sending it.

## Safety model

Filesystem commands are previews unless `--execute` is explicitly supplied. Every preview and execution creates a JSON receipt. Moves, renames, and archives are appended to `undo_log.jsonl`; reverse them with `--undo [COUNT] --execute`. Nothing deletes files.

```bash
python cli.py --move source.md destination/       # preview
python cli.py --move source.md destination/ --execute
python cli.py --scan some/folder
python cli.py --fis-actions FIS.html
python cli.py --convert report.pdf --execute
python cli.py --nlp contradiction first.md second.md
python cli.py --stats
python cli.py --health
```

The provider SDKs are imported only when selected. OpenAI, DeepSeek, Claude, Gemini, and Ollama profiles share the same CLI surface. Watch registries live under `registries/`; conversion only dispatches files to the existing NAS station and does not implement converters or Playwright workers.

## Stations

A station is a duplicatable folder containing one job definition (`station.json`), its prompt, and an auditable lifecycle: `inbox/` → `waiting/` → `outbox/` (or `failed/`), with one JSON receipt per processed item. Moving into `waiting/` is the claim lock; abandoned claims are recovered after 15 minutes. Runs preview by default and only mutate files with `--execute`.

```bash
python cli.py --station stations/01_duplicate_live_copies
python cli.py --station stations/01_duplicate_live_copies --execute
python cli.py --station-new 02_orphan_good_page --from stations/_TEMPLATE
python cli.py --station-status
python cli.py --chain stations/chain.json --execute
python cli.py --vectorize stations/01_duplicate_live_copies/outbox --station stations/01_duplicate_live_copies --execute
python cli.py --vector-search "canonical duplicate" --station stations/01_duplicate_live_copies
python cli.py --openrouter-watch --once
```

To build a chain, set station N's `on_success` to `../02_next_station/inbox`, list both folders in a root-level chain file such as `{"name":"review","stations":["01_duplicate_live_copies","02_next_station"]}`, and run it with `--chain`. The first station retains its result and sends an audited copy to the next inbox. Aggregate stations use `sources` (files, folders, or globs, including read-only shares) and emit one report without modifying their sources. See `stations/INPUT_FORMAT.md` for anomaly inputs and `stations/PLANNED.md` for jobs ready to duplicate.

## Shared system entry point

Run `SYSTEM.bat list` for readable workflow names. Both repositories expose the same front door for workflow runs, folder watching, folder-task assessment, provider profiles, and audited file routing. See [Combined system guide](docs/COMBINED_SYSTEM.md) for ownership, setup, examples, and limits.
