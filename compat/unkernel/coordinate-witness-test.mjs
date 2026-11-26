import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { HistoryDevice } from './history-device.mjs';
import { verifyWitness } from './coordinate-witness.mjs';
const dir=await mkdtemp(join(tmpdir(),'vlk-witness-')),path=join(dir,'state.sqlite');
let d,a,b;
try{
  d=await HistoryDevice.open(path,{pages:16384});const zero=d.receipt(),states=[{receipt:zero,pages:new Map()}];
  let seed=193;const rnd=()=>seed=(Math.imul(seed,1664525)+1013904223)>>>0;
  const oracle=new Map();
  for(let t=0;t<32;t++){
    const i=(t*257)%16384,raw=Uint8Array.from({length:4096},()=>rnd()>>>24);
    await d.write(i*4096,[raw]);oracle.set(i,raw);const seal=await d.seal();assert.equal(seal.identity,zero.identity);states.push({receipt:seal,pages:new Map(oracle)});
  }
  for(let i=0;i<512;i++){
    const s=states[rnd()%states.length],keys=[...s.pages.keys()],coord=i%2&&keys.length?keys[rnd()%keys.length]:rnd()%16384;
    const w=await d.witness(s.receipt.revision,coord);assert.equal(w.siblings.length,14);assert.deepEqual(verifyWitness(w,s.receipt,coord),s.pages.get(coord)??new Uint8Array(4096));
  }
  const latest=states.at(-1).receipt,w=await d.witness(latest.revision,0);
  for(const edit of [x=>x.coordinate=1,x=>x.siblings[0]='f'.repeat(64),x=>x.siblings.pop(),x=>x.page=Buffer.alloc(4096,7).toString('base64'),x=>x.receipt.identity='f'.repeat(32),x=>x.receipt.revision++,x=>x.receipt.root='f'.repeat(64)]){
    const bad=structuredClone(w);edit(bad);assert.throws(()=>verifyWitness(bad,latest,0));
  }
  await d.fork('alternative');await assert.rejects(HistoryDevice.open(path,{branch:'alternative',expected:latest}),/branch seal mismatch/);a=await HistoryDevice.open(path,{branch:'alternative'});assert.equal(a.receipt().root,latest.root);assert.equal(a.receipt().identity,latest.identity);
  await a.write(0,[new Uint8Array(4096).fill(7)]);assert.deepEqual(verifyWitness(await a.witness(latest.revision,0),latest,0),oracle.get(0));const alternative=await a.seal();assert.notEqual(alternative.root,latest.root);
  await a.close();a=undefined;await d.close();assert.deepEqual(verifyWitness(w,latest,0),oracle.get(0));d=await HistoryDevice.open(path,{expected:latest});assert.deepEqual(d.receipt(),latest);
  await assert.rejects(HistoryDevice.open(path,{branch:'alternative',expected:latest}),/receipt mismatch|branch seal mismatch/);
  b=await HistoryDevice.open(join(dir,'other.sqlite'),{pages:16384});assert.equal(b.receipt().root,zero.root);assert.notEqual(b.receipt().identity,zero.identity);await assert.rejects(HistoryDevice.open(join(dir,'other.sqlite'),{expected:zero}),/identity/);
  await d.fork('ordered');a=await HistoryDevice.open(path,{branch:'ordered'});const q=a.seal(),write=a.write(0,[new Uint8Array(4096).fill(9)]);const [boundary]=await Promise.all([q,write]);assert.equal(boundary.root,latest.root);assert.equal(boundary.dirty,false);assert(a.receipt().dirty);await a.close();a=undefined;
  await d.close();d=undefined;
  // Simulate pre-identity schema; migration preserves all roots and observations.
  execFileSync('python3',['-c','import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("DROP TABLE store_identity"); c.commit()',path]);
  d=await HistoryDevice.open(path);const migrated=d.receipt();assert.equal(migrated.root,latest.root);assert.notEqual(migrated.identity,latest.identity);assert.deepEqual(verifyWitness(await d.witness(migrated.revision,0),migrated,0),oracle.get(0));await d.close();d=await HistoryDevice.open(path);assert.deepEqual(d.receipt(),migrated);
  console.log('512 portable historical witnesses (14 siblings), 7 mutations rejected, dirty/committed separation, branch seals, store identity and legacy migration passed');
}finally{for(const x of [d,a,b])if(x)await x.close();await rm(dir,{recursive:true,force:true});}
