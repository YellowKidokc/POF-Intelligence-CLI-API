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
