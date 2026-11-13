import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/gpt-design/scripts'))
import gpt_design as gd
import studio_features as f
import releases

class FeatureTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'src';self.source.mkdir();self.data=self.root/'library'
  (self.source/'theme.css').write_text(':root { --color-brand: #112233; }')
  (self.source/'README.md').write_text('Use semantic tokens.')
  (self.source/'Button.tsx').write_text('export const Button = () => null;')
  (self.source/'logo.svg').write_text('<svg/>')
  self.system=gd.import_system(self.source,self.data,'Test');self.id=self.system['id'];self.target=self.data/'systems'/self.id
 def tearDown(self):self.tmp.cleanup()
 def test_preserved_source_boundaries(self):
  self.assertEqual(f.read_file(self.data,self.id,'README.md')['text'],'Use semantic tokens.')
  with self.assertRaises(ValueError):f.read_file(self.data,self.id,'../README.md')
  (self.target/'source/README.md').unlink();(self.target/'source/README.md').symlink_to(self.source/'README.md')
  with self.assertRaises(ValueError):f.read_file(self.data,self.id,'README.md')
  self.assertFalse(f.preview_bundle(self.data,self.id)['available'])
 def test_guidance_notes_token_add_and_conflicts(self):
  s=f.maintain(self.data,self.id,{'revision':0,'action':'guide','guide':{'principles':'Use semantic colors'}})
  self.assertEqual(s['revision'],1)
  with self.assertRaises(gd.RevisionConflict):f.maintain(self.data,self.id,{'revision':0,'action':'guide','guide':{}})
  s=f.maintain(self.data,self.id,{'revision':1,'action':'component-note','key':'Button','note':'One main action'})
  s=f.maintain(self.data,self.id,{'revision':2,'action':'add-token','token':{'name':'--color-added','value':'#abcdef','type':'color'}})
  self.assertEqual(s['componentNotes']['Button'],'One main action');self.assertIn('--color-added: #abcdef',(self.target/'tokens.css').read_text())
  with self.assertRaises(ValueError):f.maintain(self.data,self.id,{'revision':3,'action':'add-token','token':{'name':'--color-added','value':'red'}})
 def test_publications_freeze_all_content_and_rollback_preserves_draft(self):
  preview=self.target/'previews';preview.mkdir();(preview/'runtime.js').write_text('original');(preview/'runtime.css').write_text('body{}');(preview/'catalog.json').write_text('{"notes":[]}')
  r1=releases.publish(self.data,self.id,{'revision':0,'notes':'Initial','action':'publish'})
  self.assertEqual(r1['release']['version'],1)
  gd.edit_system(self.data,self.id,{'revision':1,'changes':[{'index':0,'value':'#ffffff'}]})
  (preview/'runtime.js').write_text('changed');(self.target/'source/README.md').write_text('changed guide')
  r2=releases.publish(self.data,self.id,{'revision':2,'notes':'Update'})
  self.assertEqual(releases.read(self.data,self.id,1)['tokens'][0]['value'],'#112233')
  self.assertEqual(f.preview_bundle(self.data,self.id,1)['script'],'original')
  self.assertEqual(f.read_file(self.data,self.id,'README.md',1)['text'],'Use semantic tokens.')
  r3=releases.publish(self.data,self.id,{'revision':3,'notes':'Restore initial','action':'rollback','version':1})
  self.assertEqual(r3['release']['version'],3);self.assertEqual(r3['system']['tokens'][0]['value'],'#ffffff')
  self.assertEqual(releases.read(self.data,self.id,3)['tokens'][0]['value'],'#112233')
  self.assertEqual(releases.history(self.data,self.id)['publishedVersion'],3)
  self.assertEqual(len(releases.history(self.data,self.id)['releases']),3)
  with self.assertRaises(gd.RevisionConflict):releases.publish(self.data,self.id,{'revision':0,'notes':'Stale'})
  with self.assertRaises(ValueError):releases.read(self.data,self.id,'../source')
  with self.assertRaises(ValueError):releases.publish(self.data,self.id,{'revision':4,'notes':'Invalid','action':'rollback','version':99})

if __name__=='__main__':unittest.main()
