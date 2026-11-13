'use strict';
let guidanceDirty=false, previewCatalog=[], previewSelection='', previewProps={}, previewTheme='light', previewChannel='', previewReady=false;
const previewCache=new Map();
const originalOverview=renderOverview;
renderOverview=function(){
 originalOverview();
 const guide=current.guide||{};
 const top=document.querySelector('.overview-heading');
 top.classList.add('brand-overview');
 top.innerHTML=`<div class="brand-mosaic" aria-hidden="true">${Array.from({length:9},(_,i)=>`<i data-brand-swatch="${i}"></i>`).join('')}</div><h1>${escape(current.name)}</h1><p>${escape(guide.summary||'Your reusable design foundation.')}</p><div class="overview-description">${escape(guide.description||'Explore the tokens, components, source files and usage guidelines in this saved design system.')}</div><button class="button small" id="editOverview">Edit overview</button>`;
 const palette=current.tokens.filter(t=>tokenSection(t)==='colors'&&typeof t.value==='string'&&CSS.supports('color',t.value));
 top.querySelectorAll('[data-brand-swatch]').forEach((el,i)=>{if(palette[i])el.style.backgroundColor=palette[i].value;});
 $('#editOverview').onclick=()=>{if(!canLeaveWorkspace())return;activeTab='guidelines';detail();};
 const target=document.querySelector('.overview-source');
 if(current.importReport){const r=current.importReport;target.insertAdjacentHTML('beforebegin',`<section class="token-sheet fig-import-report"><div class="sheet-heading"><h2>Figma import report</h2><span>Experimental import</span></div><div class="fig-report-grid">${[[r.variables,'variables found'],[r.styles,'saved styles found'],[r.tokensImported,'token values imported'],[r.componentsImported,'design components imported'],[r.imagesImported,'images / thumbnails imported']].map(([n,l])=>`<div><strong>${n}</strong><span>${l}</span></div>`).join('')}</div><p class="inventory-note">${r.nodes} nodes decoded. Components contain design definitions and properties; runnable previews need a linked code library. Review the source and import notes before publishing.</p><button class="button small" id="viewFigReport">View import details</button></section>`);$('#viewFigReport').onclick=()=>viewFile('figma/import-report.json');}
 target.insertAdjacentHTML('beforebegin',`<section class="token-sheet guide-preview"><div class="sheet-heading"><h2>Principles</h2><button class="button small" id="openGuidelines">Guidelines & skills →</button></div><div class="prose-block">${escape(guide.principles||'Add the principles that guide decisions in this design system.')}</div></section>`);
 $('#openGuidelines').onclick=()=>{activeTab='guidelines';detail();};
};
function heading(title,description='',actions=''){return `<div class="workspace-heading feature-heading"><div><span class="workspace-kicker">${escape(current.name)}</span><h1>${escape(title)}</h1><p>${escape(description)}</p></div>${actions}</div>`;}
async function maintainSystem(payload){if(current._release)throw new Error('Published versions are read-only. Open the working draft to edit.');if(edits.size)throw new Error('Save or discard token edits first.');const result=await api('/api/systems/'+current.id+'/maintain',{revision:current.revision||0,...payload});current=result;await refresh();return result;}
function renderGuidelines(){
 const g=current.guide||{};
 main.innerHTML=heading('Guidelines','Maintain the principles that guide every design.')+`<section class="token-sheet guide-form"><label>Short introduction<textarea id="guideSummary" rows="2">${escape(g.summary||'')}</textarea></label><label>About this system<textarea id="guideDescription" rows="4">${escape(g.description||'')}</textarea></label><label>Principles and usage guidelines<textarea id="guidePrinciples" rows="12">${escape(g.principles||'')}</textarea></label><p class="inventory-note">Saved locally with revision history. Source documentation remains unchanged.</p><div class="actions"><span id="guideStatus" role="status"></span><button class="button quiet" id="discardGuide">Discard</button><button class="button primary" id="saveGuide">Save guidelines</button></div></section><section class="token-sheet skills-panel"><div class="sheet-heading"><h2>Create with this system</h2></div><p>These skills read the saved guidelines, tokens and component contracts before they build or review.</p>${[['gpt-design-build','Build with this system','Create a page using this design system and follow its saved guidelines.'],['gpt-design-review','Review a design','Review my design against this system’s tokens, components, accessibility and guidelines.'],['gpt-design-maintain','Maintain this system','Compare this system with its source and propose updates while preserving local edits.']].map(([name,label,task])=>`<button class="skill-card" data-skill="${name}" data-task="${escape(task)}"><strong>${label}</strong><code>$${name}</code><span>Copy chat prompt →</span></button>`).join('')}</section>`;
 main.querySelectorAll('textarea').forEach(el=>el.oninput=()=>{guidanceDirty=true;$('#guideStatus').textContent='Unsaved changes';});
 $('#discardGuide').onclick=()=>{guidanceDirty=false;renderGuidelines();};
 $('#saveGuide').onclick=async()=>{const button=$('#saveGuide');button.disabled=true;try{await maintainSystem({action:'guide',guide:{summary:$('#guideSummary').value,description:$('#guideDescription').value,principles:$('#guidePrinciples').value}});guidanceDirty=false;toast('Guidelines saved');detail();}catch(e){toast(e.message);button.disabled=false;}};
 main.querySelectorAll('[data-skill]').forEach(b=>b.onclick=()=>copy(`Use $${b.dataset.skill} with GPT Design system ${current.name} (ID ${current.id}). ${b.dataset.task}`));
}
function featureDialog(title,body){$('#featureDialog')?.remove();const d=document.createElement('dialog');d.id='featureDialog';d.className='source-dialog feature-dialog';d.innerHTML=`<div class="dialog-heading"><h2>${escape(title)}</h2><button class="icon-button" id="closeFeature" aria-label="Close dialog">${icon('close')}</button></div>${body}`;document.body.append(d);d.showModal();$('#closeFeature').onclick=()=>d.close();return d;}
function renderFiles(kind){
 const list=kind==='assets'?current.assets.map(a=>({...a,path:a.source})):sourceFiles();
 main.innerHTML=heading(kind==='assets'?'Assets':'Files',kind==='assets'?'Original fonts, images and brand assets.':'Browse the preserved source behind your design system.')+`<section class="token-sheet"><div class="file-tools"><input id="fileFilter" type="search" placeholder="Filter by name, folder or extension" aria-label="Filter files"><span>${list.length} files</span></div><div id="fileRows"></div></section>`;
 function draw(q=''){$('#fileRows').innerHTML=list.filter(f=>f.path.toLowerCase().includes(q.toLowerCase())).slice(0,600).map(f=>`<button class="file-entry" data-file="${escape(f.path)}">${icon('source')}<span><strong>${escape(f.path.split('/').pop())}</strong><small>${escape(f.path)}</small></span><span>${Math.ceil((f.bytes||0)/1024)} KB</span><span>View →</span></button>`).join('')||'<p class="inventory-note">No matching files.</p>';$('#fileRows').querySelectorAll('[data-file]').forEach(b=>b.onclick=()=>viewFile(b.dataset.file));}
 $('#fileFilter').oninput=e=>draw(e.target.value);draw();
}
async function viewFile(path){
 const d=featureDialog(path,'<p>Loading file…</p>');
 try{const file=await api('/api/systems/'+current.id+'/file?path='+encodeURIComponent(path)+(current._release?'&version='+current._release.version:''));if(!d.open)return;const head=d.querySelector('.dialog-heading').outerHTML;d.innerHTML=head+`<p class="inventory-note">Saved source · ${file.bytes.toLocaleString()} bytes · read only</p>`;
 if(file.text!==undefined){const pre=document.createElement('pre');pre.className='source-code';pre.textContent=file.text;d.append(pre);}
 else if(file.mimeType.startsWith('image/')){const img=document.createElement('img');img.className='asset-preview';img.alt=path;img.src='data:'+file.mimeType+';base64,'+file.base64;d.append(img);}
 else d.insertAdjacentHTML('beforeend','<p class="inventory-note">This binary asset is preserved. Download it to open it.</p>');
 const b=document.createElement('button');b.className='button small';b.textContent='Download file';b.onclick=()=>{const blob=file.text!==undefined?new Blob([file.text],{type:file.mimeType}):new Blob([Uint8Array.from(atob(file.base64),c=>c.charCodeAt(0))],{type:file.mimeType});downloadBlob(blob,path.split('/').pop());};d.append(b);$('#closeFeature').onclick=()=>d.close();
 }catch(e){d.insertAdjacentHTML('beforeend',`<p class="error">${escape(e.message)}</p>`);}
}
function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function addTokenDialog(type='color'){
 featureDialog('Add token',`<form id="addTokenForm"><label class="field">Name<input name="name" placeholder="--brand-color-primary" required></label><label class="field">Value<input name="value" placeholder="e.g. #7357D7 or 1rem" required></label><label class="field">Type<select name="type">${['color','fontFamily','fontWeight','fontSize','typography','dimension','shadow','number'].map(t=>`<option ${type===t?'selected':''}>${t}</option>`).join('')}</select></label><label class="field">Theme<select name="context"><option value=":root">Light / default</option><option value='[data-theme="dark"]'>Dark</option></select></label><button class="button primary">Add token</button><p id="tokenAddError" role="alert"></p></form>`);
 $('#addTokenForm').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button');button.disabled=true;try{await maintainSystem({action:'add-token',token:Object.fromEntries(new FormData(form))});$('#featureDialog').close();detail();toast('Token added');}catch(err){$('#tokenAddError').textContent=err.message;button.disabled=false;}};
}
function renderColorThemes(){
 if(current.source?.kind==='figma-file'){const rows=current.tokens.map((t,index)=>({t,index})).filter(({t})=>tokenSection(t)==='colors');main.innerHTML=heading('Colors','Named Figma colors, with variable collections and modes preserved.','<button class="button small" id="addColor">＋ Add token</button>')+tokenTable(rows,'Figma colors and modes');$('#addColor').onclick=()=>addTokenDialog('color');bindRows(rows);return;}
 const rows=current.tokens.map((t,index)=>({t,index})).filter(({t})=>tokenSection(t)==='colors');
 main.innerHTML=heading('Colors','Palette values across light and dark themes.','<button class="button small" id="addColor">＋ Add token</button>');$('#addColor').onclick=()=>addTokenDialog('color');
 const byName=new Map();rows.forEach(r=>{if(!byName.has(r.t.name))byName.set(r.t.name,[]);byName.get(r.t.name).push(r);});
 const simple=[],other=[];for(const[name,values]of byName){const lights=values.filter(r=>r.t.context===':root'&&!r.t.atRules?.length);const darks=values.filter(r=>isDarkToken(r.t));if(lights.length===1&&darks.length<=1&&values.length===lights.length+darks.length)simple.push({name,light:lights[0],dark:darks[0]});else other.push(...values);}
 const cell=r=>{const draft=edits.get(r.index);return `<div class="color-cell"><span class="value-swatch" data-swatch="${r.index}"></span><input class="token-value" data-value="${r.index}" aria-label="${escape(r.t.name)} ${isDarkToken(r.t)?'Dark':'Light'}" value="${escape(draft?.raw??displayValue(r.t.value))}"><button class="icon-button source-button" data-source-index="${r.index}" aria-label="Source for ${escape(r.t.name)}">${icon('source')}</button></div>`;};
 main.insertAdjacentHTML('beforeend',`<section class="token-sheet"><div class="sheet-heading"><h2>Palette</h2><span>${simple.length} named colors</span></div><div class="table-scroll"><table class="theme-table"><thead><tr><th>Name</th><th>Light</th><th>Dark</th></tr></thead><tbody>${simple.slice(0,rowLimit).map(r=>`<tr><th><code>${escape(r.name)}</code></th><td>${cell(r.light)}</td><td>${r.dark?cell(r.dark):'<span class="inherited">Inherits default</span>'}</td></tr>`).join('')}</tbody></table></div>${simple.length>rowLimit?'<button class="load-more" id="moreColors">Show more colors</button>':''}</section>`);
 if(other.length)main.insertAdjacentHTML('beforeend',tokenTable(other,'Additional selectors and declarations'));
 bindRows(rows);if($('#moreColors'))$('#moreColors').onclick=()=>{rowLimit+=150;renderColorThemes();};
}
function renderTypography(){
 const rows=current.tokens.map((t,index)=>({t,index})).filter(({t})=>tokenSection(t)==='typography');
 main.innerHTML=heading('Typography','See type styles and maintain the values behind them.','<button class="button small" id="addType">＋ Add token</button>')+`<section class="token-sheet type-specimens"><div class="sheet-heading"><h2>Type specimens</h2><input id="typeSample" value="The quick brown fox jumps over the lazy dog." aria-label="Typography sample text"></div><div id="typeSamples"></div></section>`+tokenTable(rows,'Typography tokens');
 $('#addType').onclick=()=>addTokenDialog('fontSize');
 const cssTokens=current.tokens.filter(t=>t.format==='css');
 function draw(){const samples=$('#typeSamples');samples.innerHTML='';for(const {t} of rows.filter(({t})=>t.format==='figma'&&t.type==='typography'&&t.value?.fontName).slice(0,30)){const row=document.createElement('div');row.className='type-specimen';const label=document.createElement('code');label.textContent=t.sourceName||t.name;const sample=document.createElement('div');sample.className='specimen-text';sample.textContent=$('#typeSample').value;sample.style.fontFamily=t.value.fontName.family||'sans-serif';if(typeof t.value.fontSize==='number')sample.style.fontSize=Math.min(120,Math.max(8,t.value.fontSize))+'px';if(/bold/i.test(t.value.fontName.style||''))sample.style.fontWeight='700';row.append(label,sample);samples.append(row);}for(const{t}of rows.filter(({t})=>t.format==='css'&&(/--sds-font-/.test(t.name)||/font[-_.]?size/.test(t.name))).slice(0,30)){const row=document.createElement('div');row.className='type-specimen';const label=document.createElement('code');label.textContent=t.name;const sample=document.createElement('div');sample.className='specimen-text';sample.textContent=$('#typeSample').value;for(const v of cssTokens){if(v.context===':root'&&!v.atRules?.length&&typeof v.value==='string'&&/^--[\w-]+$/.test(v.name))sample.style.setProperty(v.name,v.value);}if(/--sds-font-/.test(t.name))sample.style.font='var('+t.name+')';else if(CSS.supports('font-size',String(t.value)))sample.style.fontSize=String(t.value);row.append(label,sample);samples.append(row);}if(!samples.children.length)samples.innerHTML='<p class="inventory-note">Individual font tokens are listed below. No complete text styles were found in this snapshot.</p>';}
 $('#typeSample').oninput=draw;draw();bindRows(rows);
}
async function renderComponents(){
 if(current.source?.kind==='figma-file'){renderFigmaComponents();return;}
 const systemId=current.id,cacheKey=systemId+':'+(current._release?.version||'draft');
 main.innerHTML=heading('Components','Explore the actual components, states and source examples.')+'<section class="token-sheet"><p class="inventory-note">Loading component playground…</p></section>';
 try{
  let bundle=previewCache.get(cacheKey);if(!bundle){bundle=await api('/api/systems/'+systemId+'/preview'+releaseQuery());previewCache.set(cacheKey,bundle);}
  if(current.id!==systemId||activeTab!=='components'||cacheKey!==current.id+':'+(current._release?.version||'draft'))return;
  if(!bundle.available){main.innerHTML=heading('Components',bundle.message)+inventorySection('components');return;}
  main.innerHTML=heading('Components','Live React stories from your imported source.',`<div class="preview-toolbar"><select id="previewTheme" aria-label="Component theme"><option value="light">Light</option><option value="dark" ${previewTheme==='dark'?'selected':''}>Dark</option></select><select id="previewWidth" aria-label="Preview width"><option value="100%">Responsive</option><option value="375px">Mobile · 375</option><option value="768px">Tablet · 768</option></select></div>`)+`<section class="component-workbench"><aside class="component-list"><input id="componentFilter" type="search" placeholder="Find a component" aria-label="Find a component"><div id="componentEntries"></div></aside><div class="component-detail"><div class="component-top"><h2 id="componentTitle">Loading…</h2><button class="button small" id="componentNotes">Usage notes</button><button class="button small" id="componentSource">Source</button></div><div class="playground-tabs"><strong>Playground</strong><button id="resetProps">Reset properties</button><span id="previewStatus" role="status">Connecting preview…</span></div><div class="preview-surface"><iframe id="componentFrame" title="Live component preview" sandbox="allow-scripts"></iframe></div><p class="property-help">Try the component’s properties below. “Component default” leaves a property unset. Changing properties restarts the example.</p><div id="componentControls" class="component-controls"></div><details class="code-example"><summary>Source example</summary><pre id="componentCode"></pre><button class="button small" id="viewStory">View complete story</button></details></div></section><p class="inventory-note">${bundle.notes.map(escape).join(' ')}</p>`;
  previewReady=false;previewCatalog=[];previewChannel=crypto.randomUUID();
  const frame=$('#componentFrame');
  const escScript=s=>s.replace(/<\/script/gi,'<\\/script');
  const css=bundle.css.replace(/<\/style/gi,'<\\/style');
  const previewDocument=`<!doctype html><html data-channel="${previewChannel}"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'"><style>${css}</style><style id="token-overrides"></style><style>html,body{min-height:100%;height:auto}#preview-root{padding:28px}.preview-single{display:flex;min-height:200px;align-items:center;justify-content:center}.preview-single>section{width:100%}.preview-matrix{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:24px}.preview-matrix>section{padding:12px;min-height:100px}.case-label{font:12px system-ui;margin-bottom:16px;opacity:.65}pre[role=alert]{white-space:pre-wrap;font:14px system-ui;color:#b3261e}</style></head><body><div id="preview-root"></div><script>${escScript(bundle.script)}</script></body></html>`;
  frame.srcdoc=previewDocument;
  const channel=previewChannel;setTimeout(()=>{if(channel===previewChannel&&!previewReady&&$('#previewStatus'))$('#previewStatus').textContent='Preview blocked by the host. Reopen GPT Design or use its local studio.';},12000);
  $('#previewTheme').onchange=e=>{previewTheme=e.target.value;sendPreview();};
  $('#previewWidth').onchange=e=>{frame.style.width=e.target.value;};
  $('#resetProps').onclick=()=>{previewProps={...selectedComponent()?.defaults};renderPlaygroundControls();sendPreview();};
  $('#componentFilter').oninput=e=>drawComponentList(e.target.value);
  $('#componentNotes').onclick=()=>editComponentNote();
  $('#componentSource').onclick=()=>{const c=selectedComponent();if(c)viewFile(c.componentSource||c.source);};
  $('#viewStory').onclick=()=>{const c=selectedComponent();if(c)viewFile(c.source);};
 }catch(e){if(current.id===systemId)main.innerHTML=heading('Components','Could not load the playground.')+`<p class="error">${escape(e.message)}</p>`;}
}
function selectedComponent(){return previewCatalog.find(c=>c.id===previewSelection);}
function drawComponentList(query=''){
 $('#componentEntries').innerHTML=previewCatalog.filter(c=>(c.name+' '+c.group).toLowerCase().includes(query.toLowerCase())).map(c=>`<button data-story="${escape(c.id)}" class="${previewSelection===c.id?'selected':''}"><strong>${escape(c.name)}</strong><small>${escape(c.group)}</small></button>`).join('');
 $('#componentEntries').querySelectorAll('[data-story]').forEach(b=>b.onclick=()=>{previewSelection=b.dataset.story;previewProps={...selectedComponent().defaults};drawComponentList($('#componentFilter').value);renderPlaygroundControls();sendPreview();});
}
function renderPlaygroundControls(){
 const c=selectedComponent();if(!c)return;$('#componentTitle').textContent=c.name;
 $('#componentControls').innerHTML=Object.entries(c.controls).sort(([a],[b])=>propRank(a)-propRank(b)).map(([key,control])=>{const value=previewProps[key];return `<label>${escape(key)}${control.type==='select'?`<select data-prop="${escape(key)}"><option value="">Component default</option>${control.options.map((v,i)=>`<option value="${i}" ${v===value?'selected':''}>${escape(v)}</option>`).join('')}</select>`:control.type==='boolean'?`<select data-prop="${escape(key)}"><option value="" ${value===undefined?'selected':''}>Component default</option><option value="true" ${value===true?'selected':''}>true</option><option value="false" ${value===false?'selected':''}>false</option></select>`:`<input type="${control.type==='number'?'number':'text'}" data-prop="${escape(key)}" value="${escape(value??'')}">`}</label>`;}).join('')||'<p class="inventory-note">This is a fixed source example. Its controls are defined within the story.</p>';
 $('#componentControls').querySelectorAll('[data-prop]').forEach(el=>el.oninput=()=>{const key=el.dataset.prop,control=c.controls[key];if(control.type==='select'){if(el.value==='')delete previewProps[key];else previewProps[key]=control.options[Number(el.value)];}else if(control.type==='boolean'){if(el.value==='')delete previewProps[key];else previewProps[key]=el.value==='true';}else previewProps[key]=control.type==='number'?Number(el.value):el.value;sendPreview();});
}
async function sendPreview(){
 if(!previewReady||!$('#componentFrame'))return;const c=selectedComponent();if(!c)return;
 const captured=previewSelection,channel=previewChannel;
 let result;try{result=window.gptDesignHost?await window.gptDesignHost.export(current.id,'tokens.css',current._release?.version):current._release?(await api('/api/systems/'+current.id+'/releases/'+current._release.version+'/tokens.css')).text:await(await fetch('/api/systems/'+current.id+'/tokens.css',{headers:{'X-GPT-Design-Token':token}})).text();}catch(e){toast(e.message);return;}
 if(captured!==previewSelection||channel!==previewChannel||!$('#componentFrame'))return;
 $('#componentFrame').contentWindow.postMessage({gptDesignPreview:channel,type:'render',id:previewSelection,props:previewProps,theme:previewTheme,css:(typeof result==='string'?result:result.text)+selectedThemeCss()},'*');
 $('#previewStatus').textContent='Interactive preview';
 $('#componentCode').textContent=`// Original story: ${c.source}\n// Component source: ${c.componentSource||'See story'}\n${JSON.stringify(previewProps,null,2)}\n\nThese are story arguments; open the complete story for its JSX composition.`;
}
window.addEventListener('message',e=>{const frame=$('#componentFrame');if(!frame||e.source!==frame.contentWindow||e.data?.gptDesignPreview!==previewChannel)return;if(e.data.type==='ready'){previewCatalog=e.data.catalog;previewReady=true;if(!previewCatalog.some(c=>c.id===previewSelection))previewSelection=previewCatalog.find(c=>c.name==='Button')?.id||previewCatalog[0]?.id;previewProps={...selectedComponent()?.defaults};drawComponentList();renderPlaygroundControls();sendPreview();}else if(e.data.type==='props-changed'&&e.data.id===previewSelection){const ordered=v=>JSON.stringify(Object.entries(v).sort(([a],[b])=>a.localeCompare(b)));if(ordered(e.data.props)!==ordered(previewProps)){previewProps=e.data.props;renderPlaygroundControls();}}else if(e.data.type==='preview-error')$('#previewStatus').textContent='Story needs setup: '+e.data.message;});
function editComponentNote(){
 if(edits.size){toast('Save or discard token changes first.');return;}const c=selectedComponent();if(!c)return;
 const note=current.componentNotes?.[c.id]||current.componentNotes?.[c.componentName]||'';
 const contract=Object.entries(c.controls).map(([k,v])=>`${k}: ${v.options?v.options.join(' · '):v.type}`).join('\n');
 const d=featureDialog('Usage notes · '+c.name,`<p class="inventory-note">Source: ${escape(c.componentSource||c.source)}</p><label class="field">Guidance<textarea id="componentNote" rows="8" placeholder="When to use it, content guidelines, accessibility, and composition rules…">${escape(note)}</textarea></label><details open><summary>Supported controls from source</summary><pre class="source-code">${escape(contract||'Fixed composition; inspect the story for its structure.')}</pre></details><button class="button primary" id="saveComponentNote">Save usage notes</button>`);
 if(current._release){$('#componentNote').readOnly=true;$('#saveComponentNote').hidden=true;}
 $('#saveComponentNote').onclick=async()=>{const b=$('#saveComponentNote');b.disabled=true;try{await maintainSystem({action:'component-note',key:c.id,note:$('#componentNote').value});d.close();toast('Usage notes saved');}catch(e){toast(e.message);b.disabled=false;}};
}
window.addEventListener('beforeunload',e=>{if(guidanceDirty){e.preventDefault();e.returnValue='';}});

