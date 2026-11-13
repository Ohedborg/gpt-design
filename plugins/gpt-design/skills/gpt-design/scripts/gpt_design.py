#!/usr/bin/env python3
"""GPT Design: dependency-free local import studio. Python 3.9+."""
import argparse
import contextlib
import fcntl
import studio_features as features
import releases
import github_library
import base64
import datetime as dt
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import tempfile
import threading
import copy
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = '0.6.1'
GROUPS = {'colors', 'spacing', 'assets', 'components'}
IGNORED = {'.git', '.next', '.codex', '.agents', 'node_modules', 'dist', 'build', '.cache', '__pycache__', '.venv', 'venv'}
ASSETS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.otf', '.pdf'}
TEXT = {'.css', '.scss', '.json', '.tsx', '.jsx', '.vue', '.svelte'}
SOURCE_TYPES = features.SOURCE_TYPES
MAX_FILE = 20 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024
MAX_FILES = 3000
STUDIO = Path(__file__).resolve().parents[1] / 'assets' / 'studio'


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def write_json(path, value):
    path.write_text(json_text(value) + '\n', encoding='utf-8')


def contained(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_relative(name, allow_generated=False):
    p = PurePosixPath(name)
    if not name or '\\' in name or p.is_absolute() or any(x in {'.', '..'} for x in name.split('/')):
        raise ValueError('Use a relative path without parent-directory segments.')
    if any(x.startswith('.') or (not allow_generated and x in IGNORED) for x in p.parts):
        raise ValueError('Hidden and generated files are excluded.')
    return p


def category(name, value, typ=''):
    n = name.lower()
    if typ.lower() in {'fontfamily', 'fontweight', 'typography', 'fontstyle', 'fontsize', 'lineheight'} or any(s in n for s in ['font', 'line-height', 'letter-spacing']):
        return 'colors'
    if any(s in n for s in ['space', 'spacing', 'radius', 'radii', 'shadow', 'size', 'width', 'height', 'border', 'gap']):
        return 'spacing'
    if typ.lower() in {'color', 'fontfamily', 'fontweight', 'typography', 'fontstyle', 'fontsize', 'lineheight'} or any(s in n for s in ['color', 'font', 'text', 'brand', 'background', 'foreground', 'palette', 'fill', 'stroke', 'line-height', 'letter-spacing']):
        return 'colors'
    if isinstance(value, str) and re.match(r'^(#|rgba?\(|hsla?\(|oklch\(|color\()', value):
        return 'colors'
    return 'spacing' if typ in {'dimension', 'shadow', 'border', 'number'} else 'colors'


def json_tokens(obj, source, prefix=(), inherited=''):
    result = []
    if not isinstance(obj, dict):
        return result
    typ = obj.get('$type', obj.get('type', inherited))
    if not isinstance(typ, str):
        typ = inherited
    if '$value' in obj or ('value' in obj and ('type' in obj or prefix)):
        value = obj.get('$value', obj.get('value'))
        name = '.'.join(prefix) or 'token'
        result.append({'name': name, 'value': value, 'type': str(typ), 'group': category(name, value, str(typ)), 'source': source, 'context': ':root', 'format': 'json', 'categoryInferred': True})
    else:
        for key, value in obj.items():
            if not key.startswith('$') and (key not in {'type', 'description', 'extensions'} or isinstance(value, dict)):
                result.extend(json_tokens(value, source, prefix + (key,), str(typ)))
    return result


def css_tokens(css, source):
    # Read nested block contexts without executing Sass or loading CSS imports.
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    result, stack, start, i = [], [], 0, 0
    quote, escaped, paren = None, False, 0
    while i < len(css):
        c = css[i]
        if escaped:
            escaped = False
        elif c == '\\':
            escaped = True
        elif quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == '(':
            paren += 1
        elif c == ')':
            paren = max(0, paren - 1)
        elif not paren and c in '{};':
            fragment = css[start:i].strip()
            if c == '{':
                stack.append(fragment)
            else:
                m = re.match(r'^(--[\w-]+)\s*:\s*(.+)$', fragment, re.S)
                if m and stack:
                    name, value = m.groups()
                    context = stack[-1]
                    result.append({'name': name, 'value': value.strip(), 'type': '', 'group': category(name, value), 'source': source, 'context': context, 'atRules': stack[:-1], 'format': 'css', 'categoryInferred': True})
                if c == '}' and stack:
                    stack.pop()
            start = i + 1
        i += 1
    return result


def css_export(tokens):
    out = ['/* GPT Design snapshot. Original selector contexts retained. */']
    omitted = 0
    for t in tokens:
        value = t['value']
        context = t.get('context', ':root')
        rules = t.get('atRules', [])
        name = t['name'] if t['format'] == 'css' else '--' + re.sub(r'[^a-zA-Z0-9_-]', '-', t['name'])
        # Complex structures, aliases, dynamic functions and nested Sass need interpretation.
        if (not isinstance(value, (str, int, float)) or isinstance(value, bool)
                or any(x in str(value) for x in ['{', '}', ';', '<', '>', '/*', '*/', '$', '@', '\\'])
                or re.search(r'(url|expression)\s*\(', str(value), re.I)
                or not re.fullmatch(r'[\w\s\[\]="\x27:.,#()>+~*-]+', context)
                or '&' in context or any(not re.match(r'^@(media|supports|layer)\b[^{};<>]*$', r) for r in rules)):
            omitted += 1
            continue
        source = re.sub(r'[^a-zA-Z0-9_./ -]', '_', t['source'])
        out.append('/* ' + source + ' */')
        out.extend(r + ' {' for r in rules)
        out.append(context + ' { ' + name + ': ' + str(value) + '; }')
        out.extend('}' for _ in rules)
    return '\n'.join(out) + '\n', omitted


def import_system(source, data, name, scope=None, source_meta=None):
    scope = set(GROUPS if scope is None else scope)
    if not scope or not scope <= GROUPS:
        raise ValueError('Choose at least one valid import group.')
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError('Give the design system a name (1–120 characters).')
    source, data = Path(source).resolve(), Path(data).resolve()
    if source.suffix.lower() == '.fig' and not source.is_dir():
        raise ValueError('Figma imports are no longer supported. Use a repository, local folder, or exported token and asset files.')
    if not source.is_dir():
        raise ValueError('The source folder does not exist.')
    data.mkdir(parents=True, exist_ok=True)
    connection = github_library.config(data)
    ident = uuid.uuid4().hex
    stage = Path(tempfile.mkdtemp(prefix='.import-', dir=data))
    system = {'schemaVersion': 1, 'revision': 0, 'id': ident, 'name': name.strip(), 'createdAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': source_meta or {'kind': 'local', 'path': str(source)}, 'scope': sorted(scope), 'tokens': [], 'assets': [], 'components': [], 'files': [], 'warnings': [], 'filesScanned': 0, 'status': 'snapshot'}
    notes = system['warnings']
    total, candidates = 0, 0
    try:
        for root, dirs, files in os.walk(source, followlinks=False):
            root = Path(root)
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in IGNORED and not (root / d).is_symlink() and not contained(root / d, data))
            for filename in sorted(files):
                p = root / filename
                if filename.startswith('.') or p.is_symlink() or p.suffix.lower() not in ASSETS | TEXT:
                    continue
                if filename in {'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock'}:
                    continue
                candidates += 1
                if candidates > MAX_FILES:
                    raise ValueError('This source exceeds 3,000 eligible files. Choose a narrower folder.')
                size = p.stat().st_size
                if size > MAX_FILE or (p.suffix.lower() in TEXT and size > 4 * 1024 * 1024):
                    notes.append('Skipped oversized file: ' + str(p.relative_to(source)))
                    continue
                total += size
                if total > MAX_TOTAL:
                    raise ValueError('This import exceeds 100 MB. Choose a narrower folder.')
                rel = p.relative_to(source).as_posix()
                suffix = p.suffix.lower()
                system['filesScanned'] += 1
                system['files'].append({'path': rel, 'bytes': size, 'kind': suffix[1:]})
                if suffix in ASSETS and 'assets' in scope:
                    dest = stage / 'assets' / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(p, dest)
                    system['assets'].append({'name': p.name, 'source': rel, 'path': 'assets/' + rel, 'bytes': size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'kind': 'font' if suffix in {'.ttf', '.otf', '.woff', '.woff2'} else 'guideline' if suffix == '.pdf' else 'image'})
                if suffix in {'.tsx', '.jsx', '.vue', '.svelte'} and 'components' in scope:
                    if not re.search(r'\.(test|spec|stories)\.', filename):
                        system['components'].append({'name': p.stem, 'source': rel, 'preview': 'source-only'})
                if suffix in {'.css', '.scss', '.json'} and scope & {'colors', 'spacing'}:
                    try:
                        content = p.read_text(encoding='utf-8')
                        found = json_tokens(json.loads(content), rel) if suffix == '.json' else css_tokens(content, rel)
                        system['tokens'].extend(t for t in found if t['group'] in scope)
                    except (ValueError, UnicodeError) as exc:
                        notes.append('Could not parse ' + rel + ': ' + str(exc)[:120])
        features.preserve_sources(source, stage, system)
        if not system['tokens'] and scope & {'colors', 'spacing'}:
            notes.append('No supported CSS variables or JSON token leaves were found. Visual guidelines and JS/TS configuration need review in chat.')
        if system['components']:
            notes.append('Components are a source inventory; live previews have not been built.')
        if any(a['kind'] == 'guideline' for a in system['assets']):
            notes.append('PDF guidelines were preserved as files. Their contents have not been extracted.')
        notes.append('Snapshot import: categories are inferred; aliases and source precedence require review. Upstream source changes are not imported automatically.')
        css, omitted = css_export(system['tokens'])
        if omitted:
            notes.append(str(omitted) + ' token(s) remain in JSON but need interpretation before CSS export.')
        system['cssOmitted'] = omitted
        write_json(stage / 'system.json', system)
        write_json(stage / 'tokens.json', {'format': 'gpt-design-tokens-v1', 'tokens': system['tokens']})
        (stage / 'tokens.css').write_text(css, encoding='utf-8')
        target = data / 'systems' / ident
        target.parent.mkdir(parents=True, exist_ok=True)
        stage.rename(target)
        if connection:
            return github_library.initialize_import(data,ident,connection)
        return system
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def parse_github(repo, ref='', folder=''):
    repo = repo.strip().removeprefix('https://github.com/').rstrip('/')
    if ':' in repo:
        repo, short_folder = repo.split(':', 1)
        folder = folder or short_folder
    if '@' in repo:
        repo, short_ref = repo.split('@', 1)
        ref = ref or short_ref
    repo = repo.removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or any(x in {'.', '..'} for x in repo.split('/')):
        raise ValueError('Enter owner/repo or owner/repo@branch:folder, without a tree URL.')
    if ref and (not re.fullmatch(r'[A-Za-z0-9_./-]+', ref) or ref.startswith('-') or '..' in ref):
        raise ValueError('Use a Git branch, tag, or commit without special characters.')
    if folder:
        safe_relative(folder, allow_generated=True)
    return repo, ref, folder


