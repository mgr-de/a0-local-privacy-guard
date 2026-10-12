import { callJsonApi } from "/js/api.js";

export default async function localDisplay(context) {
  const id = globalThis.getContext?.();
  if (!id || !context?.messages?.length) return;
  const targets = [];
  const visit = (object) => {
    if (!object || typeof object !== "object") return;
    for (const [key, value] of Object.entries(object)) {
      if (typeof value === "string" && value.includes("[LPG_")) targets.push([object, key, value]);
      else if (value && typeof value === "object") visit(value);
    }
  };
  visit(context.messages);
  try {
    const expression=/\[LPG_[a-f0-9]{16}_[A-Z_]+_\d+(?:_V\d+)?\]/g;
    const tokens=[...new Set(targets.flatMap((entry)=>entry[2].match(expression)||[]))];
    const decoded=new Map();
    for (let offset=0;offset<Math.max(tokens.length,1);offset+=500) {
      const batch=tokens.slice(offset,offset+500);
      const response=await callJsonApi("/plugins/local_privacy_guard/display",{context_id:id,texts:batch});
      if(globalThis.getContext?.()!==id || !response?.ok)return;
      response.texts.forEach((value,index)=>decoded.set(batch[index],value));
      context.localPrivacyDisplay=response;
    }
    for(const [object,key,value] of targets)object[key]=value.replace(expression,(token)=>decoded.get(token)||token);
  } catch { /* Canonical placeholders remain visible if display decoding fails. */ }
}
