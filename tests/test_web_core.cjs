const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const core=require('../docs/core.js');
const context={};vm.runInNewContext(fs.readFileSync(require.resolve('../docs/templates.js'),'utf8'),context);
const templates=JSON.parse(JSON.stringify(context.PI_TEMPLATES));
const source=(text,id='one')=>({id,name:`Fictional ${id}`,pages:[text]});
test('source aliases fill SOAP fields and preserve page and quote',()=>{
 const reports=core.assemble([source('Subjective: Fictional symptom.\n\nObjective: Fictional exam.\n\nAssessment: Fictional opinion.\n\nPlan: Fictional plan.')],templates);
 assert.deepEqual(core.stats(reports.soap),{filled:4,total:4,conflicts:0});assert.equal(reports.soap.fields.soap_1.citations[0].quote,'Fictional symptom.');assert.equal(reports.soap.fields.soap_1.citations[0].page,1);
});
test('unstructured text stays unmapped rather than becoming exam facts',()=>{
 const reports=core.assemble([source('Some unstructured account without a supported heading.')],templates);assert.equal(core.stats(reports.soap).filled,0);
});
test('different passages create an unresolved conflict without overwriting',()=>{
 const report=core.assemble([source('Subjective: Fictional first account.'),source('Subjective: Fictional different account.','two')],templates).soap;
 assert.equal(report.fields.soap_1.text,'');assert.equal(report.fields.soap_1.candidates.length,2);assert.equal(core.stats(report).conflicts,1);
});
test('identical excerpts retain both source references without a conflict',()=>{
 const report=core.assemble([source('Subjective: Same fictional account.'),source('Subjective: Same fictional account.','two')],templates).soap;
 assert.equal(core.stats(report).conflicts,0);assert.equal(report.fields.soap_1.citations.length,2);
});
test('missing fields and unresolved conflicts prevent review',()=>{
 const report=core.assemble([source('Subjective: Fictional account.')],templates).soap;assert.throws(()=>core.review(report,true),/missing/);
 for(const value of Object.values(report.fields))value.text='Explicit fictional placeholder';report.fields.soap_1.conflict=true;report.fields.soap_1.resolved=false;assert.throws(()=>core.review(report,true),/conflicting/);
});
test('review requires confirmation and remains unsigned',()=>{
 const report=core.assemble([],templates).soap;for(const value of Object.values(report.fields))value.text='Not applicable in fictional test';assert.throws(()=>core.review(report,false),/Confirm/);assert.equal(core.review(report,true).status,'reviewed_unsigned');assert.equal(report.status,'draft');
});
test('source markup and case labels are escaped in exported reports',()=>{
 const report=core.assemble([source('Subjective: <script>document.title="bad"</script>')],templates).soap;const output=core.exportHTML(templates[0],report,'<img src=x onerror=bad()>');assert.ok(!output.includes('<script>'));assert.ok(output.includes('&lt;script&gt;'));assert.ok(!output.includes('<img'));assert.ok(output.includes('MISSING'));
});
test('fictional case demonstrates SOAP, DUD/LOE, and narrative sections',()=>{
 const examples=JSON.parse(fs.readFileSync(require.resolve('../docs/fictional-sources.json'),'utf8')).map((s,i)=>({...s,id:String(i)}));const reports=core.assemble(examples,templates);
 for(const id of ['soap','dud_loe','narrative']){const s=core.stats(reports[id]);assert.equal(s.filled,s.total,id);assert.equal(s.conflicts,0,id);}
 assert.ok(core.stats(reports.imaging).filled<core.stats(reports.imaging).total);
});
