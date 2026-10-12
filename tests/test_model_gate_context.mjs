import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source=await readFile(new URL('../webui/model-gate-context.js',import.meta.url),'utf8');
const {attachChatContext}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
for(const endpoint of ['/plugins/_model_config/model_config_get','/api/plugins/_model_config/model_config_get']) {
  const ctx={endpoint,data:{}};attachChatContext(ctx,'chat-a');
  assert.deepEqual(ctx.data,{context_id:'chat-a'});
}
for(const data of [null,[],{agent_profile:'B'},{context_id:'chat-b'}]) {
  const ctx={endpoint:'/plugins/_model_config/model_config_get',data};attachChatContext(ctx,'chat-a');
  assert.equal(ctx.data,data);
}
console.log('local model gate context tests passed');
