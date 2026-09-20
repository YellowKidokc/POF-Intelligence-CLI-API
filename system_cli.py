"""Shared workflow front door; original cli.py remains available."""
import os
from pathlib import Path
import subprocess
import sys

def main(argv=None):
    root = Path(os.environ.get('PIPELINE_WORKFLOWS_ROOT', r'D:\GitHub\Canonizationv1\pipeline-workflows'))
    script = root / 'scripts' / 'unified.py'
    if not script.is_file():
        print(f'Workflow front door missing: {script}. Set PIPELINE_WORKFLOWS_ROOT.', file=sys.stderr)
        return 2
    env = dict(os.environ, POF_ROOT=str(Path(__file__).resolve().parent))
    return subprocess.run([sys.executable, str(script), *(sys.argv[1:] if argv is None else argv)], env=env).returncode

if __name__ == '__main__':
    raise SystemExit(main())
