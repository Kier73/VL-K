// Independent portable verifier: no database, E-CPU codec or Python dependency.
import { createHash } from 'node:crypto';
const EMPTY='0'.repeat(64), VERSION='vlk.coordinate-ground.v1';
const sha=b=>createHash('sha256').update(b).digest('hex');
const hex=(s,n)=>typeof s==='string'&&s.length===n&&/^[0-9a-f]+$/.test(s);
export function requireReceipt(actual,expected){
  for(const r of [actual,expected])if(!r||r.groundVersion!==VERSION||!hex(r.identity,32)||!hex(r.root,64)||!Number.isSafeInteger(r.pages)||r.pages<2||r.pages>16384||(r.pages&(r.pages-1))||!Number.isSafeInteger(r.revision)||r.revision<1)throw Error('invalid Ground receipt');
  for(const k of ['groundVersion','identity','pages','revision','root'])if(actual[k]!==expected[k])throw Error('Ground receipt mismatch: '+k);
}
export function verifyWitness(w,expected,coordinate){
  // The expected receipt and coordinate must come from the caller's trusted admission.
  requireReceipt(w?.receipt,expected);
  const depth=Math.log2(expected.pages);
  if(!Number.isSafeInteger(coordinate)||coordinate<0||coordinate>=expected.pages||w.coordinate!==coordinate||!Array.isArray(w.siblings)||w.siblings.length!==depth||w.siblings.some(s=>!hex(s,64)))throw Error('invalid coordinate witness');
  if(typeof w.page!=='string'||w.page.length!==5464)throw Error('invalid page encoding');
  const raw=Buffer.from(w.page,'base64');if(raw.length!==4096||raw.toString('base64')!==w.page)throw Error('invalid page encoding');
  let key=raw.every(x=>x===0)?EMPTY:sha(raw);
  for(let level=1;level<=depth;level++){
    const sibling=w.siblings[depth-level];const [left,right]=(coordinate&(1<<(level-1)))?[sibling,key]:[key,sibling];
    key=left===EMPTY&&right===EMPTY?EMPTY:sha(Buffer.concat([Buffer.from('VLK-node-v1\0'),Buffer.from([level]),Buffer.from(left,'hex'),Buffer.from(right,'hex')]));
  }
  if(key!==expected.root)throw Error('coordinate root mismatch');
  return new Uint8Array(raw);
}
