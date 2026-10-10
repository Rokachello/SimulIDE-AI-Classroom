(() => {
 'use strict';
 const list = document.getElementById('questionList');
 const error = document.getElementById('editorError');
 function field(parent, caption, tag, attrs, value) {
  const label = document.createElement('label'); label.textContent = caption;
  const input = document.createElement(tag);
  Object.keys(attrs || {}).forEach(key => input.setAttribute(key, attrs[key]));
  if (value !== undefined && value !== null) input.value = String(value);
  label.appendChild(input); parent.appendChild(label); return input;
 }
 function renumber() { Array.from(list.children).forEach((card,i) => card.querySelector('h3').textContent = 'Vprašanje ' + (i+1)); }
 function addQuestion(q = {}) {
  const card = document.createElement('section'); const heading = document.createElement('h3'); card.appendChild(heading);
  const kind = field(card, 'Vrsta vprašanja', 'select', {}, undefined);
  [['choice','Izbira enega odgovora'],['number','Številčni odgovor'],['text','Kratka razlaga (učiteljevo ocenjevanje)']].forEach(([value,caption]) => {const option=document.createElement('option');option.value=value;option.textContent=caption;kind.appendChild(option);});
  kind.value = q.kind || 'choice';
  const prompt = field(card,'Vprašanje','textarea',{required:'',maxlength:'3000'},q.prompt || '');
  const choiceBox=document.createElement('div');card.appendChild(choiceBox);
  const options=field(choiceBox,'Možni odgovori – vsak v svoji vrstici','textarea',{maxlength:'8000'},(q.options || []).join('\n'));
  const answerChoice=field(choiceBox,'Številka pravilnega odgovora (prvi odgovor = 1)','input',{type:'number',min:'1',step:'1'},q.kind==='choice' && Number.isInteger(q.answer) ? q.answer+1 : 1);
  const numberBox=document.createElement('div');card.appendChild(numberBox);
  const answerNumber=field(numberBox,'Pravilna številčna vrednost','input',{type:'number',step:'any'},q.kind==='number' ? q.answer : '');
  const tolerance=field(numberBox,'Dovoljeni odklon (±)','input',{type:'number',min:'0',step:'any'},q.tolerance || 0);
  const unitNote=document.createElement('small');unitNote.textContent='Enoto napiši v vprašanje, na primer: »Kolikšna je napetost v voltih?«. Študent vpiše številčno vrednost v tej enoti.';numberBox.appendChild(unitNote);
  const textNote=document.createElement('p');textNote.textContent='Po oddaji pregledaš razlago in dodeliš točke. Do takrat je rezultat označen kot neocenjen.';card.appendChild(textNote);
  const points=field(card,'Največ točk','input',{type:'number',min:'1',max:'100',step:'1',required:''},q.points || 1);
  const controls=document.createElement('div');card.appendChild(controls);
  [['↑ Premakni gor',()=>{if(card.previousElementSibling)list.insertBefore(card,card.previousElementSibling);renumber();}],['↓ Premakni dol',()=>{if(card.nextElementSibling)list.insertBefore(card.nextElementSibling,card);renumber();}],['Odstrani vprašanje',()=>{card.remove();renumber();}]].forEach(([caption,action])=>{const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent=caption;button.style.marginRight='8px';button.addEventListener('click',action);controls.appendChild(button);});
  function visibility(){choiceBox.hidden=kind.value!=='choice';numberBox.hidden=kind.value!=='number';textNote.hidden=kind.value!=='text';options.required=kind.value==='choice';answerChoice.required=kind.value==='choice';answerNumber.required=kind.value==='number';tolerance.required=kind.value==='number';answerChoice.disabled=kind.value!=='choice';answerNumber.disabled=kind.value!=='number';tolerance.disabled=kind.value!=='number';}
  kind.addEventListener('change',visibility);visibility();
  card.readQuestion=()=>{
   const data={kind:kind.value,prompt:prompt.value.trim(),points:Number(points.value)};
   if(data.kind==='choice'){data.options=options.value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);data.answer=Number(answerChoice.value)-1;if(data.options.length<2 || data.options.length>8 || !Number.isInteger(data.answer) || data.answer<0 || data.answer>=data.options.length)throw new Error('Vsako vprašanje z izbiro potrebuje od 2 do 8 odgovorov in veljavno številko pravilnega odgovora.');}
   if(data.kind==='number'){data.answer=Number(answerNumber.value);data.tolerance=Number(tolerance.value);if(!Number.isFinite(data.answer)||!Number.isFinite(data.tolerance)||data.tolerance<0)throw new Error('Preveri pravilno številčno vrednost in dovoljeni odklon.');}
   if(!data.prompt || !Number.isInteger(data.points) || data.points<1 || data.points>100)throw new Error('Vsako vprašanje potrebuje besedilo in od 1 do 100 točk.');
   return data;
  };
  list.appendChild(card);renumber();
 }
 let initial = JSON.parse(document.getElementById('initialQuestions').textContent);
 if(!Array.isArray(initial))initial=[];initial.forEach(addQuestion);if(!initial.length)addQuestion();
 document.getElementById('addQuestion').addEventListener('click',()=>{if(list.children.length>=30){error.textContent='Kviz ima lahko največ 30 vprašanj.';error.hidden=false;return;}addQuestion();});
 document.getElementById('quizEditor').addEventListener('submit',event=>{
  try {const questions=Array.from(list.children).map(card=>card.readQuestion());if(!questions.length)throw new Error('Dodaj vsaj eno vprašanje.');if(questions.length>30)throw new Error('Kviz ima lahko največ 30 vprašanj.');document.getElementById('questionsJson').value=JSON.stringify(questions);error.hidden=true;}
  catch(problem){event.preventDefault();error.textContent=problem.message;error.hidden=false;error.scrollIntoView({block:'center'});}
 });
})();

