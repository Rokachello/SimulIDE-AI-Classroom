# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('SIMULIDE_DATA', tempfile.mkdtemp(prefix='simulide-features-test-'))
import app as classroom


class FeaturesTest(unittest.TestCase):
    def setUp(self):
        with classroom.db() as c:
            for table in ['alert_feedback','help_requests','challenges','lesson_summaries','profile_overrides','teacher_alerts','exchanges','knowledge_docs','prompt_versions','revisions','lessons','sessions','attempts','users']:
                c.execute('DELETE FROM '+table)
            for name, role in [('rok','teacher'),('ana','student'),('bor','student')]:
                c.execute('INSERT INTO users(name,password,role) VALUES (?,?,?)',(name,classroom.generate_password_hash('testpass123'),role))
            c.execute("INSERT INTO lessons(id,title,lesson_date,group_name,challenge_mode) VALUES (1,'Delilnik','2026-10-08','A','optional')")
            c.execute("INSERT INTO revisions VALUES (1,1,'Razmerje uporov','Delilnik','Pomagaj','gpt-4.1-mini',60)")
        classroom.init_db()
        self.client=classroom.app.test_client()
        self.ana=self.login('ana');self.bor=self.login('bor')

    def login(self,name):
        r=self.client.post('/api/login',json={'username':name,'password':'testpass123'})
        return {'Authorization':'Bearer '+r.json['token']}

    def teacher(self):
        self.client.post('/login',data={'username':'rok','password':'testpass123'})
        return self.client.get_cookie('teacher_session').value

    def post(self,path,data,headers=None):
        return self.client.post(path,json=data,headers=headers or self.ana)

    def test_help_auth_idempotency_feedback(self):
        data={'lesson_id':1,'request_id':'help-request-00001','reason':'Potrebujem učitelja','snapshot':{'components':[]}}
        self.assertEqual(self.client.post('/api/help',json=data).status_code,401)
        self.assertEqual(self.post('/api/help',data).status_code,200)
        self.assertEqual(self.post('/api/help',data).status_code,200)
        self.assertEqual(self.post('/api/help',dict(data,reason='Drug razlog')).status_code,409)
        with classroom.db() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM help_requests').fetchone()[0],1)
            aid=c.execute('SELECT id FROM teacher_alerts').fetchone()[0]
        self.assertEqual(self.client.get('/help/1/snapshot').status_code,302)
        csrf=self.teacher()
        self.assertEqual(self.client.get('/help/1/snapshot').status_code,200)
        route='/teacher-alerts/%s/feedback'%aid
        self.assertEqual(self.client.post(route,data={'feedback':'needed'}).status_code,403)
        self.assertEqual(self.client.post(route,data={'csrf':csrf,'feedback':'false_alarm','note':'Preverjeno'}).status_code,302)
        with classroom.db() as c:
            self.assertEqual(c.execute('SELECT status FROM teacher_alerts').fetchone()[0],'resolved')
            self.assertEqual(c.execute('SELECT count(*) FROM alert_feedback').fetchone()[0],1)

    def test_challenge_steps_isolation_retry_profile(self):
        start=self.post('/api/challenge/start',{'lesson_id':1,'snapshot':{'file_name':'original.sim1'}})
        self.assertEqual(start.status_code,200)
        cid=start.json['id']
        self.assertEqual(self.post('/api/challenge/start',{'lesson_id':1}).json['id'],cid)
        data={'challenge_id':cid,'step':0,'answer':'Naraste'}
        self.assertEqual(self.post('/api/challenge/answer',data,self.bor).status_code,404)
        self.assertEqual(self.post('/api/challenge/answer',dict(data,step=2)).status_code,400)
        self.assertEqual(self.post('/api/challenge/hint',{'challenge_id':cid,'step':1}).status_code,409)
        self.assertIn('hint',self.post('/api/challenge/hint',{'challenge_id':cid,'step':0}).json)
        self.assertEqual(self.post('/api/challenge/answer',data).json['points'],10)
        self.assertEqual(self.post('/api/challenge/answer',data).json['points'],10)
        r=self.post('/api/challenge/answer',{'challenge_id':cid,'step':1,'answer':'3,75 V; spodnji upor predstavlja večji delež.'})
        self.assertEqual(r.status_code,200)
        r=self.post('/api/challenge/answer',{'challenge_id':cid,'step':2,'answer':'1'})
        self.assertTrue(r.json['completed'])
        self.assertEqual(r.json['points'],30)
        self.assertEqual(self.post('/api/challenge/start',{'lesson_id':1}).json['id'],cid)
        repeat=self.post('/api/challenge/start',{'lesson_id':1,'retry':True})
        self.assertNotEqual(repeat.json['id'],cid)
        self.assertEqual(repeat.json['attempt'],2)
        csrf=self.teacher()
        self.assertEqual(self.client.get('/student/2/profile').status_code,200)
        form={'concept':'Vpliv razmerja uporov','status':'independent','note':'Samostojno pojasnil v živo.'}
        self.assertEqual(self.client.post('/student/2/profile',data=form).status_code,403)
        self.assertEqual(self.client.post('/student/2/profile',data=dict(form,csrf=csrf)).status_code,302)
        with classroom.db() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM profile_overrides').fetchone()[0],1)
        with classroom.db() as c: c.execute('UPDATE lessons SET active=0')
        self.assertEqual(self.post('/api/challenge/answer',{'challenge_id':repeat.json['id'],'step':0,'answer':'Naraste'}).status_code,403)

    def test_summary_csrf_persistence_and_no_cross_lesson(self):
        with classroom.db() as c:
            c.execute("INSERT INTO exchanges(id,request_id,user_id,lesson_id,version,created,question,snapshot,status,answer) VALUES (1,'summary-test-00001',2,1,1,1,'Ne razumem delilnika','{}','complete','Preveriva korak.')")
        csrf=self.teacher()
        self.assertEqual(self.client.post('/lesson/1/summary').status_code,403)
        def model(payload,**kwargs):
            self.assertIn('Ne razumem delilnika',payload['input'][0]['content'])
            return json.dumps({'overview':'Pregled ure','findings':[{'text':'Ana potrebuje razlago.','exchange_ids':[1]}]}),{}
        with patch('app.model_answer',side_effect=model):
            self.assertEqual(self.client.post('/lesson/1/summary',data={'csrf':csrf}).status_code,302)
        with classroom.db() as c:
            result=json.loads(c.execute('SELECT body FROM lesson_summaries').fetchone()[0])
            self.assertEqual(result['status'],'generated')
            self.assertEqual(result['coverage']['exchange_ids'],[1])
        self.assertEqual(self.client.get('/lesson/1').status_code,200)

if __name__ == '__main__': unittest.main()
