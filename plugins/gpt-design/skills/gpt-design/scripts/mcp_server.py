#!/usr/bin/env python3
"""Local MCP stdio adapter for the GPT Design studio. No remote hosting required."""
import argparse
import base64
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import gpt_design as gd

VERSION = '0.6.1'
URI = 'ui://gpt-design/studio.html'
MIME = 'text/html;profile=mcp-app'
ROOT = Path(__file__).resolve().parents[3]


def schema(properties=None, required=None):
    return {'type': 'object', 'properties': properties or {},
            'required': required or [], 'additionalProperties': False}


def tool(name, title, description, inputs=None, read=True, destructive=False, network=False):
    return {'name': name, 'title': title, 'description': description,
            'inputSchema': inputs or schema(),
            'annotations': {'readOnlyHint': read, 'destructiveHint': destructive,
                            'idempotentHint': read, 'openWorldHint': network},
            '_meta': {'ui': {'visibility': ['app', 'model']}}}


RELEASE_VERSION = {'type':'integer','minimum':1}
ID = {'type': 'string', 'pattern': '^[0-9a-f]{32}$'}
PAYLOAD = {'type': 'object', 'description': 'Studio action parameters.'}
TOOLS = [
    tool('open_studio', 'GPT Design', 'Open GPT Design. With multiple systems, ask which to use unless already explicitly selected for this task. Pass that ID as system_id; otherwise show the chooser. Never infer from recency. Opening checks for GitHub updates and retries already queued initial uploads.', schema({'system_id': ID}), read=False, network=True),
    tool('get_file', 'Read a source file', 'Read a preserved source, guideline or asset file from the selected design system.', schema({'id': ID, 'path': {'type':'string'}, 'version': RELEASE_VERSION}, ['id','path'])),
    tool('get_preview', 'Load component playground', 'Read the compiled, isolated component playground for a design system.', schema({'id': ID, 'version': RELEASE_VERSION}, ['id'])),
    tool('maintain_system', 'Maintain design-system guidance', 'Save overview, component usage notes or a new token locally with revision history.', schema({'id': ID, 'payload': PAYLOAD}, ['id','payload']), read=False),
    tool('list_releases', 'Version history', 'List immutable local design-system publications, separate from plugin versions.', schema({'id': ID}, ['id'])),
    tool('get_release', 'Read a published design system', 'Read an immutable publication or its exports. Use published versions when consuming a design system.', schema({'id': ID, 'version': RELEASE_VERSION, 'file': {'type':'string','enum':['system.json','tokens.json','tokens.css']}}, ['id','version'])),
    tool('publish_system', 'Publish a design-system version', 'Publish the saved draft or a rollback. When a GitHub library is connected, this uploads the publication to that repository for other users. Requires repository write access. Without a connection, publishes locally. Does not update plugin software.', schema({'id': ID, 'payload': PAYLOAD}, ['id','payload']), read=False, network=True),
    tool('share_publication', 'Share an existing publication', 'Upload this system’s existing local published versions to the connected GitHub library. Preserve unpublished draft changes locally and retain version numbers. Requires explicit sharing or backup intent.', schema({'id':ID,'revision':{'type':'integer','minimum':0}}, ['id','revision']), read=False, network=True),
    tool('library_status', 'GitHub library status', 'Read the shared repository connection, sync status and local authentication availability.'),
    tool('connect_library', 'Connect GitHub library', 'Connect an explicitly selected GitHub repository and design-systems folder. Downloads published systems and resumes queued initial uploads for that destination. New imports automatically upload version 1; existing local drafts are not uploaded. Requires local GitHub authentication for private repositories.', schema({'payload': PAYLOAD}, ['payload']), read=False, network=True),
    tool('sync_library', 'Sync published design systems', 'Fetch the latest published GitHub versions before selecting a system for a new task. Retry queued initial uploads to their original destination. Preserve unpublished drafts and already pinned task versions. Report any sync error and cached-version use.', read=False, network=True),
    tool('disconnect_library', 'Disconnect GitHub library', 'Disconnect only when requested. Keep local cached releases and drafts.', read=False),
    tool('start_from_latest', 'Refresh a shared draft', 'Back up the entire local draft, then start from the latest synced publication. Use when resolving an explicitly requested stale-draft update.', schema({'id':ID,'revision':{'type':'integer','minimum':0}}, ['id','revision']), read=False),
    tool('list_systems', 'List design systems', 'List local and shared design systems; automatically checks for published updates and retries already queued initial uploads.', read=False, network=True),
    tool('get_system', 'Read a design system', 'Read tokens, assets, components and provenance.', schema({'id': ID}, ['id'])),
    tool('import_system', 'Import a design system', 'Create a new snapshot from a public GitHub repository, allowed local folder, or uploaded token, asset and component source files. When a GitHub library is connected, automatically creates and uploads version 1 to that repository. A failed upload stays queued locally for automatic retry; report pendingUpload instead of claiming it is shared. Never executes imported source code.', schema({'payload': PAYLOAD}, ['payload']), read=False, network=True),
    tool('edit_system', 'Save token edits', 'Save token edits or removals in a local snapshot, preserving revision history. Does not change source files.', schema({'id': ID, 'revision': {'type': 'integer', 'minimum': 0}, 'changes': {'type': 'array', 'minItems': 1, 'items': {'type': 'object'}}}, ['id', 'revision', 'changes']), read=False, destructive=True),
    tool('export_system', 'Export design tokens', 'Read JSON or CSS exports from the current saved revision.', schema({'id': ID, 'file': {'type': 'string', 'enum': ['tokens.json', 'tokens.css', 'system.json']}}, ['id', 'file'])),
]
ICON = [{'src': 'data:image/svg+xml;base64,' + base64.b64encode((ROOT / 'assets/icon.svg').read_bytes()).decode(), 'mimeType': 'image/svg+xml', 'sizes': ['any']}]
TOOLS[0]['icons'] = ICON
TOOLS[0]['_meta'] = {'ui': {'resourceUri': URI, 'visibility': ['app', 'model']},
                     'openai/ui': {'entrypoints': [{'type': 'global'}, {'type': 'thread'}]}}