function releaseQuery(){return current._release?'?version='+current._release.version:'';}
function applyReadOnly(){
 if(!current._release&&current._access?.canPublish!==false)return;
 document.querySelectorAll('[data-value],[data-delete],#guideSummary,#guideDescription,#guidePrinciples,#saveGuide,#discardGuide,#editOverview,#addToken,#addColor,#addType').forEach(el=>{el.disabled=true;});
 $('#saveChanges')?.setAttribute('hidden','');$('#discardChanges')?.setAttribute('hidden','');
}
function mountPublishing(){
 const actions=document.querySelector('.workspace-actions');if(!actions)return;
 const release=current._release,publication=current.publication;
 const bar=document.createElement('div');bar.className='publication-controls';
 bar.innerHTML=`<span class="release-badge">${current.pendingUpload?'Waiting to upload':release?'Published v'+release.version:'Working draft'}</span>${release?'<button class="button small" id="openDraft">Edit draft</button>':'<button class="button small primary" id="publishDraft">Publish…</button>'}${!release&&publication?`<button class="button small" id="viewPublished">View v${publication.version}</button>`:''}<button class="icon-button" id="versionHistory" title="Version history" aria-label="Version history">${icon('undo')}</button>`;
 actions.prepend(bar);$('#versionHistory').onclick=showVersionHistory;
 if($('#publishDraft'))$('#publishDraft').onclick=()=>publicationDialog();
 if($('#openDraft'))$('#openDraft').onclick=async()=>{try{current=await api('/api/systems/'+current.id);previewCache.clear();detail();}catch(e){toast(e.message);}};
 if($('#viewPublished'))$('#viewPublished').onclick=()=>openRelease(publication.version);
 if(release)$('#saveStatus').textContent=current.shared?'GitHub · v'+release.version:'Read-only release';
 if(sharedLibrary.connected&&sharedLibrary.canWrite&&!current.shared&&!current.pendingUpload&&(release||publication)){
  const share=document.createElement('button');share.className='button small';share.textContent='Back up to GitHub';share.onclick=async()=>{if(!canLeaveWorkspace())return;share.disabled=true;try{const draft=await api('/api/systems/'+current.id);await api('/api/systems/'+current.id+'/share',{revision:draft.revision||0});await refresh();current=await loadSystemForViewing(current.id);detail();toast('Published versions backed up to GitHub');}catch(e){toast(e.message);share.disabled=false;}};bar.append(share);
 }
 if(current._access?.canPublish===false){$('#openDraft')?.remove();$('#publishDraft')?.remove();}
 const connection=document.createElement('button');connection.className='icon-button';connection.title='GitHub library';connection.setAttribute('aria-label','GitHub library');connection.innerHTML=icon('global');connection.onclick=showGitHubLibrary;actions.append(connection);
 if(!release&&current.shared&&current.shared.baseVersion!==current.shared.latestVersion){
  const latest=document.createElement('button');latest.className='button small';latest.textContent='Start from latest';latest.title='Back up this draft and start from the latest published version';latest.onclick=async()=>{if(!canLeaveWorkspace())return;try{const result=await api('/api/systems/'+current.id+'/start-from-latest',{revision:current.revision||0});current=result.system;previewCache.clear();detail();toast('Previous draft backed up. Now editing the latest publication.');}catch(e){toast(e.message);}};bar.append(latest);$('#publishDraft')?.setAttribute('disabled','');
 }

 if(current.pendingUpload)$('#publishDraft')?.setAttribute('disabled','');
 renderAutomaticStatus();
 applyReadOnly();
}
async function openRelease(version){
 if(!canLeaveWorkspace())return;
 try{current=await api('/api/systems/'+current.id+'/releases/'+version);previewCache.clear();detail();}catch(e){toast(e.message);}
}
async function showVersionHistory(){
 try{
  const result=await api('/api/systems/'+current.id+'/releases');
  const d=featureDialog('Version history',`<p class="inventory-note">Published design-system versions are independent of plugin updates. ${result.mode==='github'?'Published versions are backed by GitHub.':'These publications are stored on this Mac.'}</p><div class="release-history">${result.releases.length?result.releases.map(r=>`<article><div><strong>Version ${r.version}</strong>${r.version===result.publishedVersion?'<span class="release-badge">Current</span>':''}<small>${escape(new Date(r.publishedAt).toLocaleString())} · ${escape(r.author)}</small></div><p>${escape(r.notes)}</p>${r.rollbackOf?`<p class="inventory-note">Restored from version ${r.rollbackOf}</p>`:''}<div class="actions"><button class="button small" data-view-release="${r.version}">View version</button>${r.version!==result.publishedVersion&&current._access?.canPublish!==false?`<button class="button small" data-rollback-release="${r.version}">Roll back to this…</button>`:''}</div></article>`).join(''):'<p>No published versions yet. Publish the saved draft when it is ready.</p>'}</div>`);
  d.querySelectorAll('[data-view-release]').forEach(b=>b.onclick=()=>{d.close();openRelease(Number(b.dataset.viewRelease));});
  d.querySelectorAll('[data-rollback-release]').forEach(b=>b.onclick=()=>{d.close();publicationDialog(Number(b.dataset.rollbackRelease));});
 }catch(e){toast(e.message);}
}
async function publicationDialog(rollbackVersion){
 if(!canLeaveWorkspace())return;
 let draft;try{draft=await api('/api/systems/'+current.id);}catch(e){toast(e.message);return;}
 const d=featureDialog(rollbackVersion?'Roll back published system':'Publish design system',`<p>${rollbackVersion?`Version ${rollbackVersion} will become a new published version. Your working draft and all previous releases stay intact.`:'Create a read-only release of the saved tokens, guidelines, source files, assets and component previews. Later draft edits will not change this release.'}</p><label class="field">Release notes<textarea id="releaseNotes" rows="4" placeholder="What changed, and what should people know?">${rollbackVersion?'Restore version '+rollbackVersion:''}</textarea></label><p class="inventory-note">${sharedLibrary.connected?'Publishes to '+escape(sharedLibrary.repository)+' for everyone with repository access. No plugin reinstall is needed.':'Publishes locally on this Mac. Connect a GitHub library to share publications.'}</p><button class="button primary" id="confirmPublication">${rollbackVersion?'Publish rollback':'Publish version'}</button>`);
 $('#confirmPublication').onclick=async()=>{const b=$('#confirmPublication');b.disabled=true;try{const result=await api('/api/systems/'+draft.id+'/publish',{revision:draft.revision||0,notes:$('#releaseNotes').value,action:rollbackVersion?'rollback':'publish',...(rollbackVersion?{version:rollbackVersion}:{})});d.close();current=result.system;await refresh();await openRelease(result.release.version);toast('Published version '+result.release.version+(result.shared?' to GitHub':''));}catch(e){toast(e.message);b.disabled=false;}};
}

