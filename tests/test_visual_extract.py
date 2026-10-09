import base64
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'local-service'))
import visual_extract as visual

class VisualTests(unittest.TestCase):
    def test_loopback_image_extraction_preserves_uncertainty_and_requires_review(self):
        body={'image':base64.b64encode(b'\x89PNG\r\n\x1a\nfictional fixture').decode()}
        result={'text':'Pain: handwritten 7/10. Spanish CHECKED; English UNCHECKED.', 'uncertainties':['Body-chart laterality unclear']}
        def respond(request, timeout):
            self.assertEqual(request.full_url,'http://127.0.0.1:11434/api/chat')
            packet=json.loads(request.data)
            self.assertEqual(packet['messages'][1]['images'],[body['image']])
            self.assertIn('UNCLEAR',packet['messages'][0]['content'])
            return io.BytesIO(json.dumps({'message':{'content':json.dumps(result)}}).encode())
        with patch.object(visual,'urlopen',side_effect=respond): output=visual.extract(body)
        self.assertTrue(output['requires_review']);self.assertEqual(output['uncertainties'],result['uncertainties'])
    def test_invalid_image_does_not_reach_model(self):
        with patch.object(visual,'urlopen') as request:
            with self.assertRaises(ValueError):visual.extract({'image':'not-base64'})
        request.assert_not_called()
    def test_missing_model_identifies_install_command(self):
        with patch.object(visual,'urlopen',side_effect=HTTPError('local',404,'missing',None,None)):
            with self.assertRaisesRegex(ValueError,'ollama pull'):visual.extract({'image':base64.b64encode(b'\x89PNG\r\n\x1a\n').decode()})
