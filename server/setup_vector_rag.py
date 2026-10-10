# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit, resumable upload of bundled public documentation; never student data."""
import argparse
import getpass
import hashlib
import json
import os
import time
from pathlib import Path
import vector_rag

def save(cfg):
    path=vector_rag.config_path();path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    os.chmod(temporary,0o600)
    temporary.replace(path)

def setup(records_path):
    records=json.loads(Path(records_path).read_text(encoding='utf-8'))
    records=[r for r in records if r['kind'] in {'native-guide','official-usage'} or (r['kind']=='official-guide' and r.get('types'))]
    if not records:raise RuntimeError('Paket dokumentacije je prazen.')
    path=vector_rag.config_path();path.parent.mkdir(parents=True,exist_ok=True)
    lock=path.with_suffix('.lock')
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise RuntimeError('Priprava RAG že teče. Po prekinjenem zagonu preveri proces in odstrani vector-rag.lock.') from None
    os.close(fd)
    try:
        cfg=json.loads(path.read_text()) if path.exists() else {'ready':False,'documents':{}}
        # A changed corpus requires a deliberate future migration; no stale mixed index.
        for row in records:
            previous=cfg['documents'].get(row['id'])
            digest=hashlib.sha256(row['body'].encode()).hexdigest()
            if previous and previous['sha256']!=digest:
                raise RuntimeError('Gradivo se je spremenilo. Ta različica podpira začetno nalaganje in nadaljevanje; za spremembe je potrebna migracija indeksa.')
        if not cfg.get('vector_store_id'):
            cfg['vector_store_id']=vector_rag.api('POST','/vector_stores',json={'name':'SimulIDE – javna dokumentacija v1'})['id']
            save(cfg)
        cfg['ready']=False;save(cfg)
        for n,row in enumerate(records,1):
            digest=hashlib.sha256(row['body'].encode()).hexdigest()
            entry=cfg['documents'].get(row['id'])
            if entry and entry.get('completed'):
                print(f'{n}/{len(records)} že pripravljeno: {row["title"]}',flush=True);continue
            if not entry:
                uploaded=vector_rag.api('POST','/files',data={'purpose':'assistants'},files={'file':('simulide-'+digest[:16]+'.md',row['body'].encode('utf-8'),'text/markdown')})
                entry={k:row[k] for k in ['title','source','kind','compatibility']}
                entry.update(document_id=row['id'],file_id=uploaded['id'],sha256=digest,completed=False)
                cfg['documents'][row['id']]=entry;save(cfg)
            vs=cfg['vector_store_id'];fid=entry['file_id']
            if not entry.get('attached'):
                vector_rag.api('POST','/vector_stores/'+vs+'/files',json={'file_id':fid,'attributes':{'corpus':'simulide-public-v1','kind':row['kind'],'compatibility':row['compatibility']}})
                entry['attached']=True;save(cfg)
            deadline=time.monotonic()+180
            while True:
                state=vector_rag.api('GET','/vector_stores/'+vs+'/files/'+fid)
                if state['status']=='completed':break
                if state['status'] in {'failed','cancelled'}:raise RuntimeError('Indeksiranje ni uspelo: '+row['title']+'. Nadaljevanje zahteva preverjanje te datoteke.')
                if time.monotonic()>deadline:raise RuntimeError('Indeksiranje še teče; ponovno zaženi pripravo, da nadaljuješ.')
                time.sleep(1)
            entry['completed']=True;save(cfg)
            print(f'{n}/{len(records)} pripravljeno: {row["title"]}',flush=True)
        cfg['ready']=True;save(cfg)
        print('RAG pripravljen. Vector store: '+cfg['vector_store_id'],flush=True)
    finally:lock.unlink(missing_ok=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--records',default=str(Path(__file__).parent/'knowledge/vector-records.json'));args=p.parse_args()
    try:
        if not os.environ.get('OPENAI_API_KEY'):os.environ['OPENAI_API_KEY']=getpass.getpass('OpenAI API ključ (samo v pomnilniku): ')
        setup(args.records)
    except (RuntimeError,OSError,ValueError,KeyError) as e:
        print('Priprava ni uspela: '+str(e));raise SystemExit(1)
