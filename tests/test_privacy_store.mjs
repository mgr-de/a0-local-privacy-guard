import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {test} from 'node:test';
const source=(await readFile(new URL('../webui/privacy-store.js',import.meta.url),'utf8'))
  .replace(/^import .*;\r?\n/gm,'').replace('export const store =','globalThis.store =');
function setup(api){const c={createStore:(_,s)=>s,callJsonApi:api,Date,JSON};vm.runInNewContext(source,c);return c.store;}
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
