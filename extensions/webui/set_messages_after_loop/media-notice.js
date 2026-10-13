export default function mediaNotice(context) {
  const state = context?.localPrivacyDisplay;
  const row=document.querySelector('#chat-input')?.closest('.input-row');
  const anchor=row?.parentElement;
  let status=document.getElementById('local-privacy-model-status');
  if(!state?.protection)status?.remove();
  else {
    if(!status) {
      status=document.createElement('details');status.id='local-privacy-model-status';
      const summary=document.createElement('summary');summary.textContent='Privacy: Modellroute und Schutzgrenzen';status.append(summary);
      status.append(document.createElement('p'));
      status.style.cssText='padding:.35rem .75rem;font-size:.875rem;box-sizing:border-box;max-width:100%;overflow-wrap:anywhere;';
      if(!anchor)return;
      anchor.insertBefore(status,row);
    }
    const route=state.protection.last_route;
    status.querySelector('summary').textContent=state.protection.mode_label || 'Privacy: Modellroute und Schutzgrenzen';
    status.querySelector('p').textContent='Schutzprofil: '+state.protection.owner_profile+
      (state.protection.inherited?' · vom Elternchat übernommen':'')+'. Letzte Modellroute: '+(route?.model || 'noch kein Aufruf')+
      (route?.local?' · lokal':route?.endpoint?' via '+route.endpoint:'')+
      '. '+(state.protection.mode_label || ('Textfilter: '+state.protection.text_filter))+
      '. Lokale Embeddings: '+(state.protection.local_embeddings_configured?'konfiguriert':'nicht konfiguriert')+
      '. Bildinhalte und Datenübertragungen durch Werkzeuge sind durch die Textmaskierung nicht abgedeckt.';
  }
  let note = document.getElementById("local-privacy-media-notice");
  if (!state?.media) { note?.remove(); return; }
  if (!note) {
    note = document.createElement("aside");
    note.id = "local-privacy-media-notice";
    note.className = "privacy-note";
    note.style.cssText = "padding:.5rem .75rem;font-size:.875rem;border:1px solid var(--color-border,#555);border-radius:.5rem;box-sizing:border-box;max-width:100%;overflow-wrap:anywhere;";
    if (!anchor) return;
    anchor.insertBefore(note,status || row);
  }
  note.textContent = "Bilder werden beim ausgewählten Dienst verarbeitet. Die lokale Textmaskierung schützt ihren Bildinhalt nicht. Externe Bildroute: " +
    (state.route?.model || "unknown") + (state.route?.endpoint ? " via " + state.route.endpoint : "") +
    ". Browserformulare und Uploads haben eigene Empfänger.";
}
