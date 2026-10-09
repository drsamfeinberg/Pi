import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'local-service'))
import workspace_server as app

class WorkspaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.passwords=app.init_store(Path(cls.temp.name));app.create_user('otherworker','other-password-long','worker')
  cls.server=app.ai.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);cls.base='http://127.0.0.1:'+str(cls.server.server_port);threading.Thread(target=cls.server.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
 def api(self,path,value=None,session=None,origin=None):
  headers={'Content-Type':'application/json'}
  if session:headers['X-Pi-Session']=session
  if origin:headers['Origin']=origin
  with urlopen(Request(self.base+'/api'+path,data=json.dumps(value).encode() if value is not None else None,headers=headers),timeout=10) as r:return json.load(r)
 def login(self,name):return self.api('/login',{'name':name,'password':self.passwords[name]})['session']
 def newcase(self,session):return self.api('/cases',{'case_label':'Fictional test case','encounter':'2026-01-15'},session)
 def test_worker_can_prepare_but_only_clinician_can_approve_and_other_worker_cannot_read(self):
  worker=self.login('worker');clinician=self.login('clinician');case=self.newcase(worker);cid=case['id']
  note='Subjective: Fictional symptom.\n\nObjective: Fictional examination.\n\nAssessment: Documented clinician assessment.\n\nPlan: Documented clinician plan.'
  case=self.api('/cases/'+cid+'/sources',{'version':case['version'],'source':{'name':'Fictional note','kind':'clinical','pages':[note]}},worker)
  case=self.api('/cases/'+cid+'/match',{'version':case['version'],'templates':['soap']},worker)
  self.assertEqual(case['reports']['soap']['fields']['soap_1']['text'],'Fictional symptom.')
  with self.assertRaises(HTTPError) as error:self.api('/cases/'+cid+'/approve',{'version':case['version'],'template_id':'soap','confirmed':True},worker)
  self.assertEqual(error.exception.code,403)
  with self.assertRaises(HTTPError):self.api('/cases/'+cid+'/approved/soap',session=worker)
  case=self.api('/cases/'+cid+'/approve',{'version':case['version'],'template_id':'soap','confirmed':True},clinician)
  packet=self.api('/cases/'+cid+'/approved/soap',session=worker)
  self.assertEqual(packet['report']['status'],'reviewed_unsigned');self.assertEqual(packet['version'],case['version'])
  other=self.api('/login',{'name':'otherworker','password':'other-password-long'})['session']
  with self.assertRaises(HTTPError):self.api('/cases/'+cid,session=other)
  self.assertNotIn(cid,[c['id'] for c in self.api('/cases',session=other)])
  fields={k:v['text'] for k,v in packet['report']['fields'].items()};fields['soap_1']='Changed fictional symptom.'
  case=self.api('/cases/'+cid+'/reports',{'version':case['version'],'template_id':'soap','fields':fields},worker)
  self.assertEqual(case['reports']['soap']['status'],'draft')
  with self.assertRaises(HTTPError):self.api('/cases/'+cid+'/approved/soap',session=worker)
  actions=self.api('/cases/'+cid+'/audit',session=worker);self.assertIn('clinician approved unsigned draft',[a['action'] for a in actions])
 def test_concurrent_edits_do_not_overwrite(self):
  worker=self.login('worker');case=self.newcase(worker);body={'version':case['version'],'source':{'name':'Fictional note','kind':'clinical','pages':['Fictional evidence.']}}
  self.api('/cases/'+case['id']+'/sources',body,worker)
  with self.assertRaises(HTTPError) as error:self.api('/cases/'+case['id']+'/sources',body,worker)
  self.assertEqual(error.exception.code,409)
 def test_template_examples_excluded_and_conflicts_stay_missing(self):
  template=next(t for t in app.TEMPLATES if t['id']=='soap')
  reports=app.match_sources([{'id':'a','name':'A','pages':['Subjective: One finding.']},{'id':'b','name':'B','pages':['Subjective: Different finding.']}],[template])
  self.assertEqual(reports['soap']['fields']['soap_1']['text'],'');self.assertTrue(reports['soap']['fields']['soap_1']['conflict'])
  case={'case_label':'Fictional','encounter':'2026-01-15','sources':[{'id':'t','name':'Template','pages':['Subjective: Example finding.'],'kind':'template'}]}
  with self.assertRaises(ValueError):app.process(case,[template],lambda x:None)
 def test_completed_example_upload_stays_excluded_from_evidence(self):
  worker=self.login('worker');case=self.newcase(worker)
  case=self.api('/cases/'+case['id']+'/sources',{'version':case['version'],'source':{'name':'Fictional style reference','kind':'example','pages':['Subjective: Example neck symptom.']}},worker)
  self.assertEqual(app.evidence_sources(case),[])
  with self.assertRaises(HTTPError) as error:
   self.api('/cases/'+case['id']+'/source_selection',{'version':case['version'],'source_id':case['sources'][0]['id'],'included':True},worker)
  self.assertEqual(error.exception.code,409)
 def test_audio_cancellation_stops_child_and_releases_local_job(self):
  worker=self.login('worker');other=self.api('/login',{'name':'otherworker','password':'other-password-long'})['session'];original=app.subprocess.Popen;children=[]
  def slow_worker(*args,**kwargs):
   child=original([app.sys.executable,'-u','-c','import time,json; print(json.dumps({"stage":"Fictional transcription running"}),flush=True); time.sleep(30)'],**kwargs)
   children.append(child);return child
  with patch.object(app.subprocess,'Popen',side_effect=slow_worker):
   request=Request(self.base+'/api/transcribe',data=b'fictional audio',headers={'X-Pi-Session':worker,'X-Pi-Audio-Suffix':'.m4a','Content-Type':'application/octet-stream'})
   with urlopen(request) as response:job=json.load(response)['job_id']
   for _ in range(100):
    if children:break
    time.sleep(.01)
   with self.assertRaises(HTTPError) as error:self.api('/jobs/'+job+'/cancel',{},other)
   self.assertEqual(error.exception.code,403)
   self.api('/jobs/'+job+'/cancel',{},worker)
   for _ in range(100):
    if not app.BUSY.locked():break
    time.sleep(.01)
   self.assertFalse(app.BUSY.locked());self.assertIsNotNone(children[0].poll())
   value=self.api('/jobs/'+job,session=worker)
   self.assertEqual(value['status'],'error');self.assertIn('canceled',value['error'])
 def test_unsigned_sources_cannot_supply_approved_report_and_normal_web_origins_rejected(self):
  with self.assertRaises(HTTPError):self.api('/cases')
  with self.assertRaises(HTTPError):self.api('/login',{'name':'worker','password':self.passwords['worker']},origin='https://attacker.example')
 def test_batch_generation_saves_both_reports_from_same_case_with_stubs(self):
  worker=self.login('worker');case=self.newcase(worker);case=self.api('/cases/'+case['id']+'/sources',{'version':case['version'],'source':{'name':'Fictional evidence','kind':'clinical','pages':['Fictional documented symptom.']}},worker)
  def model(payload,progress):return {'report':{'template_id':payload['template']['id'],'status':'draft','fields':{f['id']:{'text':'Fictional documented symptom.','citations':[],'candidates':[],'conflict':False} for f in payload['template']['fields']}}}
  with patch.object(app.ai,'draft',side_effect=model):
   job=self.api('/cases/'+case['id']+'/generate',{'version':case['version'],'templates':['soap','jane_evaluation']},worker)
   for attempt in range(60):
    value=self.api('/jobs/'+job['job_id'],session=worker)
    if value['status']!='running':break
    time.sleep(.01)
   self.assertEqual(value['status'],'complete');self.assertEqual(set(value['result']['reports']),{'soap','jane_evaluation'})
 def test_saved_case_survives_store_reinitialization(self):
  worker=self.login('worker');case=self.newcase(worker);self.assertEqual(app.init_store(Path(self.temp.name)),{})
  self.assertEqual(self.api('/cases/'+case['id'],session=worker)['case_label'],'Fictional test case')

 def test_uploaded_templates_present_without_example_clinical_values(self):
  expected={'jane_soap','physician','dud_loe','narrative','lien'}
  self.assertTrue(expected.issubset({t['id'] for t in app.TEMPLATES}))
  self.assertEqual(len(next(t for t in app.TEMPLATES if t['id']=='jane_soap')['fields']),17)
  for t in app.TEMPLATES:
   if not t.get('administrative'): self.assertTrue(all('static_text' not in f for f in t['fields']))
 def test_lien_preserves_bilingual_form_without_model_or_signature_execution(self):
  t=next(t for t in app.TEMPLATES if t['id']=='lien')
  case={'case_label':'Fictional administrative case','encounter':'2026-01-15','sources':[]}
  with patch.object(app.ai,'draft',side_effect=AssertionError('Lien must not call a medical model')):
   result=app.process(case,[t],lambda stage:None)['lien']
  self.assertEqual(result['status'],'draft');self.assertTrue(result['administrative'])
  self.assertIn('I do hereby authorize',result['fields']['lien_2']['text'])
  self.assertIn('Por la presente autorizo',result['fields']['lien_3']['text'])
  self.assertIn('UNSIGNED FORM',result['fields']['lien_4']['text'])
  self.assertNotIn('Ted Test',json.dumps(result))

 def test_ai_excludes_legacy_demo_and_deselected_evidence(self):
  case={'case_label':'Fictional test with new evidence','encounter':'2026-01-15','sources':[{'id':'demo','name':app.DEMO_SOURCE_NAME,'kind':'clinical','pages':[app.DEMO_SENTENCE]},{'id':'real','name':'New evaluation note','kind':'clinical','pages':['Patient-reported symptom.']},{'id':'exclude','name':'Unselected document','kind':'clinical','included':False,'pages':['Other statement.']}]}
  template=next(t for t in app.TEMPLATES if t['id']=='soap')
  def model(payload,progress):
   self.assertEqual([s['id'] for s in payload['sources']],['real'])
   return {'report':{'template_id':'soap','status':'draft','fields':{'soap_1':{'text':'Patient-reported symptom.'}}}}
  with patch.object(app.ai,'draft',side_effect=model): report=app.process(case,[template],lambda stage:None)['soap']
  self.assertEqual(report['used_source_ids'],['real']);self.assertEqual(report['generation_method'],'local_ai')
 def test_source_selection_and_rename_keep_uploads_and_prevent_old_demo_approval(self):
  worker=self.login('worker');clinician=self.login('clinician');case=self.newcase(worker);cid=case['id']
  text='\n\n'.join(f"{f['label']}: {app.DEMO_SENTENCE}" for f in next(t for t in app.TEMPLATES if t['id']=='soap')['fields'])
  case=self.api('/cases/'+cid+'/sources',{'version':case['version'],'source':{'name':app.DEMO_SOURCE_NAME,'kind':'clinical','pages':[text]}},worker)
  case=self.api('/cases/'+cid+'/match',{'version':case['version'],'templates':['soap']},worker)
  case=self.api('/cases/'+cid+'/sources',{'version':case['version'],'source':{'name':'New verified evidence','kind':'clinical','pages':['New verified facts.']}},worker)
  with self.assertRaises(HTTPError):self.api('/cases/'+cid+'/approve',{'version':case['version'],'template_id':'soap','confirmed':True},clinician)
  case=self.api('/cases/'+cid+'/details',{'version':case['version'],'case_label':'De-identified actual trial','encounter':'2026-01-15'},worker)
  self.assertEqual(len(case['sources']),2)
  sid=case['sources'][1]['id'];case=self.api('/cases/'+cid+'/source_selection',{'version':case['version'],'source_id':sid,'included':False},worker)
  self.assertEqual(app.evidence_sources(case),[])

if __name__=='__main__':unittest.main()
