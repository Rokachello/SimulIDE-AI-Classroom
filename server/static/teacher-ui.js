// SPDX-License-Identifier: GPL-3.0-or-later
(() => {
 'use strict';
 for (const search of document.querySelectorAll('[data-search]')) {
  search.addEventListener('input', () => {
   const term=search.value.toLocaleLowerCase('sl-SI').trim();
   document.querySelectorAll('[data-search-item]').forEach(item=>{
    item.hidden=!item.textContent.toLocaleLowerCase('sl-SI').includes(term);
   });
   const empty=document.getElementById('searchEmpty');
   if(empty)empty.hidden=!!document.querySelector('[data-search-item]:not([hidden])');
  });
 }
 const newLink=document.querySelector('a[href="#newLesson"]');
 if(newLink)newLink.addEventListener('click',()=>{
  const form=document.getElementById('newLesson');form.open=true;
  form.querySelector('input[name="title"]').focus();
 });
 // Warn only when leaving an edited form; submitting still follows its normal save route.
 const dirty=new Set();
 document.querySelectorAll('form').forEach(form=>{
  if(!form.querySelector('textarea') && form.id!=='quizEditor')return;
  form.addEventListener('input',()=>{dirty.add(form);});
  form.addEventListener('change',()=>{dirty.add(form);});
  form.addEventListener('submit',event=>{queueMicrotask(()=>{if(!event.defaultPrevented)dirty.delete(form);});});
  form.addEventListener('click',event=>{if(event.target.closest('#questionList button') || event.target.closest('#addQuestion'))dirty.add(form);});
 });
 window.addEventListener('beforeunload',event=>{if(dirty.size){event.preventDefault();event.returnValue='';}});
 document.querySelector('[data-go-back]')?.addEventListener('click',()=>history.back());
 const revealAnchor=()=>{
  const node=document.getElementById(location.hash.slice(1));
  if(!node)return;
  if(node.tagName==='DETAILS')node.open=true;
  let parent=node.parentElement;
  while(parent){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}
  node.scrollIntoView({block:'start'});
 };
 revealAnchor();window.addEventListener('hashchange',revealAnchor);
 const activity=document.getElementById('lessonActivity');
 if(activity){
  let running=false;
  const refresh=async()=>{
   if(running||document.hidden||activity.contains(document.activeElement))return;
   running=true;const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),10000);
   try{
    const response=await fetch(activity.dataset.url,{credentials:'same-origin',cache:'no-store',signal:controller.signal});
    if(!response.ok||response.redirected)throw new Error('connection');
    activity.innerHTML=await response.text();
    document.getElementById('activityStatus').textContent='Zadnja osvežitev: '+new Date().toLocaleTimeString('sl-SI')+'.';
   }catch(_){document.getElementById('activityStatus').textContent='Pregleda ni mogoče osvežiti. Prikazani podatki so lahko zastareli; preveri povezavo ali prijavo.';}
   finally{clearTimeout(timer);running=false;}
  };
  setInterval(refresh,20000);
 }
})();
