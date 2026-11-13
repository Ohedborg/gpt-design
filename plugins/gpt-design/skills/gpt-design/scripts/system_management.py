"""Library identity and recoverable removal, independent of published content."""
import copy
import hashlib
import json
import uuid
import github_library as gl


def archive_local(data, target, deleted_at):
    """Caller holds the library and system locks. Move the entire saved draft."""
    trash = data / 'trash'
    if trash.is_symlink():
        raise ValueError('Deleted-system storage cannot be a symbolic link.')
    trash.mkdir(exist_ok=True)
    destination = trash / (target.name + '-' + uuid.uuid4().hex)
    gl.atomic_json(target / 'deleted.json', {'id': target.name, 'deletedAt': deleted_at})
    target.rename(destination)
    return destination


def manage(data, ident, action, payload):
    import gpt_design as gd
    import studio_features as features
    if action not in {'rename', 'delete'}:
        raise ValueError('Choose rename or delete.')
    with gl.library_lock(data):
        target = features.target_for(data, ident)
        with gd.system_lock(target):
            original = json.loads((target / 'system.json').read_text())
            if type(payload.get('revision')) is not int or payload['revision'] != original.get('revision', 0):
                raise gd.RevisionConflict('This system changed. Reopen Manage design system before continuing.')
            name = payload.get('name')
            if action == 'rename':
                if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120 or any(ord(c)<32 or ord(c)==127 for c in name):
                    raise ValueError('Use a name between 1 and 120 characters, without line breaks.')
                name = name.strip()
            elif payload.get('confirmName') != original['name']:
                raise ValueError('Enter the design system’s current name to confirm deletion.')
            if (data / 'trash').is_symlink():
                raise ValueError('Deleted-system storage cannot be a symbolic link.')
            linked = original.get('shared') or original.get('pendingUpload')
            client = gl.require_write(data, original) if linked else None
            cfg = gl.config(data) if client else None
            stamp = gl.now()
            if client:
                head = client.head(cfg['branch'])
                catalog = gl.catalog_at(client, cfg, head)
                remote = next((s for s in catalog['systems'] if s['id'] == ident), None)
                deleted = next((s for s in catalog.get('deletedSystems', []) if s['id'] == ident), None)
                if deleted:
                    if action == 'delete':
                        backup = archive_local(data, target, deleted['deletedAt'])
                        return {'deleted':ident, 'shared':True, 'backup':str(backup)}
                    raise ValueError('This design system has been deleted. Refresh the library.')
                if original.get('shared'):
                    if not remote:
                        raise ValueError('This shared system is missing from GitHub. Refresh the library.')
                    if remote['version'] != linked['latestVersion'] or remote['name'] != original['name']:
                        raise gd.RevisionConflict('This system changed on GitHub. Refresh the library and reopen Manage design system.')
                elif remote:
                    # Recover an initial upload whose response was lost, without removing another system.
                    archive = target / 'releases' / str(linked['version'])
                    version = next((v for v in remote['versions'] if v['version']==linked['version']), None)
                    if remote['version']!=linked['version'] or not version or version['sha256']!=hashlib.sha256(gl.pack(archive)).hexdigest():
                        raise ValueError('The GitHub system differs from this pending upload. Refresh the library.')
                if remote:
                    files = {}
                    if action == 'rename':
                        remote['name'] = name
                        remote['renamedAt'] = stamp
                        published = json.loads(client.file(remote['path']+'/system.json', head))
                        published['name'] = name
                        files[remote['path']+'/system.json'] = gl.encoded(published)
                        files[remote['path']+'/README.md'] = ('# '+name+'\n\nPublished version '+str(remote['version'])+'\n\nFull source, assets and previews are preserved in each release archive.\n').encode()
                    else:
                        catalog['systems'] = [s for s in catalog['systems'] if s['id'] != ident]
                        tombstone = {**remote, 'deletedAt':stamp}
                        catalog.setdefault('deletedSystems', []).append(tombstone)
                        files[remote['path']+'/deleted.json'] = gl.encoded(tombstone)
                        files[remote['path']+'/README.md'] = ('# '+original['name']+'\n\nRemoved from the shared library on '+stamp+'.\n\nPublished archives are retained for recovery.\n').encode()
                    catalog['updatedAt'] = stamp
                    files[cfg['folder']+'/catalog.json'] = gl.encoded(catalog)
                    commit = client.commit(head, cfg['branch'], files, ('Rename '+original['name']+' to '+name) if action=='rename' else 'Remove '+original['name']+' from the library')
                    cfg.update(lastHead=commit, lastCheck=0, error=None)
                    gl.atomic_json(data/gl.CONFIG, cfg)
            if action == 'delete':
                backup = archive_local(data, target, stamp)
                return {'deleted':ident, 'shared':bool(client), 'backup':str(backup)}
            updated = copy.deepcopy(original)
            updated['name'] = name
            features.save_manifest(target, original, updated)
            return {'system':gl.access(data, updated), 'shared':bool(client)}
