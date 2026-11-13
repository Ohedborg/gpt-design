"""Local immutable publications. Organization authorization belongs at a shared service boundary."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import uuid
import github_library as shared


def release_path(data, ident, version):
    import studio_features as f
    root = f.target_for(data, ident)
    if isinstance(version, bool) or not str(version).isdigit() or int(version) < 1:
        raise ValueError('Invalid release version.')
    path = root / 'releases' / str(int(version))
    if (root/'releases').is_symlink() or path.is_symlink() or not (path / 'release.json').is_file():
        raise ValueError('Published version not found.')
    return path


def history(data, ident):
    import studio_features as f
    target = f.target_for(data, ident)
    system = json.loads((target / 'system.json').read_text())
    entries = [json.loads(p.read_text()) for p in (target / 'releases').glob('[0-9]*/release.json')]
    return {'releases': [{k:v for k,v in e.items() if k!='checksums'} for e in sorted(entries, key=lambda r:r['version'], reverse=True)],
            'publishedVersion': system.get('publication', {}).get('version'),
            'mode': 'github' if system.get('shared') else 'personal', 'access': shared.access(data,system)['_access']}


def read(data, ident, version, file='system.json'):
    import gpt_design as gd
    import studio_features as f
    target = release_path(data, ident, version)
    if file not in {'system.json','tokens.json','tokens.css'}:
        raise ValueError('Unknown release file.')
    if file == 'system.json':
        system = json.loads((target / file).read_text())
        system['_release'] = json.loads((target / 'release.json').read_text())
        draft=json.loads((f.target_for(data,ident)/'system.json').read_text())
        if draft.get('shared'): system['shared']=draft['shared']
        if draft.get('pendingUpload'): system['pendingUpload']=draft['pendingUpload']
        return shared.access(data,system)
    return {'text': (target / file).read_text(), 'mimeType': 'text/css' if file.endswith('.css') else 'application/json'}


def publish(data, ident, payload, *, initial_connection=None):
    import gpt_design as gd
    import studio_features as f
    target = f.target_for(data, ident)
    with shared.library_lock(data), gd.system_lock(target):
        original = json.loads((target / 'system.json').read_text())
        if payload.get('revision') != original.get('revision', 0):
            raise gd.RevisionConflict('This draft changed. Reopen it before publishing.')
        if initial_connection is not None:
            if original.get('publication') or original.get('shared') or original.get('pendingUpload') or history(data,ident)['releases']:
                raise ValueError('An initial publication can only be created for a new import.')
            context=None
        else:
            if original.get('pendingUpload'):
                raise ValueError('The initial version is waiting to upload to GitHub. It will retry automatically while the studio is open.')
            context=shared.publication_context(data,original)
        notes = payload.get('notes', '')
        if not isinstance(notes, str) or not notes.strip() or len(notes) > 4000:
            raise ValueError('Add release notes (up to 4,000 characters).')
        action = payload.get('action', 'publish')
        if action not in {'publish', 'rollback'}:
            raise ValueError('Choose publish or rollback.')
        source = release_path(data, ident, payload.get('version')) if action == 'rollback' else target
        snapshot = json.loads((source / 'system.json').read_text())
        existing = history(data, ident)['releases']
        number = max([r['version'] for r in existing] or [0]) + 1
        parent = target / 'releases'
        if parent.is_symlink():
            raise ValueError('Release storage must be a local directory.')
        parent.mkdir(exist_ok=True)
        stage = parent / ('.staging-' + uuid.uuid4().hex)
        stage.mkdir()
        try:
            for folder in ['source', 'assets', 'previews']:
                origin = source / folder
                if origin.exists():
                    if any(p.is_symlink() for p in [origin, *origin.rglob('*')]):
                        raise ValueError('Release content cannot contain symbolic links.')
                    shutil.copytree(origin, stage / folder)
            snapshot.pop('_release', None)
            snapshot.pop('publication', None)
            snapshot.pop('shared', None)
            snapshot.pop('_access', None)
            snapshot.pop('pendingUpload', None)
            gd.write_json(stage / 'system.json', snapshot)
            gd.write_json(stage / 'tokens.json', {'format':'gpt-design-tokens-v1','tokens':snapshot['tokens']})
            (stage / 'tokens.css').write_text(gd.css_export(snapshot['tokens'])[0])
            checksums = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob('*')) if p.is_file()}
            manifest = {'version':number,'notes':notes.strip(),'publishedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
                        'author':context['author'] if context else 'Local owner','sourceRevision':snapshot.get('revision',0),'rollbackOf':int(payload['version']) if action=='rollback' else None,
                        'files':len(checksums),'checksums':checksums}
            gd.write_json(stage / 'release.json', manifest)
            binding=shared.publish_prepared(data,ident,stage,snapshot,manifest,context)
            stage.rename(parent / str(number))
            updated = copy.deepcopy(original)
            if binding: updated['shared']=binding
            if initial_connection is not None:
                updated['pendingUpload']={k:initial_connection[k] for k in ['repository','branch','folder']} | {'version':number}
            updated['publication'] = {k:manifest[k] for k in ['version','notes','publishedAt','sourceRevision','rollbackOf']}
            # Rollback moves the published release only. The working draft remains intact.
            f.save_manifest(target, original, updated)
            return {'system':shared.access(data,updated),'release':{k:v for k,v in manifest.items() if k!='checksums'},'shared':bool(binding)}
        finally:
            if stage.exists():
                shutil.rmtree(stage)
