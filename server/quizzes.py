# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned teacher quizzes and immutable circuit submissions."""
import json
import math
import re
import time
import xml.etree.ElementTree as ET
from flask import abort, jsonify, redirect, render_template, request

MAX_CIRCUIT = 2 * 1024 * 1024


def migrate(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS quiz_versions(id INTEGER PRIMARY KEY, lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE, published INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL, questions TEXT NOT NULL, circuit TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS quiz_attempts(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE, quiz_id INTEGER NOT NULL REFERENCES quiz_versions(id) ON DELETE CASCADE, status TEXT NOT NULL DEFAULT 'active', answers TEXT NOT NULL DEFAULT '[]', results TEXT NOT NULL DEFAULT '[]', circuit TEXT NOT NULL DEFAULT '', snapshot TEXT NOT NULL DEFAULT '{}', created REAL NOT NULL, finished REAL);
    CREATE UNIQUE INDEX IF NOT EXISTS quiz_one_active ON quiz_attempts(user_id) WHERE status='active';
    CREATE TABLE IF NOT EXISTS assignment_submissions(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE, request_id TEXT NOT NULL, circuit TEXT NOT NULL, snapshot TEXT NOT NULL, comment TEXT NOT NULL, created REAL NOT NULL, UNIQUE(user_id,request_id));
    CREATE TABLE IF NOT EXISTS quiz_grades(id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE, question_index INTEGER NOT NULL, teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, points REAL NOT NULL, note TEXT NOT NULL, created REAL NOT NULL);
    ''')


def active_attempt(c, user_id):
    return c.execute("SELECT * FROM quiz_attempts WHERE user_id=? AND status='active'", (user_id,)).fetchone()


def guard_locked(c, user_id):
    if active_attempt(c, user_id):
        abort(423, 'Med kvizom je pomoč asistenta zaklenjena. Najprej oddaj kviz ali prosi učitelja, da prekine poskus.')


def circuit_xml(value, required=False):
    try: size = len(value.encode('utf-8')) if isinstance(value,str) else MAX_CIRCUIT+1
    except UnicodeEncodeError: abort(400, 'Vezje mora biti zapisano v UTF-8.')
    if size > MAX_CIRCUIT:
        abort(400, 'Vezje mora biti datoteka SimulIDE do 2 MB.')
    if not value.strip():
        if required: abort(400, 'Manjka vezje za oddajo.')
        return ''
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', value, re.I):
        abort(400, 'Deklaracije DTD in entitet v vezju niso dovoljene.')
    try:
        root = ET.fromstring(value)
    except (ET.ParseError, ValueError):
        abort(400, 'Vezje ni veljaven XML SimulIDE.')
    if root.tag != 'circuit': abort(400, 'Datoteka nima korenskega elementa circuit.')
    return value


def finite_number(value):
    try: return type(value) in (int,float) and math.isfinite(value)
    except (OverflowError, ValueError): return False


def validate_questions(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 30:
        abort(400, 'Kviz mora imeti od 1 do 30 vprašanj.')
    out = []
    for item in raw:
        if not isinstance(item, dict): abort(400, 'Neveljavno vprašanje.')
        kind = item.get('kind'); prompt = item.get('prompt'); points = item.get('points', 1)
        if kind not in {'choice', 'number', 'text'} or not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 3000:
            abort(400, 'Vprašanje potrebuje vrsto in kratko besedilo.')
        if type(points) is not int or not 1 <= points <= 100: abort(400, 'Točke morajo biti celo število od 1 do 100.')
        q = dict(kind=kind, prompt=prompt.strip(), points=points)
        if kind == 'choice':
            options = item.get('options'); answer = item.get('answer')
            if not isinstance(options, list) or not 2 <= len(options) <= 8 or any(not isinstance(s, str) or not s.strip() or len(s) > 1000 for s in options):
                abort(400, 'Izbirno vprašanje potrebuje od 2 do 8 možnosti.')
            if type(answer) is not int or not 0 <= answer < len(options): abort(400, 'Izberi pravilen odgovor.')
            q.update(options=options, answer=answer)
        elif kind == 'number':
            answer = item.get('answer'); tolerance = item.get('tolerance', 0)
            if not finite_number(answer) or not finite_number(tolerance) or tolerance < 0:
                abort(400, 'Številčni odgovor in nenegativna toleranca morata biti končni števili.')
            q.update(answer=answer, tolerance=tolerance)
        out.append(q)
    return out


def public_questions(raw):
    return [{k: q[k] for k in ('kind', 'prompt', 'points', 'options') if k in q} for q in raw]


def grade_answers(questions, answers):
    if not isinstance(answers, list) or len(answers) != len(questions): abort(400, 'Odgovori na vsa vprašanja.')
    results = []
    for q, a in zip(questions, answers):
        if q['kind'] == 'choice':
            if type(a) is not int or not 0 <= a < len(q['options']): abort(400, 'Izberi eno možnost pri vsakem izbirnem vprašanju.')
            correct = a == q['answer']
        else:
            if not isinstance(a, str) or not a.strip() or len(a) > 4000: abort(400, 'Vnesi kratek odgovor na vsako vprašanje.')
            if q['kind'] == 'text':
                results.append(dict(points=None, max_points=q['points'], pending_review=True)); continue
            try:
                number = float(a.strip().replace(',', '.'))
            except ValueError:
                abort(400, 'Številčni odgovor vnesi kot število brez enote.')
            if not math.isfinite(number): abort(400, 'Številčni odgovor ni veljaven.')
            correct = abs(number - q['answer']) <= q['tolerance'] + 1e-12 * max(1, abs(q['answer']))
        results.append(dict(points=q['points'] if correct else 0, max_points=q['points'], pending_review=False))
    return results


def totals(results):
    return dict(score=sum(r['points'] or 0 for r in results), max_score=sum(r['max_points'] for r in results), pending_review=any(r['pending_review'] for r in results))


def register(app, db, api_auth, teacher, json_payload):
    def identifier(value):
        if type(value) is not int or value<=0: abort(400, 'Neveljavna oznaka.')
        return value

    def lesson(c, lid, active=False):
        if type(lid) is not int: abort(400, 'Neveljavna oznaka ure.')
        row = c.execute('SELECT * FROM lessons WHERE id=?', (lid,)).fetchone()
        if not row: abort(404, 'Ura ne obstaja.')
        if active and not row['active']: abort(403, 'Ura je zaključena.')
        return row

    def snap(d):
        value = d.get('snapshot', {})
        if not isinstance(value, dict) or len(json.dumps(value).encode()) > 512000: abort(400, 'Neveljaven ali prevelik posnetek.')
        return json.dumps(value, ensure_ascii=False)

    def latest(c, lid):
        return c.execute('SELECT * FROM quiz_versions WHERE lesson_id=? ORDER BY id DESC LIMIT 1', (lid,)).fetchone()

    def active(c, uid):
        return c.execute("SELECT * FROM quiz_attempts WHERE user_id=? AND status='active'", (uid,)).fetchone()

    def state(c, uid, lid):
        l = lesson(c, lid); q = latest(c, lid); lock = active(c, uid)
        a = lock
        if a: q = c.execute('SELECT * FROM quiz_versions WHERE id=?', (a['quiz_id'],)).fetchone()
        elif q: a = c.execute("SELECT * FROM quiz_attempts WHERE user_id=? AND quiz_id=? AND status='complete' ORDER BY id DESC LIMIT 1", (uid, q['id'])).fetchone()
        available = bool(q and (q['published'] or (a and a['status'] == 'active')))
        result = dict(lesson_id=lock['lesson_id'] if lock else lid, quiz_available=available, quiz_title=q['title'] if available else '', quiz_id=q['id'] if available else None,
                      quiz_locked=bool(lock), locked_lesson_id=lock['lesson_id'] if lock else None, attempt_id=a['id'] if a else None,
                      questions=public_questions(json.loads(q['questions'])) if available else [], completed=bool(a and a['status']=='complete'),
                      submitted=bool(c.execute('SELECT id FROM assignment_submissions WHERE user_id=? AND lesson_id=? LIMIT 1', (uid,lid)).fetchone()),
                      has_circuit=bool(q and q['circuit'] and available), lesson_active=bool(l['active']))
        if a and a['status'] == 'complete': result.update(totals(json.loads(a['results'])))
        return result

    def download(raw, filename):
        return app.response_class(raw, mimetype='application/xml', headers={'Content-Disposition': 'attachment; filename="'+filename+'"'})

    @app.route('/lesson/<int:lid>/quiz', methods=['GET','POST'])
    @teacher
    def quiz_editor(u, t, lid):
        with db() as c:
            l=lesson(c,lid)
            if request.method == 'POST':
                title=request.form.get('title','').strip()
                if not 1<=len(title)<=200: abort(400,'Vnesi naslov kviza do 200 znakov.')
                raw=request.form.get('questions_json','')
                if len(raw)>150000: abort(400,'Kviz je prevelik.')
                try: questions=validate_questions(json.loads(raw))
                except (json.JSONDecodeError, ValueError): abort(400,'Vprašanja niso veljaven JSON.')
                old=latest(c,lid); circuit=old['circuit'] if old and request.form.get('keep_circuit','1')=='1' else ''
                upload=request.files.get('circuit_file')
                if upload and upload.filename:
                    if not upload.filename.lower().endswith('.sim2'): abort(400,'Priloži vezje .sim2.')
                    data=upload.read(MAX_CIRCUIT+1)
                    if len(data)>MAX_CIRCUIT: abort(400,'Vezje je preveliko.')
                    try: circuit=circuit_xml(data.decode('utf-8-sig'),True)
                    except UnicodeDecodeError: abort(400,'Vezje mora biti zapisano v UTF-8.')
                c.execute('INSERT INTO quiz_versions(lesson_id,published,title,questions,circuit,created) VALUES (?,?,?,?,?,?)',(lid,int(request.form.get('action')=='publish' if 'action' in request.form else request.form.get('published') in ('1','on','true')),title,json.dumps(questions,ensure_ascii=False),circuit,time.time()))
                return redirect('/lesson/%s/quiz?saved=1'%lid)
            row=latest(c,lid); q=dict(row) if row else None
            if q: q['questions']=json.loads(q['questions'])
            versions=[dict(r) for r in c.execute('SELECT id,title,published,created FROM quiz_versions WHERE lesson_id=? ORDER BY id DESC',(lid,))]
        return render_template('quiz_edit.html',csrf=t,lesson=l,quiz=q,versions=versions)

    @app.get('/lesson/<int:lid>/work')
    @teacher
    def work(u,t,lid):
        with db() as c:
            l=lesson(c,lid)
            submissions=[dict(r) for r in c.execute('SELECT s.*,u.name FROM assignment_submissions s JOIN users u ON u.id=s.user_id WHERE s.lesson_id=? ORDER BY s.created DESC',(lid,))]
            attempts=[dict(r) for r in c.execute('SELECT a.*,u.name,q.title,q.questions FROM quiz_attempts a JOIN users u ON u.id=a.user_id JOIN quiz_versions q ON q.id=a.quiz_id WHERE a.lesson_id=? ORDER BY a.created DESC',(lid,))]
            for a in attempts:
                for key in ('questions','answers','results'): a[key]=json.loads(a[key])
                a.update(totals(a['results']))
                if not a['results']: a['max_score']=sum(q['points'] for q in a['questions'])
                a['grades']=[dict(r) for r in c.execute('SELECT * FROM quiz_grades WHERE attempt_id=? ORDER BY id',(a['id'],))]
        return render_template('quiz_work.html',csrf=t,lesson=l,submissions=submissions,attempts=attempts)

    @app.get('/submission/<int:sid>/circuit')
    @teacher
    def submission_circuit(u,t,sid):
        with db() as c: row=c.execute('SELECT circuit FROM assignment_submissions WHERE id=?',(sid,)).fetchone()
        if not row: abort(404)
        return download(row['circuit'],'oddaja-%s.sim2'%sid)

    @app.get('/quiz-attempt/<int:aid>/circuit')
    @teacher
    def attempt_circuit(u,t,aid):
        with db() as c: row=c.execute('SELECT circuit FROM quiz_attempts WHERE id=?',(aid,)).fetchone()
        if not row or not row['circuit']: abort(404)
        return download(row['circuit'],'kviz-oddaja-%s.sim2'%aid)

    @app.get('/submission/<int:sid>/snapshot')
    @teacher
    def submission_snapshot(u,t,sid):
        with db() as c: row=c.execute('SELECT snapshot FROM assignment_submissions WHERE id=?',(sid,)).fetchone()
        if not row: abort(404)
        return app.response_class(row['snapshot'],mimetype='application/json')

    @app.get('/quiz-attempt/<int:aid>/snapshot')
    @teacher
    def attempt_snapshot(u,t,aid):
        with db() as c: row=c.execute('SELECT snapshot FROM quiz_attempts WHERE id=?',(aid,)).fetchone()
        if not row: abort(404)
        return app.response_class(row['snapshot'],mimetype='application/json')

    @app.get('/quiz/<int:qid>/circuit')
    @teacher
    def quiz_circuit(u,t,qid):
        with db() as c: row=c.execute('SELECT circuit FROM quiz_versions WHERE id=?',(qid,)).fetchone()
        if not row or not row['circuit']: abort(404)
        return download(row['circuit'],'kviz-%s.sim2'%qid)

    @app.post('/api/work/current')
    @api_auth
    def work_current(u):
        d=json_payload()
        with db() as c: return jsonify(state(c,u['id'],d.get('lesson_id')))

    @app.post('/api/work/submit')
    @api_auth
    def submit_work(u):
        d=json_payload(); rid=d.get('request_id'); comment=d.get('comment','')
        if not isinstance(rid,str) or not 16<=len(rid)<=100: abort(400,'Manjka oznaka oddaje.')
        if not isinstance(comment,str) or len(comment)>4000: abort(400,'Komentar naj ima največ 4000 znakov.')
        circuit=circuit_xml(d.get('circuit'),True); snapshot=snap(d); lid=d.get('lesson_id')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT * FROM assignment_submissions WHERE user_id=? AND request_id=?',(u['id'],rid)).fetchone()
            if old:
                if old['lesson_id']!=lid or old['comment']!=comment or old['circuit']!=circuit or old['snapshot']!=snapshot: abort(409,'Oznaka oddaje je že uporabljena za drugo oddajo.')
                return jsonify(message='Naloga je že oddana.',submission_id=old['id'],submitted=True)
            lesson(c,lid,True); guard_locked(c,u['id'])
            sid=c.execute('INSERT INTO assignment_submissions(user_id,lesson_id,request_id,circuit,snapshot,comment,created) VALUES (?,?,?,?,?,?,?)',(u['id'],lid,rid,circuit,snapshot,comment,time.time())).lastrowid
        return jsonify(message='Naloga in vezje sta shranjena pri učitelju.',submission_id=sid,submitted=True)

    @app.post('/api/quiz/start')
    @api_auth
    def start_quiz(u):
        d=json_payload(); lid=d.get('lesson_id')
        with db() as c:
            c.execute('BEGIN IMMEDIATE'); lesson(c,lid,True); old=active(c,u['id'])
            if old:
                if old['lesson_id']!=lid: abort(423,'Najprej dokončaj kviz pri drugi uri.')
                return jsonify(state(c,u['id'],lid))
            q=latest(c,lid)
            if not q or not q['published']: abort(403,'Učitelj še ni objavil kviza.')
            if c.execute("SELECT id FROM quiz_attempts WHERE user_id=? AND quiz_id=? AND status='complete'",(u['id'],q['id'])).fetchone(): return jsonify(state(c,u['id'],lid))
            if c.execute("SELECT id FROM exchanges WHERE user_id=? AND status IN ('pending','running') AND created>? LIMIT 1",(u['id'],time.time()-180)).fetchone(): abort(409,'Počakaj, da asistent konča odgovor, in nato začni kviz.')
            c.execute('INSERT INTO quiz_attempts(user_id,lesson_id,quiz_id,created) VALUES (?,?,?,?)',(u['id'],lid,q['id'],time.time()))
            return jsonify(state(c,u['id'],lid))

    @app.post('/api/quiz/circuit')
    @api_auth
    def student_circuit(u):
        d=json_payload()
        with db() as c:
            row=c.execute('SELECT a.lesson_id,q.circuit FROM quiz_attempts a JOIN quiz_versions q ON q.id=a.quiz_id WHERE a.id=? AND a.user_id=?',(identifier(d.get('attempt_id')),u['id'])).fetchone()
        if not row or row['lesson_id']!=d.get('lesson_id'): abort(404)
        if not row['circuit']: abort(404,'Kviz nima priloženega vezja.')
        return jsonify(circuit=row['circuit'],filename='kviz-vezje.sim2')

    @app.post('/api/quiz/finish')
    @api_auth
    def finish_quiz(u):
        d=json_payload()
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT a.*,q.questions FROM quiz_attempts a JOIN quiz_versions q ON q.id=a.quiz_id WHERE a.id=? AND a.user_id=?',(identifier(d.get('attempt_id')),u['id'])).fetchone()
            if not row: abort(404)
            if row['status']=='complete': return jsonify(message='Kviz je že oddan.',completed=True,**totals(json.loads(row['results'])))
            if row['status']!='active': abort(409,'Učitelj je ta poskus prekinil.')
            # Finishing an already started attempt remains possible after a lesson closes.
            results=grade_answers(json.loads(row['questions']),d.get('answers'))
            circuit=circuit_xml(d.get('circuit','')); snapshot=snap(d)
            c.execute("UPDATE quiz_attempts SET status='complete',answers=?,results=?,circuit=?,snapshot=?,finished=? WHERE id=?",(json.dumps(d['answers'],ensure_ascii=False),json.dumps(results),circuit,snapshot,time.time(),row['id']))
        return jsonify(message='Kviz je oddan. Pomoč asistenta je ponovno na voljo.',completed=True,**totals(results))

    @app.post('/quiz-attempt/<int:aid>/unlock')
    @teacher
    def unlock(u,t,aid):
        with db() as c:
            row=c.execute('SELECT * FROM quiz_attempts WHERE id=?',(aid,)).fetchone()
            if not row: abort(404)
            c.execute("UPDATE quiz_attempts SET status='abandoned',finished=? WHERE id=? AND status='active'",(time.time(),aid))
        return redirect('/lesson/%s/work'%row['lesson_id'])

    @app.post('/quiz-attempt/<int:aid>/grade')
    @teacher
    def manual_grade(u,t,aid):
        try: index=int(request.form.get('question_index','')); points=float(request.form.get('points',''))
        except ValueError: abort(400,'Neveljavna ocena.')
        note=request.form.get('note','').strip()
        if len(note)>2000 or not math.isfinite(points): abort(400,'Neveljavna ocena ali komentar.')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT a.*,q.questions FROM quiz_attempts a JOIN quiz_versions q ON q.id=a.quiz_id WHERE a.id=?',(aid,)).fetchone()
            if not row: abort(404)
            qs=json.loads(row['questions']); results=json.loads(row['results'])
            if row['status']!='complete' or not 0<=index<len(qs) or qs[index]['kind']!='text' or not 0<=points<=qs[index]['points']: abort(400,'Oceni besedilni odgovor v dovoljenem razponu točk.')
            results[index].update(points=points,pending_review=False)
            c.execute('INSERT INTO quiz_grades(attempt_id,question_index,teacher_id,points,note,created) VALUES (?,?,?,?,?,?)',(aid,index,u['id'],points,note,time.time()))
            c.execute('UPDATE quiz_attempts SET results=? WHERE id=?',(json.dumps(results),aid))
        return redirect('/lesson/%s/work'%row['lesson_id'])
