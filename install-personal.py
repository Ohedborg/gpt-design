#!/usr/bin/env python3
"""Deploy only GPT Design's code and metadata into the user's personal collection."""
import json
import shutil
from pathlib import Path

workspace = Path(__file__).resolve().parent
source = workspace / 'plugins' / 'gpt-design'
target = Path.home() / '.codex' / 'plugins' / 'gpt-design'
marketplace = Path.home() / '.agents' / 'plugins' / 'marketplace.json'
settings = Path.home() / '.codex' / 'gpt-design' / 'settings.json'
manifest = json.loads((source / 'plugin.json').read_text())
assert manifest['name'] == 'gpt-design'
if marketplace.exists():
    catalog = json.loads(marketplace.read_text())
    if catalog.get('name') != 'pk-design-tools':
        raise SystemExit('A different personal marketplace already exists; preserve it and merge this plugin deliberately.')
else:
    catalog = {'name': 'pk-design-tools', 'interface': {'displayName': 'PK Design Tools'}, 'plugins': []}
if target.exists():
    existing = json.loads((target / 'plugin.json').read_text())
    if existing.get('name') != 'gpt-design':
        raise SystemExit('The destination belongs to another plugin; nothing was changed.')
shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
# Remove code retired in 0.5.1; retain the separately configured design-system library.
for relative in ['skills/gpt-design/scripts/fig_import.py', 'skills/gpt-design/references/figma-files.md', 'skills/gpt-design/references/connectors.md', 'tests/test_fig_import.py']:
    (target / relative).unlink(missing_ok=True)
for relative in ['skills/gpt-design/scripts/fig-decoder', 'tests/fixtures']:
    retired = target / relative
    if retired.exists():
        shutil.rmtree(retired)
entry = {'name': 'gpt-design', 'source': {'source': 'local', 'path': './.codex/plugins/gpt-design'}, 'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}
catalog['plugins'] = [p for p in catalog['plugins'] if p.get('name') != 'gpt-design'] + [entry]
marketplace.parent.mkdir(parents=True, exist_ok=True)
if marketplace.exists():
    shutil.copy2(marketplace, marketplace.with_suffix('.json.backup'))
marketplace.write_text(json.dumps(catalog, indent=2) + '\n')
settings.parent.mkdir(parents=True, exist_ok=True)
preferences = json.loads(settings.read_text()) if settings.exists() else {'libraryPath': str(workspace / 'library')}
# Preserve existing access boundaries. The personal app initially uses this project only.
preferences.setdefault('allowedRoots', [str(workspace.parent)])
settings.write_text(json.dumps(preferences, indent=2) + '\n')
print(json.dumps({'plugin': manifest['name'], 'version': manifest['version'], 'personalSource': str(target), 'marketplace': str(marketplace), 'settings': str(settings)}, indent=2))
