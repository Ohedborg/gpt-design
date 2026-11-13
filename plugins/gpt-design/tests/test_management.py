import copy
import json
import unittest
from unittest.mock import patch
import test_github_library as fixtures
import gpt_design as gd
import github_library as gl
import releases
import system_management as sm


class ManagementTests(unittest.TestCase):
    setUp=fixtures.GitHubLibraryTests.setUp
    tearDown=fixtures.GitHubLibraryTests.tearDown
    draft=fixtures.GitHubLibraryTests.draft
    publish=fixtures.GitHubLibraryTests.publish

    def manage(self, action, data=None, **payload):
        data=data or self.writer
        return sm.manage(data,self.ident,action,{'revision':self.draft(data)['revision'], **payload})

    def test_rename_sync_preserves_dirty_draft_archives_folder_and_version(self):
        self.publish();gl.connect(self.consumer,self.cfg)
        original=copy.deepcopy(self.remote.files)
        gd.edit_system(self.consumer,self.ident,{'revision':self.draft(self.consumer)['revision'],'changes':[{'index':0,'value':'#abcdef'}]})
        self.manage('rename',name='New name')
        gl.sync(self.consumer,force=True)
        self.assertEqual(self.draft(self.consumer)['name'],'New name')
        self.assertEqual(self.draft(self.consumer)['tokens'][0]['value'],'#abcdef')
        self.assertEqual(self.draft()['publication']['version'],1)
        self.assertEqual(releases.read(self.consumer,self.ident,1)['name'],'New name')
        for path,value in original.items():
            if path.endswith('.zip'):self.assertEqual(self.remote.files[path],value)
        self.assertEqual(self.draft()['shared']['path'],self.draft(self.consumer)['shared']['path'])
        self.publish();gl.sync(self.consumer,force=True)
        self.assertEqual(self.draft(self.consumer)['name'],'New name')
        self.assertEqual(self.draft(self.consumer)['tokens'][0]['value'],'#abcdef')

    def test_rename_clean_legacy_fingerprint_still_receives_latest(self):
        self.publish();gl.connect(self.consumer,self.cfg)
        original=self.draft(self.consumer);original['shared']['baseFingerprint']='legacy-fingerprint-with-name'
        gl.atomic_json(self.consumer/'systems'/self.ident/'system.json',original)
        self.manage('rename',name='Renamed')
        gl.sync(self.consumer,force=True)
        gd.edit_system(self.writer,self.ident,{'revision':self.draft()['revision'],'changes':[{'index':0,'value':'#eeeeee'}]})
        self.publish();gl.sync(self.consumer,force=True)
        self.assertEqual(self.draft(self.consumer)['tokens'][0]['value'],'#eeeeee')

    def test_shared_delete_propagates_and_keeps_drafts_and_archives(self):
        self.publish();gl.connect(self.consumer,self.cfg)
        gd.edit_system(self.consumer,self.ident,{'revision':self.draft(self.consumer)['revision'],'changes':[{'index':0,'value':'#112233'}]})
        archived={p:v for p,v in self.remote.files.items() if p.endswith('.zip')}
        result=self.manage('delete',confirmName=self.draft()['name'])
        self.assertEqual(gd.summaries(self.writer),[])
        self.assertTrue(result['shared'])
        synced=gl.sync(self.consumer,force=True)
        self.assertEqual(synced['deleted'],[self.ident]);self.assertEqual(gd.summaries(self.consumer),[])
        backup=next((self.consumer/'trash').glob('*/system.json'))
        self.assertEqual(json.loads(backup.read_text())['tokens'][0]['value'],'#112233')
        for path,value in archived.items():self.assertEqual(self.remote.files[path],value)
        gl.sync(self.consumer,force=True);self.assertEqual(gd.summaries(self.consumer),[])
        stale=json.loads(backup.read_text())
        with self.assertRaisesRegex(ValueError,'deleted'):gl.publication_context(self.consumer,stale)

    def test_local_delete_and_cancel_pending_upload_do_not_publish(self):
        result=self.manage('delete',confirmName=self.draft()['name'])
        self.assertFalse(result['shared']);self.assertEqual(self.remote.files,{})
        self.remote.offline=True
        from test_github_library import ROOT
        created=gd.import_system(ROOT/'examples/starter',self.writer,'Pending')
        self.ident=created['id'];self.remote.offline=False
        self.manage('delete',confirmName='Pending')
        gl.retry_uploads(self.writer,force=True)
        self.assertEqual(self.remote.files,{})
        self.assertEqual(gd.summaries(self.writer),[])

    def test_pending_rename_retries_frozen_initial_content_with_new_name(self):
        from test_github_library import ROOT
        self.remote.offline=True
        created=gd.import_system(ROOT/'examples/starter',self.writer,'Pending');self.ident=created['id']
        self.remote.offline=False
        self.manage('rename',name='Ready')
        gl.retry_uploads(self.writer,force=True);gl.connect(self.consumer,self.cfg)
        self.assertEqual(self.draft(self.consumer)['name'],'Ready')

    def test_failed_or_unauthorized_delete_keeps_everything(self):
        self.publish();old=self.draft()
        for action,payload in [('rename',{'name':'No'}),('delete',{'confirmName':old['name']})]:
            self.remote.write=False
            with self.assertRaisesRegex(ValueError,'read-only'):self.manage(action,**payload)
            self.remote.write=True;self.remote.race=True
            with self.assertRaises(gl.GitHubError):self.manage(action,**payload)
            self.remote.race=False
            self.assertEqual(self.draft(),old)
        with self.assertRaisesRegex(ValueError,'confirm'):self.manage('delete',confirmName='wrong')
        gl.disconnect(self.writer)
        with self.assertRaisesRegex(ValueError,'Reconnect'):self.manage('delete',confirmName=old['name'])

    def test_stale_revision_and_remote_change_are_rejected(self):
        self.publish();gl.connect(self.consumer,self.cfg)
        old=self.draft();self.manage('rename',name='Updated')
        with self.assertRaises(gd.RevisionConflict):sm.manage(self.writer,self.ident,'delete',{'revision':old['revision'],'confirmName':old['name']})
        with self.assertRaises(gd.RevisionConflict):self.manage('delete',self.consumer,confirmName=old['name'])
        with self.assertRaisesRegex(ValueError,'renamed'):self.publish(self.consumer)

    def test_invalid_names_and_symlink_trash_rejected(self):
        for name in ['', '   ', 'a'*121, 'New\nname', 42]:
            with self.assertRaises(ValueError):self.manage('rename',name=name)
        (self.writer/'trash').symlink_to(self.consumer)
        with self.assertRaisesRegex(ValueError,'symbolic'):self.manage('delete',confirmName=self.draft()['name'])

if __name__=='__main__': unittest.main()
