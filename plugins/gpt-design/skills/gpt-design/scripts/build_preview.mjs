// Bundle trusted, reviewed React stories from an isolated source checkout.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const [sourceArg,outputArg,commit='local']=process.argv.slice(2);
if(!sourceArg||!outputArg)throw new Error('Usage: build_preview.mjs SOURCE OUTPUT COMMIT');
const source=path.resolve(sourceArg),out=path.resolve(outputArg),require=createRequire(path.join(source,'package.json'));
const esbuild=require('esbuild'),ts=require('typescript');
const assets=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../assets/preview');
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):[path.join(dir,e.name)]);}
const files=walk(path.join(source,'src/stories')).filter(f=>f.endsWith('.stories.tsx')&&!f.includes('/_welcome/')&&!f.includes('/hooks/'));
const config=ts.readConfigFile(path.join(source,'tsconfig.json'),ts.sys.readFile);
const parsed=ts.parseJsonConfigFileContent(config.config,ts.sys,source);
const program=ts.createProgram(parsed.fileNames,parsed.options),checker=program.getTypeChecker();
const interesting=new Set(['children','label','description','placeholder','size','variant','scheme','align','orientation','isDisabled','isRequired','isInvalid','isSelected','defaultSelected','defaultValue','value','type','direction','wrap','padding','gap','isReadOnly','autoFocus','isIndeterminate','defaultOpen','isOpen','isDismissable','isKeyboardDismissDisabled','allowsMultipleExpanded','minValue','maxValue','step','rows','maxLength','name']);
let descriptions={};
for(const file of files){
 const sf=program.getSourceFile(file);const rel=path.relative(source,file).replaceAll('\\','/');
 for(const node of sf.statements){if(!ts.isVariableStatement(node)||!node.modifiers?.some(m=>m.kind===ts.SyntaxKind.ExportKeyword))continue;
  for(const decl of node.declarationList.declarations){
   if(!ts.isIdentifier(decl.name)||!decl.initializer)continue;
   let componentName;
   const seen=new Set();function find(n){if(seen.has(n))return;seen.add(n);if(ts.isTypeQueryNode(n))componentName=n.exprName.getText(sf);if(ts.isTypeReferenceNode(n)){const sym=checker.getSymbolAtLocation(n.typeName);for(const d of sym?.declarations||[])if(ts.isTypeAliasDeclaration(d)&&d.getSourceFile()===sf)find(d.type);}ts.forEachChild(n,find);}
   if(decl.type)find(decl.type);
   if(!componentName){const meta=sf.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(sf)==='meta'));if(meta)find(meta);}
   let controls={},componentSource='';
   if(componentName){const symbol=checker.getSymbolsInScope(decl,ts.SymbolFlags.Value | ts.SymbolFlags.Alias).find(s=>s.name===componentName);if(symbol){const actual=symbol.flags&ts.SymbolFlags.Alias?checker.getAliasedSymbol(symbol):symbol;
    const location=actual.valueDeclaration||actual.declarations?.[0];if(location)componentSource=path.relative(source,location.getSourceFile().fileName).replaceAll('\\','/');
    const type=checker.getTypeOfSymbolAtLocation(symbol,decl),signature=type.getCallSignatures()[0];
    if(signature?.parameters[0]){const props=checker.getTypeOfSymbolAtLocation(signature.parameters[0],decl);
     for(const prop of props.getProperties()){if(!interesting.has(prop.name)&&!/^is[A-Z]|^allows[A-Z]|^default[A-Z]/.test(prop.name))continue;const t=checker.getTypeOfSymbolAtLocation(prop,decl);const parts=t.isUnion()?t.types:[t];const literals=parts.filter(x=>x.isStringLiteral()||x.isNumberLiteral()).map(x=>x.value);const isBool=parts.some(x=>(x.flags&(ts.TypeFlags.Boolean|ts.TypeFlags.BooleanLiteral))!==0);
      if(literals.length&&literals.length<40)controls[prop.name]={type:'select',options:[...new Set(literals)]};
      else if(isBool&&parts.every(x=>(x.flags&(ts.TypeFlags.Boolean|ts.TypeFlags.BooleanLiteral|ts.TypeFlags.Undefined|ts.TypeFlags.Null))!==0))controls[prop.name]={type:'boolean'};
      else if(parts.every(x=>(x.flags&(ts.TypeFlags.String|ts.TypeFlags.Undefined|ts.TypeFlags.Null))!==0))controls[prop.name]={type:'text'};
      else if(parts.every(x=>(x.flags&(ts.TypeFlags.Number|ts.TypeFlags.Undefined|ts.TypeFlags.Null))!==0))controls[prop.name]={type:'number'};
     }
    }
   }}
   const direct=['CheckboxField','SwitchField'].includes(componentName);const exampleProps={};
   const render=ts.isObjectLiteralExpression(decl.initializer)?decl.initializer.properties.find(p=>p.name?.getText(sf)==='render'):null;
   let forwardsAll=false;const forwarded=new Set();
   function inspect(n){
    if(ts.isSpreadAssignment(n)&&n.expression.getText(sf)==='args'||ts.isJsxSpreadAttribute(n)&&n.expression.getText(sf)==='args')forwardsAll=true;
    if(ts.isPropertyAccessExpression(n)&&n.expression.getText(sf)==='args')forwarded.add(n.name.text);
    if(ts.isVariableDeclaration(n)&&ts.isArrayBindingPattern(n.name)&&n.initializer?.getText(sf).startsWith('useArgs(')){for(const element of n.name.elements)if(ts.isBindingElement(element)&&ts.isObjectBindingPattern(element.name))for(const binding of element.name.elements)forwarded.add(binding.name.getText(sf));}
    if((ts.isJsxSelfClosingElement(n)||ts.isJsxOpeningElement(n))&&n.tagName.getText(sf)===componentName){for(const a of n.attributes.properties)if(ts.isJsxAttribute(a)&&a.initializer&&ts.isStringLiteral(a.initializer))exampleProps[a.name.text]=a.initializer.text;}
    ts.forEachChild(n,inspect);
   }
   if(render)inspect(render);
   if(render&&!forwardsAll&&!direct)controls=Object.fromEntries(Object.entries(controls).filter(([k])=>forwarded.has(k)));
   descriptions[rel+'#'+decl.name.text]={componentName,componentSource,controls,direct,exampleProps};
  }
 }
}
fs.mkdirSync(out,{recursive:true});
const shim=path.join(assets,'story-hooks.jsx');
const imports=files.map((f,i)=>`import * as s${i} from ${JSON.stringify(f)};`).join('\n');
const directImports=Object.entries(descriptions).filter(([id,d])=>d.direct).map(([id,d],i)=>({id,d,alias:'Direct'+i}));
const directCode=directImports.map(({d,alias})=>`import {${d.componentName} as ${alias}} from ${JSON.stringify(path.join(source,d.componentSource))};`).join('\n');
const directMap=directImports.map(({id,alias})=>`${JSON.stringify(id)}:${alias}`).join(',');
const modules=files.map((f,i)=>`{module:s${i},path:${JSON.stringify(path.relative(source,f).replaceAll('\\','/'))}}`).join(',');
const runtime=fs.readFileSync(path.join(assets,'runtime.jsx'),'utf8');
const entry=`import React from 'react';import {createRoot} from 'react-dom/client';import {ArgsContext} from ${JSON.stringify(shim)};import ${JSON.stringify(path.join(source,'src/index.css'))};\n${imports}\n${directCode}\nconst directComponents={${directMap}};const modules=[${modules}];const definitions=${JSON.stringify(descriptions)};\n${runtime}`;
const result=await esbuild.build({stdin:{contents:entry,resolveDir:source,loader:'tsx'},absWorkingDir:source,bundle:true,write:false,outfile:path.join(out,'runtime.js'),format:'iife',platform:'browser',jsx:'automatic',minify:true,metafile:true,define:{'process.env.NODE_ENV':'"production"'},alias:{'@storybook/preview-api':shim,'react':path.join(source,'node_modules/react'),'react-dom':path.join(source,'node_modules/react-dom')},nodePaths:[path.join(source,'node_modules')],loader:{'.svg':'dataurl','.png':'dataurl','.jpg':'dataurl','.woff2':'dataurl'},tsconfig:path.join(source,'tsconfig.json')});
for(const f of result.outputFiles){let text=f.text;if(f.path.endsWith('.css'))text=text.replace(/@import\s+(?:url\([^;]+\)|["'][^"']+["'])\s*;/g,'');fs.writeFileSync(f.path,text);}
fs.writeFileSync(path.join(out,'catalog.json'),JSON.stringify({builtAt:new Date().toISOString(),commit,storyFiles:files.map(f=>path.relative(source,f)),definitions:descriptions,notes:['Previews use the original React stories. Storybook-only hooks are adapted to React state.','External network requests and navigation are blocked in previews. Remote fonts use local fallbacks.','Variant controls come from source prop types and story args. Fixed stories may have no editable controls.']},null,2));
fs.writeFileSync(path.join(out,'build-inputs.json'),JSON.stringify(result.metafile,null,2));
console.log(JSON.stringify({storyFiles:files.length,definitions:Object.keys(descriptions).length,bytes:result.outputFiles.reduce((n,f)=>n+f.contents.length,0)}));
