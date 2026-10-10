"""Run with test-built SimulIDE binary as the sole argument. No API key or external calls."""
import os,sys,tempfile,subprocess,time,json
from pathlib import Path
def main():
    binary=str(Path(sys.argv[1]).resolve())
    data=tempfile.mkdtemp(prefix='simulide-native-')
    os.environ['SIMULIDE_DATA']=data;os.environ['SIMULIDE_DEMO']='1'
    from app import db,generate_password_hash
    with db() as c:
     for name,role in [('testteacher','teacher'),('teststudent','student')]: c.execute('INSERT INTO users(name,password,role) VALUES (?,?,?)',(name,generate_password_hash('testpass123'),role))
     c.execute("INSERT INTO lessons(title,lesson_date,group_name) VALUES ('Testna ura','2026-10-08','Test')")
     c.execute("UPDATE lessons SET challenge_mode='optional' WHERE id=1")
     c.execute("INSERT INTO revisions VALUES (1,1,'Ohmov zakon','Preveri vezje','Ponudi namig','gpt-4.1-mini',60)")
    server=subprocess.Popen([sys.executable,'app.py','serve'],cwd=Path(__file__).parent)
    try:
     import requests
     for _ in range(100):
      try:
       if requests.get('http://127.0.0.1:8765/health',timeout=1).status_code==200: break
      except requests.RequestException: time.sleep(.05)
     else: raise RuntimeError('Server not ready')
     env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_DATA_HOME=data+'/qt-data',XDG_CONFIG_HOME=data+'/qt-config',SIMULIDE_LEARNING_TEST='1',SIMULIDE_TEST_ORIGINAL=data+'/original.sim2')
     result=subprocess.run([binary,'-ai-classroom-test'],env=env,timeout=45)
     if result.returncode: raise RuntimeError('Native UI test failed')
     with db() as c:
      row=c.execute('SELECT * FROM exchanges').fetchone()
      assert row['status']=='complete' and row['lesson_id']==1 and row['version']==1
      assert any('ClassroomV' in str(x) for x in json.loads(row['snapshot'])['components'])
      print('PASS: actual native snapshot saved on server with student, lesson and prompt revision')
      assert c.execute('SELECT COUNT(*) FROM teacher_alerts').fetchone()[0]>=1
      print('PASS: native help created teacher alert')
      state=json.loads(c.execute('SELECT state FROM challenges ORDER BY id DESC LIMIT 1').fetchone()[0])
      assert state['status']=='completed' and len(state['answers'])==3 and state['points']==30
      assert Path(data+'/original.sim2').is_file()
      assert len(list(Path(data).glob('original-izziv-*.sim2')))==1
      print('PASS: native challenge completed all three steps; original and experiment files saved')
    finally:
     server.terminate();server.wait(timeout=5)

if __name__=='__main__': main()
