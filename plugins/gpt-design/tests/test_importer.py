import base64
import sys
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/gpt-design/scripts'))
spec = importlib.util.spec_from_file_location('gpt_design', ROOT / 'skills/gpt-design/scripts/gpt_design.py')
gd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gd)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.data = self.root / 'library'

    def tearDown(self):
        self.tmp.cleanup()

    def test_themes_aliases_and_scope_survive(self):
        (self.source / 'theme.css').write_text(':root { --ink: #111; --font-size: 14px; --space: 8px; } [data-theme="dark"] { --ink: #eee; } @media (max-width: 600px) { :root { --ink: #333; } }')
        (self.source / 'tokens.json').write_text(json.dumps({'brand': {'$type': 'color', 'primary': {'$value': '#7357d7'}, 'alias': {'$value': '{brand.primary}'}}}))
        result = gd.import_system(self.source, self.data, 'Theme', ['colors'])
        self.assertEqual(len(result['tokens']), 6)
        self.assertNotIn('--space', [t['name'] for t in result['tokens']])
        self.assertEqual(result['cssOmitted'], 1)
        css = (self.data / 'systems' / result['id'] / 'tokens.css').read_text()
        self.assertIn('[data-theme="dark"] { --ink: #eee; }', css)
        self.assertIn('@media (max-width: 600px)', css)
        self.assertNotIn('{brand.primary}', css)
        self.assertEqual(result['tokens'][-1]['value'], '{brand.primary}')

    def test_assets_are_copied_exactly_and_symlinks_ignored(self):
        raw = b'original asset bytes'
        (self.source / 'logo.png').write_bytes(raw)
        (self.root / 'outside.css').write_text(':root{--private:red;}')
        (self.source / 'linked.css').symlink_to(self.root / 'outside.css')
        (self.source / 'Button.tsx').write_text('export function Button() {}')
        result = gd.import_system(self.source, self.data, 'Assets', ['assets', 'components'])
        self.assertEqual(len(result['assets']), 1)
        self.assertEqual(len(result['components']), 1)
        self.assertEqual(result['components'][0]['preview'], 'source-only')
        self.assertEqual((self.data / 'systems' / result['id'] / 'assets/logo.png').read_bytes(), raw)
        self.assertEqual(result['tokens'], [])
        self.assertEqual({f['path'] for f in result['files']}, {'logo.png', 'Button.tsx'})

    def test_imports_do_not_overwrite_previous_systems(self):
        (self.source / 'theme.css').write_text(':root{--color:red;}')
        first = gd.import_system(self.source, self.data, 'Brand')
        (self.source / 'theme.css').write_text(':root{--color:blue;}')
        second = gd.import_system(self.source, self.data, 'Brand')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(len(gd.summaries(self.data)), 2)
        saved = json.loads((self.data/'systems'/first['id']/'system.json').read_text())
        self.assertEqual(saved['tokens'][0]['value'], 'red')

    def test_github_refs_and_traversal(self):
        self.assertEqual(gd.parse_github('figma/sds@main:packages/ui'), ('figma/sds','main','packages/ui'))
        self.assertEqual(gd.parse_github('https://github.com/example/design.git', 'feature/theme'), ('example/design','feature/theme',''))
        self.assertEqual(gd.parse_github('twbs/bootstrap', 'v5.3.3', 'dist/css'), ('twbs/bootstrap', 'v5.3.3', 'dist/css'))
        for value in ['../secret.css', '/tmp/file.css', 'a/../../b.css', 'a\\b.css', '.env']:
            with self.assertRaises(ValueError):
                gd.safe_relative(value)
        with self.assertRaises(ValueError):
            gd.parse_github('https://evil.example/repo')

    def test_complex_tokens_remain_in_json(self):
        (self.source/'tokens.json').write_text(json.dumps({'type':{'$type':'typography','$value':{'fontFamily':'Inter','fontSize':'16px'}}}))
        result = gd.import_system(self.source, self.data, 'Type')
        self.assertEqual(result['tokens'][0]['value']['fontFamily'], 'Inter')
        self.assertEqual(result['cssOmitted'], 1)

    def test_local_fig_file_is_rejected_and_nested_fig_is_not_imported(self):
        fig=self.source/'library.fig'
        fig.write_bytes(b'fig-kiwi')
        with self.assertRaisesRegex(ValueError,'Figma imports are no longer supported'):
            gd.import_system(fig,self.data,'Unsupported')
        self.assertFalse(self.data.exists())
        (self.source/'tokens.json').write_text('{"ink":{"$type":"color","$value":"#121212"}}')
        system=gd.import_system(self.source,self.data,'Exported tokens')
        self.assertEqual(len(system['tokens']),1)
        self.assertNotIn('library.fig',[f['path'] for f in system['files']])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / 'library'
        self.data.mkdir()
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source/'theme.css').write_text(':root{--color:#123456;}')
        self.server = ThreadingHTTPServer(('127.0.0.1',0), gd.handler_for(self.data,[self.source],'test-session'))
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, path, body=None, token='test-session', origin=None):
        headers={'X-GPT-Design-Token':token,'Content-Type':'application/json'}
        if origin:
            headers['Origin']=origin
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        return urllib.request.urlopen(req)

    def test_import_list_and_export(self):
        with self.request('/api/import',{'kind':'local','name':'Brand','path':str(self.source),'scope':['colors']}) as r:
            created=json.load(r)
        with self.request('/api/systems') as r:
            self.assertEqual(json.load(r)['systems'][0]['id'],created['id'])
        with self.request('/api/systems/'+created['id']+'/tokens.css') as r:
            self.assertIn(b'#123456',r.read())

    def test_auth_origin_and_root_boundaries(self):
        for path,body,token,origin in [('/api/systems',None,'wrong',None),('/api/import',{'kind':'local','name':'Bad','path':str(self.root)},'test-session',None),('/api/import',{},'test-session','https://other.example')]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.request(path,body,token,origin)
            self.assertIn(ctx.exception.code,[400,401,403])
        self.assertFalse((self.data/'systems').exists())

    def test_upload_and_removed_connector_endpoint(self):
        body={'kind':'upload','name':'Upload','scope':['colors'],'files':[{'name':'tokens.json','content':base64.b64encode(b'{"ink":{"$type":"color","$value":"#121212"}}').decode()}]}
        with self.request('/api/import',body) as r:
            self.assertEqual(len(json.load(r)['tokens']),1)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request('/api/requests',{'name':'Brand','location':'Figma: Brand','scope':['colors']})
        self.assertEqual(ctx.exception.code,404)
        self.assertFalse((self.data/'requests').exists())
        body['files'][0]['name']='../evil.json'
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/import',body)

    def test_fig_upload_rejection_is_atomic(self):
        token={'name':'tokens.json','content':base64.b64encode(b'{"ink":{"$type":"color","$value":"#123456"}}').decode()}
        fig={'name':'design.FIG','content':base64.b64encode(b'fig-kiwi').decode()}
        for files in ([fig],[token,fig]):
            with self.subTest(files=[f['name'] for f in files]):
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    self.request('/api/import',{'kind':'upload','name':'Unsupported','files':files})
                self.assertEqual(ctx.exception.code,400)
                self.assertIn('Figma imports are no longer supported',json.load(ctx.exception)['error'])
        self.assertEqual(gd.summaries(self.data),[])

    def test_empty_scope_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request('/api/import',{'kind':'local','name':'Empty','path':str(self.source),'scope':[]})
        self.assertEqual(ctx.exception.code,400)

    def test_saved_token_edits_export_and_preserve_history(self):
        created = gd.import_system(self.source, self.data, 'Editable')
        with self.request('/api/systems/'+created['id']+'/edit', {'revision': 0, 'changes': [{'index': 0, 'value': '#abcdef'}]}) as response:
            updated = json.load(response)
        self.assertEqual(updated['revision'], 1)
        self.assertEqual(updated['tokens'][0]['value'], '#abcdef')
        self.assertEqual(updated['tokens'][0]['importedValue'], '#123456')
        self.assertIn('#123456', (self.source/'theme.css').read_text())
        history = json.loads((self.data/'systems'/created['id']/'history/revision-0.json').read_text())
        self.assertEqual(history['tokens'][0]['value'], '#123456')
        with self.request('/api/systems/'+created['id']+'/tokens.css') as response:
            self.assertIn(b'#abcdef', response.read())
        with self.request('/api/systems/'+created['id']) as response:
            self.assertEqual(json.load(response)['tokens'][0]['value'], '#abcdef')

    def test_conflicts_and_invalid_edits_do_not_overwrite(self):
        created = gd.import_system(self.source, self.data, 'Editable')
        url = '/api/systems/'+created['id']+'/edit'
        for payload, status in [({'revision': 1, 'changes': [{'index': 0, 'value': 'red'}]}, 409), ({'revision': 0, 'changes': [{'index': 300, 'value': 'red'}]}, 400), ({'revision': 0, 'changes': [{'index': 0, 'value': ''}]}, 400), ({'revision': 0, 'changes': [{'index': 0, 'value': 'red'},{'index': 0, 'delete': True}]}, 400)]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.request(url, payload)
            self.assertEqual(ctx.exception.code, status)
        with self.request('/api/systems/'+created['id']) as response:
            self.assertEqual(json.load(response)['tokens'][0]['value'], '#123456')

    def test_token_removal_is_recoverable_and_exports_update(self):
        created = gd.import_system(self.source, self.data, 'Editable')
        with self.request('/api/systems/'+created['id']+'/edit', {'revision': 0, 'changes': [{'index': 0, 'delete': True}]}) as response:
            self.assertEqual(json.load(response)['tokens'], [])
        with self.request('/api/systems/'+created['id']+'/tokens.json') as response:
            self.assertEqual(json.load(response)['tokens'], [])
        history = json.loads((self.data/'systems'/created['id']/'history/revision-0.json').read_text())
        self.assertEqual(len(history['tokens']), 1)


if __name__=='__main__':
    unittest.main()
