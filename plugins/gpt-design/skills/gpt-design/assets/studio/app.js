'use strict';
const $ = (s) => document.querySelector(s);
const main = $('#main');
const escape = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const studioStorage = (()=>{try{sessionStorage.setItem('gpt-design-probe','1');sessionStorage.removeItem('gpt-design-probe');return sessionStorage;}catch{const memory=new Map();return {getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,String(v)),removeItem:k=>memory.delete(k)};}})();
const launchParams = new URLSearchParams(location.hash.slice(1));
const requestedSystemId=launchParams.get('system');
const session = launchParams.get('token');
if (session) { studioStorage.setItem('gpt-design-token', session); history.replaceState(null, '', '/'); }
const token = session || studioStorage.getItem('gpt-design-token') || '';
const groups = [
 ['colors','Color & type tokens','Palettes, themes, font families, and text styles.'],
 ['spacing','Spacing & radii','Spacing scale, sizing, border radii, and shadows.'],
 ['assets','Fonts & logos','Original font files, images, icons, and brand guidelines.'],
 ['components','Components','A source inventory. Live previews can be built in chat.']
];
let state, library = [], libraryPath = '', roots = [], current, activeTab = 'overview', sharedLibrary={connected:false};
const art = `<div class="art" aria-hidden="true"><svg viewBox="0 0 100 85"><g fill="none" stroke="#8e70cf" stroke-width="4"><rect x="19" y="17" width="61" height="48" rx="3"/><path d="M33 41h32M49 28v26" opacity=".3"/></g><g fill="#b7a0e3" stroke="#8e70cf" stroke-width="3"><rect x="14" y="12" width="10" height="10" rx="2"/><rect x="75" y="12" width="10" height="10" rx="2"/><rect x="14" y="60" width="10" height="10" rx="2"/></g><path d="M76 58l15 20 3-10 8-4z" fill="#8e70cf"/></svg></div>`;
async function api(path, body) {
 if(window.gptDesignHost) return window.gptDesignHost.api(path, body);
 const response = await fetch(path, {method:body?'POST':'GET', headers:{'X-GPT-Design-Token':token,...(body?{'Content-Type':'application/json'}:{})}, body:body?JSON.stringify(body):undefined});
 const result = await response.json(); if(!response.ok) throw new Error(result.error || 'Something went wrong.'); return result;
}
function toast(text) { $('#toast').textContent=text; $('#toast').style.display='block'; setTimeout(()=>$('#toast').style.display='none',3500); }
function crumb(text='Design systems') { $('#breadcrumb').innerHTML=`Workspace <span>/</span> ${escape(text)}`; }
function reset() { state={step:0,kind:'github',name:'',repo:'',ref:'',folder:'',path:'',scope:groups.map(g=>g[0]),files:[]}; }
function stepper(n) { return `<div class="steps">${['Source','Include','Review'].map((label,i)=>`${i?'<i></i>':''}<span class="step ${i+1===n?'on':''}"><b>${i+1}</b>${label}</span>`).join('')}</div>`; }
function field(id,label,placeholder='',help='',value='') { return `<label class="field" for="${id}">${label}<input id="${id}" value="${escape(value)}" placeholder="${escape(placeholder)}" autocomplete="off">${help?`<small>${escape(help)}</small>`:''}</label>`; }
function error(err) { let el=$('#error'); if(!el){el=document.createElement('div');el.id='error';el.setAttribute('role','alert');document.querySelector('.panel')?.append(el);} el.className='error';el.textContent=err.message || err; }
function choose() {
 crumb('Add design system');
 main.innerHTML=`<div class="hero">${art}<div class="eyebrow">Start with your foundation</div><h1>What should this design<br>system be built from?</h1><p class="subtitle">Bring your code, tokens, and brand assets together.</p></div><div class="options">
 <button class="source-card" data-source="github"><span class="icon">⌘</span><span><strong>GitHub repository</strong><p>Import tokens, assets, and component source<br>from your design-system repository.</p></span><span class="arrow">↗</span></button>
 <button class="source-card" data-source="local"><span class="icon">▤</span><span><strong>Local folder</strong><p>Use a repository or design-system folder<br>already on your computer.</p></span><span class="arrow">↗</span></button>
 <button class="source-card" data-source="upload"><span class="icon">↥</span><span><strong>Upload files</strong><p>Add token files, component source, fonts,<br>images, and brand guidelines.</p></span><span class="arrow">↗</span></button></div><p class="hint">Your sources. Your system. A reusable starting point.</p>`;
 document.querySelectorAll('[data-source]').forEach(b=>b.onclick=()=>{state.kind=b.dataset.source;state.step=1;sourceForm();});
}
function sourceForm() {
 let fields='';
 if(state.kind==='github') fields=field('repo','GitHub repository','owner/repository','For a private repository, use an authorized local checkout or your connected GitHub tools.',state.repo)+`<div class="two-col">${field('ref','Branch, tag, or commit','Default branch','Optional',state.ref)}${field('folder','Folder','packages/ui','Optional',state.folder)}</div>`;
 else if(state.kind==='local') fields=field('path','Folder on your computer','/path/to/your/design-system','Allowed folders: '+roots.join(', '),state.path);
 else fields=`<label class="drop">Choose your files<input id="files" type="file" multiple accept=".css,.scss,.json,.ts,.tsx,.js,.jsx,.vue,.svelte,.md,.txt,.yaml,.yml,.png,.jpg,.jpeg,.svg,.webp,.gif,.ico,.woff,.woff2,.ttf,.otf,.pdf"><small>CSS and JSON tokens, component source, fonts, images, and guidelines.<br>Up to 20 MB total. PDFs and images are preserved for review in chat.</small></label><div class="file-list" id="fileList">${state.files.length?state.files.length+' files selected':'No files selected'}</div>`;
 main.innerHTML=stepper(1)+`<section class="panel"><div class="eyebrow">Make it your own</div><h1>${state.kind==='upload'?'Bring your files together.':'Where does your system live?'}</h1><p class="subtitle">Choose a source and give your design system a name.</p>${field('name','Design system name','e.g. Acme Brand', '',state.name)}${fields}<div id="error" role="alert"></div><div class="actions"><button class="button quiet" id="back">← Back</button><button class="button primary" id="next">Continue →</button></div></section>`;
 $('#back').onclick=()=>{collect();choose();};
 if($('#files')) $('#files').onchange=e=>{state.files=[...e.target.files];$('#fileList').textContent=state.files.map(f=>f.name).join(' · ');};
 $('#next').onclick=()=>{collect();if(!state.name.trim())return error('Give your design system a name.');if(state.name.length>120)return error('Use a name shorter than 120 characters.');if(state.kind==='github'&&!state.repo.trim())return error('Enter a GitHub repository.');if(state.kind==='local'&&!state.path.trim())return error('Enter a local folder.');if(state.kind==='upload'&&!state.files.length)return error('Choose at least one file.');if(state.files.some(f=>f.name.toLowerCase().endsWith('.fig')))return error('Figma imports are no longer supported. Upload exported tokens, assets, or component source instead.');if(state.files.reduce((n,f)=>n+f.size,0)>20*1024*1024)return error('Choose files totaling less than 20 MB.');state.step=2;scopeForm();};
}
function collect(){for(const key of ['name','repo','ref','folder','path'])if($('#'+key))state[key]=$('#'+key).value;}
function scopeForm(){
 main.innerHTML=stepper(2)+`<section class="panel"><div class="eyebrow">Choose what matters</div><h1>What should we bring in?</h1><p class="subtitle">Keep the parts you want to create with. You can add more later.</p>${groups.map(([key,title,description])=>`<label class="check"><input type="checkbox" value="${key}" ${state.scope.includes(key)?'checked':''}><span><strong>${title}</strong><p>${description}</p></span></label>`).join('')}<div class="actions"><button class="button quiet" id="back">← Back</button><span class="selection-count" id="selected">${state.scope.length} selected</span><button class="button primary" id="next" ${!state.scope.length?'disabled':''}>Review import →</button></div></section>`;
 $('#back').onclick=sourceForm;document.querySelectorAll('.check input').forEach(c=>c.onchange=()=>{state.scope=[...document.querySelectorAll('.check input:checked')].map(x=>x.value);$('#selected').textContent=state.scope.length+' selected';$('#next').disabled=!state.scope.length;});$('#next').onclick=()=>{state.step=3;review();};
}
function review(){
 const source=state.kind==='github'?state.repo+(state.ref?' @ '+state.ref:'')+(state.folder?' / '+state.folder:''):state.kind==='local'?state.path:state.files.length+' files';
 main.innerHTML=stepper(3)+`<section class="panel"><div class="eyebrow">A new beginning</div><h1>Ready to build your foundation?</h1><p class="subtitle">Here’s what we’ll bring into ${escape(state.name)}.</p><div class="review-row">Design system<strong>${escape(state.name)}</strong></div><div class="review-row">Source<strong>${escape(source)}</strong></div><div class="review-row">Include<strong>${state.scope.map(k=>groups.find(g=>g[0]===k)[1]).join('<br>')}</strong></div><div class="review-row">Import mode<strong>New snapshot</strong></div><div class="notice">Tokens and assets are read directly from your files. Components are added as a source inventory; you can ask GPT Design to build live previews afterward.</div><div id="error" role="alert"></div><div class="actions"><button class="button quiet" id="back">← Back</button><button class="button primary" id="import">Create design system →</button></div></section>`;
 $('#back').onclick=scopeForm;$('#import').onclick=doImport;
}
async function doImport(){
 const button=$('#import');button.disabled=true;$('#back').disabled=true;button.innerHTML='<span class="busy"></span> '+(state.kind==='github'?'Reading repository…':'Preparing your system…');
 try{
  const payload={...state,files:[]};
  if(state.kind==='upload') for(const f of state.files){const content=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(f);});payload.files.push({name:f.name,content});}
  current=await api('/api/import',payload);await refresh();activeTab='overview';detail();toast('Design system saved');
 }catch(e){error(e);button.disabled=false;$('#back').disabled=false;button.textContent='Try again →';}
}
async function copy(text){try{await navigator.clipboard.writeText(text);toast('Copied to clipboard');}catch{toast('Select the text and copy it to continue.');}}
async function refresh(){const r=await api('/api/systems');library=r.systems;libraryPath=r.library;roots=r.allowedRoots;sharedLibrary=r.github||{connected:false};updateLibraryButton();$('#systemCount').textContent=library.length;}
function showLibrary(){
 if(!leaveWorkspace()) return; crumb();if(!library.length){reset();choose();return;}
 main.innerHTML=`<div class="library-title"><div><div class="eyebrow">Your creative foundation</div><h1>${library.length>1?'Which design system would you like to use?':'Design systems'}</h1><p class="subtitle">${library.length>1?'Choose a system to explore or work with.':'Your design foundation, ready to use.'}</p></div><button class="button primary" id="add">＋ Add design system</button></div><div class="library-grid">${library.map(s=>`<button class="system-card" data-id="${s.id}"><div class="system-art" aria-hidden="true"><span></span><span></span><span></span></div><div class="system-info"><h2>${escape(s.name)}</h2><p>${s.counts.tokens} tokens · ${s.counts.assets} assets · ${s.counts.components} ${s.source.kind==='figma-file'?'design components':'component sources'}</p><p>${escape(s.source.kind)} snapshot · ${new Date(s.createdAt).toLocaleDateString()}</p></div></button>`).join('')}</div><p class="hint">Each import is saved as its own snapshot.</p>`;
 $('#add').onclick=newSystem;document.querySelectorAll('[data-id]').forEach(b=>b.onclick=async()=>{try{current=await loadSystemForViewing(b.dataset.id);activeTab='overview';detail();}catch(e){toast(e.message);}});
}
async function download(file){try{let blob;if(window.gptDesignHost){const result=await window.gptDesignHost.export(current.id,file,current._release?.version);blob=new Blob([result.text],{type:result.mimeType});}else if(current._release){const result=await api('/api/systems/'+current.id+'/releases/'+current._release.version+'/'+file);blob=new Blob([file==='system.json'?JSON.stringify(result,null,2):result.text],{type:'application/json'});}else{const r=await fetch('/api/systems/'+current.id+'/'+file,{headers:{'X-GPT-Design-Token':token}});if(!r.ok)throw new Error('Could not export this system.');blob=await r.blob();}const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=current.name.replace(/[^a-z0-9-]/gi,'-')+'-'+file;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Export downloaded');}catch(e){toast(e.message);}}
function newSystem(){if(!leaveWorkspace())return;reset();choose();}
$('#newTop').onclick=newSystem;$('#libraryNav').onclick=showLibrary;$('.brand').onclick=e=>{e.preventDefault();showLibrary();};
async function openSelectedSystem(id){
 if(!library.some(s=>s.id===id)){showLibrary();toast('That design system is unavailable. Choose one from your library.');return;}
 if(current?.id===id&&document.body.classList.contains('workspace-mode'))return;
 if(!canLeaveWorkspace())return;
 current=await loadSystemForViewing(id);activeTab='overview';workspaceQuery='';detail();
}
mountLibraryButton();
reset();refresh().then(async()=>{
 if(requestedSystemId)await openSelectedSystem(requestedSystemId);
 else if(library.length===1)await openSelectedSystem(library[0].id);
 else showLibrary();
 window.gptDesignHost?.onSystemSelection(id=>openSelectedSystem(id).catch(e=>toast(e.message)));
}).catch(e=>{main.innerHTML=`<section class="panel"><h1>Let’s reconnect your studio.</h1><p class="subtitle">${escape(e.message)}</p><p class="notice">Ask GPT Design in chat to reopen the studio.</p></section>`;});

function mountLibraryButton(){
 if(!$('#githubLibrary')){
  const button=document.createElement('button');button.id='githubLibrary';button.className='nav github-library-button';button.type='button';button.onclick=showGitHubLibrary;
  $('#libraryNav').after(button);
 }
 updateLibraryButton();
}
function updateLibraryButton(){
 const button=$('#githubLibrary');if(button)button.textContent=sharedLibrary.connected?(sharedLibrary.error?'GitHub · needs attention':'GitHub · connected'):'Connect GitHub library';
 const footer=$('#footerRight');if(footer)footer.textContent=sharedLibrary.connected?'Published systems sync with GitHub':'Your library stays on this Mac';
}
async function showGitHubLibrary(){
 if(!canLeaveWorkspace())return;
 try{sharedLibrary=await api('/api/github');}catch(e){toast(e.message);return;}
 const s=sharedLibrary;
 const d=featureDialog('GitHub library',s.connected?`
  <p><strong>${escape(s.repository)}</strong></p><p class="subtitle">${escape(s.folder)} · ${escape(s.branch)} · ${s.canWrite?'Can publish':'Read-only access'}</p>
  <p>Published systems are shared through this repository. Draft edits stay on this Mac until you publish.</p>
  <p class="inventory-note">${s.lastSyncedAt?'Last synced '+escape(new Date(s.lastSyncedAt).toLocaleString()):'Not synced yet.'}</p>
  ${s.error?`<p class="error" role="alert">${escape(s.error)}</p>`:''}
  <div class="actions"><button class="button quiet" id="disconnectGitHub">Disconnect</button><button class="button primary" id="syncGitHub">Sync now</button></div>`:`
  <p>Choose a shared home for your design systems. Connect an existing repository with an initial commit.</p>
  ${!s.authenticated?'<p class="notice">For private repositories and publishing, sign in to GitHub on this Mac. Ask GPT Design in chat to help you connect. Public libraries can be read without signing in.</p>':''}
  <form id="connectGitHubForm">${field('libraryRepo','Repository','owner/repository')}${field('libraryFolder','Design systems folder','design-systems','','design-systems')}${field('libraryBranch','Branch','Repository default','Optional')}
  <p class="inventory-note">Connecting downloads published systems. Your local systems are uploaded only when you publish.</p><p id="githubError" class="error" role="alert" hidden></p><button class="button primary" type="submit">Connect library</button></form>`);
 if(s.connected){
  $('#syncGitHub').onclick=async()=>{const b=$('#syncGitHub');b.disabled=true;b.textContent='Syncing…';try{const result=await api('/api/github/sync',{});await refresh();d.close();if(document.body.classList.contains('workspace-mode')){toast(result.error||'Library synced. Reopen the system to use its latest publication.');}else{showLibrary();toast(result.error||'Library synced');}}catch(e){toast(e.message);b.disabled=false;b.textContent='Sync now';}};
  $('#disconnectGitHub').onclick=async()=>{try{await api('/api/github/disconnect',{});await refresh();d.close();showLibrary();toast('Disconnected. Your local copies are preserved.');}catch(e){toast(e.message);}};
 }else $('#connectGitHubForm').onsubmit=async e=>{e.preventDefault();const b=e.currentTarget.querySelector('button');b.disabled=true;b.textContent='Connecting…';try{const result=await api('/api/github/connect',{repository:$('#libraryRepo').value,folder:$('#libraryFolder').value,branch:$('#libraryBranch').value});await refresh();d.close();showLibrary();toast(result.error||'GitHub library connected');}catch(err){$('#githubError').hidden=false;$('#githubError').textContent=err.message;b.disabled=false;b.textContent='Connect library';}};
}
