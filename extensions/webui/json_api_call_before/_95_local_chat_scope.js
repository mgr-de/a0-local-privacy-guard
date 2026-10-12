import { store as modelGateStore } from '/components/chat/model-gate-store.js';
import { attachChatContext } from '/plugins/local_privacy_guard/webui/model-gate-context.js';

export default function localChatScope(ctx) {
    attachChatContext(ctx, modelGateStore.pending?.context || globalThis.getContext?.() || '');
    const endpoint=String(ctx?.endpoint || '').replace(/^\/?api\//,'/').replace(/^\//,'');
    if (endpoint==='plugins/_model_config/model_config_get' && ctx.data?.context_id && Object.keys(ctx.data).length===1)
        ctx.endpoint='plugins/local_privacy_guard/model_status';
}