// Preview uses textContent only; teacher text never becomes executable markup.
(() => {
 const form=document.getElementById('quizEditor'), list=document.getElementById('questionList');
 const state=document.getElementById('editorState'), preview=document.getElementById('quizPreview');
 if(!form || !preview)return;
 const dirty=()=>{state.textContent='Neshranjene spremembe · pred odhodom shrani osnutek ali objavi.';};
 form.addEventListener('input',dirty);form.addEventListener('change',dirty);
 document.getElementById('addQuestion').addEventListener('click',dirty);
 document.getElementById('previewQuiz').addEventListener('click',()=>{
  const error=document.getElementById('editorError');
  try{
   const questions=Array.from(list.children).map(card=>card.readQuestion());
   if(!questions.length)throw new Error('Dodaj vsaj eno vprašanje.');
   const container=document.getElementById('previewQuestions');container.replaceChildren();
   questions.forEach((q,i)=>{
    const card=document.createElement('section'),label=document.createElement('h3');
    label.textContent=(i+1)+'. '+q.prompt+' ('+q.points+' točk)';card.appendChild(label);
    if(q.kind==='choice')q.options.forEach((caption,j)=>{
     const option=document.createElement('label'),radio=document.createElement('input');radio.type='radio';radio.name='preview-'+i;radio.value=j;
     option.appendChild(radio);option.appendChild(document.createTextNode(caption));card.appendChild(option);
    });
    else {const input=document.createElement(q.kind==='text'?'textarea':'input');input.placeholder=q.kind==='text'?'Tvoja razlaga …':'Številčna vrednost';input.setAttribute('aria-label','Odgovor na vprašanje '+(i+1));card.appendChild(input);}
    container.appendChild(card);
   });
   error.hidden=true;preview.showModal();
  }catch(problem){error.textContent=problem.message;error.hidden=false;error.scrollIntoView({block:'center'});}
 });
 document.getElementById('closePreview').addEventListener('click',()=>preview.close());
})();
