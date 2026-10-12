import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../extensions/webui/set_messages_after_loop/media-notice.js',import.meta.url),'utf8');
const {default:notice}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.style={};this.textContent='';}
  append(item){item.parentElement=this;this.children.push(item);}
  insertBefore(item,before){assert.equal(before.parentElement,this);item.parentElement=this;this.children.splice(this.children.indexOf(before),0,item);}
  querySelector(tag){return this.children.find(item=>item.tag===tag);}
  remove(){this.parentElement.children=this.parentElement.children.filter(item=>item!==this);}
}
const host=new Element('div'),row=new Element('div'),input=new Element('input');
host.append(row);row.append(input);input.closest=selector=>selector==='.input-row'?row:null;
globalThis.document={createElement:tag=>new Element(tag),querySelector:selector=>selector==='#chat-input'?input:null,
  getElementById:id=>host.children.find(item=>item.id===id)};
const state={localPrivacyDisplay:{media:true,route:{model:'test/vision',endpoint:'router.test'},
  protection:{owner_profile:'own',last_route:{model:'test/main'},text_filter:'redact',local_embeddings_configured:true}}};
notice(state);notice(state);
assert.equal(host.children.length,3);
assert.equal(host.children[2],row);
assert.equal(row.children.length,1);
assert.match(host.children[0].textContent,/lokale Textmaskierung schützt ihren Bildinhalt nicht/);
notice({});assert.deepEqual(host.children,[row]);
console.log('media notices stay outside the input flex row');