def bundled_html():
    html = (gd.STUDIO / 'index.html').read_text()
    for name in ['style.css', 'workspace.css', 'features.css']:
        html = html.replace('<link rel="stylesheet" href="/' + name + '">', '<style>' + (gd.STUDIO / name).read_text() + '</style>')
    for name in ['workspace.js', 'features.js', 'app.js']:
        html = html.replace('<script defer src="/' + name + '"></script>', '')
    scripts = []
    for name in ['mcp-bridge.js', 'workspace.js', 'features.js', 'app.js']:
        text = (gd.STUDIO / name).read_text()
        scripts.append('<script>' + re.sub(r'</script', r'<\\/script', text, flags=re.I) + '</script>')
    return html.replace('</body>', ''.join(scripts) + '</body>')


class Studio:
    def __init__(self, data, allowed):
        self.data = data.resolve()
        self.allowed = [p.resolve() for p in allowed]
        self.server = None

    def start(self):
        if self.server:
            return
        self.data.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), gd.handler_for(self.data, self.allowed, self.token))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def close(self):
        if self.server:
            self.server.shutdown()
            self.worker.join()
            self.server.server_close()
            self.server = None

    def request(self, path, payload=None, text=False):
        self.start()
        headers = {'X-GPT-Design-Token': self.token, 'Content-Type': 'application/json'}
        body = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
        req = urllib.request.Request('http://127.0.0.1:' + str(self.server.server_port) + path, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                raw = response.read().decode()
                return raw if text else json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise ValueError(json.loads(exc.read()).get('error', 'Studio request failed.')) from None

    def call(self, name, args):
        definition = next((t for t in TOOLS if t['name'] == name), None)
        if not definition:
            raise ValueError('Unknown tool.')
        inputs = definition['inputSchema']
        if not isinstance(args, dict) or set(args) - set(inputs['properties']) or set(inputs['required']) - set(args):
            raise ValueError('Invalid or missing tool arguments.')
        if 'id' in args and (not isinstance(args['id'], str) or not re.fullmatch(ID['pattern'], args['id'])):
            raise ValueError('Invalid design-system ID.')
        if 'payload' in args and not isinstance(args['payload'], dict):
            raise ValueError('Expected an import request object.')
        if name in {'open_studio', 'list_systems'}:
            result = self.request('/api/systems')
            if name == 'open_studio':
                ident = args.get('system_id')
                if ident is not None and not any(s['id'] == ident for s in result['systems']):
                    raise ValueError('The selected design system was not found. List systems and ask the user to choose.')
                result['selectedSystemId'] = ident
                result['selectionRequired'] = ident is None and len(result['systems']) > 1
            return result
        if name == 'share_publication':
            return self.request('/api/systems/'+args['id']+'/share', {'revision':args['revision']})
        if name == 'library_status':
            return self.request('/api/github')
        if name == 'connect_library':
            return self.request('/api/github/connect', args['payload'])
        if name in {'sync_library','disconnect_library'}:
            return self.request('/api/github/' + ('sync' if name=='sync_library' else 'disconnect'), {})
        if name == 'start_from_latest':
            return self.request('/api/systems/'+args['id']+'/start-from-latest', {'revision':args['revision']})
        if name == 'list_releases':
            return self.request('/api/systems/' + args['id'] + '/releases')
        if name == 'get_release':
            return self.request('/api/systems/' + args['id'] + '/releases/' + str(args['version']) + '/' + args.get('file','system.json'))
        if name == 'publish_system':
            return self.request('/api/systems/' + args['id'] + '/publish', args['payload'])
        version_query = ('version=' + str(args['version'])) if 'version' in args else ''
        if name == 'get_file':
            import urllib.parse
            return self.request('/api/systems/' + args['id'] + '/file?path=' + urllib.parse.quote(args['path'], safe='') + '&' + version_query)
        if name == 'get_preview':
            return self.request('/api/systems/' + args['id'] + '/preview?' + version_query)
        if name == 'maintain_system':
            return self.request('/api/systems/' + args['id'] + '/maintain', args['payload'])
        if name == 'get_system':
            return self.request('/api/systems/' + args['id'])
        if name == 'edit_system':
            return self.request('/api/systems/' + args['id'] + '/edit', {'revision': args['revision'], 'changes': args['changes']})
        if name == 'import_system':
            return self.request('/api/import', args['payload'])
        if args['file'] not in {'tokens.json', 'tokens.css', 'system.json'}:
            raise ValueError('Unknown export format.')
        return {'text': self.request('/api/systems/' + args['id'] + '/' + args['file'], text=True),
                'mimeType': 'text/css' if args['file'].endswith('.css') else 'application/json'}


def dispatch(studio, method, params):
    if method == 'initialize':
        requested = params.get('protocolVersion')
        version = requested if requested in {'2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25'} else '2025-11-25'
        return {'protocolVersion': version, 'capabilities': {'tools': {}, 'resources': {}},
                'serverInfo': {'name': 'gpt-design', 'title': 'GPT Design', 'version': VERSION, 'icons': ICON}}
    if method == 'ping':
        return {}
    if method == 'tools/list':
        return {'tools': TOOLS}
    if method == 'resources/list':
        return {'resources': [{'uri': URI, 'name': 'GPT Design', 'mimeType': MIME}]}
    if method == 'resources/templates/list':
        return {'resourceTemplates': []}
    if method == 'resources/read':
        if params.get('uri') != URI:
            raise ValueError('Unknown resource.')
        return {'contents': [{'uri': URI, 'mimeType': MIME, 'text': bundled_html(),
                             '_meta': {'ui': {'prefersBorder': False, 'csp': {'connectDomains': [], 'resourceDomains': [], 'frameDomains': ["'self'"]}},
                                       'openai/ui': {'preferredDisplayMode': 'fullscreen', 'availableDisplayModes': ['inline', 'fullscreen']}}}]}
    if method == 'tools/call':
        try:
            result = studio.call(params.get('name'), params.get('arguments', {}))
            return {'content': [{'type': 'text', 'text': gd.json_text(result)}], 'structuredContent': result}
        except (ValueError, TypeError, KeyError, OSError) as exc:
            return {'isError': True, 'content': [{'type': 'text', 'text': str(exc)[:500]}]}
    raise LookupError('Method not found.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--allow-root', type=Path, action='append')
    args = parser.parse_args()
    settings_path = Path.home() / '.codex/gpt-design/settings.json'
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    data = (args.data or Path(settings.get('libraryPath', Path.home() / '.codex/gpt-design/library'))).expanduser()
    # Without configured roots, allow only the library. Do not infer access to the entire home directory.
    allowed = args.allow_root or [Path(p).expanduser() for p in settings.get('allowedRoots', [str(data)])]
    studio = Studio(data, allowed)
    try:
        while True:
            line = sys.stdin.buffer.readline(30 * 1024 * 1024 + 1)
            if not line:
                break
            if len(line) > 30 * 1024 * 1024:
                break
            request = None
            try:
                request = json.loads(line)
                if not isinstance(request, dict) or request.get('jsonrpc') != '2.0':
                    raise ValueError('Invalid JSON-RPC request.')
                if 'id' not in request:
                    continue
                result = dispatch(studio, request.get('method'), request.get('params', {}))
                response = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
            except (ValueError, LookupError, TypeError) as exc:
                response = {'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None,
                            'error': {'code': -32601 if isinstance(exc, LookupError) else -32602, 'message': str(exc)[:500]}}
            print(json.dumps(response, ensure_ascii=False), flush=True)
    finally:
        studio.close()


if __name__ == '__main__':
    main()
