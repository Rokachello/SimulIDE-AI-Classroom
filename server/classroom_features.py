# SPDX-License-Identifier: GPL-3.0-or-later
"""Teacher-controlled classroom features; all evidence remains on the server."""
import json, time
from flask import request, jsonify, abort, redirect, render_template
import learning
import quizzes


def migrate(c):
    for table, name, definition in [
        ('lessons','challenge_mode',"TEXT NOT NULL DEFAULT 'off'"),
        ('exchanges','snapshot_changes',"TEXT NOT NULL DEFAULT '{}'"),
    ]:
        if name not in {r['name'] for r in c.execute('PRAGMA table_info('+table+')')}:
            c.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+definition)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS help_requests(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE, request_id TEXT NOT NULL, reason TEXT NOT NULL, snapshot TEXT NOT NULL, created REAL NOT NULL, UNIQUE(user_id,request_id));
    CREATE TABLE IF NOT EXISTS alert_feedback(id INTEGER PRIMARY KEY, alert_id INTEGER REFERENCES teacher_alerts(id) ON DELETE CASCADE, teacher_id INTEGER REFERENCES users(id) ON DELETE CASCADE, exchange_id INTEGER, feedback TEXT NOT NULL, note TEXT NOT NULL, created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS challenges(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE, attempt INTEGER NOT NULL, state TEXT NOT NULL, original_snapshot TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(user_id,lesson_id,attempt));
    CREATE TABLE IF NOT EXISTS lesson_summaries(id INTEGER PRIMARY KEY, lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE, teacher_id INTEGER REFERENCES users(id) ON DELETE CASCADE, body TEXT NOT NULL, created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS profile_overrides(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, teacher_id INTEGER REFERENCES users(id) ON DELETE CASCADE, concept TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL, created REAL NOT NULL);
    ''')


def register(app,db,api_auth,teacher,json_payload,call_model):
    def lesson(c,lid,challenge=False):
        row=c.execute('SELECT * FROM lessons WHERE id=?',(lid,)).fetchone()
        if not row: abort(404,'Ura ne obstaja.')
        if not row['active']: abort(403,'Ura je zaključena.')
        if challenge and row['challenge_mode']=='off': abort(403,'Učitelj pri tej uri ni omogočil izziva.')
        return row
    def snapshot(d):
        obj=d.get('snapshot',{})
        if not isinstance(obj,dict) or len(json.dumps(obj).encode())>512000: abort(400,'Neveljaven ali prevelik posnetek vezja.')
        return obj
    def public(row):
        obj=learning.challenge_public(json.loads(row['state']))
        obj.update(id=row['id'],attempt=row['attempt'],available=True)
        return obj
    def owned(c,u,cid):
        row=c.execute('SELECT * FROM challenges WHERE id=? AND user_id=?',(cid,u['id'])).fetchone()
        if not row: abort(404,'Izziv ne obstaja.')
        lesson(c,row['lesson_id'],True)
        return row

    @app.post('/api/help')
    @api_auth
    def help_request(u):
        d=json_payload();lid=d.get('lesson_id');rid=d.get('request_id');reason=d.get('reason','')
        if not isinstance(rid,str) or not 16<=len(rid)<=100: abort(400,'Manjka oznaka zahteve.')
        if not isinstance(reason,str) or not reason.strip() or len(reason)>1500: abort(400,'Kratko opiši, pri čem potrebuješ pomoč.')
        snap=snapshot(d);now=time.time()
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT * FROM help_requests WHERE user_id=? AND request_id=?',(u['id'],rid)).fetchone()
            if old:
                if old['lesson_id']!=lid or old['reason']!=reason: abort(409,'Oznaka zahteve je že uporabljena.')
                return jsonify(message='Prošnja je že shranjena v učiteljskem pregledu.')
            lesson(c,lid)
            c.execute('INSERT INTO help_requests(user_id,lesson_id,request_id,reason,snapshot,created) VALUES (?,?,?,?,?,?)',(u['id'],lid,rid,reason,json.dumps(snap,ensure_ascii=False),now))
            c.execute('''INSERT INTO teacher_alerts(user_id,lesson_id,exchange_id,urgency,reason,evidence,created,updated) VALUES (?,?,NULL,'normal',?,?,?,?)
            ON CONFLICT(user_id,lesson_id) DO UPDATE SET exchange_id=NULL,reason=excluded.reason,evidence=excluded.evidence,status='open',updated=excluded.updated''',(u['id'],lid,'Študent je neposredno prosil za pomoč: '+reason,json.dumps([reason],ensure_ascii=False),now,now))
        return jsonify(message='Prošnja je shranjena v učiteljskem pregledu. Med čakanjem lahko nadaljuješ delo.')

    @app.get('/help/<int:hid>/snapshot')
    @teacher
    def help_snapshot(u,t,hid):
        with db() as c: row=c.execute('SELECT snapshot FROM help_requests WHERE id=?',(hid,)).fetchone()
        if not row: abort(404)
        return app.response_class(row['snapshot'],mimetype='application/json')

    @app.get('/challenge/<int:cid>/snapshot/<int:step>')
    @teacher
    def challenge_snapshot(u,t,cid,step):
        with db() as c: row=c.execute('SELECT state,original_snapshot FROM challenges WHERE id=?',(cid,)).fetchone()
        if not row: abort(404)
        if step==0: raw=row['original_snapshot']
        else:
            answers=json.loads(row['state']).get('answers',[])
            if not 1<=step<=len(answers): abort(404)
            raw=json.dumps(answers[step-1].get('snapshot',{}),ensure_ascii=False)
        return app.response_class(raw,mimetype='application/json')

    @app.post('/teacher-alerts/<int:aid>/feedback')
    @teacher
    def feedback(u,t,aid):
        value=request.form.get('feedback');note=request.form.get('note','').strip()
        if value not in {'needed','false_alarm'} or len(note)>1500: abort(400,'Neveljavna povratna informacija.')
        with db() as c:
            row=c.execute('SELECT * FROM teacher_alerts WHERE id=?',(aid,)).fetchone()
            if not row: abort(404)
            c.execute('INSERT INTO alert_feedback(alert_id,teacher_id,exchange_id,feedback,note,created) VALUES (?,?,?,?,?,?)',(aid,u['id'],row['exchange_id'],value,note,time.time()))
            if value=='false_alarm': c.execute("UPDATE teacher_alerts SET status='resolved' WHERE id=?",(aid,))
        return redirect('/?view=alerts')

    @app.post('/api/challenge/current')
    @api_auth
    def current(u):
        d=json_payload()
        with db() as c:
            l=c.execute('SELECT * FROM lessons WHERE id=?',(d.get('lesson_id'),)).fetchone()
            if not l: abort(404)
            row=c.execute('SELECT * FROM challenges WHERE user_id=? AND lesson_id=? ORDER BY attempt DESC LIMIT 1',(u['id'],l['id'])).fetchone()
        if not row: return jsonify(available=False,mode=l['challenge_mode'])
        return jsonify(public(row))

    @app.post('/api/challenge/start')
    @api_auth
    def start(u):
        d=json_payload();snap=snapshot(d);now=time.time()
        with db() as c:
            c.execute('BEGIN IMMEDIATE');quizzes.guard_locked(c,u['id']);l=lesson(c,d.get('lesson_id'),True)
            old=c.execute('SELECT * FROM challenges WHERE user_id=? AND lesson_id=? ORDER BY attempt DESC LIMIT 1',(u['id'],l['id'])).fetchone()
            if old and not d.get('retry'): return jsonify(public(old))
            if old and not learning.challenge_public(json.loads(old['state']))['completed']: return jsonify(public(old))
            attempt=old['attempt']+1 if old else 1
            if attempt>10: abort(429,'Doseženih je 10 poskusov izziva pri tej uri.')
            state=learning.challenge_start(snap)
            cid=c.execute('INSERT INTO challenges(user_id,lesson_id,attempt,state,original_snapshot,created,updated) VALUES (?,?,?,?,?,?,?)',(u['id'],l['id'],attempt,json.dumps(state,ensure_ascii=False),json.dumps(snap,ensure_ascii=False),now,now)).lastrowid
            row=c.execute('SELECT * FROM challenges WHERE id=?',(cid,)).fetchone()
        return jsonify(public(row))

    @app.post('/api/challenge/answer')
    @api_auth
    def answer(u):
        d=json_payload();snap=snapshot(d)
        if not isinstance(d.get('answer'),str) or len(d['answer'])>4000: abort(400,'Odgovor naj bo kratek.')
        with db() as c:
            c.execute('BEGIN IMMEDIATE');quizzes.guard_locked(c,u['id']);row=owned(c,u,d.get('challenge_id'));state=json.loads(row['state'])
            # Lost response/retry: previously accepted step does not award points twice.
            if isinstance(d.get('step'),int) and d['step']<learning.challenge_public(state)['step']: return jsonify(public(row))
            try: state=learning.challenge_submit(state,{'step':d.get('step'),'answer':d['answer']},snap)
            except ValueError as e: abort(400,str(e))
            c.execute('UPDATE challenges SET state=?,updated=? WHERE id=?',(json.dumps(state,ensure_ascii=False),time.time(),row['id']))
            row=c.execute('SELECT * FROM challenges WHERE id=?',(row['id'],)).fetchone()
        return jsonify(public(row))

    @app.post('/api/challenge/hint')
    @api_auth
    def hint(u):
        d=json_payload()
        with db() as c:
            c.execute('BEGIN IMMEDIATE');quizzes.guard_locked(c,u['id']);row=owned(c,u,d.get('challenge_id'));state=json.loads(row['state'])
            if d.get('step')!=learning.challenge_public(state)['step']: abort(409,'Osveži trenutni korak izziva.')
            try: state=learning.challenge_hint(state)
            except ValueError as e: abort(400,str(e))
            c.execute('UPDATE challenges SET state=?,updated=? WHERE id=?',(json.dumps(state,ensure_ascii=False),time.time(),row['id']))
        return jsonify(hint=state.get('hint',''))

    @app.post('/lesson/<int:lid>/summary')
    @teacher
    def summarize(u,t,lid):
        with db() as c:
            l=c.execute('SELECT * FROM lessons WHERE id=?',(lid,)).fetchone()
            if not l: abort(404)
            rev=c.execute('SELECT * FROM revisions WHERE lesson_id=? AND version=?',(lid,l['revision'])).fetchone()
            rows=[dict(r) for r in c.execute("SELECT e.*,u.name FROM exchanges e JOIN users u ON u.id=e.user_id WHERE lesson_id=? AND status='complete' ORDER BY e.id",(lid,))]
        result=learning.lesson_summary(rows,objectives=rev['objectives'],call_model=call_model,model=rev['model'])
        with db() as c:
            result['challenges']=[{'name':r['name'],'attempt':r['attempt'],**learning.challenge_public(json.loads(r['state']))} for r in c.execute('SELECT ch.*,u.name FROM challenges ch JOIN users u ON u.id=ch.user_id WHERE lesson_id=?',(lid,))]
            c.execute('INSERT INTO lesson_summaries(lesson_id,teacher_id,body,created) VALUES (?,?,?,?)',(lid,u['id'],json.dumps(result,ensure_ascii=False),time.time()))
        return redirect('/lesson/'+str(lid)+'?view=summary#summaries')

    @app.route('/student/<int:uid>/profile',methods=['GET','POST'])
    @teacher
    def profile_page(u,t,uid):
        with db() as c:
            student=c.execute("SELECT id,name FROM users WHERE id=? AND role='student'",(uid,)).fetchone()
            if not student: abort(404)
            attempts=[dict(r,**{'state_data':json.loads(r['state'])}) for r in c.execute('SELECT * FROM challenges WHERE user_id=? ORDER BY created',(uid,))]
            profile=learning.concept_profile([dict(r['state_data'],id=r['id'],lesson_id=r['lesson_id']) for r in attempts])
            if request.method=='POST':
                concept=request.form.get('concept','');status=request.form.get('status');note=request.form.get('note','').strip()
                if not concept or len(concept)>200 or status not in {'unknown','assisted','independent'} or not note or len(note)>1500: abort(400,'Izberi koncept in raven ter zapiši dokaz za popravek.')
                c.execute('INSERT INTO profile_overrides(user_id,teacher_id,concept,status,note,created) VALUES (?,?,?,?,?,?)',(uid,u['id'],concept,status,note,time.time()))
                return redirect('/student/'+str(uid)+'/profile')
            overrides=[dict(r) for r in c.execute('SELECT * FROM profile_overrides WHERE user_id=? ORDER BY id DESC',(uid,))]
        return render_template('profile.html',student=student,profile=profile,overrides=overrides,attempts=attempts,csrf=t)
