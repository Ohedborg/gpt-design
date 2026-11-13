import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/gpt-design/scripts/mcp_server.py'


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / 'library'
        self.process = subprocess.Popen([sys.executable, str(SCRIPT), '--data', str(self.data),
                                         '--allow-root', str(ROOT / 'examples')],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.counter = 0

    def tearDown(self):
        self.process.stdin.close()
        self.process.wait(timeout=5)
        err = self.process.stderr.read()
        self.process.stdout.close()
        self.process.stderr.close()
        self.tmp.cleanup()
        self.assertEqual(self.process.returncode, 0, err)

    def rpc(self, method, params=None):
        self.counter += 1
        self.process.stdin.write(json.dumps({'jsonrpc':'2.0','id':self.counter,'method':method,'params':params or {}}) + '\n')
        self.process.stdin.flush()
        result = json.loads(self.process.stdout.readline())
        self.assertEqual(result['id'], self.counter)
        return result['result']

    def call(self, name, args=None):
        return self.rpc('tools/call', {'name':name, 'arguments':args or {}})

    def test_rename_and_delete_through_tools(self):
        system=self.call('import_system',{'payload':{'kind':'local','name':'Manage fixture','path':str(ROOT/'examples/starter')}})['structuredContent']
        result=self.call('rename_system',{'id':system['id'],'payload':{'revision':system['revision'],'name':'Renamed fixture'}})['structuredContent']['system']
        self.assertEqual(result['name'],'Renamed fixture')
        rejected=self.call('delete_system',{'id':system['id'],'payload':{'revision':result['revision'],'confirmName':'wrong'}})
        self.assertTrue(rejected['isError'])
        removed=self.call('delete_system',{'id':system['id'],'payload':{'revision':result['revision'],'confirmName':result['name']}})['structuredContent']
        self.assertEqual(removed['deleted'],system['id'])
        self.assertEqual(self.call('list_systems')['structuredContent']['systems'],[])

    def test_removed_imports_cannot_create_snapshots_or_requests(self):
        files=[{'name':'library.fig','content':base64.b64encode(b'fig-kiwi').decode()}]
        for kind in ('figma-file','upload','connector'):
            with self.subTest(kind=kind):
                result=self.call('import_system',{'payload':{'kind':kind,'name':'Figma library','files':files}})
                self.assertTrue(result['isError'])
        self.assertTrue(self.call('save_import_request',{'payload':{'name':'Brand','location':'https://figma.com/design/test'}})['isError'])
        self.assertEqual(self.call('list_systems')['structuredContent']['systems'],[])
        self.assertFalse((self.data/'requests').exists())

    def test_existing_figma_snapshot_remains_readable(self):
        system=self.call('import_system',{'payload':{'kind':'local','name':'Legacy','path':str(ROOT/'examples/starter')}})['structuredContent']
        target=self.data/'systems'/system['id']
        raw=b'previously saved Figma source'
        original=target/'source/original/design-system.fig'
        original.parent.mkdir(parents=True)
        original.write_bytes(raw)
        system['source']={'kind':'figma-file','filename':'library.fig'}
        system['files'].append({'path':'original/design-system.fig','binary':True,'stored':True,'bytes':len(raw),'kind':'fig'})
        (target/'system.json').write_text(json.dumps(system))
        loaded=self.call('get_system',{'id':system['id']})['structuredContent']
        self.assertEqual(loaded['source']['kind'],'figma-file')
        saved=self.call('get_file',{'id':system['id'],'path':'original/design-system.fig'})['structuredContent']
        self.assertEqual(base64.b64decode(saved['base64']),raw)

    def test_discovery_resource_and_sidebar_registration(self):
        self.assertEqual(self.rpc('initialize', {'protocolVersion':'2025-11-25'})['serverInfo']['title'], 'GPT Design')
        tools = self.rpc('tools/list')['tools']
        self.assertNotIn('save_import_request',[t['name'] for t in tools])
        entry = next(t for t in tools if t['name'] == 'open_studio')
        self.assertEqual(entry['_meta']['openai/ui']['entrypoints'], [{'type':'global'},{'type':'thread'}])
        self.assertIn('data:image/svg+xml;base64,', entry['icons'][0]['src'])
        resource = self.rpc('resources/read', {'uri':entry['_meta']['ui']['resourceUri']})['contents'][0]
        self.assertEqual(resource['mimeType'], 'text/html;profile=mcp-app')
        self.assertIn("request('ui/initialize'", resource['text'])
        self.assertNotIn('<script defer src=', resource['text'])
        self.assertNotIn('<link rel="stylesheet"', resource['text'])
        self.assertNotIn('127.0.0.1:', resource['text'])
        for source in ('github','local','upload'):
            self.assertIn('data-source="'+source+'"',resource['text'])
        for source in ('figma-file','connector'):
            self.assertNotIn('data-source="'+source+'"',resource['text'])
        self.assertEqual(self.call('open_studio')['structuredContent']['systems'], [])

    def test_import_edit_export_and_stale_write_over_stdio(self):
        original = (ROOT / 'examples/starter/tokens.json').read_bytes()
        result = self.call('import_system', {'payload':{'kind':'local','name':'MCP fixture','path':str(ROOT / 'examples/starter')}})
        system = result['structuredContent']
        ident = system['id']
        saved = self.call('edit_system', {'id':ident,'revision':0,'changes':[{'index':0,'value':'#abcdef'}]})['structuredContent']
        self.assertEqual(saved['revision'], 1)
        self.assertTrue(self.call('edit_system', {'id':ident,'revision':0,'changes':[{'index':0,'value':'#badbad'}]})['isError'])
        exported = self.call('export_system', {'id':ident,'file':'tokens.json'})['structuredContent']
        self.assertEqual(json.loads(exported['text'])['tokens'][0]['value'], '#abcdef')
        self.assertEqual((ROOT / 'examples/starter/tokens.json').read_bytes(), original)
        self.assertTrue((self.data / 'systems' / ident / 'history/revision-0.json').exists())
        self.assertEqual(len(self.call('list_systems')['structuredContent']['systems']), 1)

    def test_explicit_system_choice_and_multiple_system_prompt(self):
        a=self.call('import_system', {'payload':{'kind':'local','name':'First','path':str(ROOT/'examples/starter')}})['structuredContent']
        b=self.call('import_system', {'payload':{'kind':'local','name':'Second','path':str(ROOT/'examples/starter')}})['structuredContent']
        chooser=self.call('open_studio')['structuredContent']
        self.assertTrue(chooser['selectionRequired'])
        self.assertIsNone(chooser['selectedSystemId'])
        selected=self.call('open_studio',{'system_id':b['id']})['structuredContent']
        self.assertFalse(selected['selectionRequired'])
        self.assertEqual(selected['selectedSystemId'],b['id'])
        self.assertTrue(self.call('open_studio',{'system_id':'0'*32})['isError'])

    def test_publication_guidance_and_frozen_file_through_tools(self):
        system=self.call('import_system', {'payload':{'kind':'local','name':'Release fixture','path':str(ROOT/'examples/starter')}})['structuredContent']
        ident=system['id']
        self.assertFalse(self.call('get_preview', {'id':ident})['structuredContent']['available'])
        original=self.call('get_file', {'id':ident,'path':'tokens.json'})['structuredContent']['text']
        saved=self.call('maintain_system', {'id':ident,'payload':{'revision':0,'action':'guide','guide':{'summary':'Draft guide'}}})['structuredContent']
        result=self.call('publish_system', {'id':ident,'payload':{'revision':saved['revision'],'notes':'First publication'}})['structuredContent']
        self.assertEqual(result['release']['version'],1)
        release=self.call('get_release', {'id':ident,'version':1})['structuredContent']
        self.assertEqual(release['guide']['summary'],'Draft guide')
        self.assertEqual(self.call('get_file', {'id':ident,'path':'tokens.json','version':1})['structuredContent']['text'],original)
        self.assertIn('tokens',json.loads(self.call('get_release', {'id':ident,'version':1,'file':'tokens.json'})['structuredContent']['text']))
        self.assertEqual(self.call('list_releases', {'id':ident})['structuredContent']['publishedVersion'],1)
        self.assertTrue(self.call('publish_system', {'id':ident,'payload':{'revision':0,'notes':'Stale'}})['isError'])

    def test_import_boundaries_and_uploaded_tokens(self):
        for name, args in [('get_system', {'id':'../secret'}), ('import_system', {'payload':[]}),
                           ('import_system', {'payload':{'kind':'local','name':'Invalid','path':'/Users'}}),
                           ('not_a_tool', {})]:
            self.assertTrue(self.call(name, args)['isError'])
        contents = base64.b64encode(b':root{--brand:#7357D7;}').decode()
        uploaded = self.call('import_system', {'payload':{'kind':'upload','name':'Upload','files':[{'name':'theme.css','content':contents}]}})
        self.assertEqual(uploaded['structuredContent']['tokens'][0]['value'], '#7357D7')


if __name__ == '__main__':
    unittest.main()
