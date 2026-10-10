# SPDX-License-Identifier: GPL-3.0-or-later
"""Small local lexical RAG: no embeddings, network fetches or extra service."""
import hashlib,json,re,unicodedata,math
from collections import Counter
from pathlib import Path
from io import BytesIO
ROOT=Path(__file__).resolve().parent/'knowledge'
STOP=set('a an and are as at be by for from in is it of on or the to with je so se si sem bo bi da do na od za iz in ali kot ki kaj kako kateri katera katere kateri pa pri to ta te tem tega ima imajo naj najprej uporabljam uporabim povej pomagas program programu simulide prosim lahko mi me ti v s z o'.split())
def normalize(text):
 return ''.join(c for c in unicodedata.normalize('NFKD',str(text).lower()) if not unicodedata.combining(c))
def tokens(text):
 return [w for w in re.findall(r'[a-z0-9]+',normalize(text)) if w not in STOP and len(w)>1]
def expand(text):
 words=tokens(text); result=set(words)
 aliases={'napetost':'voltage', 'vir':'source', 'sourc':'source', 'upor':'resistor resistance', 'resist':'resistor resistance', 'tok':'current', 'izmer':'meter measurement', 'mer':'meter measurement', 'oscil':'oscope oscilloscope', 'valov':'wave waveform', 'signal':'wave waveform', 'frek':'frequency', 'simul':'simulation', 'masa':'ground', 'ozem':'ground', 'term':'thermistor', 'svetl':'ldr lux', 'kond':'capacitor', 'poten':'potentiometer', 'lastn':'properties', 'nastav':'properties settings', 'volt':'voltage', 'shran':'save circuit', 'zapored':'series', 'vzpored':'parallel'}
 for w in words:
  for stem,extra in aliases.items():
   if w.startswith(stem): result.update(extra.split())
 return result

