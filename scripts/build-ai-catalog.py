# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative source catalog for our pinned build, not a runtime UI dump.
Only literal declarations are extracted; no inferred defaults or numerical limits.
"""
import json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
registry=(root/'src/gui/componentlist/itemlibrary.cpp').read_text()
registered=set(re.findall(r'addItem\(\s*(\w+)::libraryItem\(\)',registry))
# Strip comments without damaging strings (URLs, quoted symbols, etc.).
def clean(text):
 return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/',lambda m:m[0] if m[0].startswith('"') else ' ',text,flags=re.S)
def balanced(text,start):
 depth=0;quoted=False;escaped=False
 for i in range(start,len(text)):
  c=text[i]
  if quoted:
   if escaped: escaped=False
   elif c=='\\': escaped=True
   elif c=='"': quoted=False
   continue
  if c=='"': quoted=True
  elif c=='(': depth+=1
  elif c==')':
   depth-=1
   if depth==0:return text[start:i+1]
 return ''
files={};bases={}
for h in sorted((root/'src').rglob('*.h')):
 text=clean(h.read_text(errors='replace'))
 for cls,inherit in re.findall(r'class\s+(\w+)\s*:\s*([^\{;]+)\{',text):
  bases[cls]=re.findall(r'(?:public|protected|private)\s+(\w+)',inherit)
 cpp=h.with_suffix('.cpp')
 if cpp.exists():
  source=clean(cpp.read_text(errors='replace'))
  for cls in re.findall(r'class\s+(\w+)\s*[:{]',text):files[cls]=(cpp,source)
prop_pattern=r'new\s+(\w+Prop)\s*<[^>]+>\s*\(\s*"([^"]+)"\s*,\s*(?:tr\(\s*"([^"]*)"\s*\)|"([^"]*)")\s*,\s*("(?:\\.|[^"\\])*"|\w+)'
def properties(cls,seen=None):
 seen=set() if seen is None else seen
 if cls in seen:return []
 seen.add(cls);props=[]
 for base in bases.get(cls,[]):props.extend(properties(base,seen))
 if cls not in files:return props
 path,text=files[cls]
 removed=set(re.findall(r'remPropGroup\(\s*(?:tr\(\s*)?"([^"]+)"',text))
 props=[p for p in props if p['group'] not in removed]
 for match in re.finditer(r'addPropGroup\s*\(',text):
  block=balanced(text,text.index('(',match.start()))
  group=re.search(r'\{\s*(?:tr\(\s*)?"([^"]+)"',block)
  if not group:continue
  group=group[1];visibility='hidden' if 'groupHidden' in block else 'declared_visible'
  declaration_source=path; declaration_class=cls
  if 'Dialed::dialProps()' in block and 'Dialed' in files:
   declaration_source,dial_text=files['Dialed']; declaration_class='Dialed'
   helper=re.search(r'Dialed::dialProps\(\)\s*\{(.*?)\n\}',dial_text,re.S)
   if helper:block+=helper[1]
  for m in re.finditer(prop_pattern,block):
   kind,key,translated,literal,unit=m.groups()
   prop={'key':key,'label':translated or literal or key,'value_type':{'DoubProp':'number','IntProp':'integer','BoolProp':'boolean','StrProp':'string'}.get(kind,kind),'unit':unit[1:-1] if unit.startswith('"') else None,'group':group,'visibility':visibility,'declared_by':declaration_class,'source':str(declaration_source.relative_to(root))}
   if not unit.startswith('"'):prop['metadata_expression']=unit
   props=[p for p in props if p['key']!=key];props.append(prop)
 return props
items=[]
pattern=r'LibraryItem\*\s+(\w+)::libraryItem\(\).*?new LibraryItem\(\s*tr\(\s*"([^"]+)"\s*\)\s*,\s*"([^"]+)"\s*,\s*"[^"]*"\s*,\s*"([^"]+)"'
for file in sorted((root/'src/components').rglob('*.cpp')):
 text=clean(file.read_text())
 for cls,name,category,kind in re.findall(pattern,text,re.S):
  if cls not in registered:continue
  props=properties(cls)
  for prop in props:prop['inherited']=prop['declared_by']!=cls
  items.append({'name':name,'type':kind,'category':category,'properties':props,'source':str(file.relative_to(root))})
cards={c['type']:c for c in json.loads((root/'server/knowledge/component-cards.json').read_text())}
for item in items:
 card=cards.get(item['type'],{})
 for prop in item['properties']:
  if prop['key'] in card.get('verified_defaults_display_units',{}):
   prop['default_display_value']=card['verified_defaults_display_units'][prop['key']]
   prop['default_sources']=card['sources']
  if prop['key'] in card.get('verified_choices',{}):
   prop['choices']=card['verified_choices'][prop['key']]
out=root/'server/knowledge/catalog.json'
out.write_text(json.dumps({'version':'SimulIDE 2.0.0-dev / fc5da465bb15e80b6307f0c9564f5241567f7d86 / catalog-v08','scope':'Static native registry only; dynamic MCU/subcircuit libraries are not enumerated. Literal property groups include inherited declarations and removed groups; runtime visibility, helper-generated properties and dynamic choices may be incomplete. declared_visible means declared in a non-hidden group, not verified in the current UI. Units are display units, not necessarily internal storage units. Unknown defaults/limits are not inferred. English original labels; UI translations can differ. Curated cards supplement verified behavior.','items':items},ensure_ascii=False,indent=2)+'\n')
print(len(items),'native entries;',sum(len(i['properties']) for i in items),'property declarations including inherited')
