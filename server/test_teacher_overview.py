import json,unittest
import test_quizzes as quiz_tests
import app as classroom

class OverviewTest(unittest.TestCase):
 setUp=quiz_tests.QuizTest.setUp
 login=quiz_tests.QuizTest.login
 publish=quiz_tests.QuizTest.publish
 post=quiz_tests.QuizTest.post

 def test_copy_is_private_preparation_without_student_results(self):
  self.publish()
  with classroom.db() as c:
   c.execute("INSERT INTO knowledge_docs(title,body,source,lesson_id,active,created) VALUES ('Naša vaja','Dolga navodila za preizkus kopiranja.','učitelj',1,1,1)")
   c.execute("INSERT INTO exchanges(request_id,user_id,lesson_id,version,created,question,snapshot,status) VALUES ('old-copy-evidence',2,1,1,1,'Pomagaj','{}','complete')")
  r=self.client.post('/lesson/1/copy',data={'csrf':self.csrf})
  self.assertEqual(r.status_code,302)
  with classroom.db() as c:
   l=c.execute('SELECT * FROM lessons ORDER BY id DESC LIMIT 1').fetchone();new=l['id']
   self.assertFalse(l['active']);self.assertEqual(l['lesson_date'],'')
   self.assertEqual(c.execute('SELECT count(*) FROM exchanges WHERE lesson_id=?',(new,)).fetchone()[0],0)
   self.assertEqual(c.execute('SELECT count(*) FROM knowledge_docs WHERE lesson_id=?',(new,)).fetchone()[0],1)
   self.assertFalse(c.execute('SELECT published FROM quiz_versions WHERE lesson_id=?',(new,)).fetchone()[0])
   self.assertEqual(c.execute('SELECT count(*) FROM exchanges WHERE lesson_id=1').fetchone()[0],1)
  self.assertIn('Priprava je kopirana',self.client.get(r.location).text)

 def test_overview_reports_actual_activity_and_state(self):
  self.publish()
  self.post('/api/quiz/start',{'lesson_id':1})
  page=self.client.get('/lesson/1/overview')
  self.assertEqual(page.status_code,200)
  for text in ['Pregled ure','Kopiraj za novo izvedbo']:
   self.assertIn(text,page.text)
  self.assertIn('ana',page.text);self.assertIn('Rešuje',page.text)
  self.assertNotIn('bor</a>',page.text)
  self.assertIn('To ni seznam trenutno prijavljenih',page.text)
  self.assertEqual(self.client.post('/lesson/1/state',data={'csrf':self.csrf,'active':'0'}).status_code,302)
  with classroom.db() as c:self.assertFalse(c.execute('SELECT active FROM lessons WHERE id=1').fetchone()[0])
  self.assertIn('Rešuje',self.client.get('/lesson/1/activity').text)
  self.assertEqual(self.client.post('/lesson/1/state',data={'active':'1'}).status_code,403)
  self.assertEqual(classroom.app.test_client().get('/lesson/1/overview').status_code,302)

 def test_browser_errors_are_readable_and_api_errors_stay_json(self):
  r=self.client.post('/lessons',data={'csrf':self.csrf,'title':''},headers={'Accept':'text/html'})
  self.assertEqual(r.status_code,400);self.assertIn('Nazaj na prejšnjo stran',r.text);self.assertIn('Vnesi naslov',r.text)
  r=self.post('/api/quiz/start',{'lesson_id':999})
  self.assertEqual(r.status_code,404);self.assertIn('error',r.json)

if __name__=='__main__':unittest.main()
