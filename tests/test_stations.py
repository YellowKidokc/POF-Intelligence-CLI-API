import json
from pathlib import Path

import pytest

from providers.base import ProviderResponse
from stations.duplicate import duplicate_station
from stations.vectorize import VectorStore


class FakeProvider:
    model = "fake-model"
    def call(self, messages, model, temperature, max_tokens):
        return ProviderResponse('{"verdict":"keep","reason":"test"}\nDone.', 10, 4)
    def estimate_cost(self, input_tokens, output_tokens):
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": 2.0}
    def embed(self, texts, model):
        return [[float(len(text)), 1.0] for text in texts]


def make_root(tmp_path, monkeypatch):
    import cli
    import stations.runner as runner
    root = tmp_path / "repo"; root.mkdir()
    (root / "config.ini").write_text("[fake]\nPROVIDER=openai\nMODEL=fake-model\nAPI_KEY=\n")
    monkeypatch.setattr(runner, "ROOT", root); monkeypatch.setattr(cli, "ROOT", root)
    monkeypatch.setattr("providers.create_provider", lambda *args, **kwargs: FakeProvider())
    return root


def station(root, name, *, handoff="outbox", ceiling=10):
    path = root / "stations" / name
    for folder in ("inbox", "waiting", "outbox", "failed", "receipts"): (path / folder).mkdir(parents=True)
    config = {"name": name, "provider_profile": "fake", "model": "fake-model", "max_tokens": 100,
              "temperature": 0, "max_input_chars": 10, "input_globs": ["*.md"], "attachments": [],
              "output_format": "md", "output_name": "{stem}.result.{ext}", "categorize_by": "verdict",
              "on_success": handoff, "on_failure": "failed", "move_input_to": "outbox/_consumed",
              "cost_ceiling_usd": ceiling, "mode": "per_item"}
    (path / "station.json").write_text(json.dumps(config)); (path / "prompt.md").write_text("Do it")
    return path


def test_claim_lock_and_truncation_receipt(tmp_path, monkeypatch):
    root = make_root(tmp_path, monkeypatch); work = station(root, "one")
    (work / "inbox" / "a.md").write_text("0123456789EXTRA")
    from stations.runner import run_station
    result = run_station(work, execute=True)
    assert result["claimed"] == result["successes"] == 1
    assert not list((work / "waiting").iterdir())
    receipt = json.loads(next((work / "receipts").glob("*.json")).read_text())
    assert receipt["truncated"] is True and receipt["original_chars"] == 15 and receipt["used_chars"] == 10


def test_dry_run_touches_nothing(tmp_path, monkeypatch):
    root = make_root(tmp_path, monkeypatch); work = station(root, "one")
    item = work / "inbox" / "a.md"; item.write_text("hello"); before = item.stat().st_mtime_ns
    from stations.runner import run_station
    result = run_station(work)
    assert result["dry_run"] and item.exists() and item.stat().st_mtime_ns == before
    assert not list((work / "receipts").iterdir()) and not list((work / "waiting").iterdir())


def test_chain_handoff(tmp_path, monkeypatch):
    root = make_root(tmp_path, monkeypatch)
    first = station(root, "one", handoff="../two/inbox"); second = station(root, "two")
    (first / "inbox" / "a.md").write_text("hello")
    from stations.chain import run_chain
    results = run_chain([first, second], execute=True)
    assert [r["successes"] for r in results] == [1, 1]


def test_duplicate_omits_work_contents(tmp_path):
    source = station(tmp_path, "source"); (source / "inbox" / "private.md").write_text("work")
    target = duplicate_station(source, "copy", description="copy test")
    assert not list((target / "inbox").iterdir())
    assert json.loads((target / "station.json").read_text())["description"] == "copy test"


def test_cost_ceiling_stops_next_item(tmp_path, monkeypatch):
    root = make_root(tmp_path, monkeypatch); work = station(root, "one", ceiling=1)
    (work / "inbox" / "a.md").write_text("a"); (work / "inbox" / "b.md").write_text("b")
    from stations.runner import run_station
    result = run_station(work, execute=True)
    assert result["successes"] == 1 and result["skipped"] == 1 and result["status"] == "cost_ceiling_reached"
    assert (work / "inbox" / "b.md").exists()


def test_vector_store_skips_unchanged_hash(tmp_path):
    station_dir = tmp_path / "station"; station_dir.mkdir(); item = tmp_path / "result.md"; item.write_text("same")
    store = VectorStore(station_dir, model="fake-embed", provider=FakeProvider())
    assert store.add([item])["embedded"] == 1
    assert store.add([item]) == {"embedded": 0, "skipped": 1}
