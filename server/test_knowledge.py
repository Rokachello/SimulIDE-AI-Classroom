import unittest
from io import BytesIO
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
import knowledge
class KnowledgeTest(unittest.TestCase):
 def test_source_question(self):
  r=knowledge.retrieve('Program ponuja več vrst voltage sourcov, kateri je primeren?',{},[],[])
  self.assertEqual(r['excerpts'][0]['id'],'manual:voltage-sources')
  self.assertIn('Za začetni fiksni napetostni delilnik izberi Fixed Voltage',r['excerpts'][0]['text'])
  self.assertIn('Max. Voltage 5 V ne dokazuje',r['excerpts'][0]['text'])
  self.assertIn('Fixed Voltage',{x['name'] for x in r['available_native_elements']})
  self.assertNotIn('DC Voltage Source',{x['name'] for x in r['available_native_elements']})
 def test_relevance_bounds(self):
  for q,id in [('Kako uporabim osciloskop?','manual:meters'),('Kako izmerim izhodno napetost?','manual:meters'),('Kaj pomeni Lux pri LDR?','manual:sensors')]:
   self.assertIn(id,[e['id'] for e in knowledge.retrieve(q,{},[],[])['excerpts'][:3]])
  self.assertEqual(knowledge.retrieve('Teleportacija samoroga',{},[],[])['excerpts'],[])
  docs=[{'id':'teacher:1','title':'ZEBRA','body':'ZEBRA posebne informacije. '*10000,'source':'Učitelj','kind':'teacher-document'}]
  r=knowledge.retrieve('ZEBRA',{},[],docs)
  self.assertLessEqual(len(r['excerpts']),8);self.assertLess(sum(len(e['text']) for e in r['excerpts']),16000)
  self.assertTrue(r['excerpts'][0]['document_sha256'])
 def test_extended_properties_and_visibility(self):
  items={i['type']:i for i in knowledge.catalog()['items']}
  fixed={p['key']:p for p in items['Fixed Voltage']['properties']}
  self.assertEqual(fixed['Voltage']['unit'],'V')
  self.assertEqual(fixed['Small']['value_type'],'boolean')
  self.assertEqual(fixed['Voltage']['default_display_value'],5)
  wave={p['key']:p for p in items['WaveGen']['properties']}
  self.assertEqual(wave['Wave_Type']['choices'],['Sine','Saw','Triangle','Square','Random','Wav'])
  battery={p['key']:p for p in items['Battery']['properties']}
  self.assertEqual((battery['Resistance']['default_display_value'],battery['Resistance']['unit']),(1,'mΩ'))
  self.assertEqual(fixed['Out']['visibility'],'hidden')
  sensor={p['key']:p for p in items['Thermistor']['properties']}
  self.assertTrue(sensor['Temp']['inherited'])
  self.assertEqual(sensor['Temp']['declared_by'],'ThermistorBase')
  self.assertEqual(sensor['Temp']['unit'],'ºC')
  self.assertEqual(sensor['Slider']['declared_by'],'Dialed')
  doc=next(d for d in knowledge.bundled_documents() if d['id']=='catalog:Fixed Voltage')
  self.assertNotIn('[Out]',doc['body'])
  self.assertNotIn('[Pos]',doc['body'])
 def test_verified_cards_retrieved_on_demand(self):
  for q,expected,detail in [
   ('Katere nastavitve ima Thermistor?', 'card:Thermistor', 'R25'),
   ('Kako nastavljam Potentiometer?', 'card:Potentiometer', 'Value_Ohm'),
   ('Kaj lahko nastavim v Wave Generator?', 'card:WaveGen', 'Sine, Saw, Triangle, Square, Random, Wav'),
   ('Katere nastavitve ima Fixed Voltage?', 'card:Fixed Voltage', 'skrita')]:
   result=knowledge.retrieve(q,{},[],[])
   parts=[e['text'] for e in result['excerpts'] if e['id']==expected]
   self.assertTrue(parts, q)
   self.assertIn(detail,' '.join(parts))
   self.assertTrue(all(set(e)=={'name','type','category'} for e in result['available_native_elements']))
  sensor=next(d for d in knowledge.bundled_documents() if d['id']=='card:Thermistor')
  self.assertIn('setPtc takoj vrne',sensor['body'])
  self.assertIn('thermistorbase.cpp',sensor['source'])
 def test_extract_pdf_text_and_reject_scan(self):
  writer=PdfWriter();page=writer.add_blank_page(400,400)
  font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
  page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
  stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 300 Td (ZEBRA instructions for the electronics lesson and voltage measurement.) Tj ET')
  page[NameObject('/Contents')]=writer._add_object(stream);out=BytesIO();writer.write(out)
  self.assertIn('ZEBRA',knowledge.extract_file('test.pdf',out.getvalue()))
  writer=PdfWriter();writer.add_blank_page(200,200);out=BytesIO();writer.write(out)
  with self.assertRaisesRegex(ValueError,'OCR'): knowledge.extract_file('scan.pdf',out.getvalue())
  with self.assertRaises(ValueError): knowledge.extract_file('bad.exe',b'x'*100)
  with self.assertRaises(ValueError): knowledge.extract_file('bad.md',b'\xff'*50)
if __name__=='__main__': unittest.main()
