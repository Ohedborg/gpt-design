const registry={};
const plain=v=>v===null||['string','number','boolean'].includes(typeof v);
const catalog=[];
for(const item of modules){const meta=item.module.default||{};for(const [key,story]of Object.entries(item.module)){
 if(key==='default'||!story||typeof story!=='object'||(!story.render&&!meta.component))continue;
 const id=item.path+'#'+key,def=definitions[id]||{},args={...meta.args,...story.args};
 if(def.direct)Object.assign(args,{...def.exampleProps,...args});
 const overrides=Object.fromEntries(Object.entries(args).filter(([k,v])=>plain(v)));
 const flexible=story.render?story.render.length>0:!!meta.component;
 const controls=flexible?{...def.controls}:{};
 if(flexible){for(const[k,v]of Object.entries(overrides))if(!controls[k])controls[k]={type:typeof v==='boolean'?'boolean':typeof v==='number'?'number':'text'};
  for(const[k,v]of Object.entries({...meta.argTypes,...story.argTypes})){if(v.control===false){delete controls[k];continue;}if(v.options)controls[k]={type:'select',options:v.options.filter(plain)};else if(v.control?.type==='text')controls[k]={type:'text'};}
 }
 registry[id]={story,meta,args,direct:directComponents[id]};
 catalog.push({id,name:story.name||key.replace(/^Story/,''),group:item.path.split('/').slice(-2,-1)[0],source:item.path,componentSource:def.componentSource||'',componentName:def.componentName||'',controls,defaults:overrides});
}}
class Boundary extends React.Component{state={error:null};static getDerivedStateFromError(e){return {error:String(e.message||e)}}componentDidCatch(e){send({type:'preview-error',message:String(e.message||e)})}render(){return this.state.error?<pre role="alert">This story needs additional setup: {this.state.error}</pre>:this.props.children}}
function Story({entry,overrides,storyId}){const initial={...Object.fromEntries(Object.entries(entry.args).filter(([k,v])=>!plain(v))),...overrides};const[args,setArgs]=React.useState(initial);React.useEffect(()=>{send({type:"props-changed",id:storyId,props:Object.fromEntries(Object.entries(args).filter(([k,v])=>plain(v)))})},[args]);const Render=entry.direct?((props)=>React.createElement(entry.direct,{...props,onChange:(value)=>{setArgs(old=>old.isSelected===undefined?old:{...old,isSelected:value})}})):entry.story.render||((props)=>React.createElement(entry.meta.component,props));let content=<Render {...args}/>;for(const decorator of [...(entry.meta.decorators||[]),...(entry.story.decorators||[])].reverse()){const child=content;content=decorator(()=>child,{args});}return <ArgsContext.Provider value={{args,initial,update:next=>setArgs(old=>({...old,...next}))}}>{content}</ArgsContext.Provider>}
const root=createRoot(document.getElementById('preview-root'));
const channel=document.documentElement.dataset.channel;
function send(message){window.parent.postMessage({gptDesignPreview:channel,...message},'*');}
window.addEventListener('message',event=>{if(event.source!==window.parent||event.data?.gptDesignPreview!==channel)return;const msg=event.data;if(msg.type!=='render')return;
 document.documentElement.dataset.theme=msg.theme==='dark'?'dark':'light';
 document.getElementById('token-overrides').textContent=typeof msg.css==='string'?msg.css:'';
 const entry=registry[msg.id];if(!entry)return;
 root.render(<div className="preview-single"><section key={JSON.stringify([msg.id,msg.theme,msg.props])}><Boundary><Story entry={entry} overrides={msg.props||{}} storyId={msg.id}/></Boundary></section></div>);
 requestAnimationFrame(()=>send({type:'rendered',id:msg.id}));
});
document.addEventListener('click',event=>{if(event.target.closest('a'))event.preventDefault();},true);
document.addEventListener('submit',event=>event.preventDefault(),true);
send({type:'ready',catalog});
