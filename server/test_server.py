import os,tempfile,unittest,time,json
from io import BytesIO
from unittest.mock import patch,Mock
os.environ['SIMULIDE_DATA']=tempfile.mkdtemp(prefix='simulide-test-')
from app import app,db,generate_password_hash,model_answer,init_db
def model_reply(answer='Odgovor', alert=None, usage=None):
 def reply(payload, **kwargs):
  if payload.get('text',{}).get('format',{}).get('name')=='simulide_teacher_review':
   return json.dumps(alert or {'needed':False,'urgency':'none','reason':'','evidence':[]}), {'input_tokens':4}
  return answer, usage or {}
 return reply

class ClassroomTest(unittest.TestCase):
 def setUp(self):
  with db() as c:
   for table in ['alert_feedback','help_requests','challenges','lesson_summaries','profile_overrides','teacher_alerts','exchanges','knowledge_docs','prompt_versions','revisions','lessons','sessions','attempts','users']: c.execute('DELETE FROM '+table)
   for name,role in [('rok','teacher'),('ana','student'),('bor','student')]: c.execute('INSERT INTO users(name,password,role) VALUES (?,?,?)',(name,generate_password_hash('testpass123'),role))
   for title in ['Ura 1','Ura 2']:
    lid=c.execute("INSERT INTO lessons(title,lesson_date,group_name) VALUES (?,'2026-10-08','A')",(title,)).lastrowid
    c.execute('INSERT INTO revisions VALUES (?,1,?,?,?,?,?)',(lid,'Ohmov zakon','Naloga','NAMIGI','gpt-4.1-mini',60))
  init_db()
  self.client=app.test_client();self.auth=self.login('ana')
 def login(self,name):
  r=self.client.post('/api/login',json={'username':name,'password':'testpass123'})
  return {'Authorization':'Bearer '+r.json['token']}
 def chat(self,lesson=1,rid='request-test-00001',headers=None,question='Zakaj?',snapshot=None):
  return self.client.post('/api/chat',json={'lesson_id':lesson,'request_id':rid,'question':question,'snapshot':snapshot if snapshot is not None else {'components':[{'id':'R1'}]}},headers=self.auth if headers is None else headers)
 def history(self,lesson,auth=None): return self.client.post('/api/select',json={'lesson_id':lesson},headers=auth or self.auth).json['history']
 def test_vector_sources_are_sent_and_saved(self):
  folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
  from pathlib import Path
  config=Path(folder.name)/'vector-rag.json'
  config.write_text(json.dumps({'ready':True,'vector_store_id':'vs_test','documents':{'x':{'document_id':'x','file_id':'file_test','title':'Dokumentacija','source':'https://simulide.com/p/component-list/','kind':'official-guide','compatibility':'unverified','sha256':'abc','completed':True}}}))
  with patch.dict(os.environ,{'SIMULIDE_DEMO':'0'}),patch('app.vector_rag.config_path',return_value=config),patch('app.vector_rag.api',return_value={'data':[{'file_id':'file_test','score':.9,'content':[{'type':'text','text':'ZEBRA zanesljiv dokumentiran podatek.'}]}]}),patch('app.model_answer',side_effect=model_reply('Odgovor [1]')) as model:
   result=self.chat(rid='request-vector-00001',question='ZEBRA')
  self.assertEqual(result.status_code,200)
  self.assertIn('ZEBRA zanesljiv',model.call_args_list[0].args[0]['input'][-1]['content'])
  with db() as c:saved=json.loads(c.execute('SELECT knowledge FROM exchanges').fetchone()['knowledge'])
  self.assertEqual(saved['vector_retrieval']['status'],'complete')
  self.assertEqual(saved['excerpts'][0]['file_id'],'file_test')
 def test_persistence_isolation_and_retry(self):
  with patch('app.model_answer',side_effect=model_reply('Preveri R1',usage={'input_tokens':12})) as m:
   self.assertEqual(self.chat().status_code,200);self.assertEqual(self.chat().json['answer'],'Preveri R1');self.assertEqual(m.call_count,2)
   self.assertFalse(m.call_args_list[0].args[0]['store']);self.assertIn('CURRENT_CIRCUIT_SNAPSHOT',m.call_args_list[0].args[0]['input'][-1]['content'])
  self.assertEqual(len(self.history(1,self.login('ana'))),1);self.assertEqual(self.history(2),[]);self.assertEqual(self.history(1,self.login('bor')),[])
  with db() as c:
   r=c.execute('SELECT * FROM exchanges').fetchone();self.assertIn('R1',r['snapshot']);self.assertEqual(r['version'],1)
 def test_timeline_reaches_model_and_teacher_snapshot(self):
  trace={'channels':[{'component_id':'V1','pin_id':'V1-out','quantity':'voltage_V'}],
         'samples':[{'time_s':0,'values':[5]},{'time_s':.2,'values':[3]}],
         'kind':'sparse_gui_samples','max_observed_gap_sim_s':.2}
  snapshot={'components':[], 'simulation':{'measurements_valid':True,'timeline':trace}}
  with patch('app.model_answer',side_effect=model_reply()) as m:
   self.assertEqual(self.chat(snapshot=snapshot).status_code,200)
   tutor=m.call_args_list[0].args[0]
   self.assertIn('sparse_gui_samples',tutor['input'][-1]['content'])
   self.assertIn('med vzorci lahko manjka',tutor['instructions'])
  with db() as c: row=c.execute('SELECT * FROM exchanges').fetchone()
  self.client.post('/login',data={'username':'rok','password':'testpass123'})
  self.assertEqual(self.client.get('/exchange/'+str(row['id'])+'/snapshot').json['simulation']['timeline'],trace)
 def test_teacher_csrf_versions_export(self):
  self.assertEqual(self.client.post('/lessons',data={'title':'X'}).status_code,302)
  self.client.post('/login',data={'username':'rok','password':'testpass123'});csrf=self.client.get_cookie('teacher_session').value
  self.assertEqual(self.client.post('/lessons',data={'title':'X'}).status_code,403)
  self.assertEqual(self.client.post('/lessons',data={'csrf':csrf,'id':1,'title':'Ura 1','model':'gpt-4.1-mini','quota':60,'active':'on','prompt':'NOV PROMPT'}).status_code,302)
  with patch('app.model_answer',side_effect=model_reply()) as m:
   self.chat();self.assertIn('NOV PROMPT',m.call_args_list[0].args[0]['instructions'])
  export=self.client.get('/lesson/1?export=1').json;self.assertEqual(len(export['revisions']),2);self.assertEqual(export['exchanges'][0]['version'],2)
  self.assertEqual(self.client.get('/exchange/1/snapshot').status_code,200);self.assertEqual(self.client.get('/').status_code,200);self.assertEqual(self.client.get('/lesson/1').status_code,200)
 def test_failure_quota_closed(self):
  with patch('app.model_answer',side_effect=RuntimeError('Napaka')) as m:
   self.assertEqual(self.chat().status_code,502);self.assertEqual(self.chat().status_code,502);self.assertEqual(m.call_count,1)
  with db() as c: c.execute('UPDATE revisions SET quota=1')
  self.assertEqual(self.chat(rid='request-test-00002').status_code,429)
  with db() as c: c.execute('UPDATE lessons SET active=0 WHERE id=2')
  self.assertEqual(self.chat(lesson=2,rid='request-test-00003').status_code,403);self.assertEqual(self.history(2),[])
 def test_parser_auth_and_validation(self):
  response=Mock(status_code=200);response.json.return_value={'output':[{'type':'reasoning'},{'type':'message','content':[{'type':'output_text','text':'A'},{'type':'output_text','text':'B'}]}],'usage':{}}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'FAKE_TEST_ONLY','SIMULIDE_DEMO':'0'}),patch('app.requests.post',return_value=response) as m:
   self.assertEqual(model_answer({})[0],'A\nB');self.assertEqual(m.call_args.args[0],'https://api.openai.com/v1/responses')
  self.assertEqual(self.client.post('/api/chat',json={},headers=self.auth).status_code,400);self.assertEqual(self.chat(headers={}).status_code,401);self.assertEqual(self.client.get('/exchange/1/snapshot').status_code,302)
 def test_login_limit_logout(self):
  for _ in range(10): self.client.post('/api/login',json={'username':'ana','password':'wrong'})
  self.assertEqual(self.client.post('/api/login',json={'username':'ana','password':'testpass123'}).status_code,429)
  self.assertEqual(self.client.post('/api/logout',json={},headers=self.auth).status_code,200);self.assertEqual(self.client.post('/api/select',json={'lesson_id':1},headers=self.auth).status_code,401)
 def test_pending_and_stale(self):
  with db() as c: c.execute("INSERT INTO exchanges(request_id,user_id,lesson_id,version,created,question,snapshot,status) VALUES ('request-test-00001',2,1,1,?,'Zakaj?','{}','pending')",(time.time(),))
  self.assertEqual(self.chat().status_code,409)
  with db() as c: c.execute('UPDATE exchanges SET created=created-200')
  self.assertEqual(self.chat().status_code,502)
  with db() as c: self.assertEqual(c.execute('SELECT status FROM exchanges').fetchone()[0],'failed')
 def test_rag_upload_scope_revision_and_export(self):
  self.assertEqual(self.client.get('/knowledge').status_code,302)
  self.client.post('/login',data={'username':'rok','password':'testpass123'});csrf=self.client.get_cookie('teacher_session').value
  self.assertEqual(self.client.post('/knowledge',data={'title':'X'}).status_code,403)
  body='Posebno pravilo meritev ZEBRA: poimenuj rezultat Meritev ZEBRA in preveri enoto volt.'
  data={'csrf':csrf,'title':'Meritev ZEBRA','source':'Učiteljev priročnik','lesson_id':1,'active':'on','file':(BytesIO(body.encode()),'navodila.md')}
  self.assertEqual(self.client.post('/knowledge',data=data,content_type='multipart/form-data').status_code,302)
  self.assertIn('Meritev ZEBRA',self.client.get('/knowledge').text)
  with patch('app.model_answer',side_effect=model_reply('Odgovor [1]')) as m:
   r=self.client.post('/api/chat',json={'lesson_id':1,'request_id':'request-knowledge-01','question':'Kaj pomeni ZEBRA?','snapshot':{}},headers=self.auth)
   self.assertEqual(r.status_code,200)
   self.assertIn('PROGRAM_KNOWLEDGE',m.call_args_list[0].args[0]['input'][-1]['content'])
   with db() as c: saved=c.execute('SELECT knowledge,id FROM exchanges').fetchone()
   evidence=json.loads(saved['knowledge']);self.assertTrue(any(body in e['text'] for e in evidence['excerpts']))
  self.assertEqual(self.client.get('/exchange/'+str(saved['id'])+'/knowledge').json,evidence)
  self.assertEqual(self.client.get('/lesson/1?export=1').json['exchanges'][0]['knowledge'],saved['knowledge'])
  from knowledge import retrieve
  with db() as c:
   docs=[dict(r,id='teacher:'+str(r['id']),kind='teacher-document') for r in c.execute('SELECT * FROM knowledge_docs WHERE active=1 AND (lesson_id IS NULL OR lesson_id=2)')]
  self.assertFalse(any(e['id'].startswith('teacher:') for e in retrieve('Kaj pomeni ZEBRA?',{},[],docs)['excerpts']))
  self.assertEqual(self.client.post('/knowledge',data={'csrf':csrf,'id':1,'title':'Novo','body':'Spremenjeno gradivo, ki ne vsebuje prejšnjega posebnega pravila.','lesson_id':1,'source':'Učitelj'}).status_code,302)
  self.assertEqual(self.client.get('/exchange/'+str(saved['id'])+'/knowledge').json,evidence)
 def test_legacy_migration(self):
  from app import init_db
  with db() as c: c.execute('ALTER TABLE exchanges DROP COLUMN knowledge')
  init_db();init_db()
  with db() as c:
   self.assertIn('knowledge',{r['name'] for r in c.execute('PRAGMA table_info(exchanges)')})
   self.assertEqual(c.execute('SELECT count(*) FROM users').fetchone()[0],3)
 def test_browser_folders_and_original_download(self):
  self.assertEqual(self.client.get('/knowledge/1/download').status_code,302)
  self.client.post('/login',data={'username':'rok','password':'testpass123'});csrf=self.client.get_cookie('teacher_session').value
  self.assertEqual(self.client.post('/knowledge/folders',data={'name':'RAG'}).status_code,403)
  response=self.client.post('/knowledge/folders',data={'csrf':csrf,'name':'Deljena navodila'})
  self.assertEqual(response.status_code,302)
  with db() as c: fid=c.execute("SELECT id FROM knowledge_folders WHERE name='Deljena navodila'").fetchone()[0]
  original=b'This original shared document explains the voltage divider and measurements.'
  self.assertEqual(self.client.post('/knowledge',data={'csrf':csrf,'folder_id':fid,'active':'on','file':(BytesIO(original),'unique-folder-document.txt')},content_type='multipart/form-data').status_code,302)
  with db() as c: did=c.execute('SELECT id FROM knowledge_docs').fetchone()[0]
  download=self.client.get('/knowledge/'+str(did)+'/download');self.assertEqual(download.data,original);self.assertIn('attachment',download.headers['Content-Disposition'])
  page=self.client.get('/knowledge?folder='+str(fid));self.assertIn('unique-folder-document',page.text)
  self.assertNotIn('unique-folder-document',self.client.get('/knowledge?folder=1').text)
  self.assertEqual(self.client.post('/knowledge',data={'csrf':csrf,'id':did,'title':'Novo ime','body':'To je urejeno besedilo za RAG, brez spreminjanja izvirne datoteke.','folder_id':1,'active':'on'}).status_code,302)
  self.assertEqual(self.client.get('/knowledge/'+str(did)+'/download').data,original)
  self.assertIn('Novo ime',self.client.get('/knowledge?folder=1').text)
  self.assertEqual(self.client.post('/knowledge',data={'csrf':csrf,'title':'Napaka','body':'x'*40,'folder_id':9999}).status_code,400)
 def test_editable_global_prompt_and_saved_effective_prompt(self):
  self.assertEqual(self.client.get('/settings/prompt').status_code,302)
  self.client.post('/login',data={'username':'rok','password':'testpass123'});csrf=self.client.get_cookie('teacher_session').value
  self.assertEqual(self.client.post('/settings/prompt',data={'prompt':'X'}).status_code,403)
  self.assertEqual(self.client.post('/settings/prompt',data={'csrf':csrf,'prompt':'GLOBALNI PROMPT: razloži na kratko v slovenščini.'}).status_code,302)
  self.assertIn('GLOBALNI PROMPT',self.client.get('/settings/prompt').text)
  with patch('app.model_answer',side_effect=model_reply()) as m:
   self.assertEqual(self.chat().status_code,200);payload=m.call_args_list[0].args[0]
   self.assertIn('GLOBALNI PROMPT',payload['instructions']);self.assertIn('NAMIGI',payload['instructions'])
  with db() as c: saved=c.execute('SELECT system_prompt FROM exchanges').fetchone()[0]
  self.assertEqual(json.loads(saved)['effective_instructions'],payload['instructions'])
  self.assertEqual(self.client.post('/settings/prompt',data={'csrf':csrf,'action':'reset'}).status_code,302)
  with db() as c:
   from app import BASE_PROMPT
   self.assertEqual(c.execute('SELECT text FROM prompt_versions ORDER BY version DESC LIMIT 1').fetchone()[0],BASE_PROMPT)
   self.assertEqual(c.execute('SELECT system_prompt FROM exchanges').fetchone()[0],saved)
  self.assertEqual(self.client.get('/lesson/1').status_code,200)
 def test_teacher_alerts_dedup_review_escalation_and_access(self):
  def response(needed=True,urgency='normal'):
   return model_reply('Preveriva skupaj.', {'needed':needed,'urgency':urgency,'reason':'Študent potrebuje pomoč pri naslednjem koraku.' if needed else '', 'evidence':['Zakaj?'] if needed else []})
  with patch('app.model_answer',side_effect=response()) as m:
   first=self.chat();self.assertEqual(first.status_code,200);self.assertTrue(first.json['answer'].startswith('Preveriva skupaj.'));self.assertIn('Pomoč učitelja je predlagana',first.json['answer'])
   self.chat();self.assertEqual(m.call_count,2)
   self.chat(rid='request-alert-00002')
   self.assertTrue(m.call_args.args[0]['text']['format']['strict'])
  with db() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM teacher_alerts').fetchone()[0],1)
   aid=c.execute('SELECT id FROM teacher_alerts').fetchone()[0]
  self.assertEqual(self.client.get('/teacher-alerts').status_code,302)
  self.client.post('/login',data={'username':'rok','password':'testpass123'});csrf=self.client.get_cookie('teacher_session').value
  self.assertIn('Študent potrebuje pomoč',self.client.get('/teacher-alerts').text)
  self.assertEqual(self.client.post('/teacher-alerts/'+str(aid)+'/status',data={'status':'resolved'}).status_code,403)
  self.assertEqual(self.client.post('/teacher-alerts/'+str(aid)+'/status',data={'csrf':csrf,'status':'reviewed'}).status_code,302)
  with patch('app.model_answer',side_effect=response()): self.chat(rid='request-alert-00003')
  with db() as c: self.assertEqual(c.execute('SELECT status FROM teacher_alerts').fetchone()[0],'reviewed')
  with patch('app.model_answer',side_effect=response(urgency='urgent')): self.chat(rid='request-alert-00004')
  with db() as c: self.assertEqual(c.execute('SELECT status FROM teacher_alerts').fetchone()[0],'open')
  self.client.post('/teacher-alerts/'+str(aid)+'/status',data={'csrf':csrf,'status':'resolved'})
  with patch('app.model_answer',side_effect=response(False,'none')): self.chat(rid='request-alert-00005')
  with db() as c: self.assertEqual(c.execute('SELECT status FROM teacher_alerts').fetchone()[0],'resolved')
  export=self.client.get('/lesson/1?export=1').json
  self.assertEqual(len(export['teacher_alerts']),1);self.assertIn('assessment',export['exchanges'][0])
  self.assertEqual(self.client.get('/lesson/1').status_code,200)
  self.assertIn('navAlertCount',self.client.get('/').text);self.assertIn('teacherAlerts',self.client.get('/?view=alerts').text)
 def test_no_alert_for_fabricated_evidence_and_no_alert_on_failure(self):
  alert={'needed':True,'urgency':'urgent','reason':'Razlog','evidence':['Študent tega ni napisal.']}
  with patch('app.model_answer',side_effect=model_reply('Odgovor.',alert)): self.assertEqual(self.chat().status_code,200)
  with db() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM teacher_alerts').fetchone()[0],0)
   self.assertEqual(json.loads(c.execute('SELECT assessment FROM exchanges').fetchone()[0])['status'],'unavailable')
  with patch('app.model_answer',return_value=('{bad JSON',{})): self.assertEqual(self.chat(rid='request-alert-bad01').status_code,502)
  with db() as c: self.assertEqual(c.execute('SELECT count(*) FROM teacher_alerts').fetchone()[0],0)
 def test_repeated_confusion_alert_despite_independent_reviewer_no(self):
  with patch('app.model_answer',side_effect=model_reply('Preveriva samo prvi korak.')) as model:
   self.assertEqual(self.chat(question='Joj nič ne znam...').status_code,200)
   response=self.chat(rid='request-confusion-02',question='ne razumem sploh kaj govoriš..')
   self.assertEqual(response.status_code,200)
   self.assertIn('Pomoč učitelja je predlagana',response.json['answer'])
   self.assertEqual(model.call_count,4)
   self.assertEqual(model.call_args.kwargs,{'timeout':15})
   review_payload=json.loads(model.call_args.args[0]['input'][0]['content'])
   self.assertEqual(review_payload['history'][0]['student'],'Joj nič ne znam...')
   self.assertEqual(review_payload['history'][0]['tutor'],'Preveriva samo prvi korak.')
   self.assertEqual(review_payload['current_tutor'],'Preveriva samo prvi korak.')
   self.chat(rid='request-confusion-02',question='ne razumem sploh kaj govoriš..')
   self.assertEqual(model.call_count,4)
  with db() as c:
   alert=c.execute('SELECT * FROM teacher_alerts').fetchone()
   self.assertEqual(alert['urgency'],'normal')
   self.assertEqual(json.loads(alert['evidence']),['Joj nič ne znam...','ne razumem sploh kaj govoriš..'])
   assessment=json.loads(c.execute('SELECT assessment FROM exchanges ORDER BY id DESC').fetchone()[0])
   self.assertEqual(assessment['source'],'rule')
   self.assertFalse(assessment['reviewer_needed'])

 def test_reviewer_failure_preserves_tutor_and_explicit_help(self):
  def failing_reviewer(payload,**kwargs):
   if payload.get('text',{}).get('format',{}).get('name')=='simulide_teacher_review':
    raise RuntimeError('PRIVATE_DETAIL')
   return 'Poišči vir Fixed Voltage.',{'input_tokens':12}
  with patch('app.model_answer',side_effect=failing_reviewer):
   ordinary=self.chat()
   self.assertEqual(ordinary.status_code,200)
   self.assertEqual(ordinary.json['answer'],'Poišči vir Fixed Voltage.')
   explicit=self.chat(rid='request-explicit-02',question='Potrebujem učitelja.')
   self.assertEqual(explicit.status_code,200)
   self.assertIn('Pomoč učitelja je predlagana',explicit.json['answer'])
  with db() as c:
   rows=c.execute('SELECT * FROM exchanges ORDER BY id').fetchall()
   self.assertEqual(json.loads(rows[0]['assessment'])['status'],'unavailable')
   self.assertEqual(json.loads(rows[1]['assessment'])['reviewer_status'],'unavailable')
   self.assertEqual(json.loads(rows[0]['usage'])['tutor']['input_tokens'],12)
   self.assertNotIn('PRIVATE_DETAIL',str([dict(r) for r in rows]))
   self.assertEqual(c.execute('SELECT count(*) FROM teacher_alerts').fetchone()[0],1)

 def test_snapshot_changes_and_cross_lesson_profile_ground_tutor_payload(self):
  first={'components':[{'id':'R1','type':'Resistor','properties':{'Resistance':{'value':1000,'unit':'Ω'}}}]}
  second={'components':[{'id':'R1','type':'Resistor','properties':{'Resistance':{'value':1500,'unit':'Ω'}}}]}
  state={'answers':[{'concept':'razmerje uporov','correct':True,'hint_used':True,'step':0}]}
  with db() as c:
   c.execute('INSERT INTO challenges(user_id,lesson_id,attempt,state,original_snapshot,created,updated) VALUES (2,2,1,?,?,?,?)',(json.dumps(state),'{}',time.time(),time.time()))
   c.execute('INSERT INTO profile_overrides(user_id,teacher_id,concept,status,note,created) VALUES (2,1,?,?,?,?)',('razmerje uporov','potrebuje nadaljnje preverjanje','Preveri samostojno razlago.',time.time()))
  with patch('app.model_answer',side_effect=model_reply()) as model:
   self.assertEqual(self.chat(snapshot=first).status_code,200)
   self.assertEqual(self.chat(rid='request-changes-02',snapshot=second).status_code,200)
   payload=model.call_args_list[2].args[0]
   content=payload['input'][-1]['content']
   self.assertIn('SNAPSHOT_CHANGES',content)
   self.assertIn('1500',content)
   self.assertIn('1000',content)
   self.assertIn('LEARNING_EVIDENCE',content)
   self.assertIn('pravilen odgovor z namigom',content)
   self.assertIn('Preveri samostojno razlago.',content)
   self.assertIn('Prilagajanje pomoči',payload['instructions'])
  with db() as c:
   saved=json.loads(c.execute('SELECT snapshot_changes FROM exchanges ORDER BY id DESC').fetchone()[0])
   self.assertEqual(saved['status'],'compared')
   self.assertEqual(saved['changes'][0]['field'],'properties')
   self.assertEqual(saved['changes'][0]['after']['Resistance']['value'],1500)
  with patch('app.model_answer',side_effect=model_reply()) as model:
   self.assertEqual(self.chat(rid='request-other-user',headers=self.login('bor')).status_code,200)
   self.assertNotIn('Preveri samostojno razlago.',model.call_args_list[0].args[0]['input'][-1]['content'])
if __name__=='__main__': unittest.main()
