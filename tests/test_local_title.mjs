import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../webui/local-title.js',import.meta.url),'utf8');
const {readableTitle}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
assert.equal(readableTitle('Anna Weber contact form'),'Anna Weber contact form');
assert.equal(readableTitle('[LPG_123456789abcdef0_PERSON_4...'),'Privacy Chat');
assert.equal(readableTitle('Contact form [LPG_123456789abcdef0_PERSON_4...]'),'Contact form');
console.log('local caption tests passed');
