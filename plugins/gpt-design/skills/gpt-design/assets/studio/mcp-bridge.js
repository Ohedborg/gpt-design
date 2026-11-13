/* MCP Apps JSON-RPC bridge. Bundled only in the embedded studio resource. */
(() => {
 'use strict';
 const pending = new Map();
 let sequence = 0, hostOrigin, selectedSystemId, selectionHandler;
 function post(message) { window.parent.postMessage(message, hostOrigin && hostOrigin !== 'null' ? hostOrigin : '*'); }
 function request(method, params, timeout = 180000) {
  return new Promise((resolve, reject) => {
   const id = 'gpt-design-' + (++sequence);
   const timer = setTimeout(() => {pending.delete(id);reject(new Error('The app connection timed out. Close and reopen GPT Design.'));}, timeout);
   pending.set(id, {resolve, reject, timer});
   post({jsonrpc:'2.0', id, method, params});
  });
 }
 window.addEventListener('message', event => {
  if(event.source !== window.parent || (hostOrigin && event.origin !== hostOrigin)) return;
  const message = event.data;
  if(!message || message.jsonrpc !== '2.0') return;
  const call = pending.get(message.id);
  if(call && ('result' in message || 'error' in message)) {
   hostOrigin = event.origin; clearTimeout(call.timer); pending.delete(message.id);
   if(message.error) call.reject(new Error(message.error.message || 'App connection failed.'));
   else call.resolve(message.result);
  }
  if(message.method === 'ui/notifications/tool-result') {
   const id=message.params?.structuredContent?.selectedSystemId;
   if(typeof id==='string' && /^[a-f0-9]{32}$/.test(id) && id!==selectedSystemId){selectedSystemId=id;if(selectionHandler)selectionHandler(id);}
  }
  if(message.method === 'ui/resource-teardown' && message.id !== undefined) post({jsonrpc:'2.0',id:message.id,result:{}});
 });
 const ready = request('ui/initialize', {
  protocolVersion:'2026-01-26', appInfo:{name:'GPT Design',version:'0.6.2'},
  appCapabilities:{availableDisplayModes:['inline','fullscreen']}
 }, 20000).then(result => {
  post({jsonrpc:'2.0',method:'ui/notifications/initialized',params:{}});
  return result;
 });
 async function call(name, args = {}) {
  await ready;
  const result = await request('tools/call',{name,arguments:args});
  if(result.isError) throw new Error(result.content?.find(c=>c.type==='text')?.text || 'The studio could not complete this action.');
  return result.structuredContent;
 }
 window.gptDesignHost = {
  onSystemSelection(handler){selectionHandler=handler;if(selectedSystemId)handler(selectedSystemId);},
  async api(path, payload) {
   if(path === '/api/github') return call('library_status');
   if(path === '/api/github/connect') return call('connect_library',{payload});
   if(path === '/api/github/sync') return call('sync_library');
   if(path === '/api/github/disconnect') return call('disconnect_library');
   const management=/^\/api\/systems\/([a-f0-9]{32})\/(rename|delete)$/.exec(path);
   if(management) return call(management[2]+'_system',{id:management[1],payload});
   const share=/^\/api\/systems\/([a-f0-9]{32})\/share$/.exec(path);
   if(share) return call('share_publication',{id:share[1],revision:payload.revision});
   const latest=/^\/api\/systems\/([a-f0-9]{32})\/start-from-latest$/.exec(path);
   if(latest) return call('start_from_latest',{id:latest[1],revision:payload.revision});
   if(path === '/api/systems') return call('list_systems');
   if(path === '/api/import') return call('import_system', {payload});
   const releases=/^\/api\/systems\/([a-f0-9]{32})\/releases(?:\/(\d+)(?:\/(tokens\.css|tokens\.json|system\.json))?)?$/.exec(path);
   if(releases)return releases[2]?call('get_release',{id:releases[1],version:Number(releases[2]),file:releases[3]||'system.json'}):call('list_releases',{id:releases[1]});
   const publishing=/^\/api\/systems\/([a-f0-9]{32})\/publish$/.exec(path);
   if(publishing)return call('publish_system',{id:publishing[1],payload});
   const fileMatch=/^\/api\/systems\/([a-f0-9]{32})\/(file|preview|maintain)(?:\?(.*))?$/.exec(path);
   if(fileMatch){const id=fileMatch[1];const params=new URLSearchParams(fileMatch[3]),v=params.get('version');const version=v?{version:Number(v)}:{};if(fileMatch[2]==='file')return call('get_file',{id,path:params.get('path'),...version});if(fileMatch[2]==='preview')return call('get_preview',{id,...version});return call('maintain_system',{id,payload});}
   const match = /^\/api\/systems\/([a-f0-9]{32})(\/edit)?$/.exec(path);
   if(!match) throw new Error('Unsupported studio action.');
   return match[2] ? call('edit_system',{id:match[1],...payload}) : call('get_system',{id:match[1]});
  },
  async export(id, file, version) { const result=await (version?call('get_release',{id,file,version}):call('export_system',{id,file}));return version&&file==='system.json'?{text:JSON.stringify(result,null,2),mimeType:'application/json'}:result; }
 };
})();
