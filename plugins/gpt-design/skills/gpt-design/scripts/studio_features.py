"""Stored source files, guidance, and isolated component preview artifacts."""
import base64
import copy
import datetime as dt
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import uuid

SOURCE_TYPES = {'.md', '.txt', '.ts', '.tsx', '.js', '.jsx', '.css', '.scss', '.json', '.vue', '.svelte', '.yaml', '.yml'}


def target_for(data, ident):
    if not isinstance(ident, str) or not re.fullmatch('[0-9a-f]{32}', ident):
        raise ValueError('Invalid system ID.')
    target = data / 'systems' / ident
    if target.is_symlink() or not (target / 'system.json').is_file():
        raise ValueError('Design system not found.')
    return target


def preserve_sources(source, target, system):
    import gpt_design as gd
    entries = {f['path']: f for f in system.get('files', [])}
    total = 0
    paths = []
    for root, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in gd.IGNORED and not (Path(root)/d).is_symlink())
        paths.extend(Path(root)/name for name in sorted(files))
    for p in paths:
        relative = p.relative_to(source)
        if any(part.startswith('.') or part in gd.IGNORED for part in relative.parts) or any(parent.is_symlink() for parent in [p, *p.parents] if parent == source or source in parent.parents):
            continue
        if not p.is_file() or not (p.suffix.lower() in SOURCE_TYPES or p.name in {'LICENSE', 'LICENSE-MIT'}):
            continue
        raw = p.read_bytes()
        if len(raw) > 4 * 1024 * 1024:
            continue
        total += len(raw)
        if total > gd.MAX_TOTAL or len(entries) > gd.MAX_FILES:
            raise ValueError('Source snapshot is too large. Choose a narrower source.')
        dest = target / 'source' / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        entries[relative.as_posix()] = {'path': relative.as_posix(), 'kind': p.suffix[1:] or 'text', 'bytes': len(raw), 'stored': True, 'sha256': hashlib.sha256(raw).hexdigest()}
    system['files'] = sorted(entries.values(), key=lambda f:f['path'])
    system['sourceStored'] = True


def read_file(data, ident, path, version=None):
    import gpt_design as gd
    target = target_for(data, ident)
    if version is not None:
        from releases import release_path
        target = release_path(data, ident, version)
    relative = gd.safe_relative(path, allow_generated=True)
    system = json.loads((target / 'system.json').read_text())
    entry = next((f for f in system.get('files', []) if f['path'] == path), None)
    asset = next((a for a in system.get('assets', []) if a['source'] == path), None)
    if not entry and not asset:
        raise ValueError('This file is not in the saved system.')
    file = target / ('assets' if asset else 'source') / relative
    if not gd.contained(file, target) or any(p.is_symlink() for p in [file, *file.parents] if p == target or target in p.parents) or not file.is_file():
        raise ValueError('This older snapshot has no stored file content. Restore its source snapshot from the recorded revision in chat.')
    if file.stat().st_size > gd.MAX_FILE:
        raise ValueError('File is too large to preview.')
    raw = file.read_bytes()
    result = {'path': path, 'bytes': len(raw), 'mimeType': mimetypes.guess_type(path)[0] or 'text/plain'}
    if asset or (entry and entry.get('binary')):
        if not asset:
            result['mimeType'] = 'application/octet-stream'
        result['base64'] = base64.b64encode(raw).decode()
    else:
        result['text'] = raw.decode('utf-8', errors='replace')
    return result


def preview_bundle(data, ident, version=None):
    target = target_for(data, ident)
    if version is not None:
        from releases import release_path
        target = release_path(data, ident, version)
    manifest = target / 'previews' / 'catalog.json'
    if not manifest.is_file():
        system = json.loads((target / 'system.json').read_text())
        if system.get('source', {}).get('kind') == 'figma-file':
            return {'available': False, 'message': 'Figma design definitions and properties. Connect a code library to create runnable component previews.'}
        return {'available': False, 'message': 'Live previews have not been built for this source. Ask GPT Design to prepare its component stories.'}
    catalog = json.loads(manifest.read_text())
    return {'available': True, **catalog, 'script': (target / 'previews/runtime.js').read_text(), 'css': (target / 'previews/runtime.css').read_text()}


def save_manifest(target, original, updated):
    import gpt_design as gd
    updated['revision'] = original.get('revision', 0) + 1
    updated['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    updated['status'] = 'locally-edited'
    history = target / 'history'
    history.mkdir(exist_ok=True)
    gd.write_json(history / ('revision-' + str(original.get('revision', 0)) + '.json'), original)
    css, omitted = gd.css_export(updated['tokens'])
    updated['cssOmitted'] = omitted
    gd.write_json(target / 'tokens.json', {'format':'gpt-design-tokens-v1','tokens':updated['tokens']})
    (target / 'tokens.css').write_text(css)
    temp = target / ('.system-' + uuid.uuid4().hex + '.json')
    gd.write_json(temp, updated)
    temp.replace(target / 'system.json')
    return updated


def maintain(data, ident, payload):
    import gpt_design as gd
    target = target_for(data, ident)
    with gd.system_lock(target):
        original = json.loads((target / 'system.json').read_text())
        if original.get('shared'):
            import github_library
            github_library.require_write(data, original)
        if payload.get('revision') != original.get('revision', 0):
            raise gd.RevisionConflict('This system changed in another window. Reopen it before saving.')
        updated = copy.deepcopy(original)
        action = payload.get('action')
        if action == 'guide':
            guide = payload.get('guide')
            if not isinstance(guide, dict) or set(guide) - {'summary','description','principles'}:
                raise ValueError('Provide summary, description and principles.')
            if any(not isinstance(v, str) or len(v) > 20000 for v in guide.values()):
                raise ValueError('Guidance must be text, at most 20,000 characters per field.')
            updated['guide'] = {**original.get('guide', {}), **guide, 'editedLocally':True}
        elif action == 'component-note':
            key, note = payload.get('key'), payload.get('note')
            if not isinstance(key, str) or not key or len(key)>300 or not isinstance(note,str) or len(note)>20000:
                raise ValueError('Provide a valid component and usage note.')
            updated.setdefault('componentNotes', {})[key] = note
        elif action == 'add-token':
            token = payload.get('token', {})
            name, value, typ = token.get('name'), token.get('value'), token.get('type','')
            if not isinstance(name,str) or not re.fullmatch(r'[-a-zA-Z_][a-zA-Z0-9_.-]{0,199}',name) or not isinstance(value,str) or not value.strip() or len(value)>16000:
                raise ValueError('Use a token name and a nonempty text value.')
            if typ not in {'color','fontFamily','fontWeight','fontSize','typography','dimension','shadow','number',''}:
                raise ValueError('Choose a supported token type.')
            context = token.get('context', ':root')
            if context not in {':root', '[data-theme="dark"]'}:
                raise ValueError('Choose Light or Dark.')
            if any(t['name']==name and t.get('context',':root')==context for t in original['tokens']):
                raise ValueError('A token with that name and theme already exists.')
            updated['tokens'].append({'name':name,'value':value,'type':typ,'context':context,'source':'Local additions','format':'css' if name.startswith('--') else 'json','group':gd.category(name,value,typ),'locallyAdded':True})
        else:
            raise ValueError('Unknown maintenance action.')
        return save_manifest(target, original, updated)
