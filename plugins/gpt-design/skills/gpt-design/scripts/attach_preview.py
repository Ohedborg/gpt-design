#!/usr/bin/env python3
"""Attach a verified component build to a matching draft without changing publications."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import gpt_design as gd
import studio_features as f

def attach(data, ident, bundle, revision):
 target=f.target_for(data,ident)
 catalog=json.loads((bundle/'catalog.json').read_text())
 names=['catalog.json','runtime.js','runtime.css','build-inputs.json']
 if any(not (bundle/n).is_file() or (bundle/n).is_symlink() for n in names):
  raise ValueError('Provide a complete verified preview build.')
 with gd.system_lock(target):
  original=json.loads((target/'system.json').read_text())
  if original.get('revision',0)!=revision:raise gd.RevisionConflict('The draft changed. Review it before attaching this build.')
  if original.get('source',{}).get('commit') and original['source']['commit']!=catalog.get('commit'):
   raise ValueError('Preview commit does not match the imported source.')
  preview=target/'previews'
  if preview.exists():
   backup=target/'history'/('preview-revision-'+str(revision))
   shutil.copytree(preview,backup)
  preview.mkdir(exist_ok=True)
  for n in names:shutil.copy2(bundle/n,preview/n)
  updated=copy.deepcopy(original)
  updated['preview']={k:catalog[k] for k in ['builtAt','commit','storyFiles','notes']}
  updated['preview']['status']='built'
  return f.save_manifest(target,original,updated)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--data',type=Path,required=True);parser.add_argument('--id',required=True)
 parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--revision',type=int,required=True)
 args=parser.parse_args();result=attach(args.data,args.id,args.bundle,args.revision)
 print(json.dumps({'id':result['id'],'revision':result['revision'],'preview':result['preview']['status']}))
