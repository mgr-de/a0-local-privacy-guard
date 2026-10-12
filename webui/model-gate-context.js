// Only add the selected chat to the native model gate's empty request.
export function attachChatContext(ctx, contextId) {
    const endpoint = String(ctx?.endpoint || '').replace(/^\/?api\//, '/').replace(/^\//, '');
    if (endpoint !== 'plugins/_model_config/model_config_get') return;
    if (!ctx.data || typeof ctx.data !== 'object' || Array.isArray(ctx.data)) return;
    if (Object.keys(ctx.data).length !== 0) return;
    if (typeof contextId !== 'string' || !contextId.trim()) return;
    ctx.data = { context_id: contextId.trim() };
}
