import importlib.util
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location('pi_service', Path(__file__).resolve().parents[1] / 'local-service/pi_service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def case():
    return {'case_label': 'Fictional patient', 'encounter': '2026-01-15', 'template': {'id': 'soap', 'fields': [{'id': 'soap_1', 'label': 'Subjective'}]}, 'sources': [{'id': 's1', 'name': 'Fictional note', 'pages': ['Patient reports neck discomfort. No other documented findings.']}]}


def response(quote='Patient reports neck discomfort.', text='The patient reports neck discomfort.'):
    return {'fields': {'soap_1': {'text': text, 'has_support':True, 'evidence_ids':['E1'], 'citations': [{'source_id': 's1', 'page': 1, 'quote': quote}]}}}


class EvidenceTests(unittest.TestCase):
    def test_generated_draft_has_verified_citations_and_is_unsigned(self):
        with patch.object(service, 'chat', return_value=response()):
            packet = service.draft(case())
        self.assertEqual(packet['report']['status'], 'draft')
        self.assertEqual(packet['report']['fields']['soap_1']['citations'][0]['page'], 1)
        self.assertIn('neck discomfort', packet['report']['fields']['soap_1']['text'])

    def test_fabricated_quotation_does_not_enter_draft(self):
        with patch.object(service, 'chat', return_value=response('Invented fracture finding.')):
            packet = service.draft(case())
        self.assertEqual(packet['report']['fields']['soap_1']['text'], '')

    def test_shorter_exact_quote_from_verified_passage_is_accepted(self):
        with patch.object(service, 'chat', side_effect=[
            response('Patient reports neck discomfort. No other documented findings.'),
            response('Patient reports neck discomfort.')]):
            packet = service.draft(case())
        self.assertIn('neck discomfort', packet['report']['fields']['soap_1']['text'])

    def test_source_quote_is_immutable_when_drafting_references_verified_evidence(self):
        payload=case();quote='Patient reports neck discomfort rated 7/10.'
        payload['sources'][0]['pages']=[quote]
        extraction=response(quote)
        synthesis={'fields':{'soap_1':{'text':'Patient reports neck discomfort rated 7/10.',
                                      'has_support':True,'evidence_ids':['E1'],
                                      'citations':[{'source_id':'s1','page':1,'quote':'Patient reports neck discomfort rated 7/1:10.'}]}}}
        with patch.object(service,'chat',side_effect=[extraction,synthesis]) as model:
            report=service.draft(payload)['report']
        self.assertEqual(report['fields']['soap_1']['citations'][0]['quote'],quote)
        self.assertIn('7/10',report['fields']['soap_1']['text'])
        self.assertIn('DO NOT retype',model.call_args_list[1].args[0])
        self.assertNotIn('citations',model.call_args_list[1].args[1]['properties']['fields']['properties']['soap_1']['properties'])

    def test_symptom_only_excerpt_does_not_fill_plan_when_support_is_false(self):
        payload=case();payload['template']['fields']=[{'id':'soap_4','label':'Plan'}]
        extraction={'fields':{'soap_4':{'citations':[{'source_id':'s1','page':1,'quote':'Patient reports neck discomfort.'}]}}}
        synthesis={'fields':{'soap_4':{'text':'Patient reports neck discomfort.','has_support':False,'evidence_ids':['E1']}}}
        with patch.object(service,'chat',side_effect=[extraction,synthesis]):
            value=service.draft(payload)['report']['fields']['soap_4']
        self.assertEqual(value['text'],'')

    def test_unknown_evidence_id_cannot_support_this_section(self):
        bad={'fields':{'soap_1':{'text':'Unrelated assertion','has_support':True,'evidence_ids':['E99']}}}
        with patch.object(service, 'chat', side_effect=[
            response('Patient reports neck discomfort.'),
            bad]):
            packet = service.draft(case())
        self.assertEqual(packet['report']['fields']['soap_1']['text'], '')

    def test_cross_date_history_and_partial_evidence_are_requested(self):
        payload = case()
        payload['sources'][0]['pages'][0] = 'Intake dated 2025-12-01: Patient reports neck discomfort.'
        with patch.object(service, 'chat', return_value=response()) as model:
            packet = service.draft(payload)
        prompt = model.call_args_list[0].args[0]
        self.assertIn('Use partial evidence', prompt)
        self.assertIn('2025-12-01', prompt)
        self.assertIn('target_report_date', prompt)
        self.assertIn('Subjective', prompt)
        self.assertIn('neck discomfort', packet['report']['fields']['soap_1']['text'])

    def test_style_profile_reaches_model_without_sample_patient_details(self):
        with patch.object(service, 'chat', return_value=response()) as model:
            service.draft(case())
        prompt = model.call_args_list[0].args[0]
        self.assertIn('writing_guidance', prompt)
        self.assertIn('Subjective:', prompt)
        guide = json.dumps(service.writing_guidance('soap'))
        self.assertNotRegex(guide, r'\b\d{4}-\d{2}-\d{2}\b|[\w.+-]+@[\w.-]+')
        self.assertIn('specific task', str(service.writing_guidance('dud_loe')))
        self.assertIn('verified', str(service.writing_guidance('mri')))

    def test_style_example_is_rejected_as_clinical_source(self):
        payload = case(); payload['sources'][0]['kind'] = 'example'
        with self.assertRaisesRegex(ValueError, 'not patient evidence'):
            service.validate_payload(payload)

    def test_large_template_extracts_small_labeled_batches(self):
        payload = case()
        payload['template']['fields'] = [{'id': 'field_'+str(i), 'label': 'Clinical section '+str(i)} for i in range(13)]
        def empty_model(prompt, schema):
            ids = list(schema['properties']['fields']['properties'])
            self.assertLessEqual(len(ids), 3)
            for field in ids:
                label = next(f['label'] for f in payload['template']['fields'] if f['id'] == field)
                self.assertIn(label, prompt)
            return {'fields': {i: {'text': '', 'citations': []} for i in ids}}
        with patch.object(service, 'chat', side_effect=empty_model) as model:
            packet = service.draft(payload)
        self.assertEqual(model.call_count, 5)
        self.assertEqual(len(packet['report']['fields']), 13)

    def test_uncited_generated_text_is_discarded(self):
        bad = {'fields': {'soap_1': {'text': 'Unsupported finding', 'citations': []}}}
        with patch.object(service, 'chat', side_effect=[response(), bad]):
            packet = service.draft(case())
        self.assertEqual(packet['report']['fields']['soap_1']['text'], '')

    def test_duplicate_source_ids_and_missing_encounters_rejected(self):
        payload = case(); payload['sources'] *= 2
        with self.assertRaises(ValueError): service.validate_payload(payload)
        payload = case(); payload['encounter'] = ''
        with self.assertRaises(ValueError): service.validate_payload(payload)

    def test_wrong_page_references_rejected(self):
        citation = response()['fields']['soap_1']['citations'][0]; citation['page'] = 2
        self.assertEqual(service.checked_citations([citation], case()['sources']), [])

    def test_model_connection_and_missing_model_errors_are_distinct(self):
        with patch.object(service, 'urlopen', side_effect=URLError('refused')):
            with self.assertRaisesRegex(ValueError, 'Ollama is running'): service.chat('Fictional input', {})
        with patch.object(service, 'urlopen', side_effect=HTTPError('http://127.0.0.1:11434',404,'Missing',{},None)):
            with self.assertRaisesRegex(ValueError, 'ollama pull'): service.chat('Fictional input', {})

    def test_incomplete_model_json_is_not_misreported_as_missing_model(self):
        import io
        responses = [io.BytesIO(json.dumps({'message':{'content':'{"fields":'}, 'done_reason':'length', 'eval_count':3500}).encode()) for _ in range(2)]
        with patch.object(service, 'urlopen', side_effect=responses):
            with self.assertRaisesRegex(ValueError, 'model-output error'): service.chat('Fictional input', {})

    def test_complete_fenced_json_is_accepted_without_retry(self):
        import io
        envelope = {'message': {'content': '```json\n'+json.dumps(response())+'\n```'}}
        with patch.object(service, 'urlopen', return_value=io.BytesIO(json.dumps(envelope).encode())) as request:
            result = service.chat('Fictional input', service.output_schema(case()['template']['fields']))
        self.assertIn('neck discomfort', result['fields']['soap_1']['text'])
        self.assertEqual(request.call_count, 1)

    def test_truncated_response_retries_once_and_validates_required_fields(self):
        import io
        replies = [{'message': {'content': '{"fields":'}, 'done_reason': 'length'}, {'message': {'content': json.dumps(response())}, 'done_reason': 'stop'}]
        requests=[]
        def reply(request, timeout):
            requests.append(json.loads(request.data))
            return io.BytesIO(json.dumps(replies[len(requests)-1]).encode())
        with patch.object(service, 'urlopen', side_effect=reply):
            result=service.chat('Fictional input',service.output_schema(case()['template']['fields']))
        self.assertEqual(len(requests),2)
        self.assertIn('FORMAT RETRY',requests[1]['messages'][1]['content'])
        self.assertIn('neck discomfort',result['fields']['soap_1']['text'])

    def test_missing_field_is_engine_error_and_diagnostics_do_not_expose_content(self):
        import io
        private='Fictional confidential fixture'
        replies=[io.BytesIO(json.dumps({'message':{'content':json.dumps({'fields':{},'extra':private})},'done_reason':'stop','eval_count':12}).encode()) for _ in range(2)]
        with patch.object(service,'urlopen',side_effect=replies):
            with self.assertRaisesRegex(ValueError,'incorrect section structure') as error:
                service.chat('Fictional input',service.output_schema(case()['template']['fields']))
        self.assertNotIn(private,str(error.exception));self.assertIn('output_tokens=12',str(error.exception))

    def test_engine_check_requires_actual_cited_symptom_output(self):
        quote='The fictional patient reports neck discomfort rated 7/10 after a fictional collision.'
        def model(prompt, schema):
            return {'fields':{key:{'text':'Patient reports neck discomfort rated 7/10.' if key=='soap_1' else '',
                                  'has_support':key=='soap_1','evidence_ids':['E1'] if key=='soap_1' else [],
                                  'citations':[{'source_id':'engine_fixture','page':1,'quote':quote}] if key=='soap_1' else []}
                             for key in schema['properties']['fields']['properties']}}
        with patch.object(service,'chat',side_effect=model):
            self.assertTrue(service.check_report_engine()['passed'])
        with patch.object(service,'chat',return_value={'fields':{}}):
            with self.assertRaisesRegex(ValueError,'Engine check failed'):service.check_report_engine()


class ConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = service.ThreadingHTTPServer(('127.0.0.1', 0), service.Handler)
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def request(self, path, data=None, token=service.TOKEN, origin=None):
        headers = {'X-Pi-Token': token}
        if origin: headers['Origin'] = origin
        if data is not None: headers['Content-Type'] = 'application/json'
        with urlopen(Request(self.base+path, data=json.dumps(data).encode() if data is not None else None, headers=headers), timeout=5) as response:
            return response.status, json.load(response)

    def test_missing_pairing_code_is_rejected(self):
        with self.assertRaises(HTTPError) as error: self.request('/health', token='')
        self.assertEqual(error.exception.code, 401)

    def test_web_origin_is_rejected_even_with_pairing_code(self):
        with self.assertRaises(HTTPError) as error: self.request('/health', origin='https://example.com')
        self.assertEqual(error.exception.code, 403)

    def test_extension_origin_can_generate_and_result_is_removed_after_collection(self):
        with patch.object(service, 'chat', return_value=response()):
            status, value = self.request('/generate', case(), origin='chrome-extension://'+'a'*32)
            self.assertEqual(status, 202)
            for attempt in range(30):
                status, value2 = self.request('/jobs/'+value['job_id'])
                if value2['status'] == 'complete': break
                time.sleep(.01)
            self.assertEqual(value2['result']['report']['status'], 'draft')
            with self.assertRaises(HTTPError) as error: self.request('/jobs/'+value['job_id'])
            self.assertEqual(error.exception.code, 404)

    def test_invalid_case_is_rejected(self):
        with self.assertRaises(HTTPError) as error: self.request('/generate', {})
        self.assertEqual(error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
