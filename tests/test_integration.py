import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
import integration_service as service


def test_provider_preview_requires_no_sdk_or_api(tmp_path, monkeypatch):
    monkeypatch.setattr(service, 'settings_for', lambda r: {'provider': 'openai', 'model': 'fixture'})
    result = service.dispatch({'action': 'evaluate', 'text': 'x' * 15000 + 'TAIL'})
    assert result['status'] == 'preview'
    assert result['input_chars'] == 15004


@pytest.mark.parametrize('provider_name', ['openai', 'deepseek', 'claude', 'gemini', 'ollama', 'openrouter'])
def test_complete_provider_dispatch_and_receipt(tmp_path, monkeypatch, provider_name):
    import providers
    calls = []
    class Fake:
        def call(self, messages, *args):
            calls.append(messages)
            return SimpleNamespace(text='review', input_tokens=10, output_tokens=2)
        def estimate_cost(self, *args):
            return {'cost_usd': 0}
    monkeypatch.setattr(service, 'ROOT', tmp_path)
    monkeypatch.setattr(service, 'settings_for', lambda r: {'provider':provider_name, 'model':'fixture', 'api_key':'', 'base_url':'', 'temperature':0, 'max_tokens':100})
    monkeypatch.setattr(providers, 'create_provider', lambda *a: Fake())
    source = 'a' * 20000 + 'FINAL'
    result = service.evaluate({'text': source, 'execute': True})
    assert calls[0][-1]['content'] == source
    assert Path(result['receipt']).is_file()
    assert result['status'] == 'completed'
    assert result['provider'] == provider_name


def test_folder_task_inventory_omits_credentials(tmp_path):
    (tmp_path / 'README.md').write_text('task description')
    (tmp_path / 'config.ini').write_text('private credentials')
    (tmp_path / '.env').write_text('private credentials')
    result = service.folder_tasks(tmp_path)
    assert len(result['files']) == 1
    assert result['files'][0]['text'] == 'task description'


def test_process_bridge_provider_list():
    result = subprocess.run([sys.executable, str(Path(service.__file__))], input=json.dumps({'action':'providers'}),
        capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert 'api_key' not in result.stdout
    assert any(p['provider'] == 'deepseek' for p in payload['profiles'])


def test_routing_collision_and_undo(tmp_path, monkeypatch):
    monkeypatch.setattr(service, 'ROOT', tmp_path)
    source = tmp_path / 'a.md'; source.write_text('preserve')
    dest = tmp_path / 'b.md'; dest.write_text('existing')
    with pytest.raises(FileExistsError):
        service.dispatch({'action':'file', 'operation':'move', 'args':[str(source), str(dest)], 'execute':True})
    moved = tmp_path / 'moved.md'
    service.dispatch({'action':'file', 'operation':'move', 'args':[str(source), str(moved)], 'execute':True})
    result = service.dispatch({'action':'file', 'operation':'undo', 'args':[1], 'execute':True})
    assert result['status'] == 'success'
    assert source.read_text() == 'preserve'
    assert dest.read_text() == 'existing'