async function loadSystemForViewing(id){const draft=await api("/api/systems/"+id);return draft.publication?await api("/api/systems/"+id+"/releases/"+draft.publication.version):draft;}

function isDarkToken(t){return /data-theme[^\]]*dark/.test(t.context)&&!t.atRules?.length||t.context===':root'&&t.atRules?.length===1&&/^@media\s*\(prefers-color-scheme:\s*dark\)$/.test(t.atRules[0]);}
function selectedThemeCss(){
 const values=new Map();const tokens=current.tokens.filter(t=>t.format==='css'&&/^--[\w-]+$/.test(t.name)&&typeof t.value==='string'&&!/[;{}<>]/.test(t.value));
 for(const t of tokens)if(t.context===':root'&&!t.atRules?.length)values.set(t.name,t.value);
 if(previewTheme==='dark')for(const t of tokens)if(isDarkToken(t))values.set(t.name,t.value);
 return '\nhtml[data-theme="'+previewTheme+'"]{color-scheme:'+previewTheme+';'+[...values].map(([k,v])=>k+':'+v).join(';')+'}';
}

function propRank(key){const keys=["isDisabled","isSelected","defaultSelected","isIndeterminate","isReadOnly","isRequired","isInvalid","variant","size","label","description"];return keys.includes(key)?keys.indexOf(key):99;}

