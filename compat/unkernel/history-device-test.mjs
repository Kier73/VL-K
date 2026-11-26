import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { HistoryDevice } from './history-device.mjs';
const dir=await mkdtemp(join(tmpdir(),'vlk-pathway-')),path=join(dir,'state.sqlite');
let d,a,b;
try {
  d=await HistoryDevice.open(path,{pages:64});const start=d.receipt();const oracle=new Uint8Array(d.size);
  const initial=new Uint8Array(1536).fill(17);const w=d.write(3584,[initial.subarray(0,513),initial.subarray(513)]);oracle.set(initial,3584);initial.fill(42);
  const out=new Uint8Array(1536);await Promise.all([w,d.read(3584,[out.subarray(0,731),out.subarray(731)])]);assert.deepEqual(out,oracle.slice(3584,5120));assert(d.receipt().dirty);
  const fence=d.whenFlushed(d.flushSeq);await d.flush();await fence;const committed=d.receipt();assert.equal(committed.revision,start.revision+1);assert(!committed.dirty);await d.fork('alternative');
  let seed=74;const rnd=()=>seed=(Math.imul(seed,1664525)+1013904223)>>>0;
  for(let i=0;i<250;i++){
    const n=(1+(rnd()>>>16)%8)*512,off=((rnd()>>>8)%(d.size/512-n/512+1))*512;
    const x=Uint8Array.from({length:n},()=>rnd()>>>24);const y=new Uint8Array(n);
    oracle.set(x,off);await Promise.all([d.write(off,[x]),d.read(off,[y])]);assert.deepEqual(x,y);
    if(i%25===0)await d.flush();
  }
  await d.flush();const final=d.receipt();await d.close();d=await HistoryDevice.open(path);assert.deepEqual(d.receipt(),final);
  const all=new Uint8Array(d.size);await d.read(0,[all]);assert.deepEqual(all,oracle);
  assert.throws(()=>d.write(d.size-512,[new Uint8Array(1024)]),/range/);
  await d.write(0,[new Uint8Array(512).fill(99)]);d.abort();await d.close();d=await HistoryDevice.open(path);assert.deepEqual(d.receipt(),final);await d.read(0,[all]);assert.deepEqual(all,oracle);
  a=await HistoryDevice.open(path,{branch:'alternative'});assert.equal(a.receipt().root,committed.root);await a.read(3584,[out]);assert(out.every(x=>x===17));await a.close();a=undefined;
  b=await HistoryDevice.open(path);await d.write(0,[new Uint8Array(512).fill(77)]);await b.write(0,[new Uint8Array(512).fill(88)]);
  const race=await Promise.allSettled([d.flush(),b.flush()]);assert.equal(race.filter(x=>x.status==='fulfilled').length,1);assert.match(race.find(x=>x.status==='rejected').reason.message,/stale branch revision/);
  const winner=race[0].status==='fulfilled'?77:88;await d.close();await b.close();d=await HistoryDevice.open(path);await d.read(0,[out.subarray(0,512)]);assert(out.subarray(0,512).every(x=>x===winner));
  const pending=d.whenFlushed(d.flushSeq);const rejected=assert.rejects(pending,/aborted/);d.abort();await rejected;
  console.log('250 paired writes/reads, 11 batched flushes plus initial commit, exact reopen, dirty abort, branch isolation, CAS race, flush waiter refusal passed');
}finally{for(const x of [d,a,b])if(x)await x.close();await rm(dir,{recursive:true,force:true});}