def chunks(text,size=1400,overlap=180):
 text=text.replace('\x00','').strip();start=0
 while start<len(text):
  end=min(start+size,len(text))
  if end<len(text):
   split=text.rfind('\n',start+size//2,end)
   if split>start: end=split
  yield text[start:end].strip()
  if end==len(text): break
  start=max(start+1,end-overlap)

def catalog():
 return json.loads((ROOT/'catalog.json').read_text())

def bundled_documents():
 cat=catalog();docs=[]
 # Exact names are compact enough to include every time; only detailed excerpts are retrieved.
 for item in cat['items']:
  lines=[f"Element: {item['name']}; interni tip: {item['type']}; kategorija: {item['category']}."]
  lines.append('Lastnosti iz deklaracij kode; trenutna vidnost je lahko odvisna od načina. Enote so prikazne. Privzetih vrednosti ne sklepaj iz imen.')
  for p in item['properties']:
   # Hidden serialization/geometry fields must never look like available controls.
   if p.get('visibility')=='hidden': continue
   line=f"{p['label']} [{p['key']}]: {p.get('value_type','unknown')}; enota {p.get('unit') or 'ni podana'}; skupina {p.get('group','')}"
   if 'default_display_value' in p: line+='; začetna vrednost '+str(p['default_display_value'])
   if p.get('choices'): line+='; izbire '+', '.join(p['choices'])
   if p.get('inherited'): line+='; podedovano iz '+p['declared_by']
   lines.append(line+'.')
  body='\n'.join(lines)
  docs.append({'id':'catalog:'+item['type'],'title':item['name'],'body':body,'source':item['source'],'types':[item['type']],'kind':'catalog'})
 for card in json.loads((ROOT/'component-cards.json').read_text()):
  docs.append({'id':'card:'+card['type'],'title':card['name']+' — nastavitve in uporaba','body':card['body'],'source':'; '.join(card['sources']), 'types':[card['type']], 'kind':'component-card'})
 for file in sorted(ROOT.glob('*.md')):
  body=file.read_text();title=body.splitlines()[0].lstrip('# ').strip()
  docs.append({'id':'manual:'+file.stem,'title':title,'body':body,'source':'Prirejena navodila za našo različico; '+file.name,'kind':'manual'})
 return docs

def retrieve(question,snapshot,past,uploaded,limit=8,budget=16000):
 query=expand(question)
 # The previous learner question helps resolve short follow-ups; never use model claims as facts.
 follow=expand(past[0]['question']) if past and len(tokens(question))<=4 else set()
 types={str(c.get('type','')) for c in snapshot.get('components',[]) if isinstance(c,dict)} if isinstance(snapshot.get('components'),list) else set()
 candidates=[]
 for doc in bundled_documents()+uploaded:
  for number,part in enumerate(chunks(doc['body']),1):
   words=Counter(tokens(doc['title']+' '+part));head=set(tokens(doc['title']));score=0.
   for term in query:
    hits=sum(n for w,n in words.items() if w==term or (len(term)>=5 and len(w)>=5 and w[:5]==term[:5]))
    if hits: score+=1+math.log1p(hits)+(2 if term in head else 0)
   measuring=any(w.startswith(('izmer','merim','merit','merjen')) for w in tokens(question))
   if measuring and (doc['id']=='manual:meters' or (doc['id']=='card:Voltimeter' and 'voltage' in query) or (doc['id']=='card:Amperimeter' and 'current' in query)): score+=12
   if doc.get('kind')=='component-card':
    name=doc['title'].split(' — ')[0]
    if normalize(name) in normalize(question): score+=8
   score+=.2*len(follow.intersection(words))
   if types.intersection(doc.get('types',[])): score+=.5
   if score<=0: continue
   excerpt={k:doc.get(k,'') for k in ['id','title','source','kind']}
   excerpt.update(chunk=number,text=part,document_sha256=hashlib.sha256(doc['body'].encode()).hexdigest())
   candidates.append((score,excerpt))
 candidates.sort(key=lambda v:(-v[0],v[1]['id'],v[1]['chunk']))
 selected=[];used=0;perdoc=Counter()
 for _,part in candidates:
  if perdoc[part['id']]>=2: continue
  cost=len(json.dumps(part,ensure_ascii=False))
  if used+cost>budget: continue
  part['ref']=len(selected)+1;selected.append(part);used+=cost;perdoc[part['id']]+=1
  if len(selected)>=limit: break
 cat=catalog()
 return {'catalog_version':cat['version'],'catalog_scope':cat['scope'],'available_native_elements':[{'name':x['name'],'type':x['type'],'category':x['category']} for x in cat['items']], 'excerpts':selected}

def extract_file(filename,data):
 suffix=Path(filename).suffix.lower()
 if suffix in {'.txt','.md'}:
  try: text=data.decode('utf-8-sig')
  except UnicodeDecodeError: raise ValueError('TXT/Markdown uvozi v kodiranju UTF-8.') from None
 elif suffix=='.pdf':
  from pypdf import PdfReader
  try:
   reader=PdfReader(BytesIO(data))
   if reader.is_encrypted: raise ValueError('Zaščitenega PDF ni mogoče uvoziti.')
   if len(reader.pages)>150: raise ValueError('PDF naj ima največ 150 strani; razdeli gradivo.')
   pages=[];count=0
   for n,page in enumerate(reader.pages,1):
    content=page.get_contents()
    if content and len(content.get_data())>5000000: raise ValueError('PDF stran je preveč zahtevna za uvoz.')
    part=page.extract_text() or '';count+=len(part)
    if count>250000: raise ValueError('Gradivo je predolgo; razdeli ga.')
    pages.append(f'\n[Stran {n}]\n'+part)
   if count<30: raise ValueError('PDF nima dovolj besedila; skenirano gradivo potrebuje OCR.')
   text='\n'.join(pages)
  except ValueError: raise
  except Exception: raise ValueError('PDF ni mogoče prebrati; uporabi besedilni PDF, TXT ali Markdown.') from None
 else: raise ValueError('Podprte so datoteke PDF, TXT in Markdown (.md).')
 if len(text.strip())<30: raise ValueError('Premalo besedila. Skeniran PDF potrebuje OCR; slike in sheme se ne uvažajo kot besedilo.')
 if len(text)>250000: raise ValueError('Gradivo je predolgo; razdeli ga.')
 return text
