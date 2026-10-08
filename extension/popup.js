let report = null, scannedTab = null, fields = [], schema = [];
// The Safari iPad package opens a full-tab workspace so picking a file from Files
// does not depend on keeping a small extension popup alive. Pin the Jane tab ID,
// not patient identifiers or a session cookie, in the extension-page URL.
const targetValue = new URLSearchParams(location.search).get('tab');
const targetTab = targetValue !== null && /^\d+$/.test(targetValue) ? Number(targetValue) : null;
const $ = id => document.getElementById(id);
const node = (tag,text) => {const e = document.createElement(tag); if(text !== undefined)e.textContent=text; return e;};
function show(text,error=false){$('result').textContent=text;$('result').className=error?'error':'';}
function handle(action){return async () => {try{await action();}catch(e){show(e.message,true);}};}
async function tab(){
  if(targetValue !== null && (targetTab === null || !Number.isSafeInteger(targetTab)))throw new Error('Invalid target tab. Reopen the workspace from the Jane tab.');
  const active=targetTab === null ? (await PiExtension.tabs.query({active:true,currentWindow:true}))[0] : await PiExtension.tabs.get(targetTab);
  if(!active || !PiBridge.isJaneURL(active.url))throw new Error('Open your clinic’s Jane admin page and allow the extension access to that site. If the tab was closed, reopen the workspace from Jane.');
  return active;
}
async function install(tabId){await PiExtension.scripting.executeScript({target:{tabId},files:['content.js']});}
function reset(){fields=[];scannedTab=null;$('mapping').replaceChildren();$('fill').disabled=true;$('confirm-patient').checked=false;}
function clearApproved(){report=null;reset();$('scan').disabled=true;$('report-summary').textContent='Draft changed. Review it before filling Jane.';}
window.addEventListener('pi-draft-edited',clearApproved);
window.addEventListener('pi-reviewed',event=>handle(async()=>{
 report=PiBridge.parseReport(event.detail);reset();schema=await (await fetch(PiExtension.runtime.getURL('reports.json'))).json();
 const template=schema.find(t=>t.id===report.templateId);for(const section of report.sections)section.label=template.fields.find(f=>f.id===section.id).label;
 $('report-summary').textContent=`Case: ${report.caseLabel}\nEncounter: ${report.encounter}\n${template.title} · reviewed locally, unsigned`;
 $('scan').disabled=false;show('Draft ready. Scan the matching Jane template and choose the destination fields.');
})());
$('report-file').addEventListener('change',handle(async()=>{
 const file=$('report-file').files[0];if(!file)return;clearApproved();if(file.size>4*1024*1024)throw new Error('Report limit: 4 MB.');
 await PiIntakeImport(JSON.parse(await file.text()));$('report-file').value='';
}));
$('scan').addEventListener('click',handle(async()=>{
  reset();const active=await tab();await install(active.id);const result=await PiExtension.tabs.sendMessage(active.id,{action:'pi-scan'});if(result.error)throw new Error(result.error);
  scannedTab={id:active.id,url:active.url};fields=result.fields;
  if(!fields.length)throw new Error('No supported visible editable fields found. Open the template editor. Editors in iframes require a separate adapter.');
  for(const section of report.sections){
    const box=node('div');box.className='section';const label=node('label',section.label);const select=node('select');select.dataset.section=section.id;
    const skip=node('option','Do not fill this section');skip.value='';select.append(skip);
    for(const field of fields){const option=node('option',`${field.label}${field.empty?'':' · already contains text — skipped'}`);option.value=field.id;option.disabled=!field.empty;select.append(option);}
    select.addEventListener('change',()=>{$('confirm-patient').checked=false;});
    label.append(select);const excerpt=node('div',section.text);excerpt.className='excerpt';box.append(label,excerpt);$('mapping').append(box);
  }
  $('fill').disabled=false;show('Map report sections to the correct empty fields. Existing text is protected. Nothing has been inserted yet.');
}));
$('fill').addEventListener('click',handle(async()=>{
  if(!$('confirm-patient').checked)throw new Error('Verify the correct patient and encounter and confirm the mapping first.');
  const active=await tab();if(!scannedTab || active.id!==scannedTab.id || active.url!==scannedTab.url)throw new Error('The tab or page changed. Scan and map the fields again.');
  const mapping={};document.querySelectorAll('select[data-section]').forEach(e=>mapping[e.dataset.section]=e.value);
  const assignments=PiBridge.validateMapping(report.sections,mapping);
  $('fill').disabled=true;
  try{const result=await PiExtension.tabs.sendMessage(active.id,{action:'pi-fill',assignments});if(result.error)throw new Error(result.error);
    show(result.results.map(r=>`${r.section}: ${r.status}${r.detail?' — '+r.detail:''}`).join('\n')+'\nReview the inserted text in Jane before saving.');
    $('confirm-patient').checked=false;
  }finally{$('fill').disabled=false;}
}));
