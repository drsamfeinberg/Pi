const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const path=require('node:path');
let server,browser,base;
before(async()=>{
 const root=path.resolve(__dirname,'../docs');
 server=spawn('python',['-u','-c','from http.server import HTTPServer,SimpleHTTPRequestHandler\ns=HTTPServer(("127.0.0.1",0),SimpleHTTPRequestHandler)\nprint(s.server_port,flush=True)\ns.serve_forever()'],{cwd:root,stdio:['ignore','pipe','ignore']});
 const port=await new Promise((resolve,reject)=>{server.stdout.once('data',data=>resolve(Number(data.toString().trim())));server.once('error',reject);server.once('exit',code=>reject(new Error(`Static server exited: ${code}`)));});
 base=`http://127.0.0.1:${port}`;
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
});
after(async()=>{if(browser)await browser.close();if(server)server.kill();});
async function page(){const context=await browser.newContext({viewport:{width:820,height:1180},deviceScaleFactor:2,isMobile:true,hasTouch:true});await context.addInitScript(()=>Object.defineProperty(navigator,'canShare',{value:()=>false,configurable:true}));const page=await context.newPage();await page.goto(base);return{page,context};}
test('iPad-sized layout loads a fictional case and edits clear review status',async()=>{
 const {page:p,context}=await page();try{
  const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.getByRole('button',{name:'Try a fictional case'}).click();await p.locator('#soap_1').waitFor();
  assert.match(await p.locator('#progress').innerText(),/4 \/ 4/);await p.locator('#review-confirm').check();await p.locator('#review').click();assert.match(await p.locator('#review-state').innerText(),/Reviewed locally/);
  await p.locator('#soap_1').fill('Edited fictional symptom.');assert.match(await p.locator('#review-state').innerText(),/DRAFT/);
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
  await p.locator('#template').selectOption('narrative');assert.match(await p.locator('#progress').innerText(),/22 \/ 22/);
  await p.locator('#template').selectOption('dud_loe');assert.match(await p.locator('#progress').innerText(),/15 \/ 15/);
 }finally{await context.close();}
});
test('conflicting source passages require a choice before review',async()=>{
 const {page:p,context}=await page();try{
  await p.locator('#demo').click();await p.locator('#soap_1').waitFor();await p.locator('#source-title').fill('Fictional conflicting note');await p.locator('#source-input').fill('Subjective: A different fictional complaint.');await p.locator('#add-source').click();p.once('dialog',dialog=>dialog.accept());await p.locator('#build').click();
  assert.match(await p.locator('#progress').innerText(),/1 source conflicts/);assert.equal(await p.locator('#soap_1').inputValue(),'');await p.getByRole('button',{name:'Use this passage'}).first().click();assert.match(await p.locator('#progress').innerText(),/0 source conflicts/);
 }finally{await context.close();}
});
test('PDF import extracts two pages and fills matching sections',async()=>{
 const {page:p,context}=await page();try{
  const pdf=execFileSync('python',['-c','from reportlab.pdfgen.canvas import Canvas\nfrom io import BytesIO\nimport sys\nb=BytesIO();c=Canvas(b)\nc.drawString(60,740,"Subjective: Fictional PDF symptom.")\nc.drawString(60,700,"Objective: Fictional PDF examination.")\nc.showPage()\nc.drawString(60,740,"Assessment: Fictional PDF clinician input.")\nc.drawString(60,700,"Plan: Fictional PDF plan.")\nc.save();sys.stdout.buffer.write(b.getvalue())']);
  await p.locator('#file').setInputFiles({name:'fictional-two-page.pdf',mimeType:'application/pdf',buffer:pdf});await p.locator('#sources summary').waitFor({timeout:30000});assert.match(await p.locator('#sources summary').innerText(),/2 page/);await p.locator('#build').click();assert.match(await p.locator('#progress').innerText(),/4 \/ 4/);assert.match(await p.locator('#soap_4').inputValue(),/Fictional PDF plan/);
 }finally{await context.close();}
});
test('report download escapes source markup and includes draft labeling',async()=>{
 const {page:p,context}=await page();try{
  await p.locator('#source-input').fill('Subjective: <script>document.title="injected"</script>');await p.locator('#add-source').click();await p.locator('#build').click();assert.equal(await p.title(),'Pi · Case workspace');const downloadPromise=p.waitForEvent('download');await p.locator('#export-html').click();const download=await downloadPromise;const html=await fs.readFile(await download.path(),'utf8');assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.ok(html.includes('DRAFT'));
 }finally{await context.close();}
});
test('JSON downloads directly even if the browser Share API rejects files',async()=>{const {page:p,context}=await page();try{await p.evaluate(()=>{Object.defineProperty(navigator,'canShare',{value:()=>true});Object.defineProperty(navigator,'share',{value:()=>{throw new Error('Share blocked');}});});await p.locator('#demo').click();await p.locator('#soap_1').waitFor();const event=p.waitForEvent('download');await p.locator('#export-json').click();const file=await event;const packet=JSON.parse(await fs.readFile(await file.path(),'utf8'));assert.equal(packet.report.template_id,'soap');assert.equal(await p.locator('#download-link').isVisible(),true);assert.deepEqual(JSON.parse(await p.locator('#json-text').inputValue()),packet);}finally{await context.close();}});
