import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/gpt-design/scripts'))
import gpt_design as gd
import github_library as gl
import releases


class Remote:
    def __init__(self):
        self.files={};self.sha='1'*40;self.snapshots={self.sha:{}};self.write=True;self.offline=False;self.race=False

    def factory(self,repo):
        return self

    def metadata(self):
        if self.offline: raise gl.GitHubError('GitHub is unavailable.')
        return {'default_branch':'main','permissions':{'push':self.write}}

    def identity(self): return 'publisher'
    def head(self,branch): return self.sha

    def file(self,path,commit):
        if path not in self.snapshots[commit]: raise gl.GitHubError('Not found',404)
        return self.snapshots[commit][path]

    def commit(self,head,branch,files,message):
        if self.race or head!=self.sha: raise gl.GitHubError('Concurrent publication',409)
        self.files.update(files);self.sha=hashlib.sha1((self.sha+message).encode()).hexdigest();self.snapshots[self.sha]=copy.deepcopy(self.files)
        return self.sha


class GitHubLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.writer=self.root/'writer';self.consumer=self.root/'consumer';self.remote=Remote()
        self.client=patch.object(gl,'GitHub',self.remote.factory);self.client.start()
        self.auth=patch.object(gl,'credentials',return_value='fake-test-credential');self.auth.start()
        self.system=gd.import_system(ROOT/'examples/starter',self.writer,'Shared demo',gd.GROUPS)
        self.ident=self.system['id'];self.cfg={'repository':'example/library','folder':'design-systems'}
        gl.connect(self.writer,self.cfg)

    def tearDown(self):
        self.auth.stop();self.client.stop();self.tmp.cleanup()

    def draft(self,data=None):
        return json.loads(((data or self.writer)/'systems'/self.ident/'system.json').read_text())

    def publish(self,data=None,**payload):
        data=data or self.writer
        return releases.publish(data,self.ident,{'revision':self.draft(data).get('revision',0),'notes':'Shared version',**payload})

    def test_publish_sync_new_install_and_followup_without_plugin_update(self):
        first=self.publish();self.assertTrue(first['shared']);self.assertEqual(first['release']['version'],1)
        result=gl.connect(self.consumer,self.cfg);self.assertEqual(result['updated'],[self.ident])
        self.assertEqual(self.draft(self.consumer)['tokens'],self.system['tokens'])
        old=releases.read(self.consumer,self.ident,1)
        gd.edit_system(self.writer,self.ident,{'revision':self.draft()['revision'],'changes':[{'index':0,'value':'#123456'}]})
        self.publish();gl.sync(self.consumer,force=True)
        self.assertEqual(self.draft(self.consumer)['tokens'][0]['value'],'#123456')
        self.assertEqual(releases.read(self.consumer,self.ident,1)['tokens'],old['tokens'])
        self.assertEqual(self.draft(self.consumer)['publication']['version'],2)

    def test_dirty_draft_is_preserved_and_stale_publishing_rejected(self):
        self.publish();gl.connect(self.consumer,self.cfg)
        gd.edit_system(self.consumer,self.ident,{'revision':self.draft(self.consumer)['revision'],'changes':[{'index':0,'value':'#abcabc'}]})
        gd.edit_system(self.writer,self.ident,{'revision':self.draft()['revision'],'changes':[{'index':0,'value':'#112233'}]})
        self.publish();result=gl.sync(self.consumer,force=True)
        self.assertEqual(result['draftsBehind'],[self.ident])
        self.assertEqual(self.draft(self.consumer)['tokens'][0]['value'],'#abcabc')
        with self.assertRaisesRegex(ValueError,'newer version'): self.publish(self.consumer)
        refreshed=gl.start_from_latest(self.consumer,self.ident,self.draft(self.consumer)['revision'])
        backup=json.loads((Path(refreshed['backup'])/'system.json').read_text())
        self.assertEqual(backup['tokens'][0]['value'],'#abcabc')
        self.assertEqual(refreshed['system']['tokens'][0]['value'],'#112233')

    def test_failed_remote_commit_does_not_publish_local_pointer_or_version(self):
        self.publish();old=self.draft();self.remote.race=True
        with self.assertRaises(gl.GitHubError): self.publish()
        self.assertEqual(self.draft(),old)
        self.assertFalse((self.writer/'systems'/self.ident/'releases/2').exists())

    def test_read_only_repository_rejects_edits_and_publishing(self):
        self.publish();self.remote.write=False;gl.connect(self.consumer,self.cfg)
        self.assertFalse(gl.access(self.consumer,self.draft(self.consumer))['_access']['canPublish'])
        with self.assertRaisesRegex(ValueError,'read-only'):
            gd.edit_system(self.consumer,self.ident,{'revision':self.draft(self.consumer)['revision'],'changes':[{'index':0,'value':'#123123'}]})
        with self.assertRaisesRegex(ValueError,'read-only'): self.publish(self.consumer)

    def test_offline_sync_keeps_cache_and_reports_failure(self):
        self.publish();gl.connect(self.consumer,self.cfg);old=self.draft(self.consumer);self.remote.offline=True
        result=gl.sync(self.consumer,force=True)
        self.assertIn('unavailable',result['error']);self.assertEqual(self.draft(self.consumer),old)

    def test_archive_integrity_failure_keeps_existing_version(self):
        self.publish();gl.connect(self.consumer,self.cfg);self.publish()
        path=next(p for p in self.remote.files if p.endswith('/2.zip'))
        self.remote.snapshots[self.remote.sha][path]=b'corrupted'
        result=gl.sync(self.consumer,force=True)
        self.assertIn('integrity',result['error']);self.assertEqual(self.draft(self.consumer)['publication']['version'],1)

    def test_remote_rewrite_of_cached_release_is_rejected(self):
        self.publish();gl.connect(self.consumer,self.cfg)
        path='design-systems/catalog.json';catalog=json.loads(self.remote.files[path]);catalog['systems'][0]['versions'][0]['sha256']='0'*64
        self.remote.snapshots[self.remote.sha][path]=gl.encoded(catalog)
        self.assertIn('changed an existing release',gl.sync(self.consumer,force=True)['error'])

    def test_rollback_is_new_shared_version_and_preserves_draft(self):
        self.publish();old=self.draft()['tokens'][0]['value']
        gd.edit_system(self.writer,self.ident,{'revision':self.draft()['revision'],'changes':[{'index':0,'value':'#abcdef'}]})
        self.publish();result=self.publish(action='rollback',version=1)
        self.assertEqual(result['release']['version'],3)
        self.assertEqual(self.draft()['tokens'][0]['value'],'#abcdef')
        gl.connect(self.consumer,self.cfg)
        self.assertEqual(self.draft(self.consumer)['tokens'][0]['value'],old)

    def test_initial_publish_backs_up_previous_local_releases(self):
        gl.disconnect(self.writer);self.publish();self.publish()
        gl.connect(self.writer,self.cfg);self.publish()
        gl.connect(self.consumer,self.cfg)
        self.assertEqual([r['version'] for r in releases.history(self.consumer,self.ident)['releases']],[3,2,1])

    def test_share_existing_publication_keeps_unpublished_changes_local(self):
        gl.disconnect(self.writer);self.publish();published=self.draft()['tokens'][0]['value']
        gd.edit_system(self.writer,self.ident,{'revision':self.draft()['revision'],'changes':[{'index':0,'value':'#fedcba'}]})
        gl.connect(self.writer,self.cfg)
        gl.share_publication(self.writer,self.ident,self.draft()['revision'])
        self.assertEqual(self.draft()['tokens'][0]['value'],'#fedcba')
        gl.connect(self.consumer,self.cfg)
        self.assertEqual(self.draft(self.consumer)['tokens'][0]['value'],published)
        self.assertEqual(self.draft(self.consumer)['publication']['version'],1)

    def test_paths_and_archive_traversal_rejected(self):
        for path in ['../secrets','a/../../x','/tmp/a','a\\x','a/.git/config','a//b']:
            with self.assertRaises(ValueError): gl.relative(path)
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z: z.writestr('../outside.txt','unsafe')
        data=raw.getvalue();dest=self.root/'unpacked';dest.mkdir()
        with self.assertRaises(ValueError): gl.unpack(data,dest,self.ident,1,hashlib.sha256(data).hexdigest())
        self.assertFalse((self.root/'outside.txt').exists())

    def test_disconnected_shared_system_cannot_publish_locally_by_accident(self):
        self.publish();gl.disconnect(self.writer)
        with self.assertRaisesRegex(ValueError,'Reconnect'): self.publish()


class GitHubTransportTests(unittest.TestCase):
    def test_commit_preserves_tree_and_uses_non_force_branch_update(self):
        with patch.object(gl,'credentials',return_value='token'):
            client=gl.GitHub('example/library')
        calls=[]
        def request(path,payload=None,**kwargs):
            calls.append((path,payload,kwargs))
            if '/git/commits/' in path: return {'tree':{'sha':'original-tree'}}
            if path.endswith('/git/trees'): return {'sha':'new-tree'}
            return {'sha':'new-commit'}
        client.request=request
        client.commit('old-commit','main',{'design-systems/catalog.json':b'{}'},'Publish')
        self.assertEqual(calls[1][1]['base_tree'],'original-tree')
        self.assertEqual(calls[2][1]['parents'],['old-commit'])
        self.assertEqual(calls[-1][1],{'sha':'new-commit','force':False})
        self.assertEqual(calls[-1][2]['method'],'PATCH')


if __name__=='__main__': unittest.main()
