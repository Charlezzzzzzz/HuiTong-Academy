import json, sys, pathlib, unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
from app.config import DEFAULT_MODEL, Settings
from app.model_gateway import ModelGateway, GatewayError
class TestGateway(unittest.TestCase):
 def test_default_is_alibaba_model(self): self.assertEqual(Settings().model, DEFAULT_MODEL); self.assertEqual(DEFAULT_MODEL, 'deepseek-v4.1-flash-1017')
 def test_mock(self): self.assertEqual(ModelGateway(Settings(mode='mock')).complete([{'role':'user','content':'x'}])['mode'],'mock')
 def test_json_validation(self):
  with self.assertRaises(GatewayError): ModelGateway(Settings(mode='fixture')).complete([{'role':'user','content':'x'}],fixture='not json')
 def test_missing_key(self):
  with self.assertRaises(GatewayError): ModelGateway(Settings(mode='live',api_key='')).complete([{'role':'user','content':'x'}])
 def test_live_uses_model_and_does_not_expose_key_in_result(self):
  class Response:
   def __enter__(self): return self
   def __exit__(self, *args): return False
   def read(self): return json.dumps({'id':'req-1','choices':[{'message':{'content':'{"ok": true}'}}], 'usage':{'total_tokens':3}}).encode()
  settings=Settings(mode='live', api_key='secret', base_url='https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1')
  with patch('urllib.request.urlopen', return_value=Response()) as opener:
   result=ModelGateway(settings).complete([{'role':'user','content':'x'}], response_format={'type':'json_object'})
  self.assertTrue(result['ok']); self.assertNotIn('secret', json.dumps(result)); request=opener.call_args.args[0]; self.assertTrue(request.full_url.endswith('/chat/completions')); self.assertEqual(json.loads(request.data)['model'], 'deepseek-v4.1-flash-1017')
