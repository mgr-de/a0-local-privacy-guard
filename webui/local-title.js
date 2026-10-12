// Native automatic naming can truncate a long canonical token. Do not invent
// an original value; display a neutral caption until the user renames the chat.
export function readableTitle(value) {
  if(typeof value!=='string' || !value.includes('[LPG_'))return value;
  return value.slice(0,value.indexOf('[LPG_')).trim() || 'Privacy Chat';
}
