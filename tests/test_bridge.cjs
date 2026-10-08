const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const bridge = require('../extension/bridge.js');
function sample(){return {case_label:'Fictional case',encounter:'2026-01-15',report:{status:'reviewed_unsigned',template_id:'soap',fields:{soap_1:{text:'Fictional statement'},soap_2:{text:'Not supplied in demonstration'}}}};}
test('only the exact clinic HTTPS admin URL is eligible',()=>{
  assert.equal(bridge.isJaneURL('https://chiroduo.janeapp.com/admin'),true);
  assert.equal(bridge.isJaneURL('https://chiroduo.janeapp.com/admin/patient/1'),true);
  for(const url of ['http://chiroduo.janeapp.com/admin','https://chiroduo.janeapp.com.attacker.example/admin','https://other.janeapp.com/admin','https://chiroduo.janeapp.com/administrator','javascript:alert(1)'])assert.equal(bridge.isJaneURL(url),false);
});
test('reviewed report carries case context and section text',()=>{
  const report=bridge.parseReport(sample());assert.equal(report.caseLabel,'Fictional case');assert.equal(report.sections.length,2);assert.equal(report.sections[0].text,'Fictional statement');
});
test('drafts and malformed or empty sections are rejected',()=>{
  const draft=sample();draft.report.status='draft';assert.throws(()=>bridge.parseReport(draft),/reviewed/);
  const empty=sample();empty.report.fields.soap_1.text=' ';assert.throws(()=>bridge.parseReport(empty),/empty section/);
  assert.throws(()=>bridge.parseReport({}),/case label/);
});
test('only explicitly selected sections are assigned',()=>{
  const sections=bridge.parseReport(sample()).sections;
  assert.deepEqual(bridge.validateMapping(sections,{soap_2:'field-b'}),[{section:'soap_2',target:'field-b',text:'Not supplied in demonstration'}]);
});
test('duplicate destinations and zero selections are rejected',()=>{
  const sections=bridge.parseReport(sample()).sections;
  assert.throws(()=>bridge.validateMapping(sections,{soap_1:'same',soap_2:'same'}),/only one section/);
  assert.throws(()=>bridge.validateMapping(sections,{}),/at least one/);
});
test('extension template schema matches report application',()=>{
  const root=path.join(__dirname,'..');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(root,'templates/reports.json'))),JSON.parse(fs.readFileSync(path.join(root,'extension/reports.json'))));
});
