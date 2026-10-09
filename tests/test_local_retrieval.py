import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('pi_retrieval',Path(__file__).resolve().parents[1]/'local-service/pi_service.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class LocalRetrievalTests(unittest.TestCase):
 def case(self):
  template=next(t for t in json.loads(Path(s.__file__).with_name('workspace').joinpath('templates.json').read_text()) if t['id']=='jane_soap')
  return {'case_label':'Fictional test','encounter':'2026-02-01','template':template,'sources':[{'id':'fixture','name':'Fictional note','kind':'clinical','pages':['Visit March 26, 2026. Patient reports neck pain 4/10. Cervical rotation is 35 degrees. Clinician diagnoses cervical strain. Plan: 3 visits per week for 4 weeks. Goal is restored driving tolerance. Home exercise prescribed. Prognosis good. CPT 97140 manual therapy rationale documented.','Unassigned administrative material.']}]}
 def test_no_mapping_calls_are_made_and_original_quotes_and_dates_are_preserved(self):
  payload=self.case();calls=[]
  def model(prompt,schema):
   self.assertIn('Draft each requested report section',prompt);calls.append(prompt)
   data=json.loads(prompt.split('Sections and verified source DATA:\n')[1])
   return {'fields':{d['section']['id']:{'text':'Documented source extract.' if d['excerpts'] else '',
             'has_support':bool(d['excerpts']),'evidence_ids':[e['evidence_id'] for e in d['excerpts']]} for d in data}}
  with patch.object(s,'chat',side_effect=model):packet=s.draft(payload)
  self.assertEqual(packet['generation']['mapping_requests'],0)
  self.assertLessEqual(len(calls),6)
  self.assertEqual(packet['generation']['engine_version'],'local_retrieval_v3')
  self.assertIn('Unassigned administrative material.',[p['quote'] for p in packet['report']['retrieval_review']['unassigned']])
  for f in packet['report']['fields'].values():self.assertEqual(f['citations'],s.checked_citations(f['citations'],payload['sources']))
  evidence,unused,count=s.route_local_evidence(payload['template']['fields'],payload['sources'])
  self.assertTrue(any('March 26, 2026' in c['quote'] for c in evidence['jane_soap_06']))
 def test_police_source_is_never_a_candidate_for_exam_diagnosis_or_treatment(self):
  payload=self.case();payload['sources'][0]['kind']='police'
  evidence,_,_=s.route_local_evidence(payload['template']['fields'],payload['sources'])
  self.assertTrue(evidence['jane_soap_01'])
  self.assertFalse(evidence['jane_soap_02']);self.assertFalse(evidence['jane_soap_06']);self.assertFalse(evidence['jane_soap_11'])
 def test_lexical_candidates_do_not_automatically_fill_sections(self):
  payload=self.case()
  def unsupported(prompt,schema):return {'fields':{key:{'text':'','has_support':False,'evidence_ids':[]} for key in schema['properties']['fields']['properties']}}
  with patch.object(s,'chat',side_effect=unsupported):packet=s.draft(payload)
  self.assertTrue(all(not f['text'] for f in packet['report']['fields'].values()))
  self.assertEqual(packet['report']['fields']['jane_soap_06']['evidence_status'],'draft_not_verified')
 def test_every_passage_is_retained_as_candidate_or_unassigned_for_review(self):
  payload=self.case();payload['sources'][0]['pages'][0]*=50
  evidence,unassigned,_=s.route_local_evidence(payload['template']['fields'],payload['sources'])
  quotes={s.normalized(c['quote']) for values in evidence.values() for c in values}|{s.normalized(c['quote']) for c in unassigned}
  for passage in s.source_passages(payload['sources']):self.assertIn(s.normalized(passage['quote']),quotes)
 def test_large_evidence_is_processed_in_parts_without_discarding_passages(self):
  payload=self.case();payload['sources'][0]['pages'][0]*=70
  received=[]
  def model(prompt,schema):
   data=json.loads(prompt.split('Sections and verified source DATA:\n')[1]);received.extend(data)
   return {'fields':{d['section']['id']:{'text':'Cited source part.','has_support':bool(d['excerpts']),
              'evidence_ids':[e['evidence_id'] for e in d['excerpts']]} for d in data}}
  evidence,_,_=s.route_local_evidence(payload['template']['fields'],payload['sources'])
  with patch.object(s,'chat',side_effect=model):packet=s.draft(payload)
  self.assertTrue(packet['report']['split_sections'])
  for field,excerpts in evidence.items():
   self.assertEqual({s.normalized(c['quote']) for c in excerpts},
                    {s.normalized(c['quote']) for c in packet['report']['fields'][field]['citations']})
 def test_headings_preserve_multiple_paragraphs_across_pages_without_broad_rerouting(self):
  payload=self.case();payload['sources'][0]['pages']=['Chief Complaint:\nPain with driving.\n\nMore reported limitations.','Still limited with dressing.\nWorking Diagnosis / ICD-10 (Diagnosis) Codes:\nClinician documents cervical strain.']
  evidence,_,_=s.route_local_evidence(payload['template']['fields'],payload['sources'])
  self.assertTrue(any('More reported limitations' in c['quote'] for c in evidence['jane_soap_01']))
  self.assertTrue(any('cervical strain' in c['quote'] for c in evidence['jane_soap_06']))

if __name__=='__main__':unittest.main()
