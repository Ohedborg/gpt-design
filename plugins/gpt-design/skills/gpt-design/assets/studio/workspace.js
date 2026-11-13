'use strict';
const sections = [
 ['overview','Overview','book'],['guidelines','Guidelines','book'],['colors','Colors','palette'],['typography','Typography','type'],
 ['spacing','Spacing','space'],['radius','Corner radius','radius'],['shadows','Shadows','shadow'],
 ['size','Size','size'],['global','Global','global'],['components','Components','box'],['assets','Assets','image'],['files','Files','folder']
];
const iconPaths = {
 book:'M12 6c-3-2-6-2-9-1v14c3-1 6-1 9 1m0-14c3-2 6-2 9-1v14c-3-1-6-1-9 1V6',
 palette:'M12 3a9 9 0 1 0 0 18h2a3 3 0 0 0 0-6h-1a2 2 0 0 1 0-4h3a5 5 0 0 0 0-8h-4M7 8h.01M6 13h.01M10 6h.01',
 type:'M3 5h14M10 5v15M15 11h7M18.5 11v9',space:'M9 8l-4 4 4 4M5 12h14m-4-4 4 4-4 4',
 radius:'M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m8 0h3a2 2 0 0 0 2-2v-3',
 shadow:'M8 8h12v12H8zM4 4h12v12H4z',size:'M6 3h12a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3M8 12h8m-4-4v8',
 global:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M3 12h18M12 3c-5 5-5 13 0 18 5-5 5-13 0-18',
 box:'M12 3l9 5-9 5-9-5 9-5m-9 5v10l9 5 9-5V8M12 13v10',image:'M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2M3 16l6-6 12 11M15 7h.01',
 folder:'M3 6h7l2 3h9v12H3V6',search:'M16 16l5 5M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14',
 source:'M6 3h12a2 2 0 0 1 2 2v7l-8 9H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2m6 18v-7a2 2 0 0 1 2-2h6',
 trash:'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',close:'M6 6l12 12M18 6L6 18',
 download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',check:'M5 12l4 4L19 6',back:'M10 5l-7 7 7 7M3 12h18',undo:'M3 9h10a6 6 0 0 1 0 12M3 9l5-5M3 9l5 5'
};
function icon(name){return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${iconPaths[name]||iconPaths.global}"/></svg>`;}
let edits = new Map(), saving = false, workspaceQuery = '', rowLimit = 150;
function tokenSection(t){
 const n=t.name.toLowerCase(), typ=(t.type||'').toLowerCase();
 if(/typograph|font|line[-_.]?height|letter[-_.]?spacing|text[-_.]?(size|weight)/.test(n)||/font|typography|lineheight/.test(typ))return 'typography';
 if(/shadow/.test(n+' '+typ))return 'shadows';
 if(/radius|radii/.test(n))return 'radius';
 if(typ==='color'||/color|palette|background|foreground|(^|[-_.])(fill|stroke|ink)([-_.]|$)/.test(n)||typeof t.value==='string'&&/^(#|rgba?\(|hsla?\(|oklch\(|color\()/.test(t.value))return 'colors';
 if(/spacing|space|gap|padding|margin/.test(n))return 'spacing';
 if(/size|width|height|dimension/.test(n))return 'size';
 return 'global';
}
function displayValue(v){return typeof v==='object'?JSON.stringify(v):String(v);}
function sourceFiles(){
 if(current.files)return current.files;
 const paths=new Set([...current.tokens,...current.assets,...current.components].map(t=>t.source).filter(Boolean));
 return [...paths].sort().map(path=>({path,kind:path.split('.').pop(),bytes:null}));
}
function canLeaveWorkspace(){if(saving||edits.size||guidanceDirty){toast('Save or discard your changes before leaving this system.');return false;}return true;}
function leaveWorkspace(){
 if(!canLeaveWorkspace())return false;
 document.body.classList.remove('workspace-mode');$('#workspaceNav').hidden=true;
 $('header').innerHTML='<div id="breadcrumb">Workspace <span>/</span> Design systems</div><button class="button small" id="newTop">＋ Add design system</button>';
 $('#newTop').onclick=newSystem;studioStorage.removeItem('gpt-design-system');return true;
}
function detail(){
 if(!sections.some(s=>s[0]===activeTab))activeTab='overview';
 document.body.classList.add('workspace-mode');
 studioStorage.setItem('gpt-design-system',current.id);studioStorage.setItem('gpt-design-section',activeTab);
 const counts=Object.fromEntries(sections.map(s=>[s[0],0]));current.tokens.forEach(t=>counts[tokenSection(t)]++);
 Object.assign(counts,{components:current.components.length,assets:current.assets.length,files:sourceFiles().length});
 $('header').innerHTML=`<div class="system-title"><select id="systemSelect" aria-label="Design system">${library.map(s=>`<option value="${s.id}" ${s.id===current.id?'selected':''}>${escape(s.name)}</option>`).join('')}</select></div><div class="workspace-actions"><span id="saveStatus" role="status"></span><button class="button small" id="discardChanges" hidden>Discard</button><button class="button small primary" id="saveChanges" hidden>Save changes</button><details id="exportMenu"><summary class="workspace-export">${icon('download')} Export</summary><div class="export-menu"><button data-export="tokens.json">Tokens JSON</button><button data-export="tokens.css">CSS variables</button><button data-export="system.json">Full system manifest</button></div></details><button class="icon-button" id="closeSystem" aria-label="Back to design systems">${icon('close')}</button></div>`;
 const nav=$('#workspaceNav');nav.hidden=false;
 nav.innerHTML=`<div class="workspace-search">${icon('search')}<input id="systemSearch" placeholder="Search" aria-label="Search design system" value="${escape(workspaceQuery)}"></div><nav aria-label="Design system sections">${sections.map(([key,label,symbol])=>`<button class="section-link ${key===activeTab?'selected':''} ${key==='files'?'files-link':''}" data-section="${key}" ${key===activeTab?'aria-current="page"':''}>${icon(symbol)}<span>${label}</span>${['overview','guidelines'].includes(key)?'':`<span class="section-count">${counts[key]}</span>`}</button>`).join('')}</nav><div class="workspace-bottom"><span class="saved-dot"></span> Saved on this Mac <span>GPT Design</span></div>`;
 $('#systemSearch').oninput=e=>{workspaceQuery=e.target.value;rowLimit=150;renderWorkspaceSection();};
 nav.querySelectorAll('[data-section]').forEach(b=>b.onclick=()=>{if(saving||guidanceDirty){toast('Save or discard your notes first.');return;}activeTab=b.dataset.section;workspaceQuery='';rowLimit=150;detail();window.scrollTo(0,0);});
 $('#closeSystem').onclick=showLibrary;
 $('#systemSelect').onchange=async e=>{if(!canLeaveWorkspace()){e.target.value=current.id;return;}try{current=await loadSystemForViewing(e.target.value);activeTab='overview';workspaceQuery='';detail();}catch(err){toast(err.message);}};
 $('#discardChanges').onclick=()=>{edits.clear();detail();toast('Changes discarded');};$('#saveChanges').onclick=saveTokenChanges;
 document.querySelectorAll('[data-export]').forEach(b=>b.onclick=()=>{if(edits.size){toast('Save or discard changes before exporting.');return;}download(b.dataset.export);$('#exportMenu').open=false;});
 updateSaveStatus();renderWorkspaceSection();mountPublishing();
}
function updateSaveStatus(){
 const status=$('#saveStatus');if(!status)return;
 status.innerHTML=saving?'<span class="status-dot pending"></span> Saving…':edits.size?`<span class="status-dot pending"></span> ${edits.size} unsaved change${edits.size===1?'':'s'}`:'<span class="status-dot"></span> Saved locally';
 $('#saveChanges').hidden=!edits.size;$('#discardChanges').hidden=!edits.size;
 $('#saveChanges').disabled=saving;$('#discardChanges').disabled=saving;
}
function sectionDescription(key){return ({colors:'Your palette, themes, and semantic colors.',typography:'Font families, weights, sizes, and text styles.',spacing:'A consistent rhythm for layouts and components.',radius:'The curves and edges that shape your system.',shadows:'Depth, elevation, and layered surfaces.',size:'Dimensions for layouts and elements.',global:'Shared values and tokens without a recognized category.'})[key]||'';}
function renderWorkspaceSection(){
 const q=workspaceQuery.trim().toLowerCase();
 if(q){
  const rows=current.tokens.map((t,index)=>({t,index})).filter(({t})=>[t.name,displayValue(t.value),t.source,t.context,t.mode,t.collection].some(x=>String(x).toLowerCase().includes(q)));
  main.innerHTML=`<div class="workspace-heading"><span class="workspace-kicker">${escape(current.name)}</span><h1>Search results</h1><p>${rows.length} token${rows.length===1?'':'s'} matching “${escape(workspaceQuery)}”</p></div>`+tokenTable(rows,'Matching tokens')+inventorySection('components',q)+inventorySection('assets',q)+inventorySection('files',q);
  bindRows(rows);return;
 }
 if(activeTab==='overview'){renderOverview();return;}
 if(activeTab==='guidelines'){renderGuidelines();return;}
 if(activeTab==='components'){renderComponents();return;}
 if(activeTab==='files'||activeTab==='assets'){renderFiles(activeTab);return;}
 if(activeTab==='colors'){renderColorThemes();return;}
 if(activeTab==='typography'){renderTypography();return;}
 const section=sections.find(s=>s[0]===activeTab);
 main.innerHTML=`<div class="workspace-heading"><span class="workspace-kicker">${escape(current.name)}</span><h1>${section[1]}</h1><p>${escape(sectionDescription(activeTab))}</p></div>`;
 if(['components','assets','files'].includes(activeTab)){main.insertAdjacentHTML('beforeend',inventorySection(activeTab));return;}
 const rows=current.tokens.map((t,index)=>({t,index})).filter(({t})=>tokenSection(t)===activeTab);
 main.insertAdjacentHTML('beforeend',tokenTable(rows,section[1]));bindRows(rows);
 const next=sections[sections.findIndex(s=>s[0]===activeTab)+1];
 if(next) { main.insertAdjacentHTML('beforeend',`<button class="next-category" id="nextCategory"><span>Next section</span><strong>${next[1]}</strong><span>→</span></button>`);$('#nextCategory').onclick=()=>{activeTab=next[0];detail();window.scrollTo(0,0);}; }
}
function tokenTable(rows,title){
 return `<section class="token-sheet" aria-label="${escape(title)}"><div class="sheet-heading"><h2>${escape(title)}</h2><span>${rows.length} tokens</span></div>${rows.length?`<div class="table-scroll"><table class="token-table"><thead><tr><th scope="col">Token</th><th scope="col">Value</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead><tbody>${rows.slice(0,rowLimit).map(({t,index})=>{
 const draft=edits.get(index),deleted=draft?.delete,raw=draft?.raw??displayValue(t.value),composite=typeof t.value==='object';
 return `<tr class="${deleted?'token-deleted':''}" data-row="${index}"><th scope="row"><span class="token-name" title="${escape(t.name)}">${escape(t.name)}</span><span class="token-context" title="${escape(t.source)}">${escape(t.mode?[t.collection,t.mode].filter(Boolean).join(' · '):t.context||':root')}${t.locallyEdited?' · edited locally':''}</span></th><td><div class="token-value-wrap">${tokenSection(t)==='colors'?`<span class="value-swatch" data-swatch="${index}" aria-hidden="true"></span>`:''}${composite?`<textarea class="token-value composite" data-value="${index}" aria-label="Value for ${escape(t.name)}" ${deleted?'disabled':''} spellcheck="false">${escape(raw)}</textarea>`:`<input class="token-value" data-value="${index}" aria-label="Value for ${escape(t.name)}" value="${escape(raw)}" ${deleted?'disabled':''} spellcheck="false">`}</div></td><td class="token-actions"><button class="icon-button source-button" data-source-index="${index}" aria-label="Source for ${escape(t.name)}" title="View token source">${icon('source')}</button><button class="icon-button delete-button" data-delete="${index}" aria-label="${deleted?'Restore':'Remove'} ${escape(t.name)}" title="${deleted?'Restore token':'Remove token'}">${icon(deleted?'undo':'trash')}</button></td></tr>`;
 }).join('')}</tbody></table></div>${rows.length>rowLimit?`<button class="load-more" id="loadMore">Show more · ${rows.length-rowLimit} remaining</button>`:''}`:`<div class="workspace-empty">${icon(sections.find(s=>s[1]===title)?.[2]||'global')}<h3>No ${escape(title.toLowerCase())} tokens yet</h3><p>This import didn’t include matching tokens.</p></div>`}</section>`;
}
function bindRows(rows){
 document.querySelectorAll('[data-value]').forEach(input=>input.oninput=()=>{
  const index=Number(input.dataset.value),t=current.tokens[index];
  if(input.value===displayValue(t.value))edits.delete(index);else edits.set(index,{raw:input.value});
  updateSwatch(index,input.value);updateSaveStatus();
 });
 document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>{const index=Number(b.dataset.delete),draft=edits.get(index);if(draft?.delete){if(draft.previous)edits.set(index,draft.previous);else edits.delete(index);}else edits.set(index,{delete:true,previous:draft});renderWorkspaceSection();updateSaveStatus();});
 document.querySelectorAll('[data-source-index]').forEach(b=>b.onclick=()=>showTokenSource(Number(b.dataset.sourceIndex)));
 applyReadOnly();
 rows.slice(0,rowLimit).forEach(({t,index})=>updateSwatch(index,edits.get(index)?.raw??displayValue(t.value)));
 if($('#loadMore'))$('#loadMore').onclick=()=>{rowLimit+=150;renderWorkspaceSection();};
}
function updateSwatch(index,value){const swatch=document.querySelector(`[data-swatch="${index}"]`);if(swatch)swatch.style.backgroundColor=CSS.supports('color',value)?value:'transparent';}
function showTokenSource(index){
 const t=current.tokens[index];let dialog=$('#sourceDialog');if(dialog)dialog.remove();
 dialog=document.createElement('dialog');dialog.id='sourceDialog';dialog.className='source-dialog';
 dialog.innerHTML=`<div class="dialog-heading"><h2>Token source</h2><button class="icon-button" id="closeSource" aria-label="Close token source">${icon('close')}</button></div><code>${escape(t.name)}</code><dl><dt>Source file</dt><dd>${escape(t.source)}</dd><dt>Selector / theme</dt><dd>${escape(t.context||':root')}</dd><dt>Original value</dt><dd>${escape(displayValue(t.importedValue??t.value))}</dd><dt>Format</dt><dd>${escape(t.format)}${t.type?' · '+escape(t.type):''}</dd>${t.atRules?.length?`<dt>At-rules</dt><dd>${escape(t.atRules.join(' → '))}</dd>`:''}</dl><p>Edits are saved in GPT Design. The original source file is unchanged.</p>`;
 document.body.append(dialog);dialog.showModal();$('#closeSource').onclick=()=>dialog.close();
}
async function saveTokenChanges(){
 if(saving||!edits.size)return;
 try{
  const changes=[...edits].map(([index,edit])=>{if(edit.delete)return {index,delete:true};const original=current.tokens[index].value;let value=edit.raw;if(typeof original!=='string'){try{value=JSON.parse(edit.raw);}catch{throw new Error('Enter valid JSON for '+current.tokens[index].name);}if(value===null||typeof value!==typeof original||Array.isArray(value)!==Array.isArray(original))throw new Error('Keep the value type for '+current.tokens[index].name);}if(typeof value==='string'&&!value.trim())throw new Error('Enter a value for '+current.tokens[index].name);return {index,value};});
  saving=true;updateSaveStatus();document.querySelectorAll('[data-value],[data-delete]').forEach(el=>el.disabled=true);
  current=await api('/api/systems/'+current.id+'/edit',{revision:current.revision||0,changes});edits.clear();await refresh();toast('Changes saved · previous revision preserved');
 }catch(err){toast(err.message);}finally{saving=false;detail();}
}
function renderOverview(){
 const meta=current.source,source=meta.repository||meta.path||meta.filename||(meta.files!=null?meta.files+' uploaded files':'Saved source');
 main.innerHTML=`<div class="workspace-heading overview-heading"><span class="workspace-kicker">Design system</span><h1>${escape(current.name)}</h1><p>Your design foundation, ready to work with.</p></div><div class="overview-metrics">${[['tokens',current.tokens.length,'colors'],['assets',current.assets.length,'assets'],['components',current.components.length,'components'],['files',sourceFiles().length,'files']].map(([label,count,section])=>`<button data-jump="${section}"><strong>${count}</strong><span>${label}</span>${icon('back')}</button>`).join('')}</div><section class="token-sheet overview-source"><div class="sheet-heading"><h2>Source</h2><span>${current.status==='locally-edited'?'Edited locally':'Imported snapshot'}</span></div><dl><dt>Imported from</dt><dd>${escape(source)}</dd>${meta.commit?`<dt>Source commit</dt><dd><code>${escape(meta.commit.slice(0,12))}</code></dd>`:''}<dt>Created</dt><dd>${escape(new Date(current.createdAt).toLocaleString())}</dd><dt>Revision</dt><dd>${current.revision||0}${current.updatedAt?' · Last saved '+escape(new Date(current.updatedAt).toLocaleString()):''}</dd></dl></section><section class="overview-categories">${sections.filter(s=>!['overview','guidelines','components','assets','files'].includes(s[0])).map(([key,title,symbol])=>`<button data-jump="${key}">${icon(symbol)}<span><strong>${title}</strong><small>${current.tokens.filter(t=>tokenSection(t)===key).length} tokens</small></span><span>→</span></button>`).join('')}</section><section class="token-sheet import-notes"><div class="sheet-heading"><h2>Import notes</h2></div>${current.warnings.map(w=>`<p>${escape(w)}</p>`).join('')}</section>`;
 document.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>{activeTab=b.dataset.jump;detail();window.scrollTo(0,0);});
}
function inventorySection(key,query=''){
 const list=key==='files'?sourceFiles():current[key],filtered=list.filter(x=>!query||JSON.stringify(x).toLowerCase().includes(query));
 const label=sections.find(s=>s[0]===key)[1];
 if(query&&!filtered.length)return '';
 return `<section class="token-sheet inventory-sheet"><div class="sheet-heading"><h2>${label}</h2><span>${filtered.length} ${label.toLowerCase()}</span></div>${key==='components'?'<p class="inventory-note">Component definitions are indexed. Live previews require corresponding code.</p>':key==='files'&&!current.files?'<p class="inventory-note">This older snapshot lists files referenced by its tokens, assets, and components. New imports record every scanned file.</p>':''}${filtered.length?`<div class="inventory-table">${filtered.slice(0,500).map(item=>`<div class="inventory-row">${icon(key==='files'?'source':key==='assets'?'image':'box')}<div><strong>${escape(item.name||item.path)}</strong><small>${escape(item.source||item.kind)}</small></div><span>${key==='components'?(item.preview==='design-only'?'Figma design':'Source only'):item.bytes!=null?Math.ceil(item.bytes/1024)+' KB':escape(item.kind||'')}</span></div>`).join('')}</div>${filtered.length>500?'<p class="inventory-note">Showing the first 500 items. Search to narrow the list.</p>':''}`:`<div class="workspace-empty"><h3>No ${label.toLowerCase()} in this import</h3><p>Items appear here when they are included in your source and import choices.</p></div>`}</section>`;
}
window.addEventListener('beforeunload',e=>{if(edits.size||saving){e.preventDefault();e.returnValue='';}});
