import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import vector_rag,setup_vector_rag

class VectorRagTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.env=patch.dict(os.environ,{'SIMULIDE_DATA':self.temp.name,'SIMULIDE_DEMO':'0','OPENAI_API_KEY':'TEST_ONLY'})
  self.env.start();self.addCleanup(self.env.stop)
  self.local={'excerpts':[{'id':'catalog:R','text':'Known','ref':1}],'available_native_elements':[{'type':'R'}]}
 def configure(self):
  cfg={'ready':True,'vector_store_id':'vs_test','documents':{'x':{'document_id':'x','file_id':'file_test','title':'Fixed Voltage','source':'code','kind':'native-guide','compatibility':'source_catalog','sha256':'hash','completed':True}}}
  vector_rag.config_path().write_text(json.dumps(cfg));return cfg
 def test_missing_config_never_calls_api(self):
  with patch('vector_rag.api') as api:
   self.assertEqual(vector_rag.augment(copy.deepcopy(self.local),'Test',[])['vector_retrieval']['status'],'not-configured');api.assert_not_called()
 def test_retrieval_metadata_filter_and_bounds(self):
  self.configure()
  result={'data':[{'file_id':'file_test','score':.8,'content':[{'type':'text','text':'Voltage '*2000}]},{'file_id':'unknown','content':[{'type':'text','text':'ignore me'}]}]}
  with patch('vector_rag.api',return_value=result) as api:
   r=vector_rag.augment(copy.deepcopy(self.local),'In potem?',[{'question':'Nastavitve vira'}])
  self.assertEqual(r['vector_retrieval']['added'],1)
  self.assertLessEqual(len(r['excerpts'][1]['text']),2400)
  self.assertEqual(r['excerpts'][1]['ref'],2)
  self.assertIn('Nastavitve vira',api.call_args.kwargs['json']['query'])
  self.assertEqual(api.call_args.kwargs['json']['filters']['value'],'simulide-public-v1')
  self.assertEqual(r['available_native_elements'],self.local['available_native_elements'])
 def test_failure_and_demo_keep_local(self):
  self.configure()
  with patch('vector_rag.api',side_effect=RuntimeError('fail')):
   r=vector_rag.augment(copy.deepcopy(self.local),'?',[])
   self.assertEqual(r['vector_retrieval']['status'],'unavailable-local-fallback');self.assertEqual(r['excerpts'],self.local['excerpts'])
  with patch.dict(os.environ,{'SIMULIDE_DEMO':'1'}),patch('vector_rag.api') as api:
   self.assertEqual(vector_rag.augment(copy.deepcopy(self.local),'?',[])['vector_retrieval']['status'],'demo');api.assert_not_called()
 def test_setup_is_resumable_and_excludes_unmapped(self):
  record={'id':'x','title':'Source','body':'This is a documented source.','source':'code','kind':'native-guide','compatibility':'source_catalog','types':['R']}
  unknown=dict(record,id='unknown',kind='official-guide',types=[])
  path=Path(self.temp.name)/'records.json';path.write_text(json.dumps([record,unknown]))
  responses=[{'id':'vs_test'},{'id':'file_test'},{'id':'file_test'},{'status':'completed'}]
  with patch('vector_rag.api',side_effect=responses) as api:
   setup_vector_rag.setup(path);self.assertEqual(api.call_count,4)
  cfg=json.loads(vector_rag.config_path().read_text());self.assertTrue(cfg['ready']);self.assertEqual(list(cfg['documents']),['x'])
  self.assertNotIn('TEST_ONLY',vector_rag.config_path().read_text())
  with patch('vector_rag.api') as api:
   setup_vector_rag.setup(path);api.assert_not_called()
 def test_setup_resumes_pending_file(self):
  row={'id':'x','title':'Source','body':'Body','source':'code','kind':'native-guide','compatibility':'source_catalog'}
  import hashlib
  cfg=self.configure();entry=cfg['documents']['x'];entry.update(completed=False,attached=True,sha256=hashlib.sha256(b'Body').hexdigest());cfg['ready']=False
  vector_rag.config_path().write_text(json.dumps(cfg))
  path=Path(self.temp.name)/'records.json';path.write_text(json.dumps([row]))
  with patch('vector_rag.api',return_value={'status':'completed'}) as api:
   setup_vector_rag.setup(path);self.assertEqual(api.call_count,1);self.assertEqual(api.call_args.args[0],'GET')
if __name__=='__main__':unittest.main()
