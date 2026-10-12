import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {test} from 'node:test';
const source=(await readFile(new URL('../webui/privacy-store.js',import.meta.url),'utf8'))
  .replace(/^import .*;\r?\n/gm,'').replace('export const store =','globalThis.store =');
function setup(api,onError=()=>{}){const c={createStore:(_,s)=>s,callJsonApi:api,Date,JSON,toastFrontendError:onError};vm.runInNewContext(source,c);return c.store;}
test('example result is invalidated by settings changes and errors stay visible',async()=>{
  const s=setup(async()=>({ok:true,output:'example'}));const c={enabled:true};await s.runExample(c);
  assert.ok(s.current(c));c.enabled=false;assert.equal(s.current(c),false);
  const bad=setup(async()=>({ok:false,error:'Example error'}));await bad.runExample(c);
  assert.equal(bad.error,'Example error');assert.equal(bad.result,null);assert.equal(bad.busy,false);
});
test('closing or changing settings while checking ignores late responses',async()=>{
  let resolve;const s=setup(()=>new Promise(r=>resolve=r));const c={enabled:true};const p=s.runExample(c);
  s.cleanup();resolve({ok:true,output:'late'});await p;assert.equal(s.result,null);
  const next=s.runExample(c);c.enabled=false;resolve({ok:true,output:'late'});await next;assert.equal(s.result,null);
});
test('OCR is local, reports failures and discards results after close',async()=>{
  let request;
  const s=setup(async(path,body)=>{request={path,body};return {ok:true,text:'Fictional contact'};});
  s.ocrPath='/a0/usr/workdir/fictional.png';await s.runOcr();
  assert.equal(request.path,'plugins/local_privacy_guard/ocr');
  assert.equal(s.ocrText,'Fictional contact');assert.equal(s.ocrBusy,false);
  let resolve;const late=setup(()=>new Promise(r=>resolve=r));late.ocrPath=s.ocrPath;
  const pending=late.runOcr();late.cleanup();resolve({ok:true,text:'late'});await pending;
  assert.equal(late.ocrText,'');assert.equal(late.ocrBusy,false);
});


test('optional backend setup has fixed actions and ignores results after close',async()=>{
  let request,resolve;
  const s=setup((path,body)=>{request={path,body};return new Promise(r=>resolve=r);});
  const pending=s.setupPresidio('install');
  assert.equal(request.path,'plugins/local_privacy_guard/presidio_setup');
  assert.deepEqual(JSON.parse(JSON.stringify(request.body)),{action:'install'});
  assert.equal(s.backendBusy,true);
  s.cleanup();resolve({ok:true,available:true,restart_required:true});await pending;
  assert.equal(s.backendResult,null);assert.equal(s.backendBusy,false);
});

test('optional installation failure remains visible without changing the engine',async()=>{
  const errors=[];const s=setup(async()=>({ok:false,error:'Install failed'}),message=>errors.push(message));
  await s.setupPresidio('install');
  assert.equal(s.backendResult.error,'Install failed');assert.deepEqual(errors,['Install failed']);
  assert.equal(s.backendBusy,false);assert.equal(s.config,undefined);
});
