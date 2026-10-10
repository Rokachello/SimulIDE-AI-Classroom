# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
import os
import tempfile
import time
import unittest
os.environ.setdefault('SIMULIDE_DATA', tempfile.mkdtemp(prefix='simulide-quizzes-'))
import app as classroom
import quizzes

CIRCUIT='<circuit version="2.0"><item itemtype="Resistor" objectName="Resistor-1" /></circuit>'
QUESTIONS=[{'kind':'choice','prompt':'Napetost?','options':['3 V','5 V'],'answer':0,'points':2},
           {'kind':'number','prompt':'Izračunaj.','answer':3.75,'tolerance':0.02,'points':3},
           {'kind':'text','prompt':'Pojasni razmerje.','points':5}]

class QuizTest(unittest.TestCase):
    def setUp(self):
        classroom.init_db()
        with classroom.db() as c:
            for table in ['quiz_grades','quiz_attempts','assignment_submissions','quiz_versions','alert_feedback','help_requests','challenges','lesson_summaries','profile_overrides','teacher_alerts','exchanges','knowledge_docs','prompt_versions','revisions','lessons','sessions','attempts','users']:
                c.execute('DELETE FROM '+table)
            for name,role in [('rok','teacher'),('ana','student'),('bor','student')]:
                c.execute('INSERT INTO users(name,password,role) VALUES (?,?,?)',(name,classroom.generate_password_hash('testpass123'),role))
            for lid in (1,2):
                c.execute("INSERT INTO lessons(id,title,lesson_date,group_name) VALUES (?,'Vaja','2026-10-09','A')",(lid,))
                c.execute("INSERT INTO revisions VALUES (?,1,'Razmerje uporov','Delilnik','Pomagaj','gpt-4.1-mini',60)",(lid,))
        self.client=classroom.app.test_client()
        self.ana=self.login('ana');self.bor=self.login('bor')
        self.client.post('/login',data={'username':'rok','password':'testpass123'})
        self.csrf=self.client.get_cookie('teacher_session').value

    def login(self,name):
        r=self.client.post('/api/login',json={'username':name,'password':'testpass123'})
        return {'Authorization':'Bearer '+r.json['token']}

    def post(self,path,data,headers=None):
        return self.client.post(path,json=data,headers=headers or self.ana)

    def publish(self,questions=QUESTIONS,published=True,circuit=CIRCUIT):
        form={'csrf':self.csrf,'title':'Končni kviz','questions_json':json.dumps(questions)}
        if published: form['published']='on'
        if circuit: form['circuit_file']=(io.BytesIO(circuit.encode()),'primer.sim2')
        r=self.client.post('/lesson/1/quiz',data=form)
        self.assertEqual(r.status_code,302,r.data)
        with classroom.db() as c: return c.execute('SELECT max(id) FROM quiz_versions').fetchone()[0]

    def test_editor_draft_publish_preview_and_navigation(self):
        page=self.client.get('/lesson/1/quiz').text
        for caption in ['Priprava kviza','Oddaje in rezultati','Povzetek ure','Shrani osnutek','Objavi študentom','quizPreview']:
            self.assertIn(caption,page)
        form={'csrf':self.csrf,'title':'Kviz','questions_json':json.dumps(QUESTIONS),'action':'draft','published':'on'}
        self.assertEqual(self.client.post('/lesson/1/quiz',data=form).status_code,302)
        self.assertFalse(self.post('/api/work/current',{'lesson_id':1}).json['quiz_available'])
        form['action']='publish'
        self.assertEqual(self.client.post('/lesson/1/quiz',data=form).status_code,302)
        self.assertTrue(self.post('/api/work/current',{'lesson_id':1}).json['quiz_available'])
        self.assertIn('Kviz je objavljen',self.client.get('/lesson/1/quiz?saved=1').text)
        self.assertIn('Ustvari nov povzetek',self.client.get('/lesson/1?view=summary').text)
        self.assertNotIn('Ustvari nov povzetek',self.client.get('/lesson/1').text)

    def test_published_revision_pinned_answers_hidden_and_global_lock(self):
        first=self.publish()
        current=self.post('/api/work/current',{'lesson_id':1}).json
        self.assertTrue(current['quiz_available']);self.assertFalse(current['quiz_locked'])
        self.assertNotIn('answer',json.dumps(current['questions']));self.assertNotIn('tolerance',json.dumps(current['questions']))
        with classroom.db() as c:
            c.execute("INSERT INTO exchanges(request_id,user_id,lesson_id,version,created,question,snapshot,status,answer) VALUES ('old-quiz-answer-00001',2,1,1,1,'Pomagaj','{}','complete','Prejšnja pomoč')")
        self.assertEqual(len(self.post('/api/select',{'lesson_id':1}).json['history']),1)
        start=self.post('/api/quiz/start',{'lesson_id':1});self.assertEqual(start.status_code,200)
        self.assertEqual(self.post('/api/select',{'lesson_id':1}).json['history'],[])
        aid=start.json['attempt_id']
        self.assertEqual(self.post('/api/quiz/start',{'lesson_id':1}).json['attempt_id'],aid)
        other=self.post('/api/work/current',{'lesson_id':2}).json
        self.assertTrue(other['quiz_locked']);self.assertEqual(other['attempt_id'],aid);self.assertEqual(other['lesson_id'],1)
        self.assertEqual(self.post('/api/quiz/start',{'lesson_id':2}).status_code,423)
        for lid in (1,2):
            blocked=self.post('/api/chat',{'lesson_id':lid,'request_id':'blocked-quiz-chat-01','question':'Poračunaj mi kviz','snapshot':{}})
            self.assertEqual(blocked.status_code,423)
            self.assertIn('zaklenjena',blocked.json['error'])
        self.assertEqual(self.post('/api/challenge/hint',{'challenge_id':1,'step':0}).status_code,423)
        with classroom.app.test_request_context():
            with classroom.db() as c:
                from werkzeug.exceptions import Locked
                with self.assertRaises(Locked): quizzes.guard_locked(c,2)
                quizzes.guard_locked(c,3)
        self.publish([dict(QUESTIONS[0],answer=1)])
        self.assertEqual(self.post('/api/work/current',{'lesson_id':1}).json['quiz_id'],first)
        r=self.post('/api/quiz/finish',{'attempt_id':aid,'answers':[0,'3,76','Razmerje med uporoma določi napetost.'],'circuit':CIRCUIT,'snapshot':{'components':[]}})
        self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.json['score'],5);self.assertTrue(r.json['pending_review'])
        with classroom.db() as c:
            saved=dict(c.execute('SELECT * FROM quiz_attempts WHERE id=?',(aid,)).fetchone())
        again=self.post('/api/quiz/finish',{'attempt_id':aid,'answers':[1,'999','Drugo'],'circuit':'broken'})
        self.assertEqual(again.status_code,200)
        with classroom.db() as c: self.assertEqual(dict(c.execute('SELECT * FROM quiz_attempts WHERE id=?',(aid,)).fetchone()),saved)
        self.assertFalse(self.post('/api/work/current',{'lesson_id':1}).json['quiz_locked'])

    def test_submission_immutable_isolation_xml_and_teacher_access(self):
        data={'lesson_id':1,'request_id':'immutable-submit-001','circuit':CIRCUIT,'snapshot':{'components':[]},'comment':'Meritev se ujema.'}
        r=self.post('/api/work/submit',data);self.assertEqual(r.status_code,200);sid=r.json['submission_id']
        self.assertEqual(self.post('/api/work/submit',data).json['submission_id'],sid)
        self.assertEqual(self.post('/api/work/submit',dict(data,comment='Novo')).status_code,409)
        self.assertEqual(self.post('/api/work/submit',dict(data,request_id='bad-xml-submit-001',circuit='<other/>')).status_code,400)
        self.assertEqual(self.post('/api/work/submit',dict(data,request_id='bad-xml-submit-001',circuit='<!DOCTYPE circuit [<!ENTITY x "ha">]><circuit/>')).status_code,400)
        self.assertEqual(self.post('/api/work/submit',dict(data,request_id='huge-submit-00001',circuit='<circuit>'+' '*quizzes.MAX_CIRCUIT+'</circuit>')).status_code,400)
        self.assertEqual(self.client.get('/submission/%s/circuit'%sid).data.decode(),CIRCUIT)
        self.client.delete_cookie('teacher_session')
        self.assertEqual(self.client.get('/submission/%s/circuit'%sid).status_code,302)
        self.assertFalse(self.post('/api/work/current',{'lesson_id':1},self.bor).json['submitted'])

    def test_draft_csrf_bad_question_upload_and_pending_chat(self):
        self.assertEqual(self.client.post('/lesson/1/quiz',data={'title':'x','questions_json':json.dumps(QUESTIONS)}).status_code,403)
        self.publish(published=False)
        self.assertFalse(self.post('/api/work/current',{'lesson_id':1}).json['quiz_available'])
        self.assertEqual(self.post('/api/quiz/start',{'lesson_id':1}).status_code,403)
        bad=dict(QUESTIONS[1],answer=float('inf'))
        self.assertEqual(self.client.post('/lesson/1/quiz',data={'csrf':self.csrf,'title':'x','questions_json':json.dumps([bad])}).status_code,400)
        self.publish()
        with classroom.db() as c:
            c.execute("INSERT INTO exchanges(request_id,user_id,lesson_id,version,created,question,snapshot,status) VALUES ('pending-quiz-00001',2,1,1,?,'Vprašanje','{}','pending')",(time.time(),))
        self.assertEqual(self.post('/api/quiz/start',{'lesson_id':1}).status_code,409)
        with classroom.db() as c: c.execute('UPDATE exchanges SET created=1')
        self.assertEqual(self.post('/api/quiz/start',{'lesson_id':1}).status_code,200)
        self.assertEqual(self.client.get('/lesson/1/quiz').status_code,200)
        self.assertEqual(self.client.get('/lesson/1/work').status_code,200)

    def test_manual_grade_unlock_ownership_and_finish_closed_lesson(self):
        self.publish();aid=self.post('/api/quiz/start',{'lesson_id':1}).json['attempt_id']
        self.assertEqual(self.post('/api/quiz/circuit',{'lesson_id':1,'attempt_id':aid},self.bor).status_code,404)
        self.assertEqual(self.post('/api/quiz/circuit',{'lesson_id':1,'attempt_id':aid}).json['circuit'],CIRCUIT)
        self.assertEqual(self.post('/api/quiz/finish',{'attempt_id':aid,'answers':[0,'nan','x']}).status_code,400)
        self.assertEqual(self.post('/api/quiz/finish',{'attempt_id':{}}).status_code,400)
        self.assertEqual(self.post('/api/quiz/circuit',{'attempt_id':[],'lesson_id':1}).status_code,400)
        with classroom.db() as c: c.execute('UPDATE lessons SET active=0 WHERE id=1')
        result=self.post('/api/quiz/finish',{'attempt_id':aid,'answers':[0,'3.75','Razmerje.'],'circuit':CIRCUIT})
        self.assertEqual(result.status_code,200)
        path='/quiz-attempt/%s/grade'%aid
        self.assertEqual(self.client.post(path,data={'question_index':2,'points':4}).status_code,403)
        self.assertEqual(self.client.post(path,data={'csrf':self.csrf,'question_index':2,'points':6}).status_code,400)
        self.assertEqual(self.client.post(path,data={'csrf':self.csrf,'question_index':2,'points':4,'note':'Dobro.'}).status_code,302)
        result=self.post('/api/quiz/finish',{'attempt_id':aid}).json
        self.assertEqual(result['score'],9);self.assertFalse(result['pending_review'])
        with classroom.db() as c:
            c.execute('UPDATE lessons SET active=1 WHERE id=1')
        self.publish();aid2=self.post('/api/quiz/start',{'lesson_id':1}).json['attempt_id']
        path='/quiz-attempt/%s/unlock'%aid2
        self.assertEqual(self.client.post(path,data={}).status_code,403)
        self.assertEqual(self.client.post(path,data={'csrf':self.csrf}).status_code,302)
        self.assertEqual(self.post('/api/quiz/finish',{'attempt_id':aid2}).status_code,409)
        self.assertFalse(self.post('/api/work/current',{'lesson_id':1}).json['quiz_locked'])

if __name__=='__main__': unittest.main()
