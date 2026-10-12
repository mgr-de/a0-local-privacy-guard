import { callJsonApi } from '/js/api.js';
import { readableTitle } from '/plugins/local_privacy_guard/webui/local-title.js';

// Decode names only in the browser snapshot. Server titles remain canonical.
const cache=new Map();
export default async function localTitles(ctx) {
  const contexts=ctx?.snapshot?.contexts;
  if(!Array.isArray(contexts))return;
  for(const chat of contexts) {
    if(typeof chat?.name!=='string' || !chat.name.includes('[LPG_'))continue;
    const key=JSON.stringify([chat.id,chat.agent_profile,chat.project,chat.name]);
    try {
      if(!cache.has(key)) {
        const result=await callJsonApi('/plugins/local_privacy_guard/display',{context_id:chat.id,texts:[chat.name]});
        if(!result?.ok || !Array.isArray(result.texts))continue;
        if(cache.size>=256)cache.delete(cache.keys().next().value);
        cache.set(key,result.texts[0]);
      }
      chat.name=readableTitle(cache.get(key));
    } catch { /* Keep the canonical name when decoding is unavailable. */ }
  }
}
