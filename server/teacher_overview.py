# SPDX-License-Identifier: GPL-3.0-or-later
"""Lesson operations and evidence-based activity overview for the teacher."""
import json,time
from flask import abort,render_template,request,redirect

def register(app,db,teacher,read_alerts):
    def lesson(c,lid):
        row=c.execute('SELECT l.*,r.objectives,r.instructions,r.prompt,r.model,r.quota FROM lessons l JOIN revisions r ON r.lesson_id=l.id AND r.version=l.revision WHERE l.id=?',(lid,)).fetchone()
        if not row:abort(404,'Ura ne obstaja.')
        return dict(row)

    def activity(c,lid):
        people={}
        def student(uid):
            if uid not in people:people[uid]={'id':uid,'questions':0,'submission':None,'quiz':None,'last':0,'help':None}
            return people[uid]
        for r in c.execute('SELECT user_id,count(*) n,max(created) latest FROM exchanges WHERE lesson_id=? GROUP BY user_id',(lid,)):
            s=student(r['user_id']);s['questions']=r['n'];s['last']=r['latest']
        for r in c.execute('SELECT id,user_id,created FROM assignment_submissions WHERE lesson_id=? ORDER BY id',(lid,)):
            s=student(r['user_id']);s['submission']=r['id'];s['last']=max(s['last'],r['created'])
        for r in c.execute('SELECT id,user_id,status,created,finished FROM quiz_attempts WHERE lesson_id=? ORDER BY id',(lid,)):
            s=student(r['user_id']);s['quiz']=dict(r);s['last']=max(s['last'],r['finished'] or r['created'])
        for r in c.execute('SELECT user_id,created FROM help_requests WHERE lesson_id=?',(lid,)):
            s=student(r['user_id']);s['last']=max(s['last'],r['created'])
        for r in c.execute('SELECT user_id,status,urgency FROM teacher_alerts WHERE lesson_id=?',(lid,)):
            student(r['user_id'])['help']=dict(r)
        names={r['id']:r['name'] for r in c.execute("SELECT id,name FROM users WHERE role='student'")}
        for uid,s in people.items():s['name']=names.get(uid,'Študent')
        return sorted(people.values(),key=lambda s:(not(s['help'] and s['help']['status']!='resolved'),s['name'].casefold()))

    def values(lid,t):
        with db() as c:
            l=lesson(c,lid);students=activity(c,lid)
            q=c.execute('SELECT id,title,published FROM quiz_versions WHERE lesson_id=? ORDER BY id DESC LIMIT 1',(lid,)).fetchone()
            docs=c.execute('SELECT count(*) FROM knowledge_docs WHERE active=1 AND (lesson_id IS NULL OR lesson_id=?)',(lid,)).fetchone()[0]
        alerts=read_alerts(lid)
        return dict(lesson=l,students=students,quiz=q,documents=docs,alerts=alerts,csrf=t,
                    counts={'students':len(students),'submissions':sum(bool(s['submission']) for s in students),'quizzes':sum(bool(s['quiz'] and s['quiz']['status']=='complete') for s in students),'help':sum(a['status']!='resolved' for a in alerts)})

    @app.get('/lesson/<int:lid>/overview')
    @teacher
    def lesson_overview(u,t,lid):return render_template('lesson_overview.html',**values(lid,t))

    @app.get('/lesson/<int:lid>/activity')
    @teacher
    def lesson_activity(u,t,lid):return render_template('lesson_activity.html',**values(lid,t))

    @app.post('/lesson/<int:lid>/state')
    @teacher
    def lesson_state(u,t,lid):
        desired=request.form.get('active')
        if desired not in {'0','1'}:abort(400,'Izberi odpiranje ali zaključek ure.')
        with db() as c:
            l=lesson(c,lid)
            c.execute('UPDATE lessons SET active=? WHERE id=?',(int(desired),lid))
        return redirect('/lesson/%s/overview?notice=%s'%(lid,'opened' if desired=='1' else 'closed'))

    @app.post('/lesson/<int:lid>/copy')
    @teacher
    def lesson_copy(u,t,lid):
        with db() as c:
            c.execute('BEGIN IMMEDIATE');l=lesson(c,lid)
            new=c.execute('INSERT INTO lessons(title,lesson_date,group_name,active,challenge_mode) VALUES (?,?,?,0,?)',((l['title'][:175]+' – nova izvedba'),'',l['group_name'],l['challenge_mode'])).lastrowid
            c.execute('INSERT INTO revisions VALUES (?,1,?,?,?,?,?)',(new,l['objectives'],l['instructions'],l['prompt'],l['model'],l['quota']))
            q=c.execute('SELECT * FROM quiz_versions WHERE lesson_id=? ORDER BY id DESC LIMIT 1',(lid,)).fetchone()
            if q:c.execute('INSERT INTO quiz_versions(lesson_id,published,title,questions,circuit,created) VALUES (?,0,?,?,?,?)',(new,q['title'],q['questions'],q['circuit'],time.time()))
            c.execute('INSERT INTO knowledge_docs(title,body,source,lesson_id,active,created,folder_id,original,filename) SELECT title,body,source,?,active,?,folder_id,original,filename FROM knowledge_docs WHERE lesson_id=?',(new,time.time(),lid))
        return redirect('/lesson/%s/overview?notice=copied'%new)