def fetch_public(repo, ref, folder, temp):
    repo, ref, folder = parse_github(repo, ref, folder)
    headers = {'User-Agent': 'GPT-Design/' + VERSION, 'Accept': 'application/vnd.github+json'}
    def get(url, limit):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    raise ValueError('Repository archive is too large; use a local folder.')
                return raw
        except urllib.error.HTTPError as exc:
            raise ValueError('GitHub returned HTTP ' + str(exc.code) + '. For private repositories, use an authorized local checkout or continue through GitHub in chat.') from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ValueError('Could not reach GitHub. Check your connection or use a local checkout.') from exc
    # Resolve to a commit so the saved snapshot has immutable provenance.
    if not ref:
        meta = json.loads(get('https://api.github.com/repos/' + repo, 1024 * 1024))
        ref = meta['default_branch']
    commit = json.loads(get('https://api.github.com/repos/' + repo + '/commits/' + urllib.parse.quote(ref, safe=''), 2 * 1024 * 1024))['sha']
    raw = get('https://codeload.github.com/' + repo + '/zip/' + commit, 40 * 1024 * 1024)
    size, count = 0, 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            parts = PurePosixPath(item.filename).parts
            if len(parts) < 2:
                continue
            relative = PurePosixPath(*parts[1:])
            try:
                safe_relative(str(relative), allow_generated=True)
            except ValueError:
                continue
            if folder:
                try:
                    relative = relative.relative_to(PurePosixPath(folder))
                except ValueError:
                    continue
            try:
                safe_relative(str(relative))
            except ValueError:
                continue
            if relative.suffix.lower() not in ASSETS | TEXT | SOURCE_TYPES and relative.name not in {'LICENSE','LICENSE-MIT'} or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                continue
            count += 1
            size += item.file_size
            if size > MAX_TOTAL or item.file_size > MAX_FILE or count > MAX_FILES:
                raise ValueError('Repository selection is too large; choose a narrower folder.')
            dest = temp / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as src, dest.open('wb') as out:
                shutil.copyfileobj(src, out)
    if not count:
        raise ValueError('No supported files were found in that repository folder.')
    return {'kind': 'github', 'repository': repo, 'ref': ref, 'commit': commit, 'folder': folder, 'url': 'https://github.com/' + repo + '/tree/' + commit}


