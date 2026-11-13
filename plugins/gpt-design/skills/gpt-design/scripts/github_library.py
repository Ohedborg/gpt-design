"""Versioned GitHub library. Credentials stay in the local credential provider.

New imports upload their initial publication automatically. Later publications
are explicit; local drafts and running consumers keep their own versions.
"""
import base64
import contextlib
import copy
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

MAX_ARCHIVE = 40 * 1024 * 1024
MAX_UNPACKED = 128 * 1024 * 1024
MAX_FILE = 20 * 1024 * 1024
CONFIG = 'github-library.json'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        temp.write_bytes(encoded(value))
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


@contextlib.contextmanager
def library_lock(data):
    data.mkdir(parents=True, exist_ok=True)
    with (data / '.github.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def relative(value):
    if not isinstance(value, str) or not value or len(value) > 500 or '\\' in value or ':' in value or any(ord(c) < 32 for c in value):
        raise ValueError('Use a relative folder path.')
    parts = value.split('/')
    if any(not p or p in {'.', '..'} or p.startswith('.') for p in parts):
        raise ValueError('Use a relative folder path without hidden or parent folders.')
    return PurePosixPath(value)


def validate_config(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid GitHub library configuration.')
    repo = value.get('repository', '').strip().removeprefix('https://github.com/').removesuffix('.git').rstrip('/')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', repo) or repo.split('/')[1] in {'.','..'}:
        raise ValueError('Enter a GitHub repository as owner/repository.')
    branch = value.get('branch', '').strip()
    if branch and (len(branch)>200 or any(c in branch for c in '~^:?*[\\') or '..' in branch or '@{' in branch or any(ord(c)<=32 for c in branch) or branch.startswith(('/', '-')) or branch.endswith(('/', '.', '.lock'))):
        raise ValueError('Enter a valid branch name.')
    folder = value.get('folder', 'design-systems').strip().strip('/')
    relative(folder)
    return {**value, 'repository':repo, 'branch':branch, 'folder':folder}


def config(data):
    path = data / CONFIG
    if path.is_symlink():
        raise ValueError('The library configuration cannot be a symbolic link.')
    return validate_config(json.loads(path.read_text())) if path.exists() else None


def credentials():
    token = os.environ.get('GPT_DESIGN_GITHUB_TOKEN', '').strip()
    if token:
        return token
    gh = shutil.which('gh')
    if not gh:
        for candidate in ['/opt/homebrew/bin/gh', '/usr/local/bin/gh']:
            if Path(candidate).is_file():
                gh = candidate
                break
    if gh:
        try:
            result = subprocess.run([gh, 'auth', 'token', '--hostname', 'github.com'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


class GitHubError(ValueError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, repository):
        self.repository = validate_config({'repository':repository})['repository']
        self.token = credentials()
        self.prefix = '/repos/' + self.repository

    def request(self, path, payload=None, method=None, raw=False, limit=MAX_ARCHIVE):
        if not path.startswith(self.prefix + '/') and path not in {self.prefix, '/user'}:
            raise ValueError('Unexpected GitHub API path.')
        headers = {'Accept':'application/vnd.github.raw+json' if raw else 'application/vnd.github+json',
                   'X-GitHub-Api-Version':'2022-11-28', 'User-Agent':'GPT-Design/0.6'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request('https://api.github.com' + path, data=encoded(payload) if payload is not None else None,
                                     headers=headers, method=method)
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=45) as response:
                body = response.read(limit + 1)
            if len(body) > limit:
                raise GitHubError('The GitHub response exceeds the supported size.')
            return body if raw else json.loads(body)
        except urllib.error.HTTPError as exc:
            messages = {401:'Sign in to GitHub on this Mac, then reconnect the library.',
                        403:'GitHub denied this request. Check repository access, branch rules, or the API rate limit.',
                        404:'GitHub repository, branch or file not found. For a private repository, sign in with access.',
                        409:'The GitHub branch changed. Sync the library before trying again.',
                        422:'GitHub could not publish this change. Sync and check branch protection rules.'}
            raise GitHubError(messages.get(exc.code, 'GitHub request failed (HTTP '+str(exc.code)+').'), exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GitHubError('GitHub is unavailable. Your cached library and local drafts are still available.') from None

    def metadata(self):
        return self.request(self.prefix)

    def identity(self):
        return self.request('/user')['login']

    def head(self, branch):
        ref = self.request(self.prefix + '/git/ref/heads/' + urllib.parse.quote(branch, safe=''))
        return ref['object']['sha']

    def file(self, path, commit):
        relative(path)
        return self.request(self.prefix + '/contents/' + urllib.parse.quote(path, safe='/') + '?ref=' + urllib.parse.quote(commit, safe=''), raw=True)

    def commit(self, head, branch, files, message):
        parent = self.request(self.prefix + '/git/commits/' + head)
        entries = []
        for path, content in files.items():
            relative(path)
            entry = {'path':path, 'mode':'100644', 'type':'blob'}
            try:
                value = content.decode('utf-8')
                if len(content) > 800000:
                    raise UnicodeError()
                entry['content'] = value
            except UnicodeError:
                blob = self.request(self.prefix+'/git/blobs', {'encoding':'base64','content':base64.b64encode(content).decode()})
                entry['sha'] = blob['sha']
            entries.append(entry)
        tree = self.request(self.prefix+'/git/trees', {'base_tree':parent['tree']['sha'], 'tree':entries})
        commit = self.request(self.prefix+'/git/commits', {'message':message, 'tree':tree['sha'], 'parents':[head]})
        # Never force: concurrent publishing cannot overwrite another publisher.
        try:
            self.request(self.prefix+'/git/refs/heads/'+urllib.parse.quote(branch,safe=''), {'sha':commit['sha'],'force':False}, method='PATCH')
        except GitHubError as exc:
            # A lost response is not proof the publication failed.
            if exc.status is not None or self.head(branch)!=commit['sha']:
                raise
        return commit['sha']


def fingerprint(system):
    content = {k:v for k,v in system.items() if k not in {'name','revision','updatedAt','publication','shared','pendingUpload','_release','_access','status'}}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def catalog_at(client, cfg, head):
    try:
        catalog = json.loads(client.file(cfg['folder']+'/catalog.json', head))
    except GitHubError as exc:
        if exc.status == 404:
            return {'schemaVersion':1,'systems':[]}
        raise
    if not isinstance(catalog,dict) or catalog.get('schemaVersion')!=1 or not isinstance(catalog.get('systems'),list) or len(catalog['systems'])>1000:
        raise ValueError('This folder is not a supported GPT Design library.')
    ids, paths = set(), set()
    deleted = catalog.get('deletedSystems', [])
    if not isinstance(deleted, list) or len(deleted)>1000:
        raise ValueError('Invalid deleted design-system history.')
    if any(not isinstance(s,dict) or not isinstance(s.get('deletedAt'),str) for s in deleted):
        raise ValueError('Invalid deleted design-system entry.')
    for s in catalog['systems'] + deleted:
        if not isinstance(s,dict) or not re.fullmatch('[a-f0-9]{32}',s.get('id','')) or s['id'] in ids or not isinstance(s.get('name'),str):
            raise ValueError('Invalid design-system entry in the GitHub catalog.')
        ids.add(s['id'])
        path = str(relative(s.get('path','')))
        if not path.startswith(cfg['folder']+'/') or len(PurePosixPath(path).parts)!=len(PurePosixPath(cfg['folder']).parts)+1 or path.casefold() in paths:
            raise ValueError('Invalid or duplicate design-system folder.')
        paths.add(path.casefold())
        versions = s.get('versions')
        if not isinstance(versions,list) or not versions or len(versions)>1000:
            raise ValueError('Invalid version history in GitHub.')
        seen=set()
        for v in versions:
            number=v.get('version')
            if type(number)!=int or number<1 or number in seen or not re.fullmatch('[a-f0-9]{64}',v.get('sha256','')):
                raise ValueError('Invalid version metadata in GitHub.')
            seen.add(number)
            if v.get('archive')!=path+'/releases/'+str(number)+'.zip':
                raise ValueError('Invalid release archive path.')
        if s.get('version')!=max(seen):
            raise ValueError('The current publication must be the newest release.')
    return catalog


def public_status(cfg):
    if not cfg:
        return {'connected':False, 'authenticated':bool(credentials())}
    return {'connected':True, **{k:cfg.get(k) for k in ['repository','branch','folder','canWrite','lastSyncedAt','lastHead','error','pendingUploads']},
            'url':'https://github.com/'+cfg['repository'], 'authenticated':bool(credentials())}


def status(data):
    return public_status(config(data))


def connect(data, payload, client_factory=None):
    client_factory=client_factory or GitHub
    cfg=validate_config({k:payload[k] for k in ['repository','branch','folder'] if k in payload})
    with library_lock(data):
        prior=config(data)
        if prior and any(prior[k]!=cfg[k] for k in ['repository','folder']) or prior and cfg['branch'] and cfg['branch']!=prior['branch']:
            raise ValueError('Disconnect the current library before connecting a different repository or folder.')
        client=client_factory(cfg['repository']);meta=client.metadata()
        cfg['branch']=cfg['branch'] or meta['default_branch']
        head=client.head(cfg['branch'])
        catalog_at(client,cfg,head)
        cfg.update(canWrite=bool(meta.get('permissions',{}).get('push')), connectedAt=now(),error=None)
        atomic_json(data/CONFIG,cfg)
    return sync(data, force=True, client_factory=client_factory)


def disconnect(data):
    with library_lock(data):
        (data/CONFIG).unlink(missing_ok=True)
    return {'connected':False,'message':'Disconnected. Cached releases and drafts remain on this Mac.'}


def require_write(data, system=None, client_factory=None):
    client_factory=client_factory or GitHub
    cfg=config(data)
    if system and (system.get('shared') or system.get('pendingUpload')):
        shared=system.get('shared') or system['pendingUpload']
        if not cfg or any(cfg[k]!=shared.get(k) for k in ['repository','branch','folder']):
            raise ValueError('Reconnect this system’s GitHub library before editing or publishing.')
    if not cfg:
        return None
    client=client_factory(cfg['repository'])
    if not client.metadata().get('permissions',{}).get('push'):
        raise ValueError('This GitHub account has read-only access. Repository write access is required to edit or publish shared systems.')
    return client


def access(data, system):
    cfg=config(data);shared=system.get('shared')
    linked=bool(shared)
    matches=bool(cfg and (not linked or all(cfg[k]==shared.get(k) for k in ['repository','branch','folder'])))
    return {**system,'_access':{'shared':linked,'canPublish':bool(cfg.get('canWrite')) if matches else not linked and not cfg,
                             'repository':cfg['repository'] if matches else shared.get('repository') if shared else None}}


def publication_context(data, original, client_factory=None):
    client_factory=client_factory or GitHub
    cfg=config(data)
    if not cfg:
        require_write(data,original,client_factory)
        return None
    client=require_write(data,original,client_factory)
    head=client.head(cfg['branch']);catalog=catalog_at(client,cfg,head)
    remote=next((s for s in catalog['systems'] if s['id']==original['id']),None)
    if any(s['id']==original['id'] for s in catalog.get('deletedSystems', [])):
        raise ValueError('This design system was deleted from the shared library. Refresh the library before continuing.')
    if remote and original.get('shared') and remote['name']!=original['name']:
        raise ValueError('This design system was renamed on GitHub. Refresh the library before publishing.')
    shared=original.get('shared')
    pending=original.get('pendingUpload')
    recovered=False
    if remote and not shared and pending and remote['version']==pending['version']:
        # A commit may have succeeded before the process saved the local binding.
        version=next(v for v in remote['versions'] if v['version']==pending['version'])
        snapshot=data/'systems'/original['id']/'releases'/str(pending['version'])
        recovered=hashlib.sha256(pack(snapshot)).hexdigest()==version['sha256']
    if remote and not recovered and (not shared or shared.get('baseVersion')!=remote['version']):
        raise ValueError('A newer version is on GitHub. Sync, then use “Start from latest” before publishing; your draft will be backed up.')
    if shared and not remote:
        raise ValueError('This shared system is missing from GitHub. Reconnect or restore the repository before publishing.')
    return {'config':cfg,'client':client,'head':head,'catalog':catalog,'remote':remote,'author':client.identity(),'name':original['name']}


def pack(folder):
    output=io.BytesIO();total=0;count=0
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(folder.rglob('*')):
            if file.is_symlink():
                raise ValueError('Publication archives cannot contain symbolic links.')
            if not file.is_file():
                continue
            name=file.relative_to(folder).as_posix();relative(name)
            size=file.stat().st_size;total+=size;count+=1
            if size>MAX_FILE or total>MAX_UNPACKED or count>6000:
                raise ValueError('This publication exceeds the GitHub library size limits.')
            info=zipfile.ZipInfo(name,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,file.read_bytes())
    raw=output.getvalue()
    if len(raw)>MAX_ARCHIVE:
        raise ValueError('This publication exceeds the 40 MB archive limit.')
    return raw


def unpack(raw, dest, ident, version, expected):
    if len(raw)>MAX_ARCHIVE or hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('The downloaded release failed its integrity check.')
    seen=set();total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries=archive.infolist()
        if len(entries)>6000:
            raise ValueError('Too many files in the release archive.')
        for entry in entries:
            path=relative(entry.filename)
            if entry.is_dir() or stat.S_ISLNK(entry.external_attr>>16) or entry.filename.casefold() in seen:
                raise ValueError('Unsafe or duplicate release archive entry.')
            if path.parts[0] not in {'system.json','tokens.json','tokens.css','release.json','source','assets','previews'}:
                raise ValueError('Unexpected file in the release archive.')
            total+=entry.file_size
            if entry.file_size>MAX_FILE or total>MAX_UNPACKED:
                raise ValueError('The expanded release exceeds the supported size.')
            seen.add(entry.filename.casefold())
            file=dest/path;file.parent.mkdir(parents=True,exist_ok=True)
            file.write_bytes(archive.read(entry))
    manifest=json.loads((dest/'release.json').read_text());system=json.loads((dest/'system.json').read_text())
    if manifest.get('version')!=version or system.get('id')!=ident or not isinstance(system.get('tokens'),list) or system.get('shared'):
        raise ValueError('The release identity does not match the shared library.')
    checksums=manifest.get('checksums',{})
    files={p.relative_to(dest).as_posix():p for p in dest.rglob('*') if p.is_file() and p!=dest/'release.json'}
    if set(checksums)!=set(files) or not {'system.json','tokens.json','tokens.css'}.issubset(files):
        raise ValueError('The release has missing or unexpected files.')
    for name,file in files.items():
        if hashlib.sha256(file.read_bytes()).hexdigest()!=checksums[name]:
            raise ValueError('A release file failed its integrity check.')
    return system,manifest


def publish_prepared(data, ident, stage, snapshot, manifest, context):
    if not context:
        return None
    cfg=context['config'];catalog=copy.deepcopy(context['catalog']);remote=context['remote']
    slug=re.sub('[^a-z0-9]+','-',snapshot['name'].lower()).strip('-')[:70] or 'design-system'
    path=remote['path'] if remote else cfg['folder']+'/'+slug+'-'+ident[:8]
    versions=copy.deepcopy(remote['versions']) if remote else []
    files={}
    candidates=[p for p in (data/'systems'/ident/'releases').glob('[0-9]*') if p.is_dir()] + [stage]
    for folder in candidates:
        info=json.loads((folder/'release.json').read_text())
        if any(v['version']==info['version'] for v in versions):
            continue
        raw=pack(folder);archive=path+'/releases/'+str(info['version'])+'.zip'
        versions.append({'version':info['version'],'archive':archive,'sha256':hashlib.sha256(raw).hexdigest(),
                         'publishedAt':info['publishedAt'],'notes':info['notes']})
        files[archive]=raw
    library_name=context.get('name', snapshot['name'])
    entry={'id':ident,'name':library_name,'path':path,'version':manifest['version'],
           'versions':sorted(versions,key=lambda v:v['version'])}
    catalog['systems']=[s for s in catalog['systems'] if s['id']!=ident]+[entry]
    catalog['updatedAt']=now()
    files[cfg['folder']+'/catalog.json']=encoded(catalog)
    for name in ['system.json','tokens.json','tokens.css']:
        files[path+'/'+name]=(stage/name).read_bytes()
    files[path+'/system.json']=encoded({**snapshot, 'name':library_name})
    files[path+'/guidelines.json']=encoded({'guide':snapshot.get('guide',{}),'componentNotes':snapshot.get('componentNotes',{})})
    files[path+'/README.md']=('# '+library_name+'\n\nPublished version '+str(manifest['version'])+'\n\n'+manifest['notes']+'\n\nFull source, assets and previews are preserved in each release archive.\n').encode()
    commit=context['client'].commit(context['head'],cfg['branch'],files,'Publish '+snapshot['name']+' v'+str(manifest['version']))
    cfg.update(lastHead=commit,lastSyncedAt=now(),lastCheck=time.time(),canWrite=True,error=None)
    atomic_json(data/CONFIG,cfg)
    return {k:cfg[k] for k in ['repository','branch','folder']} | {'path':path,'baseVersion':manifest['version'],
            'latestVersion':manifest['version'],'baseFingerprint':fingerprint(snapshot),'commit':commit}


def share_publication(data, ident, revision):
    """Back up existing publications without publishing an unfinished draft."""
    import gpt_design as gd
    import studio_features as features
    import releases
    with library_lock(data):
        target=features.target_for(data,ident)
        with gd.system_lock(target):
            original=json.loads((target/'system.json').read_text())
            if original.get('revision',0)!=revision:
                raise ValueError('Reopen the system before sharing its publication.')
            if original.get('shared'):
                raise ValueError('This system is already shared. Publish its draft to send a new version.')
            version=original.get('publication',{}).get('version')
            if not version:
                raise ValueError('Publish a version before backing up this system.')
            context=publication_context(data,original)
            if not context:
                raise ValueError('Connect a GitHub library first.')
            stage=releases.release_path(data,ident,version)
            snapshot=json.loads((stage/'system.json').read_text())
            manifest=json.loads((stage/'release.json').read_text())
            binding=publish_prepared(data,ident,stage,snapshot,manifest,context)
            updated=copy.deepcopy(original);updated['shared']=binding
            updated.pop('pendingUpload',None)
            features.save_manifest(target,original,updated)
            return {'system':access(data,updated),'version':version,'repository':binding['repository']}


def initialize_import(data, ident, connection):
    """Freeze v1 before uploading, so retries never publish subsequent draft edits."""
    import releases
    target=data/'systems'/ident
    system=json.loads((target/'system.json').read_text())
    releases.publish(data,ident,{'revision':system.get('revision',0),
                                'notes':'Initial version created automatically when the design system was added.'},
                     initial_connection=connection)
    retry_uploads(data,ident=ident,force=True)
    return access(data,json.loads((target/'system.json').read_text()))


def retry_uploads(data, ident=None, force=False):
    """Retry only queued initial publications, bound to their original destination."""
    import gpt_design as gd
    errors=[];pending=0
    paths=[data/'systems'/ident/'system.json'] if ident else sorted((data/'systems').glob('*/system.json'))
    for path in paths:
        try:
            system=json.loads(path.read_text())
        except FileNotFoundError:
            continue
        upload=system.get('pendingUpload')
        if not upload:
            continue
        if not force and time.time()-upload.get('lastAttempt',0)<60:
            pending+=1
            if upload.get('error'): errors.append(system['name']+': '+upload['error'])
            continue
        try:
            share_publication(data,system['id'],system.get('revision',0))
        except (ValueError,OSError,zipfile.BadZipFile) as exc:
            message=str(exc)[:400]
            with library_lock(data):
                if not path.is_file():
                    continue
                with gd.system_lock(path.parent):
                    latest=json.loads(path.read_text())
                    if latest.get('pendingUpload'):
                        latest['pendingUpload'].update(lastAttempt=time.time(),error=message)
                        atomic_json(path,latest)
                        pending+=1;errors.append(latest['name']+': '+message)
    return pending,errors


def copy_snapshot(source, dest):
    for name in ['system.json','tokens.json','tokens.css','source','assets','previews']:
        origin=source/name;target=dest/name
        if target.is_symlink():
            raise ValueError('A local snapshot path cannot be a symbolic link.')
        if origin.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(origin,target)
        elif origin.exists():
            shutil.copyfile(origin,target)
        elif target.is_dir():
            shutil.rmtree(target)


def backup_draft(target):
    backup=target/'history'/('draft-'+uuid.uuid4().hex)
    backup.mkdir(parents=True)
    copy_snapshot(target,backup)
    return backup


def sync(data, force=False, client_factory=None):
    client_factory=client_factory or GitHub
    import gpt_design as gd
    cfg=config(data)
    if not cfg:
        return {'connected':False}
    if not force and time.time()-cfg.get('lastCheck',0)<60:
        return public_status(cfg)
    pending,upload_errors=retry_uploads(data,force=force)
    with library_lock(data):
        cfg=config(data)
        if not cfg:
            return {'connected':False}
        try:
            client=client_factory(cfg['repository']);meta=client.metadata();head=client.head(cfg['branch'])
            cfg['canWrite']=bool(meta.get('permissions',{}).get('push'))
            catalog=catalog_at(client,cfg,head)
            updated=[];conflicts=[];deleted=[]
            from system_management import archive_local
            for entry in catalog.get('deletedSystems', []):
                target=data/'systems'/entry['id']
                if target.is_symlink():
                    raise ValueError('A cached system cannot be a symbolic link.')
                if not (target/'system.json').is_file():
                    continue
                with gd.system_lock(target):
                    old=json.loads((target/'system.json').read_text())
                    binding=old.get('shared') or old.get('pendingUpload')
                    if binding and all(binding.get(k)==cfg[k] for k in ['repository','branch','folder']):
                        archive_local(data,target,entry['deletedAt'])
                        deleted.append(entry['id'])
            for entry in catalog['systems']:
                target=data/'systems'/entry['id']
                if target.is_symlink() or (target/'releases').is_symlink():
                    raise ValueError('A cached system cannot be a symbolic link.')
                target.mkdir(parents=True,exist_ok=True)
                with gd.system_lock(target):
                    old=json.loads((target/'system.json').read_text()) if (target/'system.json').exists() else None
                    if old and (not old.get('shared') or any(old['shared'].get(k)!=cfg[k] for k in ['repository','branch','folder'])):
                        raise ValueError('A local system has the same ID as a different shared system. It has been preserved.')
                    if old and old['shared'].get('latestVersion',0)>entry['version']:
                        raise ValueError('GitHub removed a newer publication. The cached version has been preserved; use a new rollback release instead.')
                    releases=target/'releases';releases.mkdir(exist_ok=True)
                    for version in entry['versions']:
                        dest=releases/str(version['version'])
                        receipt=dest/'.github-sha256'
                        if dest.is_symlink():
                            raise ValueError('A cached release cannot be a symbolic link.')
                        if receipt.is_file():
                            if receipt.read_text()!=version['sha256']:
                                raise ValueError('GitHub changed an existing release. The cached version has been preserved.')
                            continue
                        with tempfile.TemporaryDirectory(dir=releases,prefix='.sync-') as tmp:
                            stage=Path(tmp)
                            raw=client.file(version['archive'],head)
                            unpack(raw,stage,entry['id'],version['version'],version['sha256'])
                            if dest.exists():
                                if (dest/'release.json').read_bytes()!=(stage/'release.json').read_bytes():
                                    raise ValueError('A local publication differs from GitHub. It has been preserved.')
                            else:
                                shutil.copytree(stage,dest)
                            receipt.write_text(version['sha256'])
                    latest=releases/str(entry['version'])
                    snapshot=json.loads((latest/'system.json').read_text());release=json.loads((latest/'release.json').read_text())
                    clean=old is None or fingerprint(old)==old['shared'].get('baseFingerprint')
                    # Older clients included the display name in their fingerprint.
                    if old and not clean:
                        base=target/'releases'/str(old['shared'].get('baseVersion'))/'system.json'
                        clean=base.is_file() and fingerprint(old)==fingerprint(json.loads(base.read_text()))
                    previous=old.get('shared',{}).get('latestVersion') if old else None
                    binding={k:cfg[k] for k in ['repository','branch','folder']} | {'path':entry['path'],'latestVersion':entry['version'],'commit':head}
                    if old is None or clean and previous!=entry['version']:
                        if old: backup_draft(target)
                        copy_snapshot(latest,target)
                        system=copy.deepcopy(snapshot)
                        system['revision']=(old.get('revision',0)+1) if old else 0
                        binding.update(baseVersion=entry['version'],baseFingerprint=fingerprint(snapshot))
                        updated.append(entry['id'])
                    else:
                        system=copy.deepcopy(old)
                        binding.update(baseVersion=old['shared']['baseVersion'],baseFingerprint=old['shared']['baseFingerprint'])
                        if binding['baseVersion']!=entry['version']: conflicts.append(entry['id'])
                    if system['name']!=entry['name']:
                        system['name']=entry['name']
                        system['revision']=max(system.get('revision',0),old.get('revision',0) if old else 0)+1
                        if entry['id'] not in updated: updated.append(entry['id'])
                    system['shared']=binding
                    system['publication']={k:release[k] for k in ['version','notes','publishedAt','sourceRevision','rollbackOf']}
                    atomic_json(target/'system.json',system)
            cfg.update(lastHead=head,lastSyncedAt=now(),lastCheck=time.time(),pendingUploads=pending,
                       error=('Waiting to upload '+str(pending)+' system(s). '+upload_errors[0])[:500] if upload_errors else None)
            atomic_json(data/CONFIG,cfg)
            return public_status(cfg) | {'updated':updated,'draftsBehind':conflicts,'deleted':deleted}
        except (ValueError,OSError,zipfile.BadZipFile,KeyError,TypeError) as exc:
            cfg.update(lastCheck=time.time(),error=str(exc)[:500])
            if isinstance(exc,GitHubError) and exc.status in {401,403,404}:
                cfg['canWrite']=False
            atomic_json(data/CONFIG,cfg)
            return public_status(cfg)


def start_from_latest(data, ident, revision, client_factory=None):
    client_factory=client_factory or GitHub
    import gpt_design as gd
    import studio_features as features
    with library_lock(data):
        target=features.target_for(data,ident)
        with gd.system_lock(target):
            old=json.loads((target/'system.json').read_text())
            require_write(data,old,client_factory)
            if old.get('revision',0)!=revision or not old.get('shared'):
                raise ValueError('Reopen the shared system before refreshing its draft.')
            latest=target/'releases'/str(old['shared']['latestVersion'])
            backup=backup_draft(target);copy_snapshot(latest,target)
            system=json.loads((latest/'system.json').read_text())
            system['name']=old['name']
            system['revision']=old.get('revision',0)+1
            system['publication']=old['publication']
            system['shared']={**old['shared'],'baseVersion':old['shared']['latestVersion'],'baseFingerprint':fingerprint(system)}
            atomic_json(target/'system.json',system)
            return {'system':access(data,system),'backup':str(backup)}
