"""Full native submission/quiz/restart test, no OpenAI calls. Pass test-built binary."""
import os,sys,tempfile,subprocess,time,json
from pathlib import Path
def main():
    binary=str(Path(sys.argv[1]).resolve()); data=tempfile.mkdtemp(prefix='simulide-quiz-native-')
    os.environ['SIMULIDE_DATA']=data; os.environ['SIMULIDE_DEMO']='1'
    from app import db,generate_password_hash
    circuit='<circuit version="2.0.0-" rev="0" stepSize="1000000" stepsPS="1000000" NLsteps="100" reaStep="10000000" animate="0" anicurr="0" ansi="0" width="1700" height="1000"></circuit>'
    questions=[dict(kind='choice',prompt='Kaj meri voltmeter?',options=['Tok','Napetost','Upornost'],answer=1,points=2),dict(kind='number',prompt='Napetost v voltih?',answer=3,tolerance=.05,points=3),dict(kind='text',prompt='Pojasni vpliv razmerja uporov.',points=5)]
    with db() as c:
        for name,role in [('testteacher','teacher'),('teststudent','student')]: c.execute('INSERT INTO users(name,password,role) VALUES (?,?,?)',(name,generate_password_hash('testpass123'),role))
        c.execute("INSERT INTO lessons(title,lesson_date,group_name) VALUES ('Kvizna ura','2026-10-09','Test')")
        c.execute("INSERT INTO revisions VALUES (1,1,'Razmerje uporov','Delilnik','Pomagaj','gpt-4.1-mini',60)")
        c.execute('INSERT INTO quiz_versions(lesson_id,published,title,questions,circuit,created) VALUES (1,1,?,?,?,?)',('Testni končni kviz',json.dumps(questions),circuit,time.time()))
    server=subprocess.Popen([sys.executable,'app.py','serve'],cwd=Path(__file__).parent)
    try:
        import requests
        for _ in range(100):
            try:
                if requests.get('http://127.0.0.1:8765/health',timeout=1).status_code==200: break
            except requests.RequestException: time.sleep(.05)
        else: raise RuntimeError('Server not ready')
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_DATA_HOME=data+'/qt-data',XDG_CONFIG_HOME=data+'/qt-config',SIMULIDE_QUIZ_BACKUP=data+'/original.sim2')
        subprocess.run([binary,'-ai-quiz-test'],env=env,check=True,timeout=45)
        with db() as c:
            sub=c.execute('SELECT * FROM assignment_submissions').fetchone();assert sub and 'QuizOriginal' in sub['circuit']
            a=c.execute('SELECT * FROM quiz_attempts').fetchone();assert a['status']=='active'
        assert Path(data+'/original.sim2').is_file() and len(list(Path(data).glob('kviz-*.sim2')))==1
        auth={'Authorization':'Bearer '+requests.post('http://127.0.0.1:8765/api/login',json={'username':'teststudent','password':'testpass123'}).json()['token']}
        blocked=requests.post('http://127.0.0.1:8765/api/chat',headers=auth,json={'lesson_id':1,'request_id':'native-quiz-blocked-0001','question':'Pomagaj','snapshot':{}})
        assert blocked.status_code==423,blocked.text
        subprocess.run([binary,'-ai-quiz-test'],env=dict(env,SIMULIDE_QUIZ_RESUME='1'),check=True,timeout=45)
        with db() as c:
            a=c.execute('SELECT * FROM quiz_attempts').fetchone();assert a['status']=='complete'
            results=json.loads(a['results']);assert results[0]['points']==2 and results[1]['points']==3 and results[2]['pending_review']
            assert c.execute('SELECT COUNT(*) FROM exchanges').fetchone()[0]==0
        teacher=requests.Session(); teacher.post('http://127.0.0.1:8765/login',data={'username':'testteacher','password':'testpass123'})
        page=teacher.get('http://127.0.0.1:8765/lesson/1/work');assert page.status_code==200 and 'Oddaja iz' in page.text
        saved=teacher.get('http://127.0.0.1:8765/submission/1/circuit');assert saved.text==sub['circuit']
        csrf=teacher.cookies.get('teacher_session')
        grade=teacher.post('http://127.0.0.1:8765/quiz-attempt/1/grade',data={'csrf':csrf,'question_index':2,'points':4,'note':'Dobra razlaga.'});assert grade.status_code==200
        with db() as c:
            assert json.loads(c.execute('SELECT results FROM quiz_attempts').fetchone()[0])[2]['points']==4
        print('PASS: native assignment, circuit copy, persistent global tutor lock, restart/resume, finish, teacher download and text grading')
    finally: server.terminate();server.wait(timeout=5)
if __name__=='__main__':main()
