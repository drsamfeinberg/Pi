const templates=globalThis.PI_TEMPLATES,core=globalThis.PiDemoCore;
let sources=[],reports={},sourceCounter=0;
const $=id=>document.getElementById(id);
const element=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
function message(text,error=false){$('message').textContent=text;$('message').className=error?'error':'';}
function handle(fn){return async event=>{try{await fn(event);}catch(error){if(error.name!=='AbortError')message(error.message,true);}};}
function template(){return templates.find(t=>t.id===$('template').value);}
function report(){return reports[$('template').value];}
function updateStatus(){
 const current=report(),s=current?core.stats(current):null;
 $('progress').textContent=s?`${s.filled} / ${s.total} sections filled · ${s.conflicts} source conflicts`:'Load the fictional case or add notes to get started.';
 $('review-state').textContent=current?(current.status==='reviewed_unsigned'?'Reviewed locally · unsigned':'DRAFT · clinician review required'):'No report built yet.';
 for(const id of ['review','export-html','export-json'])$(id).disabled=!current;
}
function edited(current){current.status='draft';delete current.reviewed_at;$('review-confirm').checked=false;updateStatus();}
function render(){
 const current=report();if(!current){updateStatus();return;}$('fields').replaceChildren();$('review-confirm').checked=false;
 for(const field of template().fields){
  const value=current.fields[field.id],box=element('div',undefined,'field'+(!value.text?' missing':''));
  const label=element('label',field.label);label.htmlFor=field.id;
  const tag=element('span',value.conflict&&!value.resolved?'CHOOSE A SOURCE':value.text?(value.edited?'EDITED · VERIFY REFERENCES':'SOURCE PASSAGE'):'MISSING · COMPLETE OR EXPLAIN', 'tag'+(!value.text||value.conflict&&!value.resolved?' flag':''));
  const input=element('textarea');input.id=field.id;input.value=value.text;input.placeholder='No matching source passage. Enter clinician input, or explain why this field is not applicable.';
  input.addEventListener('input',()=>{value.text=input.value;value.edited=true;edited(current);tag.textContent='EDITED · VERIFY REFERENCES';});
  box.append(label,tag,input);
  if(value.conflict&&!value.resolved){
   box.append(element('p','Different source passages match this section. Choose one or write a reconciled statement, then mark the conflict resolved.','help'));
   for(const candidate of value.candidates){const card=element('div',undefined,'candidate');card.append(element('p',candidate.text));card.append(element('p',candidate.citations.map(c=>`${c.source_name} · page ${c.page}`).join('; '),'help'));const choose=element('button','Use this passage','secondary');choose.addEventListener('click',()=>{value.text=candidate.text;value.citations=structuredClone(candidate.citations);value.resolved=true;value.edited=false;edited(current);render();});card.append(choose);box.append(card);}
   const resolve=element('button','Resolve using my edited statement','secondary');resolve.addEventListener('click',()=>{if(!value.text.trim()){message('Enter your reconciled statement first.',true);return;}value.citations=value.candidates.flatMap(c=>c.citations);value.resolved=true;value.edited=true;edited(current);render();});box.append(resolve);
  }
  for(const citation of value.citations){const ref=element('details',undefined,'reference');ref.append(element('summary',`${citation.source_name} · page ${citation.page}, line ${citation.line}`),element('p',citation.quote));box.append(ref);}
  if(!value.citations.length)box.append(element('p','Clinician input · no selected source excerpt.','help'));
  $('fields').append(box);
 }
 updateStatus();
}
function renderSources(){
 $('sources').replaceChildren();
 for(const source of sources){const box=element('details',undefined,'source');box.append(element('summary',`${source.name} · ${source.pages.length} page(s)`),element('pre',source.pages.map((p,i)=>`PAGE ${i+1}\n${p}`).join('\n\n')));$('sources').append(box);}
}
function addSource(name,pages){if(sources.length>=20)throw new Error('This demo supports 20 sources per workspace.');const total=sources.reduce((n,s)=>n+s.pages.reduce((m,p)=>m+p.length,0),0)+pages.reduce((n,p)=>n+p.length,0);if(total>2000000)throw new Error('Workspace text limit reached. Use smaller samples.');sources.push({id:`source-${++sourceCounter}`,name,pages});renderSources();message('Source added. Build drafts to update the reports.');}
function build(ask=true){if(!sources.length)throw new Error('Add notes or a document first.');if(ask&&Object.keys(reports).length&&!confirm('Rebuild drafts from the sources? This replaces your edited report text.'))return;reports=core.assemble(sources,templates);render();message('Drafts built from matching source headings. Review missing sections and conflicts.');}
for(const t of templates){const option=element('option',t.title);option.value=t.id;$('template').append(option);}
$('template').addEventListener('change',render);
$('case-label').addEventListener('input',()=>{for(const current of Object.values(reports))edited(current);});
$('add-source').addEventListener('click',handle(()=>{const text=$('source-input').value.trim();if(!text)throw new Error('Enter source notes first.');if(text.length>1000000)throw new Error('Use a source smaller than one million characters.');addSource($('source-title').value.trim()||`Pasted notes ${sources.length+1}`,[text]);$('source-input').value='';$('source-title').value='';}));
$('file').addEventListener('change',handle(async event=>{
 const file=event.target.files[0];if(!file)return;$('file').disabled=true;message('Reading source…');
 try{
  if(file.size>8*1024*1024)throw new Error('Choose a file no larger than 8 MB.');
  const suffix=file.name.toLowerCase().split('.').pop();let pages=[];
  if(suffix==='txt'){const bytes=await file.arrayBuffer();const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);if(!text.trim())throw new Error('The text file is empty.');pages=[text];}
  else if(suffix==='pdf'){
   const pdfjs=await import('./vendor/pdf.mjs');pdfjs.GlobalWorkerOptions.workerSrc=new URL('./vendor/pdf.worker.mjs',location.href).href;
   let pdf;
   try{pdf=await pdfjs.getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false,useSystemFonts:false,disableFontFace:true,cMapUrl:undefined}).promise;
    if(pdf.numPages>500)throw new Error('Split documents longer than 500 pages.');
    for(let p=1;p<=pdf.numPages;p++){message(`Extracting PDF page ${p} of ${pdf.numPages}…`);const page=await pdf.getPage(p),text=await page.getTextContent();pages.push(text.items.filter(i=>typeof i.str==='string').map(i=>i.str+(i.hasEOL?'\n':' ')).join(''));if(pages.reduce((n,page)=>n+page.length,0)>1000000)throw new Error('Extracted text is too large. Use a smaller document.');}
   }finally{if(pdf)await pdf.destroy();}
   if(!pages.some(p=>p.trim()))throw new Error('No searchable text found. This scan needs OCR before import.');
  }else throw new Error('Choose a searchable PDF or UTF-8 TXT file.');
  addSource(file.name,pages);
 }finally{$('file').disabled=false;$('file').value='';}
}));
$('build').addEventListener('click',handle(()=>build()));
$('review').addEventListener('click',handle(()=>{const current=report();reports[current.template_id]=core.review(current,$('review-confirm').checked);render();message('Marked reviewed locally. This report remains unsigned.');}));
async function saveFile(name,text,type){
 const file=new File([text],name,{type});
 if(navigator.canShare&&navigator.canShare({files:[file]})){await navigator.share({files:[file],title:'Pi report'});return;}
 const url=URL.createObjectURL(file),a=element('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);
}
$('export-html').addEventListener('click',handle(async()=>{const current=report();await saveFile(`pi-${current.template_id}-${current.status}.html`,core.exportHTML(template(),current,$('case-label').value,$('include-references').checked),'text/html');message('Report prepared for saving. Nothing was sent to Jane or emailed.');}));
$('export-json').addEventListener('click',handle(async()=>{const current=report();await saveFile(`pi-${current.template_id}-${current.status}.json`,JSON.stringify({case_label:$('case-label').value||'Unspecified case',report:current},null,2),'application/json');message('Report JSON prepared for saving.');}));
$('reset').addEventListener('click',()=>{if(!confirm('Clear sources and reports? Save any reports you need first.'))return;sources=[];reports={};$('case-label').value='';$('source-input').value='';$('source-title').value='';renderSources();$('fields').replaceChildren(element('p','Workspace cleared. Add sources or try the fictional case.','help'));updateStatus();message('Workspace cleared.');});
$('demo').addEventListener('click',handle(async()=>{
 if(sources.length&&!confirm('Replace this workspace with the fictional example?'))return;
 sources=[];reports={};$('case-label').value='Fictional demo patient A';
 const demo=await (await fetch('./fictional-sources.json')).json();
 for(const source of demo)addSource(source.name,source.pages);build(false);
 message('Fictional case loaded. SOAP and DUD/LOE demonstrate filled sections; other reports show what is still missing.');
}));
