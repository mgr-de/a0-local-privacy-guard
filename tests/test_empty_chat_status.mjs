import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {test} from 'node:test';

test('new empty chat obtains effective mode without decoding history',async()=>{
 const source=(await readFile(new URL('../extensions/webui/set_messages_before_loop/local-display.js',import.meta.url),'utf8')).replace(/^import .*;\r?\n/gm,'').replace('export default async function localDisplay','async function localDisplay');
 const calls=[];
 const scope={getContext:()=> 'synthetic-chat',callJsonApi:async(path,input)=>{calls.push(input);return {ok:true,texts:[],protection:{mode_label:'PII-Maskierung aus · Secret-Prüfung aktiv'}};}};
 vm.createContext(scope);vm.runInContext(source,scope);
 const context={messages:[]};await scope.localDisplay(context);
 assert.equal(calls.length,1);assert.equal(calls[0].texts.length,0);
 assert.equal(context.localPrivacyDisplay.protection.mode_label,'PII-Maskierung aus · Secret-Prüfung aktiv');
});
