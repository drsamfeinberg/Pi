"""Production speed path: request counts, complete input coverage and citation isolation."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('pi_speed_service',Path(__file__).resolve().parents[1]/'local-service/pi_service.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def fixture():
    fields=[{'id':f'clinic_{i}','label':f'Clinical section {i}'} for i in range(17)]
    pages=[(f'Visit on 2026-01-{i+1:02d}. Patient reports symptoms rated 4/10. '+('Documented functional activity and clinical follow-up. '*65)) for i in range(9)]
    return {'case_label':'Fictional speed fixture','encounter':'2026-02-01',
            'template':{'id':'jane_soap','fields':fields},
            'sources':[{'id':'fixture','name':'Fictional dated notes','kind':'clinical','pages':pages}],
            '_evidence_cache':{}}


class SpeedTests(unittest.TestCase):
    def model(self,prompt,schema):
        fields=schema['properties']['fields']['properties']
        if 'text' not in next(iter(fields.values()))['properties']:
            passages=json.loads(prompt.split('Source passages:\n')[1])
            # Spread relevant passages across the sections; keep all citations original.
            return {'fields':{key:{'evidence_ids':[p['evidence_id'] for n,p in enumerate(passages) if (int(p['evidence_id'][1:])-1)%17==i]}
                              for i,key in enumerate(fields)}}
        result={}
        for key,definition in fields.items():
            ids=definition['properties']['evidence_ids']['items'].get('enum',[])
            # Schema contains only this section's IDs and protected numeric tokens.
            pattern=definition['properties']['text']['pattern']
            result[key]={'text':'Documented functional activity.' if ids else '',
                         'has_support':bool(ids),'evidence_ids':ids}
        return {'fields':result}

    def test_every_page_and_character_reaches_mapping_and_requests_are_reduced(self):
        payload=fixture();seen=[]
        def model(prompt,schema):
            if 'Source passages:\n' in prompt:seen.extend(json.loads(prompt.split('Source passages:\n')[1]))
            return self.model(prompt,schema)
        with patch.object(s,'chat',side_effect=model) as calls:
            packet=s.draft(payload)
        for page,original in enumerate(payload['sources'][0]['pages'],1):
            self.assertEqual(''.join(p['quote'] for p in seen if p['page']==page),original)
        metrics=packet['generation']
        self.assertEqual(metrics['mapping_requests'],metrics['source_chunks'])
        self.assertEqual(metrics['drafting_requests'],6)
        self.assertLess(calls.call_count,20)
        self.assertEqual(len(packet['report']['fields']),17)
        self.assertTrue(all(f['text'] and f['citations'] for f in packet['report']['fields'].values()))
        for value in packet['report']['fields'].values():
            self.assertEqual(s.checked_citations(value['citations'],payload['sources']),value['citations'])

    def test_nine_page_clinic_fixture_compares_same_source_with_legacy_request_count(self):
        payload=fixture()
        def legacy(prompt,schema):
            fields=schema['properties']['fields']['properties']
            if 'Source DATA:\n' in prompt:
                chunk=json.loads(prompt.split('Source DATA:\n')[1]);source=chunk[0]
                return {'fields':{key:{'citations':[{'source_id':source['source_id'],'page':source['page'],'quote':source['text'][:150]}]} for key in fields}}
            return self.model(prompt,schema)
        with patch.object(s,'chat',side_effect=legacy) as old:
            s.draft_legacy(payload)
        payload['_evidence_cache']={}
        with patch.object(s,'chat',side_effect=self.model) as new:
            packet=s.draft(payload)
        self.assertEqual(old.call_count,71)
        self.assertEqual(new.call_count,packet['generation']['source_chunks']+6)
        self.assertLessEqual(new.call_count,15)

    def test_production_chat_validates_mapping_and_batched_drafting_schemas(self):
        import io
        requests=[]
        def ollama(request,timeout):
            data=json.loads(request.data);requests.append(data)
            answer=self.model(data['messages'][1]['content'],data['format'])
            return io.BytesIO(json.dumps({'message':{'content':json.dumps(answer)},'done_reason':'stop'}).encode())
        with patch.object(s,'urlopen',side_effect=ollama):
            packet=s.draft(fixture())
        self.assertEqual(len(requests),packet['generation']['mapping_requests']+packet['generation']['drafting_requests'])
        self.assertTrue(all(f['text'] for f in packet['report']['fields'].values()))
        self.assertTrue(all(r['think'] is False for r in requests))

    def test_repeat_reuses_mapping_and_changed_source_or_model_invalidates_it(self):
        payload=fixture()
        with patch.object(s,'chat',side_effect=self.model):
            first=s.draft(payload);repeat=s.draft(payload)
            self.assertEqual(repeat['generation']['mapping_requests'],0)
            self.assertEqual(repeat['generation']['cached_mapping_chunks'],first['generation']['source_chunks'])
            payload['sources'][0]['pages'][0]='Changed clinician note. '+payload['sources'][0]['pages'][0]
            self.assertGreater(s.draft(payload)['generation']['mapping_requests'],0)
            with patch.object(s,'MODEL','different-local-model'):
                self.assertEqual(s.draft(payload)['generation']['cached_mapping_chunks'],0)

    def test_mapper_cannot_supply_invented_quote_or_unknown_passage(self):
        payload=fixture()
        def forged(prompt,schema):
            return {'fields':{key:{'evidence_ids':['invented'],'citations':[{'source_id':'fixture','page':1,'quote':'Invented fracture.'}]}
                              for key in schema['properties']['fields']['properties']}}
        with patch.object(s,'chat',side_effect=forged) as calls:
            packet=s.draft(payload)
        self.assertEqual(calls.call_count,packet['generation']['source_chunks'])
        self.assertTrue(all(not f['text'] and not f['citations'] for f in packet['report']['fields'].values()))

    def test_drafting_cannot_use_other_sections_numeric_tokens(self):
        payload=fixture();payload['template']['fields']=payload['template']['fields'][:2]
        payload['sources'][0]['pages']=['Patient reports pain 4/10. Clinician records rotation 35 degrees.']
        def model(prompt,schema):
            fields=list(schema['properties']['fields']['properties'])
            if 'Source passages:\n' in prompt:return {'fields':{key:{'evidence_ids':['P1']} for key in fields}}
            # Both sections have their own copies of the source and separate numeric tokens.
            return {'fields':{fields[0]:{'text':'Pain {{N3}}.','has_support':True,'evidence_ids':['E1']},
                              fields[1]:{'text':'','has_support':False,'evidence_ids':[]}}}
        with patch.object(s,'chat',side_effect=model):
            with self.assertRaisesRegex(ValueError,'uncited'):s.draft(payload)

    def test_empty_sections_have_valid_schema_and_no_synthesis_request(self):
        payload=fixture()
        def empty(prompt,schema):return {'fields':{key:{'evidence_ids':[]} for key in schema['properties']['fields']['properties']}}
        with patch.object(s,'chat',side_effect=empty):packet=s.draft(payload)
        self.assertEqual(packet['generation']['drafting_requests'],0)
        schema=s.section_schema(payload['template']['fields'][0],[])
        definition=schema['properties']['fields']['properties']['clinic_0']['properties']['evidence_ids']
        self.assertEqual(definition['maxItems'],0)
        self.assertNotIn('enum',definition['items'])


if __name__=='__main__':unittest.main()