function renderFigmaComponents(){
 const all=current.components||[];
 main.innerHTML=heading('Components','Design definitions imported from Figma. Connect the corresponding code library for interactive previews.')+`<section class="token-sheet"><div class="file-tools"><input id="figComponentFilter" type="search" placeholder="Find a component" aria-label="Find a Figma component"><span>${all.length} definitions</span></div><div id="figComponentRows"></div></section>`;
 function draw(q=''){
  const rows=all.filter(c=>(c.name+' '+(c.componentSet||'')).toLowerCase().includes(q.toLowerCase())).slice(0,300);
  $('#figComponentRows').innerHTML=rows.map(c=>`<article class="fig-component"><div class="sheet-heading"><div><h2>${escape(c.name)}</h2><small>${escape(c.isComponentSet?'Component set':c.componentSet||'Design component')}</small></div><button class="button small" data-fig-source="${escape(c.source)}">View definition</button></div>${c.description?`<p>${escape(c.description)}</p>`:''}${c.properties?.length?`<table class="fig-property-table"><thead><tr><th>Property</th><th>Type</th><th>Default in Figma</th></tr></thead><tbody>${c.properties.map(p=>`<tr><td>${escape(p.name)}</td><td>${escape(p.type)}</td><td><code>${escape(figPropertyDefault(p.initialValue))}</code></td></tr>`).join('')}</tbody></table>`:'<p class="inventory-note">No explicit properties found on this definition.</p>'}${c.variants?.length?`<details><summary>Variant definitions</summary><pre class="source-code">${escape(JSON.stringify(c.variants,null,2))}</pre></details>`:''}</article>`).join('')||'<p class="inventory-note">No matching component definitions. Ordinary frames are not automatically treated as components.</p>';
  $('#figComponentRows').querySelectorAll('[data-fig-source]').forEach(b=>b.onclick=()=>viewFile(b.dataset.figSource));
 }
 $('#figComponentFilter').oninput=e=>draw(e.target.value);draw();
}
function figPropertyDefault(value){if(!value)return 'Not specified';if('boolValue' in value)return String(value.boolValue);if(value.textValue?.characters!==undefined)return value.textValue.characters;if(value.textValue?.text!==undefined)return value.textValue.text;return JSON.stringify(value);}