def summaries(data):
    result = []
    for p in (data / 'systems').glob('*/system.json'):
        try:
            s = json.loads(p.read_text())
            result.append({k: s[k] for k in ['id', 'name', 'createdAt', 'source', 'scope']} | {'counts': {k: len(s[k]) for k in ['tokens', 'assets', 'components']}, 'pendingUpload':s.get('pendingUpload'), 'shared':s.get('shared')})
        except (OSError, ValueError, KeyError):
            continue
    return sorted(result, key=lambda s: s['createdAt'], reverse=True)


class RevisionConflict(ValueError):
    pass


@contextlib.contextmanager
def system_lock(target):
    with (target / '.edit.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def edit_system(data, ident, payload):
    with system_lock(features.target_for(data, ident)):
        return _edit_system_unlocked(data, ident, payload)


def _edit_system_unlocked(data, ident, payload):
    """Caller serializes edits. Keep prior manifests; source repositories are never changed."""
    target = data / 'systems' / ident
    original = json.loads((target / 'system.json').read_text())
    if original.get('shared'):
        github_library.require_write(data,original)
    if payload.get('revision') != original.get('revision', 0):
        raise RevisionConflict('This system changed in another window. Reload it before editing again.')
    changes = payload.get('changes')
    if not isinstance(changes, list) or not changes or len(changes) > 20000:
        raise ValueError('Provide one or more token changes.')
    updated = copy.deepcopy(original)
    removed, seen = set(), set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError('Invalid token change.')
        index = change.get('index')
        if type(index) is not int or index < 0 or index >= len(updated['tokens']) or index in seen:
            raise ValueError('Invalid or duplicate token index.')
        seen.add(index)
        if change.get('delete') is True:
            removed.add(index)
            continue
        if 'value' not in change:
            raise ValueError('A token value is required.')
        value = change['value']
        try:
            encoded = json.dumps(value, allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError('Use a valid JSON token value.')
        if value is None or len(encoded) > 16000 or (isinstance(value, str) and not value.strip()):
            raise ValueError('Token values must be nonempty and under 16,000 characters.')
        t = updated['tokens'][index]
        t.setdefault('importedValue', copy.deepcopy(t['value']))
        t['value'] = value
        t['locallyEdited'] = value != t['importedValue']
    updated['tokens'] = [t for i, t in enumerate(updated['tokens']) if i not in removed]
    updated['revision'] = original.get('revision', 0) + 1
    updated['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    updated['status'] = 'locally-edited'
    css, omitted = css_export(updated['tokens'])
    updated['cssOmitted'] = omitted
    updated['warnings'] = [w for w in updated.get('warnings', []) if not re.match(r'^\d+ token\(s\) remain in JSON', w)]
    if omitted:
        updated['warnings'].append(str(omitted) + ' token(s) remain in JSON but need interpretation before CSS export.')
    history = target / 'history'
    history.mkdir(exist_ok=True)
    write_json(history / ('revision-' + str(original.get('revision', 0)) + '.json'), original)
    # The manifest is canonical. Atomically replace it after preparing the derived exports.
    write_json(target / 'tokens.json', {'format': 'gpt-design-tokens-v1', 'tokens': updated['tokens']})
    (target / 'tokens.css').write_text(css, encoding='utf-8')
    temp = target / ('.system-' + uuid.uuid4().hex + '.json')
    write_json(temp, updated)
    temp.replace(target / 'system.json')
    return updated


def handler_for(data, allowed, token):
    edit_lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Do not log session credentials or imported data.

        def reply(self, code, body, content_type='application/json'):
            raw = json_text(body).encode() if content_type == 'application/json' else body
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; frame-src 'self' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            return secrets.compare_digest(self.headers.get('X-GPT-Design-Token', ''), token)

        def valid_host(self):
            return self.headers.get('Host') in {'127.0.0.1:' + str(self.server.server_port), 'localhost:' + str(self.server.server_port)}

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {'error': 'Invalid host.'})
            path = urllib.parse.urlparse(self.path).path
            if path.startswith('/api/'):
                if not self.authorized():
                    return self.reply(401, {'error': 'Reopen the studio from its session link.'})
                if path == '/api/github':
                    return self.reply(200, github_library.status(data))
                feature_match = re.fullmatch(r'/api/systems/([0-9a-f]{32})/(file|preview)', path)
                if feature_match:
                    try:
                        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                        result = features.read_file(data, feature_match[1], params.get('path', [''])[0], params.get('version', [None])[0]) if feature_match[2] == 'file' else features.preview_bundle(data, feature_match[1], params.get('version', [None])[0])
                        return self.reply(200, result)
                    except (ValueError, OSError) as exc:
                        return self.reply(400, {'error':str(exc)[:500]})
                release_match = re.fullmatch(r'/api/systems/([0-9a-f]{32})/releases(?:/([0-9]+)(?:/(tokens\.css|tokens\.json|system\.json))?)?', path)
                if release_match:
                    try:
                        result = releases.read(data, release_match[1], release_match[2], release_match[3] or 'system.json') if release_match[2] else releases.history(data, release_match[1])
                        return self.reply(200, result)
                    except (ValueError, OSError) as exc:
                        return self.reply(400, {'error':str(exc)[:500]})
                if path == '/api/systems':
                    shared_status=github_library.sync(data)
                    return self.reply(200, {'systems': summaries(data), 'library': str(data), 'allowedRoots': [str(p) for p in allowed], 'github':shared_status})
                match = re.fullmatch(r'/api/systems/([0-9a-f]{32})(?:/(tokens\.json|tokens\.css|system\.json))?', path)
                if match:
                    p = data / 'systems' / match[1] / 'system.json'
                    if p.is_file():
                        system = json.loads(p.read_text())
                        if match[2] == 'tokens.css':
                            return self.reply(200, css_export(system['tokens'])[0].encode(), 'text/css; charset=utf-8')
                        if match[2] == 'tokens.json':
                            return self.reply(200, {'format': 'gpt-design-tokens-v1', 'tokens': system['tokens']})
                        return self.reply(200, github_library.access(data,system))
                return self.reply(404, {'error': 'Not found.'})
            files = {'/features.js': 'features.js', '/features.css': 'features.css', '/': 'index.html', '/app.js': 'app.js', '/workspace.js': 'workspace.js', '/workspace.css': 'workspace.css', '/style.css': 'style.css'}
            if path in files:
                p = STUDIO / files[path]
                return self.reply(200, p.read_bytes(), mimetypes.guess_type(p.name)[0] + '; charset=utf-8')
            return self.reply(404, {'error': 'Not found.'})

        def do_POST(self):
            if not self.valid_host() or not self.authorized():
                return self.reply(403, {'error': 'Reopen the studio from its session link.'})
            if self.headers.get('Origin') not in {None, 'http://' + self.headers.get('Host', '')}:
                return self.reply(403, {'error': 'Cross-origin requests are not allowed.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size <= 0 or size > 30 * 1024 * 1024:
                    raise ValueError('Upload must be smaller than 30 MB per request.')
                if self.headers.get_content_type() != 'application/json':
                    raise ValueError('Expected JSON.')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Expected a request object.')
                if self.path == '/api/github/connect':
                    return self.reply(200, github_library.connect(data,payload))
                if self.path == '/api/github/sync':
                    return self.reply(200, github_library.sync(data,force=True))
                if self.path == '/api/github/disconnect':
                    return self.reply(200, github_library.disconnect(data))
                refresh_draft=re.fullmatch(r'/api/systems/([0-9a-f]{32})/start-from-latest',self.path)
                if refresh_draft:
                    return self.reply(200,github_library.start_from_latest(data,refresh_draft[1],payload.get('revision')))
                share=re.fullmatch(r'/api/systems/([0-9a-f]{32})/share',self.path)
                if share:
                    return self.reply(200,github_library.share_publication(data,share[1],payload.get('revision')))
                publication = re.fullmatch(r'/api/systems/([0-9a-f]{32})/publish', self.path)
                if publication:
                    return self.reply(200, releases.publish(data, publication[1], payload))
                maintenance = re.fullmatch(r'/api/systems/([0-9a-f]{32})/maintain', self.path)
                if maintenance:
                    return self.reply(200, github_library.access(data,features.maintain(data, maintenance[1], payload)))
                match = re.fullmatch(r'/api/systems/([0-9a-f]{32})/edit', self.path)
                if match:
                    with edit_lock:
                        result = edit_system(data, match[1], payload)
                    return self.reply(200, github_library.access(data,result))
                if self.path != '/api/import':
                    return self.reply(404, {'error': 'Not found.'})
                kind, name, scope = payload.get('kind'), payload.get('name', ''), checked_scope(payload)
                if kind == 'local':
                    source = Path(payload.get('path', '')).expanduser().resolve()
                    if not any(contained(source, root) for root in allowed):
                        raise ValueError('This folder is outside the studio’s allowed project folders. Ask GPT Design in chat to open it with access to that folder.')
                    result = import_system(source, data, name, scope)
                elif kind in {'upload', 'github'}:
                    with tempfile.TemporaryDirectory(prefix='gpt-design-') as tmp:
                        source = Path(tmp)
                        if kind == 'github':
                            meta = fetch_public(payload.get('repo', ''), payload.get('ref', ''), payload.get('folder', ''), source)
                        else:
                            files = payload.get('files', [])
                            if not isinstance(files, list) or not files or len(files) > MAX_FILES:
                                raise ValueError('Choose 1–3,000 files.')
                            seen = set()
                            for entry in files:
                                relative = safe_relative(entry['name'])
                                if relative.suffix.lower() == '.fig':
                                    raise ValueError('Figma imports are no longer supported. Upload exported tokens, assets, or component source instead.')
                                if relative.suffix.lower() not in ASSETS | TEXT | SOURCE_TYPES and relative.name not in {'LICENSE','LICENSE-MIT'}:
                                    raise ValueError('Unsupported file: ' + str(relative))
                                if str(relative).casefold() in seen:
                                    raise ValueError('Duplicate uploaded filename: ' + str(relative))
                                seen.add(str(relative).casefold())
                                blob = base64.b64decode(entry['content'], validate=True)
                                if len(blob) > MAX_FILE:
                                    raise ValueError('Each file must be smaller than 20 MB.')
                                dest = source / relative
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                dest.write_bytes(blob)
                            meta = {'kind': 'upload', 'files': len(files)}
                        result = import_system(source, data, name, scope, meta)
                else:
                    raise ValueError('Choose GitHub, a local folder, or uploaded files.')
                self.reply(201, result)
            except RevisionConflict as exc:
                self.reply(409, {'error': str(exc)})
            except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
                self.reply(400, {'error': str(exc)[:500]})
    return Handler


def checked_scope(payload):
    scope = payload.get('scope', sorted(GROUPS))
    if not isinstance(scope, list) or not scope or not all(isinstance(s, str) and s in GROUPS for s in scope):
        raise ValueError('Choose at least one import group.')
    return sorted(set(scope))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['serve', 'import', 'list']:
        cmd = sub.add_parser(name)
        cmd.add_argument('--data', type=Path, required=True)
        if name == 'serve':
            cmd.add_argument('--port', type=int, default=0)
            cmd.add_argument('--allow-root', type=Path, action='append', required=True)
        elif name == 'import':
            cmd.add_argument('--source', type=Path, required=True)
            cmd.add_argument('--name', required=True)
            cmd.add_argument('--scope', default='colors,spacing,assets,components')
    args = parser.parse_args()
    if args.command == 'import':
        print(json_text(import_system(args.source, args.data, args.name, args.scope.split(','))))
    elif args.command == 'list':
        print(json_text(summaries(args.data)))
    else:
        data = args.data.expanduser().resolve()
        data.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(data, [p.expanduser().resolve() for p in args.allow_root], token))
        print('GPT Design ' + VERSION + '\nhttp://127.0.0.1:' + str(server.server_port) + '/#token=' + token, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()


if __name__ == '__main__':
    main()
