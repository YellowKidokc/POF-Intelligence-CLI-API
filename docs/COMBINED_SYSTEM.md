# One system, two repositories

## Start here

Both repositories now expose `SYSTEM.bat` with the same commands. POF keeps its existing `cli.py` interface too. No older stations or workflow definitions were deleted or renamed.

```bat
SYSTEM.bat list
SYSTEM.bat providers
SYSTEM.bat run review-document D:\PipelineRuntime\my-paper
SYSTEM.bat run review-document D:\PipelineRuntime\my-paper --profile deepseek --execute
SYSTEM.bat run review-document D:\PipelineRuntime\my-paper --profile openai --execute
SYSTEM.bat assess-folder D:\SomeFolder
SYSTEM.bat assess-folder D:\SomeFolder --profile deepseek --execute
SYSTEM.bat station D:\SomeStation
SYSTEM.bat station D:\SomeStation --execute
SYSTEM.bat copy D:\source.md D:\destination\source.md
SYSTEM.bat move D:\source.md D:\destination\source.md --execute
SYSTEM.bat undo 1 --execute
SYSTEM.bat watch watch-folders.example.json --once
```

`run` previews by default without creating a packet or invoking a provider. Place selected documents in the packet's `INPUT` before execution. `review-document` produces a candidate review in `OUTPUT/pof-source-review` and stops with REVIEW. It does not publish or admit canon. `--profile` selects a configured POF profile; `--model` overrides its model. Existing workflow names still work.

`assess-folder` reads the selected folder's README, station/job definitions, launchers, and prompt Markdown. It reports that bounded scope. It does not recursively upload the corpus, credentials, or arbitrary files. Its AI assessment requires `--execute`.

`copy`, `move`, `rename`, and `undo` delegate to POF's FileRouter, preserving receipts and the undo ledger. Existing destinations are refused instead of overwritten. These commands do not organize any folder unless explicitly invoked.

## Ownership and overlap

| Overlapping capability | Owner for the integrated path | Integration decision |
|---|---|---|
| Provider calls / model profiles | POF | Workflows call the process-isolated POF bridge; no copied SDK implementation. |
| OpenRouter model discovery | POF | Existing `cli.py --openrouter-watch` and model router remain available. |
| Workflow dependency scheduling | pipeline-workflows | Existing orchestrator runs workflow definitions and resolves registered stations. |
| Folder watching | pipeline-workflows unified watcher | Durable source-copy handoff to workflows; legacy watchers remain available but must not watch the same inputs simultaneously. |
| Copy / move / rename / undo | POF | Shared front door delegates to the audited FileRouter. |
| POF station lifecycle and chains | POF | Existing inbox/waiting/outbox stations remain runnable through the shared front door. |
| Classification and corpus triage | pipeline-workflows | Uses the content-based implementation, not filename-length ranking. |
| Review / validation prompts | pipeline-workflows | Full-source review with the one admitted root axiom, God Is. |
| Run records | Both at their boundary | Workflow STATUS/MANIFEST plus POF call receipt; review output records source hash and receipt path. |

`integration-overlap.json` records exact same-relative-path overlap and file hashes. It is an inventory, not a claim that matching filenames mean matching responsibilities. Native legacy provider paths are retained for compatibility; the new integrated workflow uses POF. Historical health labels in old registries are not fresh live verification.

## Watcher operation

Copy `watch-folders.example.json` to a local configuration and set real folder paths. Set `enabled` to true for the selected entries. Use a state folder outside the watched source folders. Each watch can specify `profile` and `model`.

```bat
SYSTEM.bat watch D:\PipelineRuntime\watch-folders.json --execute
```

The watcher runs in the foreground until stopped. It waits for file metadata to settle across polls, copies the full source into a hash-identified packet, verifies the copy, and executes the selected workflow. Source files remain in place. An operating-system lock prevents overlapping watcher scans. State survives restarts. Review, failed, and interrupted/running entries are not automatically retried, preventing repeated billed requests. Inspect the recorded packet and explicitly resume/restart after resolving the issue. Changed content becomes a new packet. No production watcher was started during integration.

## Provider configuration

Credentials remain in POF; they are not copied into workflow definitions or bridge messages. Standard provider environment variables override INI credentials. Available implementations: OpenAI, DeepSeek, Claude, Gemini, Ollama, and OpenRouter. Use `providers` to see configured profiles; an implementation existing does not mean a key or model is configured. Add profiles to private configuration or use existing profiles and `--model`.

Full source is passed without arbitrary character cropping. Provider context capacity is finite: a failed or exhausted generation is not a complete review. POF local calls request a context allocation sized for the prompt. Successful mock tests do not establish a model's live long-document capacity. Cost figures are estimates; unlisted model prices may be unavailable.

Repo locations can be changed without editing code:

- `POF_ROOT`: execution/provider repository.
- `POF_CONFIG`: private provider INI path; standard key environment variables are also supported.
- `PIPELINE_WORKFLOWS_ROOT`: workflow repository, used by POF's front door.

Default local paths are the two repositories selected by David on 2026-09-20. Python dependencies for both repositories must be installed in the interpreter used by `SYSTEM.bat`.

## Personas

Persona reasoning instructions belong in `prompts/personas/`; each station references the applicable prompt. Operational responsibilities stay in station configuration: selected provider, allowed task, input/output contract, and review conditions. POF stations already have `prompt.md` beside `station.json`. Personality instructions must not silently authorize publishing, file movement, or canon admission. No personas have been activated by this integration.

## Baselines and previous fixes

Both repositories retain the local branch `baseline/pre-integration-20260920` at the pre-integration commit. The same baseline references are included in the overlap receipt. Earlier corrections from David's separate `D:\GitHub\pipeline-workflows` checkout were applied only after per-file patch compatibility checks to the selected Canonization checkout. That earlier checkout remains separate.

The legacy `PaperGrading` and `KnowledgeRefineryBackplane` packet templates still report NOT CONFIGURED. The new `review-document` route is the connected provider-backed review workflow; it does not pretend to implement every planned station in the larger backplane.

## Validation boundary

Integration validation uses temporary source files and mocked provider responses, plus real subprocess checks of the shared front door. No paid model calls or production watcher runs were performed. The existing YouTube refinery addendum tests have two failures (`no such table: videos`) reproduced on the untouched pre-integration baseline; this integration does not alter that unrelated database schema.
